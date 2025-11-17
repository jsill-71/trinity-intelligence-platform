"""
Workflow Engine - Automated workflow orchestration and scheduling
Manages complex multi-step workflows with dependencies and retries
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncpg
import httpx
import os
from datetime import datetime, timedelta
from croniter import croniter
import json
import asyncio

app = FastAPI(title="Trinity Workflow Engine")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")

pool = None

class WorkflowStep(BaseModel):
    step_id: str
    service_url: str
    method: str = "POST"
    payload: Dict
    retry_count: int = 3
    timeout: int = 30
    depends_on: Optional[List[str]] = None

class Workflow(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[WorkflowStep]
    schedule: Optional[str] = None  # Cron expression
    enabled: bool = True

class WorkflowExecution(BaseModel):
    workflow_id: int
    trigger: str = "manual"

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)

    # Create tables
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id SERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                steps JSONB NOT NULL,
                schedule VARCHAR(100),
                enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_executions (
                id SERIAL PRIMARY KEY,
                workflow_id INTEGER REFERENCES workflows(id),
                trigger VARCHAR(50),
                status VARCHAR(50) DEFAULT 'running',
                current_step VARCHAR(100),
                steps_completed INTEGER DEFAULT 0,
                total_steps INTEGER,
                result JSONB,
                error TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_step_results (
                id SERIAL PRIMARY KEY,
                execution_id INTEGER REFERENCES workflow_executions(id),
                step_id VARCHAR(100),
                status VARCHAR(50),
                result JSONB,
                error TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

async def execute_workflow_step(step: WorkflowStep, execution_id: int) -> bool:
    """Execute single workflow step"""

    # Record step start
    async with pool.acquire() as conn:
        step_result_id = await conn.fetchval("""
            INSERT INTO workflow_step_results (execution_id, step_id, status)
            VALUES ($1, $2, 'running')
            RETURNING id
        """, execution_id, step.step_id)

    # Execute with retries
    for attempt in range(step.retry_count):
        try:
            async with httpx.AsyncClient(timeout=step.timeout) as client:
                if step.method == "POST":
                    response = await client.post(step.service_url, json=step.payload)
                elif step.method == "GET":
                    response = await client.get(step.service_url)
                elif step.method == "PUT":
                    response = await client.put(step.service_url, json=step.payload)
                else:
                    response = await client.request(step.method, step.service_url, json=step.payload)

                if response.status_code < 400:
                    # Success
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE workflow_step_results
                            SET status = 'completed',
                                result = $1,
                                completed_at = NOW()
                            WHERE id = $2
                        """, json.dumps(response.json()), step_result_id)
                    return True

        except Exception as e:
            if attempt == step.retry_count - 1:
                # Final failure
                async with pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE workflow_step_results
                        SET status = 'failed',
                            error = $1,
                            completed_at = NOW()
                        WHERE id = $2
                    """, str(e), step_result_id)
                return False

            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    return False

async def execute_workflow_background(workflow_id: int, execution_id: int, trigger: str):
    """Execute workflow in background"""

    # Get workflow definition
    async with pool.acquire() as conn:
        workflow_data = await conn.fetchrow("""
            SELECT name, steps FROM workflows WHERE id = $1
        """, workflow_id)

        if not workflow_data:
            return

        steps_json = workflow_data["steps"]
        steps = [WorkflowStep(**s) for s in steps_json]

        # Update execution
        await conn.execute("""
            UPDATE workflow_executions
            SET total_steps = $1
            WHERE id = $2
        """, len(steps), execution_id)

    # Execute steps
    step_results = {}
    completed = 0

    for step in steps:
        # Check dependencies
        if step.depends_on:
            for dep in step.depends_on:
                if not step_results.get(dep, False):
                    # Dependency failed, skip this step
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE workflow_executions
                            SET status = 'failed',
                                error = $1,
                                completed_at = NOW()
                            WHERE id = $2
                        """, f"Dependency {dep} failed", execution_id)
                    return

        # Update current step
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE workflow_executions
                SET current_step = $1
                WHERE id = $2
            """, step.step_id, execution_id)

        # Execute step
        success = await execute_workflow_step(step, execution_id)
        step_results[step.step_id] = success

        if not success:
            # Step failed, abort workflow
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE workflow_executions
                    SET status = 'failed',
                        steps_completed = $1,
                        error = $2,
                        completed_at = NOW()
                    WHERE id = $3
                """, completed, f"Step {step.step_id} failed", execution_id)
            return

        completed += 1

        # Update progress
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE workflow_executions
                SET steps_completed = $1
                WHERE id = $2
            """, completed, execution_id)

    # All steps completed
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE workflow_executions
            SET status = 'completed',
                completed_at = NOW()
            WHERE id = $1
        """, execution_id)

@app.post("/workflows", response_model=Dict)
async def create_workflow(workflow: Workflow):
    """Create new workflow"""

    async with pool.acquire() as conn:
        workflow_id = await conn.fetchval("""
            INSERT INTO workflows (name, description, steps, schedule, enabled)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """,
            workflow.name,
            workflow.description,
            json.dumps([s.model_dump() for s in workflow.steps]),
            workflow.schedule,
            workflow.enabled
        )

    return {
        "workflow_id": workflow_id,
        "name": workflow.name,
        "steps": len(workflow.steps),
        "created": True
    }

@app.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: int,
    execution: WorkflowExecution,
    background_tasks: BackgroundTasks
):
    """Execute workflow"""

    # Check workflow exists
    async with pool.acquire() as conn:
        workflow = await conn.fetchrow("""
            SELECT id, enabled FROM workflows WHERE id = $1
        """, workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        if not workflow["enabled"]:
            raise HTTPException(status_code=400, detail="Workflow disabled")

        # Create execution record
        execution_id = await conn.fetchval("""
            INSERT INTO workflow_executions (workflow_id, trigger, status)
            VALUES ($1, $2, 'running')
            RETURNING id
        """, workflow_id, execution.trigger)

    # Execute in background
    background_tasks.add_task(
        execute_workflow_background,
        workflow_id,
        execution_id,
        execution.trigger
    )

    return {
        "execution_id": execution_id,
        "workflow_id": workflow_id,
        "status": "running"
    }

@app.get("/workflows/{workflow_id}/executions/{execution_id}")
async def get_execution_status(workflow_id: int, execution_id: int):
    """Get workflow execution status"""

    async with pool.acquire() as conn:
        execution = await conn.fetchrow("""
            SELECT id, workflow_id, trigger, status, current_step,
                   steps_completed, total_steps, error, started_at, completed_at
            FROM workflow_executions
            WHERE id = $1 AND workflow_id = $2
        """, execution_id, workflow_id)

        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        # Get step results
        step_results = await conn.fetch("""
            SELECT step_id, status, error, started_at, completed_at
            FROM workflow_step_results
            WHERE execution_id = $1
            ORDER BY started_at
        """, execution_id)

        return {
            "execution_id": execution["id"],
            "workflow_id": execution["workflow_id"],
            "trigger": execution["trigger"],
            "status": execution["status"],
            "current_step": execution["current_step"],
            "progress": f"{execution['steps_completed']}/{execution['total_steps']}",
            "error": execution["error"],
            "started_at": execution["started_at"].isoformat(),
            "completed_at": execution["completed_at"].isoformat() if execution["completed_at"] else None,
            "steps": [
                {
                    "step_id": s["step_id"],
                    "status": s["status"],
                    "error": s["error"],
                    "duration": (s["completed_at"] - s["started_at"]).total_seconds() if s["completed_at"] else None
                }
                for s in step_results
            ]
        }

@app.get("/workflows")
async def list_workflows(enabled: Optional[bool] = None):
    """List all workflows"""

    conditions = []
    params = []

    if enabled is not None:
        conditions.append("enabled = $1")
        params.append(enabled)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        workflows = await conn.fetch(f"""
            SELECT id, name, description, schedule, enabled, created_at
            FROM workflows
            {where_clause}
            ORDER BY created_at DESC
        """, *params)

        return {
            "workflows": [
                {
                    "workflow_id": w["id"],
                    "name": w["name"],
                    "description": w["description"],
                    "schedule": w["schedule"],
                    "enabled": w["enabled"],
                    "created_at": w["created_at"].isoformat()
                }
                for w in workflows
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
