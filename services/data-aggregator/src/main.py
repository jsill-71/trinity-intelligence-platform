"""
Data Aggregator Service - Cross-system data aggregation and analytics
Combines data from PostgreSQL, Neo4j, and external sources
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncpg
from neo4j import AsyncGraphDatabase
import httpx
import os
import pandas as pd
from datetime import datetime, timedelta
import json

app = FastAPI(title="Trinity Data Aggregator")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity123")

pg_pool = None
neo4j_driver = None

class DataQuery(BaseModel):
    sources: List[str]  # e.g., ["postgres", "neo4j", "audit"]
    filters: Optional[Dict] = None
    aggregation: Optional[str] = None
    time_range: Optional[Dict] = None

class Dashboard(BaseModel):
    name: str
    widgets: List[Dict]
    refresh_interval: int = 300

@app.on_event("startup")
async def startup():
    global pg_pool, neo4j_driver
    pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)
    neo4j_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@app.on_event("shutdown")
async def shutdown():
    if pg_pool:
        await pg_pool.close()
    if neo4j_driver:
        await neo4j_driver.close()

@app.get("/aggregate/system-overview")
async def get_system_overview():
    """Get system-wide overview from all sources"""

    # PostgreSQL stats
    async with pg_pool.acquire() as conn:
        total_events = await conn.fetchval("SELECT COUNT(*) FROM events")
        total_audits = await conn.fetchval("SELECT COUNT(*) FROM audit_log")
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")

        recent_events = await conn.fetch("""
            SELECT event_type, COUNT(*) as count
            FROM events
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 10
        """)

    # Neo4j stats
    async with neo4j_driver.session() as session:
        kg_stats = await session.run("""
            MATCH (n)
            RETURN labels(n)[0] as label, COUNT(*) as count
        """)

        node_counts = {}
        async for record in kg_stats:
            node_counts[record["label"]] = record["count"]

        # Relationship stats
        rel_stats = await session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, COUNT(*) as count
            ORDER BY count DESC
            LIMIT 10
        """)

        relationship_counts = []
        async for record in rel_stats:
            relationship_counts.append({
                "type": record["rel_type"],
                "count": record["count"]
            })

    return {
        "timestamp": datetime.now().isoformat(),
        "postgresql": {
            "total_events": total_events,
            "total_audit_logs": total_audits,
            "total_users": total_users,
            "recent_events_24h": [
                {"type": r["event_type"], "count": r["count"]}
                for r in recent_events
            ]
        },
        "knowledge_graph": {
            "nodes_by_type": node_counts,
            "total_nodes": sum(node_counts.values()),
            "top_relationships": relationship_counts
        }
    }

@app.get("/aggregate/performance-metrics")
async def get_performance_metrics():
    """Aggregate performance metrics from all services"""

    metrics = {}

    # Get metrics from each service
    services = {
        "audit": "http://audit-service:8000/audit/stats",
        "vector_search": "http://vector-search:8000/stats",
        "agent_orchestrator": "http://agent-orchestrator:8000/stats",
        "ml_training": "http://ml-training:8000/models"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, url in services.items():
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    metrics[name] = response.json()
            except:
                metrics[name] = {"error": "unavailable"}

    return metrics

@app.get("/aggregate/issue-analysis")
async def get_issue_analysis(time_window_hours: int = 24):
    """Analyze issue patterns across time"""

    # Get issues from knowledge graph
    async with neo4j_driver.session() as session:
        result = await session.run("""
            MATCH (i:Issue)
            RETURN i.id as id,
                   i.title as title,
                   i.status as status,
                   i.severity as severity,
                   i.category as category
        """)

        issues = []
        async for record in result:
            issues.append({
                "issue_id": record["id"],
                "title": record["title"],
                "status": record["status"] if record["status"] else "unknown",
                "severity": record["severity"] if record["severity"] else "unknown",
                "category": record["category"] if record["category"] else "general"
            })

    # Group by category and status
    df = pd.DataFrame(issues)

    if len(df) == 0:
        return {"total_issues": 0, "by_category": [], "by_status": [], "by_severity": []}

    by_category = df.groupby('category').size().to_dict()
    by_status = df.groupby('status').size().to_dict()
    by_severity = df.groupby('severity').size().to_dict()

    return {
        "total_issues": len(df),
        "by_category": [{"category": k, "count": v} for k, v in by_category.items()],
        "by_status": [{"status": k, "count": v} for k, v in by_status.items()],
        "by_severity": [{"severity": k, "count": v} for k, v in by_severity.items()]
    }

@app.get("/aggregate/service-health")
async def get_service_health():
    """Aggregate service health from knowledge graph"""

    async with neo4j_driver.session() as session:
        result = await session.run("""
            MATCH (s:Service)
            RETURN s.name as name,
                   s.status as status,
                   s.health_score as health_score
            LIMIT 100
        """)

        services = []
        async for record in result:
            services.append({
                "service": record["name"],
                "status": record["status"] if record["status"] else "unknown",
                "health_score": record["health_score"] if record["health_score"] else 0
            })

    # Calculate overall health
    if len(services) > 0:
        avg_health = sum(s.get("health_score", 0) for s in services) / len(services)
        healthy_count = sum(1 for s in services if s.get("status") == "healthy")
    else:
        avg_health = 0
        healthy_count = 0

    return {
        "total_services": len(services),
        "healthy_services": healthy_count,
        "average_health_score": round(avg_health, 2),
        "services": services
    }

@app.post("/dashboards")
async def create_dashboard(dashboard: Dashboard):
    """Create custom dashboard"""

    # Store in PostgreSQL
    async with pg_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboards (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200),
                widgets JSONB,
                refresh_interval INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        dashboard_id = await conn.fetchval("""
            INSERT INTO dashboards (name, widgets, refresh_interval)
            VALUES ($1, $2, $3)
            RETURNING id
        """, dashboard.name, json.dumps(dashboard.widgets), dashboard.refresh_interval)

    return {
        "dashboard_id": dashboard_id,
        "name": dashboard.name,
        "created": True
    }

@app.get("/health")
async def health():
    try:
        async with pg_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        async with neo4j_driver.session() as session:
            await session.run("RETURN 1")

        return {
            "status": "healthy",
            "postgres": "connected",
            "neo4j": "connected"
        }
    except:
        return {"status": "unhealthy"}
