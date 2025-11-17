"""
Metrics Collector - Prometheus metrics exporter
Collects metrics from all Trinity services and exposes for scraping
"""

from prometheus_client import start_http_server, Gauge, Counter, Histogram
import asyncpg
from neo4j import GraphDatabase
import redis
import httpx
import asyncio
import os
import time

# Prometheus metrics
SERVICES_UP = Gauge('trinity_services_up', 'Number of healthy services')
KG_NODES = Gauge('trinity_kg_nodes_total', 'Total nodes in knowledge graph')
KG_RELATIONSHIPS = Gauge('trinity_kg_relationships_total', 'Total relationships in knowledge graph')
VECTOR_DOCUMENTS = Gauge('trinity_vector_documents', 'Documents in vector index')
AUDIT_EVENTS = Counter('trinity_audit_events_total', 'Total audit events')
AGENT_TASKS = Counter('trinity_agent_tasks_total', 'Total agent tasks', ['status'])
API_REQUESTS = Counter('trinity_api_requests_total', 'Total API requests')

# Configuration
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity123")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

METRICS_PORT = int(os.getenv("METRICS_PORT", "9090"))
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "15"))

# Service health check URLs
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
    "data-aggregator": "http://data-aggregator:8000/health"
}

async def collect_service_health():
    """Check service health"""
    healthy = 0

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in SERVICES.items():
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    healthy += 1
            except:
                pass

    SERVICES_UP.set(healthy)

# Global Neo4j driver (create once, reuse to prevent connection leaks)
_neo4j_driver = None

def get_neo4j_driver():
    """Get or create Neo4j driver (singleton pattern)"""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _neo4j_driver

async def collect_kg_metrics():
    """Collect knowledge graph metrics"""
    driver = get_neo4j_driver()

    try:
        with driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            record = result.single()
            KG_NODES.set(record["count"] if record else 0)

            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            record = result.single()
            KG_RELATIONSHIPS.set(record["count"] if record else 0)
    except:
        pass

async def collect_vector_metrics():
    """Collect vector search metrics"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://vector-search:8000/stats")
            if response.status_code == 200:
                data = response.json()
                VECTOR_DOCUMENTS.set(data.get("total_documents", 0))
    except:
        pass

async def collect_postgres_metrics():
    """Collect PostgreSQL metrics"""
    try:
        conn = await asyncpg.connect(POSTGRES_URL)

        # Audit events
        count = await conn.fetchval("SELECT COUNT(*) FROM audit_log")
        AUDIT_EVENTS._value._value = count if count else 0

        # Agent tasks by status
        rows = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM agent_tasks
            GROUP BY status
        """)

        for row in rows:
            AGENT_TASKS.labels(status=row["status"])._value._value = row["count"]

        await conn.close()
    except:
        pass

async def collect_metrics():
    """Main metrics collection loop"""

    print(f"[METRICS COLLECTOR] Starting on port {METRICS_PORT}")
    print(f"[METRICS COLLECTOR] Collection interval: {COLLECT_INTERVAL}s")

    while True:
        try:
            await collect_service_health()
            await collect_kg_metrics()
            await collect_vector_metrics()
            await collect_postgres_metrics()

            print(f"[METRICS COLLECTOR] Metrics updated - {time.strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            print(f"[METRICS COLLECTOR] Error: {e}")

        await asyncio.sleep(COLLECT_INTERVAL)

if __name__ == "__main__":
    # Start Prometheus HTTP server
    start_http_server(METRICS_PORT)

    # Run metrics collection
    asyncio.run(collect_metrics())
