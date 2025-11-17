"""
API Gateway - Unified entry point for all Trinity services
Handles authentication, rate limiting, routing, and service discovery
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import httpx
import os
from jose import JWTError, jwt
import redis
from datetime import datetime, timedelta
import hashlib

app = FastAPI(title="Trinity API Gateway")

# Service URLs
USER_MGMT_URL = os.getenv("USER_MGMT_URL", "http://user-management:8000")
RCA_API_URL = os.getenv("RCA_API_URL", "http://rca-api:8000")
INVESTIGATION_URL = os.getenv("INVESTIGATION_URL", "http://investigation-api:8000")
VECTOR_SEARCH_URL = os.getenv("VECTOR_SEARCH_URL", "http://vector-search:8000")
AUDIT_URL = os.getenv("AUDIT_URL", "http://audit-service:8000")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification-service:8000")
ML_TRAINING_URL = os.getenv("ML_TRAINING_URL", "http://ml-training:8000")

JWT_SECRET = os.getenv("JWT_SECRET", "trinity-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Redis for rate limiting
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

security = HTTPBearer(auto_error=False)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ServiceHealth(BaseModel):
    service: str
    status: str
    url: str

async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verify JWT token"""

    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def rate_limit(request: Request, user_data: Optional[Dict] = Depends(verify_token)):
    """Rate limiting middleware"""

    if not REDIS_AVAILABLE:
        return

    # Get client identifier (user ID or IP)
    client_id = user_data.get("sub") if user_data else request.client.host

    # Rate limit: 100 requests per minute
    key = f"rate_limit:{client_id}:{datetime.now().strftime('%Y%m%d%H%M')}"
    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, 60)

    if count > 100:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

async def audit_log(request: Request, user_data: Optional[Dict], response_status: int):
    """Log request to audit service"""

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{AUDIT_URL}/audit",
                json={
                    "event_type": "api_request",
                    "actor": user_data.get("username") if user_data else "anonymous",
                    "resource": request.url.path,
                    "action": request.method,
                    "result": "success" if response_status < 400 else "failure",
                    "ip_address": request.client.host,
                    "metadata": {
                        "path": request.url.path,
                        "method": request.method,
                        "status_code": response_status
                    }
                }
            )
    except:
        pass  # Audit logging failure should not block requests

# Authentication endpoints (proxy to user-management)
@app.post("/auth/register")
async def register(request: Request):
    """Proxy to user management registration"""

    body = await request.json()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{USER_MGMT_URL}/users/register",
            json=body
        )

        await audit_log(request, None, response.status_code)

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.json())

        return response.json()

@app.post("/auth/login")
async def login(request: Request):
    """Proxy to user management login"""

    body = await request.json()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{USER_MGMT_URL}/users/login",
            json=body
        )

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.json())

        result = response.json()
        await audit_log(request, {"username": body.get("username")}, response.status_code)

        return result

# RCA endpoints (proxy with auth)
@app.post("/rca/analyze")
async def rca_analyze(
    request: Request,
    user_data: Optional[Dict] = Depends(verify_token),
    _: None = Depends(rate_limit)
):
    """Proxy to RCA API"""

    body = await request.json()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{RCA_API_URL}/api/rca",
            json=body
        )

        await audit_log(request, user_data, response.status_code)

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()

# Investigation endpoints (proxy with auth)
@app.post("/investigate")
async def investigate(
    request: Request,
    user_data: Optional[Dict] = Depends(verify_token),
    _: None = Depends(rate_limit)
):
    """Proxy to Investigation API"""

    body = await request.json()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{INVESTIGATION_URL}/api/investigate",
            json=body
        )

        await audit_log(request, user_data, response.status_code)

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()

# Vector search endpoints (admin only)
@app.post("/vector/search")
async def vector_search(
    request: Request,
    user_data: Dict = Depends(verify_token),
    _: None = Depends(rate_limit)
):
    """Proxy to Vector Search API (authenticated)"""

    body = await request.json()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{VECTOR_SEARCH_URL}/search",
            json=body
        )

        await audit_log(request, user_data, response.status_code)

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()

# ML Training endpoints (admin only)
@app.post("/ml/train")
async def ml_train(
    request: Request,
    user_data: Dict = Depends(verify_token),
    _: None = Depends(rate_limit)
):
    """Proxy to ML Training API (authenticated)"""

    body = await request.json()

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{ML_TRAINING_URL}/train",
            json=body
        )

        await audit_log(request, user_data, response.status_code)

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()

@app.get("/ml/jobs/{job_id}")
async def ml_job_status(
    job_id: str,
    request: Request,
    user_data: Dict = Depends(verify_token)
):
    """Get ML training job status"""

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{ML_TRAINING_URL}/jobs/{job_id}"
        )

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()

# System health aggregation
@app.get("/health")
async def health_check():
    """Aggregate health from all services"""

    services = {
        "user-management": USER_MGMT_URL,
        "rca-api": RCA_API_URL,
        "investigation-api": INVESTIGATION_URL,
        "vector-search": VECTOR_SEARCH_URL,
        "audit-service": AUDIT_URL,
        "notification-service": NOTIFICATION_URL,
        "ml-training": ML_TRAINING_URL
    }

    health_status = {}

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in services.items():
            try:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    health_status[name] = {"status": "healthy", "details": response.json()}
                else:
                    health_status[name] = {"status": "unhealthy", "code": response.status_code}
            except:
                health_status[name] = {"status": "unreachable"}

    all_healthy = all(s.get("status") == "healthy" for s in health_status.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": health_status,
        "redis": "available" if REDIS_AVAILABLE else "unavailable"
    }

@app.get("/metrics")
async def get_metrics():
    """Get system metrics"""

    if not REDIS_AVAILABLE:
        return {"error": "Redis unavailable"}

    # Get rate limit stats
    now = datetime.now()
    rate_limits = {}

    for i in range(5):
        minute = (now - timedelta(minutes=i)).strftime('%Y%m%d%H%M')
        pattern = f"rate_limit:*:{minute}"

        keys = redis_client.keys(pattern)
        total = sum(int(redis_client.get(k) or 0) for k in keys)
        rate_limits[f"minute_{i}"] = total

    return {
        "requests_per_minute": rate_limits,
        "total_recent": sum(rate_limits.values())
    }
