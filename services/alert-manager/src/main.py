"""
Alert Manager - Intelligent alerting and escalation
Manages alert rules, deduplication, and escalation policies
"""

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncpg
import httpx
import redis
import os
from datetime import datetime, timedelta
import json
import hashlib

app = FastAPI(title="Trinity Alert Manager")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification-service:8000")

pool = None

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

class AlertRule(BaseModel):
    name: str
    condition: str
    severity: str = "medium"
    channels: List[str] = ["email"]
    deduplication_window: int = 300  # 5 minutes
    escalation_delay: int = 900  # 15 minutes
    enabled: bool = True

class Alert(BaseModel):
    alert_type: str
    title: str
    description: str
    severity: str
    metadata: Optional[Dict] = None

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) UNIQUE NOT NULL,
                condition TEXT NOT NULL,
                severity VARCHAR(50),
                channels TEXT[],
                deduplication_window INTEGER,
                escalation_delay INTEGER,
                enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                alert_type VARCHAR(100) NOT NULL,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                severity VARCHAR(50),
                status VARCHAR(50) DEFAULT 'active',
                metadata JSONB,
                fingerprint VARCHAR(64),
                first_seen TIMESTAMP DEFAULT NOW(),
                last_seen TIMESTAMP DEFAULT NOW(),
                occurrence_count INTEGER DEFAULT 1,
                resolved_at TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_fingerprint ON alerts(fingerprint);
            CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
        """)

        # Add unique constraint on fingerprint for active alerts (prevents race condition duplicates)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_fingerprint_active
            ON alerts(fingerprint)
            WHERE status = 'active'
        """)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

def generate_fingerprint(alert: Alert) -> str:
    """Generate deduplication fingerprint - includes severity and description to prevent collisions"""
    desc_preview = alert.description[:100] if alert.description else ""
    data = f"{alert.alert_type}:{alert.severity}:{alert.title}:{desc_preview}"
    return hashlib.sha256(data.encode()).hexdigest()

async def send_alert_notification(alert_id: int, alert: Alert):
    """Send alert via configured channels"""

    # Get alert rule
    async with pool.acquire() as conn:
        rule = await conn.fetchrow("""
            SELECT channels, severity FROM alert_rules
            WHERE condition LIKE $1 AND enabled = true
            LIMIT 1
        """, f"%{alert.alert_type}%")

    channels = rule["channels"] if rule else ["webhook"]

    # Send notifications
    for channel in channels:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{NOTIFICATION_URL}/notify",
                    json={
                        "channel": channel,
                        "priority": alert.severity,
                        "notification_data": {
                            "url": "http://api-gateway:8000/webhooks/alert",
                            "payload": {
                                "alert_id": alert_id,
                                "title": alert.title,
                                "description": alert.description,
                                "severity": alert.severity,
                                "timestamp": datetime.now().isoformat()
                            },
                            "retry": 3
                        }
                    }
                )
        except Exception as e:
            print(f"Failed to send {channel} notification: {e}")

@app.post("/alerts/rules", response_model=Dict)
async def create_alert_rule(rule: AlertRule):
    """Create alert rule"""

    async with pool.acquire() as conn:
        rule_id = await conn.fetchval("""
            INSERT INTO alert_rules (name, condition, severity, channels, deduplication_window, escalation_delay, enabled)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (name) DO UPDATE
            SET condition = $2, severity = $3, channels = $4, deduplication_window = $5, escalation_delay = $6, enabled = $7
            RETURNING id
        """, rule.name, rule.condition, rule.severity, rule.channels,
            rule.deduplication_window, rule.escalation_delay, rule.enabled)

    return {"rule_id": rule_id, "name": rule.name, "created": True}

@app.post("/alerts/trigger")
async def trigger_alert(alert: Alert, background_tasks: BackgroundTasks):
    """Trigger new alert with deduplication"""

    fingerprint = generate_fingerprint(alert)

    # Check for duplicate (deduplication)
    if REDIS_AVAILABLE:
        recent = redis_client.get(f"alert_dedup:{fingerprint}")
        if recent:
            # Increment occurrence count
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE alerts
                    SET occurrence_count = occurrence_count + 1,
                        last_seen = NOW()
                    WHERE fingerprint = $1 AND status = 'active'
                """, fingerprint)

            return {"deduplicated": True, "fingerprint": fingerprint}

    # Create new alert
    async with pool.acquire() as conn:
        alert_id = await conn.fetchval("""
            INSERT INTO alerts (alert_type, title, description, severity, metadata, fingerprint)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, alert.alert_type, alert.title, alert.description, alert.severity,
            json.dumps(alert.metadata) if alert.metadata else None, fingerprint)

    # Set deduplication window
    if REDIS_AVAILABLE:
        redis_client.setex(f"alert_dedup:{fingerprint}", 300, str(alert_id))

    # Send notifications in background
    background_tasks.add_task(send_alert_notification, alert_id, alert)

    return {
        "alert_id": alert_id,
        "fingerprint": fingerprint,
        "triggered": True
    }

@app.get("/alerts/active")
async def get_active_alerts(severity: Optional[str] = None, limit: int = 50):
    """Get active alerts"""

    conditions = ["status = 'active'"]
    params = []

    if severity:
        params.append(severity)
        conditions.append(f"severity = ${len(params)}")

    params.append(limit)

    async with pool.acquire() as conn:
        alerts = await conn.fetch(f"""
            SELECT id, alert_type, title, severity, occurrence_count, first_seen, last_seen
            FROM alerts
            WHERE {' AND '.join(conditions)}
            ORDER BY first_seen DESC
            LIMIT ${len(params)}
        """, *params)

    return {
        "alerts": [
            {
                "alert_id": a["id"],
                "type": a["alert_type"],
                "title": a["title"],
                "severity": a["severity"],
                "occurrences": a["occurrence_count"],
                "first_seen": a["first_seen"].isoformat(),
                "last_seen": a["last_seen"].isoformat()
            }
            for a in alerts
        ]
    }

@app.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    """Resolve alert"""

    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE alerts
            SET status = 'resolved', resolved_at = NOW()
            WHERE id = $1
        """, alert_id)

    return {"alert_id": alert_id, "resolved": True}

@app.get("/alerts/stats")
async def get_alert_stats():
    """Get alert statistics"""

    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM alerts")
        active = await conn.fetchval("SELECT COUNT(*) FROM alerts WHERE status = 'active'")

        by_severity = await conn.fetch("""
            SELECT severity, COUNT(*) as count
            FROM alerts
            WHERE status = 'active'
            GROUP BY severity
        """)

        recent = await conn.fetch("""
            SELECT alert_type, severity, title, occurrence_count, first_seen
            FROM alerts
            WHERE status = 'active'
            ORDER BY first_seen DESC
            LIMIT 10
        """)

    return {
        "total_alerts": total,
        "active_alerts": active,
        "by_severity": [{"severity": r["severity"], "count": r["count"]} for r in by_severity],
        "recent_active": [
            {
                "type": r["alert_type"],
                "severity": r["severity"],
                "title": r["title"],
                "occurrences": r["occurrence_count"],
                "age_minutes": (datetime.now() - r["first_seen"]).total_seconds() / 60
            }
            for r in recent
        ]
    }

@app.get("/health")
async def health():
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "available" if REDIS_AVAILABLE else "unavailable"
        }
    except:
        return {"status": "unhealthy"}
