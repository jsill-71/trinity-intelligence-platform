"""
Health Monitor - Continuous health checking and auto-recovery
Monitors all services and triggers alerts on failures
"""

import httpx
import asyncio
import asyncpg
import redis
import os
from datetime import datetime
import json
from typing import Dict

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
ALERT_MANAGER_URL = os.getenv("ALERT_MANAGER_URL", "http://alert-manager:8000")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))

# Services to monitor
SERVICES = {
    "api-gateway": "http://api-gateway:8000/health",
    "user-management": "http://user-management:8000/health",
    "rca-api": "http://rca-api:8000/health",
    "investigation-api": "http://investigation-api:8000/health",
    "vector-search": "http://vector-search:8000/health",
    "audit-service": "http://audit-service:8000/health",
    "notification-service": "http://notification-service:8000/health",
    "ml-training": "http://ml-training:8000/health",
    "agent-orchestrator": "http://agent-orchestrator:8000/health",
    "workflow-engine": "http://workflow-engine:8000/health",
    "data-aggregator": "http://data-aggregator:8000/health",
    "alert-manager": "http://alert-manager:8000/health",
    "query-optimizer": "http://query-optimizer:8000/health",
    "cache-service": "http://cache-service:8000/health"
}

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

pg_pool = None

async def check_service_health(name: str, url: str) -> Dict:
    """Check single service health"""

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)

            if response.status_code == 200:
                return {"service": name, "status": "healthy", "response_time": response.elapsed.total_seconds()}
            else:
                return {"service": name, "status": "unhealthy", "code": response.status_code}
    except Exception as e:
        return {"service": name, "status": "down", "error": str(e)}

async def trigger_alert(service: str, status: str, details: str):
    """Trigger alert for service issue"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{ALERT_MANAGER_URL}/alerts/trigger",
                json={
                    "alert_type": "service_health",
                    "title": f"Service {service} is {status}",
                    "description": details,
                    "severity": "high" if status == "down" else "medium",
                    "metadata": {
                        "service": service,
                        "status": status,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            )
    except:
        pass

async def monitor_loop():
    """Main monitoring loop"""

    print("[HEALTH MONITOR] Starting health monitoring")
    print(f"[HEALTH MONITOR] Check interval: {CHECK_INTERVAL}s")
    print(f"[HEALTH MONITOR] Monitoring {len(SERVICES)} services")

    service_state = {}  # Track previous state

    while True:
        try:
            # Check all services
            checks = []
            async with httpx.AsyncClient(timeout=5.0) as client:
                for name, url in SERVICES.items():
                    result = await check_service_health(name, url)
                    checks.append(result)

                    # Detect state changes
                    prev_status = service_state.get(name, "unknown")
                    current_status = result["status"]

                    if prev_status == "healthy" and current_status != "healthy":
                        # Service degraded
                        print(f"[ALERT] {name}: healthy -> {current_status}")
                        await trigger_alert(name, current_status, json.dumps(result))

                    elif prev_status in ["unhealthy", "down"] and current_status == "healthy":
                        # Service recovered
                        print(f"[RECOVERY] {name}: {prev_status} -> healthy")

                    service_state[name] = current_status

            # Store health check results
            if pg_pool:
                async with pg_pool.acquire() as conn:
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS health_checks (
                            id SERIAL PRIMARY KEY,
                            service_name VARCHAR(100),
                            status VARCHAR(50),
                            response_time FLOAT,
                            details JSONB,
                            checked_at TIMESTAMP DEFAULT NOW()
                        )
                    """)

                    for check in checks:
                        await conn.execute("""
                            INSERT INTO health_checks (service_name, status, response_time, details)
                            VALUES ($1, $2, $3, $4)
                        """,
                            check["service"],
                            check["status"],
                            check.get("response_time", 0),
                            json.dumps(check)
                        )

            # Update Redis
            if REDIS_AVAILABLE:
                redis_client.set("health_check:last_run", datetime.now().isoformat())
                redis_client.set("health_check:results", json.dumps(checks))

            # Summary
            healthy = sum(1 for c in checks if c["status"] == "healthy")
            print(f"[HEALTH MONITOR] {datetime.now().strftime('%H:%M:%S')} - {healthy}/{len(checks)} services healthy")

        except Exception as e:
            print(f"[HEALTH MONITOR] Error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

async def setup():
    """Initialize health monitor"""

    global pg_pool

    # Connect to PostgreSQL
    pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)

    # Create health_checks table at startup (prevents race condition)
    async with pg_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id SERIAL PRIMARY KEY,
                service_name VARCHAR(100),
                status VARCHAR(50),
                response_time FLOAT,
                details JSONB,
                checked_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("[HEALTH MONITOR] health_checks table ready")

    # Start monitoring
    await monitor_loop()

if __name__ == "__main__":
    from typing import Dict
    asyncio.run(setup())
