"""
Scheduler Service - Cron-based job scheduling
Executes scheduled workflows and maintenance tasks
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncpg
import httpx
import asyncio
import os
from datetime import datetime

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
WORKFLOW_ENGINE_URL = os.getenv("WORKFLOW_ENGINE_URL", "http://workflow-engine:8000")
AGENT_ORCHESTRATOR_URL = os.getenv("AGENT_ORCHESTRATOR_URL", "http://agent-orchestrator:8000")

scheduler = AsyncIOScheduler()
pg_pool = None

async def execute_scheduled_workflow(workflow_id: int):
    """Execute workflow on schedule"""

    print(f"[SCHEDULER] Executing workflow {workflow_id}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{WORKFLOW_ENGINE_URL}/workflows/{workflow_id}/execute",
                json={"workflow_id": workflow_id, "trigger": "scheduled"}
            )

            if response.status_code == 200:
                print(f"[SCHEDULER] Workflow {workflow_id} started successfully")
            else:
                print(f"[SCHEDULER] Workflow {workflow_id} failed: {response.status_code}")
    except Exception as e:
        print(f"[SCHEDULER] Error executing workflow {workflow_id}: {e}")

async def daily_kg_maintenance():
    """Daily knowledge graph maintenance"""

    print("[SCHEDULER] Running daily KG maintenance")

    # Trigger KG optimization workflow
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            await client.post(
                f"{AGENT_ORCHESTRATOR_URL}/agent/execute",
                json={
                    "task_type": "kg_maintenance",
                    "description": "Optimize knowledge graph: remove orphaned nodes, reindex relationships",
                    "priority": "low",
                    "max_tokens": 1000
                }
            )
    except Exception as e:
        print(f"[SCHEDULER] KG maintenance failed: {e}")

async def hourly_metrics_aggregation():
    """Hourly metrics aggregation"""

    print("[SCHEDULER] Aggregating hourly metrics")

    # Store metrics snapshot
    if pg_pool:
        try:
            async with pg_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS metrics_snapshots (
                        id SERIAL PRIMARY KEY,
                        snapshot_type VARCHAR(50),
                        metrics JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

                # Get current metrics from Prometheus
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get("http://metrics-collector:9090/metrics")

                    if response.status_code == 200:
                        await conn.execute("""
                            INSERT INTO metrics_snapshots (snapshot_type, metrics)
                            VALUES ('hourly', $1)
                        """, json.dumps({"raw_metrics": response.text[:1000]}))  # Truncate for storage
        except Exception as e:
            print(f"[SCHEDULER] Metrics aggregation failed: {e}")

async def load_scheduled_workflows():
    """Load workflows with schedules from database"""

    if not pg_pool:
        return

    async with pg_pool.acquire() as conn:
        workflows = await conn.fetch("""
            SELECT id, name, schedule
            FROM workflows
            WHERE schedule IS NOT NULL AND enabled = true
        """)

        for workflow in workflows:
            workflow_id = workflow["id"]
            schedule = workflow["schedule"]
            name = workflow["name"]

            try:
                scheduler.add_job(
                    execute_scheduled_workflow,
                    CronTrigger.from_crontab(schedule),
                    args=[workflow_id],
                    id=f"workflow_{workflow_id}",
                    name=name,
                    replace_existing=True
                )
                print(f"[SCHEDULER] Added: {name} (cron: {schedule})")
            except Exception as e:
                print(f"[SCHEDULER] Failed to schedule {name}: {e}")

async def setup():
    """Initialize scheduler"""

    global pg_pool

    print("[SCHEDULER] Starting Trinity Scheduler Service")

    # Connect to PostgreSQL
    pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)

    # Add built-in jobs
    scheduler.add_job(
        daily_kg_maintenance,
        CronTrigger(hour=2, minute=0),  # 2 AM daily
        id="daily_kg_maintenance",
        name="Daily KG Maintenance"
    )

    scheduler.add_job(
        hourly_metrics_aggregation,
        CronTrigger(minute=0),  # Every hour
        id="hourly_metrics",
        name="Hourly Metrics Aggregation"
    )

    # Load workflows from database
    await load_scheduled_workflows()

    # Start scheduler
    scheduler.start()
    print(f"[SCHEDULER] Scheduler started with {len(scheduler.get_jobs())} jobs")

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)

            # Reload workflows every 5 minutes
            if datetime.now().minute % 5 == 0:
                await load_scheduled_workflows()
    except KeyboardInterrupt:
        print("[SCHEDULER] Shutting down...")
        scheduler.shutdown()
        if pg_pool:
            await pg_pool.close()

if __name__ == "__main__":
    import json
    asyncio.run(setup())
