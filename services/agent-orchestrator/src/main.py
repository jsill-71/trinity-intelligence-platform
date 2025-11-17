"""
Agent Orchestrator Service - AI agent coordination and task execution
Uses Claude Haiku 4.5 for cost-efficient agent operations
"""

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import anthropic
import os
import asyncpg
import redis
import json
from datetime import datetime

app = FastAPI(title="Trinity Agent Orchestrator")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4.5-20250514")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Initialize Anthropic client
if ANTHROPIC_API_KEY:
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    ANTHROPIC_AVAILABLE = True
else:
    anthropic_client = None
    ANTHROPIC_AVAILABLE = False

# Redis for task queue
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

pool = None

class AgentTask(BaseModel):
    task_type: str
    description: str
    context: Optional[Dict] = None
    priority: str = "medium"
    max_tokens: int = 2000

class AgentResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[str] = None
    tokens_used: Optional[int] = None
    model: str

class SwarmTask(BaseModel):
    task_description: str
    agent_count: int = 3
    coordination_mode: str = "parallel"

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)

    # Create agent_tasks table
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id SERIAL PRIMARY KEY,
                task_type VARCHAR(100) NOT NULL,
                description TEXT NOT NULL,
                context JSONB,
                status VARCHAR(50) DEFAULT 'pending',
                result TEXT,
                tokens_used INTEGER,
                model VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()

async def execute_agent_task(task_id: int, task: AgentTask):
    """Execute agent task in background"""

    if not ANTHROPIC_AVAILABLE:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE agent_tasks
                SET status = 'failed', result = 'Anthropic API not configured'
                WHERE id = $1
            """, task_id)
        return

    try:
        # Update status to running
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE agent_tasks SET status = 'running' WHERE id = $1
            """, task_id)

        # Build prompt
        system_prompt = f"You are a {task.task_type} agent. Be concise and focused."
        user_prompt = task.description

        if task.context:
            user_prompt += f"\n\nContext:\n{json.dumps(task.context, indent=2)}"

        # Call Claude Haiku
        message = anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=task.max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        result = message.content[0].text
        tokens_used = message.usage.input_tokens + message.usage.output_tokens

        # Update with result
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE agent_tasks
                SET status = 'completed',
                    result = $1,
                    tokens_used = $2,
                    model = $3,
                    completed_at = NOW()
                WHERE id = $4
            """, result, tokens_used, ANTHROPIC_MODEL, task_id)

    except Exception as e:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE agent_tasks
                SET status = 'failed',
                    result = $1,
                    completed_at = NOW()
                WHERE id = $2
            """, str(e), task_id)

@app.post("/agent/execute", response_model=AgentResponse)
async def execute_agent(task: AgentTask, background_tasks: BackgroundTasks):
    """Execute single agent task"""

    # Store task
    async with pool.acquire() as conn:
        task_id = await conn.fetchval("""
            INSERT INTO agent_tasks (task_type, description, context, status, model)
            VALUES ($1, $2, $3, 'queued', $4)
            RETURNING id
        """, task.task_type, task.description,
            json.dumps(task.context) if task.context else None,
            ANTHROPIC_MODEL)

    # Queue task
    if REDIS_AVAILABLE:
        redis_client.rpush(f"agent_queue:{task.priority}", str(task_id))

    # Execute in background
    background_tasks.add_task(execute_agent_task, task_id, task)

    return AgentResponse(
        task_id=f"task-{task_id}",
        status="queued",
        model=ANTHROPIC_MODEL
    )

@app.get("/agent/task/{task_id}")
async def get_task_status(task_id: str):
    """Get agent task status"""

    task_num = int(task_id.replace("task-", ""))

    async with pool.acquire() as conn:
        task = await conn.fetchrow("""
            SELECT id, task_type, description, status, result, tokens_used, model, created_at, completed_at
            FROM agent_tasks
            WHERE id = $1
        """, task_num)

        if not task:
            return {"error": "Task not found"}, 404

        return {
            "task_id": f"task-{task['id']}",
            "task_type": task["task_type"],
            "description": task["description"],
            "status": task["status"],
            "result": task["result"],
            "tokens_used": task["tokens_used"],
            "model": task["model"],
            "created_at": task["created_at"].isoformat(),
            "completed_at": task["completed_at"].isoformat() if task["completed_at"] else None
        }

@app.post("/swarm/deploy")
async def deploy_swarm(swarm: SwarmTask):
    """Deploy agent swarm for complex tasks"""

    # Create multiple agent tasks
    task_ids = []

    # Break task into subtasks
    subtasks = [
        f"Subtask {i+1}: {swarm.task_description}",
        for i in range(swarm.agent_count)
    ]

    async with pool.acquire() as conn:
        for subtask in subtasks:
            task_id = await conn.fetchval("""
                INSERT INTO agent_tasks (task_type, description, status, model)
                VALUES ('swarm_agent', $1, 'queued', $2)
                RETURNING id
            """, subtask, ANTHROPIC_MODEL)
            task_ids.append(task_id)

    return {
        "swarm_id": f"swarm-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "agent_count": swarm.agent_count,
        "task_ids": [f"task-{tid}" for tid in task_ids],
        "coordination_mode": swarm.coordination_mode,
        "model": ANTHROPIC_MODEL,
        "status": "queued"
    }

@app.get("/stats")
async def get_stats():
    """Get agent orchestration statistics"""

    async with pool.acquire() as conn:
        # Total tasks
        total = await conn.fetchval("SELECT COUNT(*) FROM agent_tasks")

        # By status
        by_status = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM agent_tasks
            GROUP BY status
        """)

        # Token usage
        total_tokens = await conn.fetchval("""
            SELECT COALESCE(SUM(tokens_used), 0) FROM agent_tasks
            WHERE tokens_used IS NOT NULL
        """)

        # Recent tasks
        recent = await conn.fetch("""
            SELECT id, task_type, status, tokens_used, created_at
            FROM agent_tasks
            ORDER BY created_at DESC
            LIMIT 20
        """)

    return {
        "total_tasks": total,
        "by_status": [{"status": r["status"], "count": r["count"]} for r in by_status],
        "total_tokens_used": total_tokens,
        "current_model": ANTHROPIC_MODEL,
        "recent_tasks": [
            {
                "task_id": f"task-{r['id']}",
                "type": r["task_type"],
                "status": r["status"],
                "tokens": r["tokens_used"],
                "created_at": r["created_at"].isoformat()
            }
            for r in recent
        ]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "anthropic_configured": ANTHROPIC_AVAILABLE,
        "model": ANTHROPIC_MODEL,
        "redis": "available" if REDIS_AVAILABLE else "unavailable"
    }
