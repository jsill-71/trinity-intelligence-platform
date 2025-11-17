"""
Rate Limiter Service - Advanced rate limiting with multiple strategies
Token bucket, sliding window, and adaptive rate limiting
"""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict
import redis
import os
from datetime import datetime
import time
import hashlib
import json

app = FastAPI(title="Trinity Rate Limiter")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

class RateLimitConfig(BaseModel):
    identifier: str  # user_id, IP, API key
    limit: int  # requests per window
    window_seconds: int  # time window
    strategy: str = "sliding_window"  # token_bucket, fixed_window, sliding_window

class RateLimitCheck(BaseModel):
    identifier: str
    cost: int = 1  # Request cost (default 1)

def check_sliding_window(identifier: str, limit: int, window: int) -> bool:
    """Sliding window rate limiting"""

    key = f"rate_limit:sliding:{identifier}"
    now = time.time()
    window_start = now - window

    # Remove old entries
    redis_client.zremrangebyscore(key, 0, window_start)

    # Count requests in window
    count = redis_client.zcard(key)

    if count >= limit:
        return False

    # Add current request
    redis_client.zadd(key, {str(now): now})
    redis_client.expire(key, window)

    return True

def check_token_bucket(identifier: str, limit: int, window: int, cost: int = 1) -> bool:
    """Token bucket rate limiting"""

    key = f"rate_limit:bucket:{identifier}"
    now = time.time()

    # Get current bucket state
    bucket = redis_client.get(key)

    if bucket:
        data = json.loads(bucket)
        tokens = data["tokens"]
        last_refill = data["last_refill"]
    else:
        tokens = limit
        last_refill = now

    # Refill tokens based on time elapsed
    elapsed = now - last_refill
    refill_rate = limit / window
    tokens = min(limit, tokens + (elapsed * refill_rate))

    # Check if enough tokens
    if tokens < cost:
        return False

    # Consume tokens
    tokens -= cost

    # Save state
    redis_client.setex(
        key,
        window,
        json.dumps({"tokens": tokens, "last_refill": now})
    )

    return True

def check_fixed_window(identifier: str, limit: int, window: int) -> bool:
    """Fixed window rate limiting"""

    minute = int(time.time() / window)
    key = f"rate_limit:fixed:{identifier}:{minute}"

    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, window)

    return count <= limit

@app.post("/rate-limit/check")
async def check_rate_limit(check: RateLimitCheck, config: RateLimitConfig):
    """Check if request is within rate limit"""

    if config.strategy == "sliding_window":
        allowed = check_sliding_window(config.identifier, config.limit, config.window_seconds)
    elif config.strategy == "token_bucket":
        allowed = check_token_bucket(config.identifier, config.limit, config.window_seconds, check.cost)
    elif config.strategy == "fixed_window":
        allowed = check_fixed_window(config.identifier, config.limit, config.window_seconds)
    else:
        raise HTTPException(status_code=400, detail="Unknown strategy")

    # Get current usage
    if config.strategy == "sliding_window":
        key = f"rate_limit:sliding:{config.identifier}"
        current_count = redis_client.zcard(key)
    elif config.strategy == "token_bucket":
        key = f"rate_limit:bucket:{config.identifier}"
        bucket = redis_client.get(key)
        current_count = config.limit - json.loads(bucket)["tokens"] if bucket else 0
    else:
        minute = int(time.time() / config.window_seconds)
        key = f"rate_limit:fixed:{config.identifier}:{minute}"
        current_count = int(redis_client.get(key) or 0)

    return {
        "allowed": allowed,
        "limit": config.limit,
        "current": int(current_count),
        "remaining": max(0, config.limit - int(current_count)),
        "reset_at": int(time.time() + config.window_seconds)
    }

@app.post("/rate-limit/configs")
async def set_rate_limit_config(config: RateLimitConfig):
    """Store rate limit configuration"""

    key = f"rate_limit:config:{config.identifier}"

    redis_client.setex(
        key,
        86400,  # Config TTL: 24 hours
        json.dumps(config.model_dump())
    )

    return {"identifier": config.identifier, "configured": True}

@app.get("/rate-limit/stats/{identifier}")
async def get_rate_limit_stats(identifier: str):
    """Get rate limiting statistics for identifier"""

    stats = {}

    # Check all strategies
    for strategy in ["sliding", "bucket", "fixed"]:
        pattern = f"rate_limit:{strategy}:{identifier}*"
        keys = redis_client.keys(pattern)

        if keys:
            stats[strategy] = {
                "active_windows": len(keys),
                "keys": [k.decode() for k in keys[:5]]  # Sample first 5
            }

    return {"identifier": identifier, "stats": stats}

@app.delete("/rate-limit/reset/{identifier}")
async def reset_rate_limit(identifier: str):
    """Reset rate limit for identifier"""

    patterns = [
        f"rate_limit:sliding:{identifier}",
        f"rate_limit:bucket:{identifier}",
        f"rate_limit:fixed:{identifier}*"
    ]

    total_deleted = 0

    for pattern in patterns:
        keys = redis_client.keys(pattern)
        if keys:
            total_deleted += redis_client.delete(*keys)

    return {"identifier": identifier, "deleted_keys": total_deleted}

@app.get("/health")
async def health():
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except:
        return {"status": "unhealthy", "redis": "disconnected"}
