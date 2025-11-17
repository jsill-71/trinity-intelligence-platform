"""
Event Collector Service - Receives GitHub webhooks and emits events to NATS

This is OPERATIONAL CODE - it actually runs and processes webhooks.
"""

import hmac
import hashlib
import os
import json
from fastapi import FastAPI, Request, HTTPException, Header
from nats.aio.client import Client as NATS
import asyncpg
import logging
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trinity Event Collector")

# Global connections
nc: NATS = None
db_pool: asyncpg.Pool = None

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev_webhook_secret")
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:password@localhost:5432/trinity_events")


@app.on_event("startup")
async def startup():
    """Initialize connections on startup"""
    global nc, db_pool

    # Connect to NATS
    nc = NATS()
    await nc.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL}")

    # Setup JetStream
    js = nc.jetstream()

    # Create streams if they don't exist
    try:
        await js.add_stream(name="GIT_COMMITS", subjects=["git.commits"])
        await js.add_stream(name="GITHUB_EVENTS", subjects=["github.>"])
        await js.add_stream(name="NTAI_EVENTS", subjects=["ntai.>"])
        logger.info("JetStream streams configured")
    except Exception as e:
        logger.warning(f"Streams may already exist: {e}")

    # Connect to PostgreSQL
    db_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)
    logger.info(f"Connected to PostgreSQL")

    # Create events table if not exists
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                event_data JSONB NOT NULL,
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
        logger.info("Events table ready")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup connections"""
    if nc:
        await nc.close()
    if db_pool:
        await db_pool.close()


@app.post("/webhooks/ntai")
async def ntai_webhook(
    request: Request,
    x_nt_ai_event: str = Header(...),
    x_webhook_secret: str = Header(None)
):
    """
    Receive NT-AI-Engine webhook events

    Validates secret and publishes to NATS
    """

    # Validate secret
    if x_webhook_secret:
        if x_webhook_secret != WEBHOOK_SECRET:
            raise HTTPException(401, "Invalid webhook secret")

    payload = await request.json()

    # Extract event data
    event_data = {
        "event_type": payload.get("event_type", f"ntai.{x_nt_ai_event}"),
        "tenant_id": payload.get("tenant_id"),
        "timestamp": payload.get("timestamp", datetime.now().isoformat()),
        **payload.get("data", {})
    }

    # Publish to NATS
    await nc.publish(f"ntai.{x_nt_ai_event}", json.dumps(event_data).encode('utf-8'))

    # Store in PostgreSQL
    await db_pool.execute(
        """
        INSERT INTO events (event_type, event_data, timestamp)
        VALUES ($1, $2, $3)
        """,
        event_data["event_type"],
        json.dumps(event_data),
        datetime.now()
    )

    logger.info(f"Published NT-AI event: {x_nt_ai_event} (tenant: {payload.get('tenant_id')})")

    return {"status": "received", "event": x_nt_ai_event}

@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str = Header(None)
):
    """
    Receive GitHub webhook, validate signature, emit event to NATS

    This ACTUALLY processes webhooks and publishes events.
    """

    # Get request body
    body = await request.body()

    # Validate signature
    if x_hub_signature_256:
        expected = "sha256=" + hmac.new(
            WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(401, "Invalid signature")

    payload = await request.json()

    # Process based on event type
    if x_github_event == "push":
        await handle_push_event(payload)
    elif x_github_event == "issues":
        await handle_issue_event(payload)
    elif x_github_event == "pull_request":
        await handle_pr_event(payload)
    else:
        logger.info(f"Ignoring event type: {x_github_event}")

    return {"status": "received", "event": x_github_event}


async def handle_push_event(payload: dict):
    """Process push event (commits)"""

    for commit in payload.get("commits", []):
        event_data = {
            "event_type": "git.commit.received",
            "commit_hash": commit["id"],
            "author": commit["author"]["name"],
            "author_email": commit["author"]["email"],
            "message": commit["message"],
            "files_changed": commit.get("added", []) + commit.get("modified", []),
            "repository": payload["repository"]["full_name"],
            "timestamp": datetime.now().isoformat()
        }

        # Publish to NATS
        await nc.publish("git.commits", json.dumps(event_data).encode('utf-8'))

        # Store in PostgreSQL (event store)
        await db_pool.execute(
            """
            INSERT INTO events (event_type, event_data, timestamp)
            VALUES ($1, $2, $3)
            """,
            event_data["event_type"],
            json.dumps(event_data),
            datetime.now()
        )

        logger.info(f"Published commit event: {commit['id'][:7]}")


async def handle_issue_event(payload: dict):
    """Process issue event"""

    if payload["action"] in ["opened", "closed"]:
        event_data = {
            "event_type": "github.issue." + payload["action"],
            "issue_number": payload["issue"]["number"],
            "title": payload["issue"]["title"],
            "body": payload["issue"]["body"],
            "labels": [l["name"] for l in payload["issue"].get("labels", [])],
            "repository": payload["repository"]["full_name"],
            "timestamp": datetime.now().isoformat()
        }

        # Publish to NATS
        await nc.publish(f"github.issues.{payload['action']}", json.dumps(event_data).encode('utf-8'))

        # Store in event store
        await db_pool.execute(
            """
            INSERT INTO events (event_type, event_data, timestamp)
            VALUES ($1, $2, $3)
            """,
            event_data["event_type"],
            json.dumps(event_data),
            datetime.now()
        )

        logger.info(f"Published issue event: #{payload['issue']['number']}")


async def handle_pr_event(payload: dict):
    """Process pull request event"""

    if payload["action"] in ["opened", "closed", "merged"]:
        event_data = {
            "event_type": "github.pr." + payload["action"],
            "pr_number": payload["pull_request"]["number"],
            "title": payload["pull_request"]["title"],
            "files_changed": payload["pull_request"].get("changed_files", 0),
            "repository": payload["repository"]["full_name"],
            "timestamp": datetime.now().isoformat()
        }

        # Publish to NATS
        await nc.publish(f"github.pr.{payload['action']}", json.dumps(event_data).encode('utf-8'))

        # Store in event store
        await db_pool.execute(
            """
            INSERT INTO events (event_type, event_data, timestamp)
            VALUES ($1, $2, $3)
            """,
            event_data["event_type"],
            json.dumps(event_data),
            datetime.now()
        )

        logger.info(f"Published PR event: #{payload['pull_request']['number']}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "nats_connected": nc.is_connected if nc else False,
        "postgres_connected": bool(db_pool)
    }


@app.get("/metrics")
async def metrics():
    """Metrics endpoint for monitoring"""
    # Query event count from PostgreSQL
    if db_pool:
        event_count = await db_pool.fetchval("SELECT COUNT(*) FROM events")
    else:
        event_count = 0

    return {
        "events_processed": event_count,
        "nats_connected": nc.is_connected if nc else False
    }
