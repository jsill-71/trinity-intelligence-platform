"""
Audit Service - System-wide audit logging and compliance tracking
Immutable audit trail for all critical operations
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import asyncpg
import os
import json

app = FastAPI(title="Trinity Audit Service")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")

pool = None

class AuditEvent(BaseModel):
    event_type: str
    actor: str
    resource: str
    action: str
    result: str
    metadata: Optional[Dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditQuery(BaseModel):
    event_type: Optional[str] = None
    actor: Optional[str] = None
    resource: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)

    # Create audit table if not exists
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                actor VARCHAR(200) NOT NULL,
                resource VARCHAR(500) NOT NULL,
                action VARCHAR(100) NOT NULL,
                result VARCHAR(50) NOT NULL,
                metadata JSONB,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
            CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
            CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at);
        """)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

@app.post("/audit")
async def log_audit_event(event: AuditEvent):
    """Log audit event (immutable)"""

    async with pool.acquire() as conn:
        event_id = await conn.fetchval("""
            INSERT INTO audit_log (
                event_type, actor, resource, action, result,
                metadata, ip_address, user_agent
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """,
            event.event_type,
            event.actor,
            event.resource,
            event.action,
            event.result,
            json.dumps(event.metadata) if event.metadata else None,
            event.ip_address,
            event.user_agent
        )

    return {
        "audit_id": event_id,
        "logged_at": datetime.now().isoformat()
    }

@app.post("/audit/query")
async def query_audit_log(query: AuditQuery):
    """Query audit log"""

    conditions = ["1=1"]
    params = []
    param_count = 0

    if query.event_type:
        param_count += 1
        conditions.append(f"event_type = ${param_count}")
        params.append(query.event_type)

    if query.actor:
        param_count += 1
        conditions.append(f"actor = ${param_count}")
        params.append(query.actor)

    if query.resource:
        param_count += 1
        conditions.append(f"resource LIKE ${param_count}")
        params.append(f"%{query.resource}%")

    if query.start_time:
        param_count += 1
        conditions.append(f"created_at >= ${param_count}")
        params.append(query.start_time)

    if query.end_time:
        param_count += 1
        conditions.append(f"created_at <= ${param_count}")
        params.append(query.end_time)

    param_count += 1
    limit_param = param_count

    sql = f"""
        SELECT id, event_type, actor, resource, action, result,
               metadata, ip_address, created_at
        FROM audit_log
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT ${limit_param}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params, query.limit)

    events = []
    for row in rows:
        events.append({
            "audit_id": row["id"],
            "event_type": row["event_type"],
            "actor": row["actor"],
            "resource": row["resource"],
            "action": row["action"],
            "result": row["result"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
            "ip_address": row["ip_address"],
            "created_at": row["created_at"].isoformat()
        })

    return {"events": events, "count": len(events)}

@app.get("/audit/stats")
async def get_audit_stats():
    """Get audit log statistics"""

    async with pool.acquire() as conn:
        # Total events
        total = await conn.fetchval("SELECT COUNT(*) FROM audit_log")

        # Events by type
        by_type = await conn.fetch("""
            SELECT event_type, COUNT(*) as count
            FROM audit_log
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 10
        """)

        # Recent activity
        recent = await conn.fetch("""
            SELECT event_type, actor, resource, action, result, created_at
            FROM audit_log
            ORDER BY created_at DESC
            LIMIT 20
        """)

        # Success/failure ratio
        results = await conn.fetch("""
            SELECT result, COUNT(*) as count
            FROM audit_log
            GROUP BY result
        """)

    return {
        "total_events": total,
        "by_type": [{"type": r["event_type"], "count": r["count"]} for r in by_type],
        "recent_activity": [
            {
                "event_type": r["event_type"],
                "actor": r["actor"],
                "resource": r["resource"],
                "action": r["action"],
                "result": r["result"],
                "created_at": r["created_at"].isoformat()
            }
            for r in recent
        ],
        "by_result": [{"result": r["result"], "count": r["count"]} for r in results]
    }

@app.get("/audit/compliance/report")
async def get_compliance_report():
    """Generate compliance report"""

    async with pool.acquire() as conn:
        # Failed authentication attempts
        failed_auth = await conn.fetchval("""
            SELECT COUNT(*) FROM audit_log
            WHERE event_type = 'authentication'
              AND result = 'failure'
              AND created_at > NOW() - INTERVAL '24 hours'
        """)

        # Privileged operations
        privileged_ops = await conn.fetch("""
            SELECT actor, action, resource, created_at
            FROM audit_log
            WHERE event_type IN ('admin_action', 'data_deletion', 'permission_change')
            ORDER BY created_at DESC
            LIMIT 50
        """)

        # Data access patterns
        data_access = await conn.fetch("""
            SELECT actor, COUNT(*) as access_count
            FROM audit_log
            WHERE event_type = 'data_access'
              AND created_at > NOW() - INTERVAL '7 days'
            GROUP BY actor
            ORDER BY access_count DESC
            LIMIT 20
        """)

    return {
        "report_generated_at": datetime.now().isoformat(),
        "failed_authentication_24h": failed_auth,
        "privileged_operations": [
            {
                "actor": r["actor"],
                "action": r["action"],
                "resource": r["resource"],
                "timestamp": r["created_at"].isoformat()
            }
            for r in privileged_ops
        ],
        "data_access_patterns": [
            {"actor": r["actor"], "access_count": r["access_count"]}
            for r in data_access
        ]
    }

@app.get("/health")
async def health():
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except:
        return {"status": "unhealthy", "database": "disconnected"}
