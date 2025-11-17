"""
Real-Time Event Processor - Stream processing and real-time analytics
Processes NATS events for real-time dashboards and alerts
"""

import nats
from nats.js.api import StreamConfig
import asyncpg
import httpx
import asyncio
import os
import json
from datetime import datetime

NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://notification-service:8000")

# Alert thresholds
ERROR_RATE_THRESHOLD = 0.1  # 10% error rate
CRITICAL_ISSUE_SEVERITY = ["critical", "high"]

async def process_event(msg):
    """Process incoming event"""

    try:
        data = json.loads(msg.data.decode())
        event_type = data.get("event_type")

        print(f"[RT-PROCESSOR] Processing: {event_type}")

        # Real-time analytics
        if event_type == "issue.created":
            await handle_new_issue(data)
        elif event_type == "service.health.degraded":
            await handle_service_degradation(data)
        elif event_type == "error.occurred":
            await check_error_rate(data)
        elif event_type in ["rca.completed", "investigation.completed"]:
            await update_realtime_stats(data)

        await msg.ack()

    except Exception as e:
        print(f"[RT-PROCESSOR] Error processing event: {e}")

async def handle_new_issue(data):
    """Handle newly created issue"""

    severity = data.get("severity", "medium")

    if severity in CRITICAL_ISSUE_SEVERITY:
        # Send alert
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{NOTIFICATION_URL}/notify",
                    json={
                        "channel": "webhook",
                        "priority": "high",
                        "notification_data": {
                            "url": "http://api-gateway:8000/webhooks/critical-issue",
                            "payload": {
                                "issue_id": data.get("issue_id"),
                                "title": data.get("title"),
                                "severity": severity,
                                "timestamp": datetime.now().isoformat()
                            },
                            "retry": 3
                        }
                    }
                )
        except:
            pass

async def handle_service_degradation(data):
    """Handle service health degradation"""

    service_name = data.get("service")

    print(f"[ALERT] Service degraded: {service_name}")

    # Log to PostgreSQL for trending
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
        await conn.execute("""
            INSERT INTO service_health_events (service_name, status, timestamp, metadata)
            VALUES ($1, $2, NOW(), $3)
        """, service_name, "degraded", json.dumps(data))
        await conn.close()
    except:
        pass

async def check_error_rate(data):
    """Check if error rate exceeds threshold"""

    # Calculate error rate from recent events
    try:
        conn = await asyncpg.connect(POSTGRES_URL)

        total = await conn.fetchval("""
            SELECT COUNT(*) FROM events
            WHERE timestamp > NOW() - INTERVAL '5 minutes'
        """)

        errors = await conn.fetchval("""
            SELECT COUNT(*) FROM events
            WHERE timestamp > NOW() - INTERVAL '5 minutes'
              AND event_type LIKE '%error%'
        """)

        await conn.close()

        if total > 0:
            error_rate = errors / total
            if error_rate > ERROR_RATE_THRESHOLD:
                print(f"[ALERT] High error rate: {error_rate*100:.1f}%")

                # Trigger auto-investigation
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        await client.post(
                            "http://investigation-api:8000/api/investigate",
                            json={
                                "task_description": f"High error rate detected: {error_rate*100:.1f}%",
                                "component": data.get("component", "unknown")
                            }
                        )
                except:
                    pass

    except:
        pass

async def update_realtime_stats(data):
    """Update real-time statistics"""

    # Store in PostgreSQL for dashboard queries
    try:
        conn = await asyncpg.connect(POSTGRES_URL)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS realtime_stats (
                id SERIAL PRIMARY KEY,
                stat_type VARCHAR(100),
                value JSONB,
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            INSERT INTO realtime_stats (stat_type, value)
            VALUES ($1, $2)
        """, data.get("event_type"), json.dumps(data))

        await conn.close()
    except:
        pass

async def run():
    """Main processor loop"""

    print("[RT-PROCESSOR] Starting real-time event processor")
    print(f"[RT-PROCESSOR] Connecting to NATS: {NATS_URL}")

    # Connect to NATS
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    # Create stream if not exists
    try:
        await js.add_stream(
            name="EVENTS",
            subjects=["events.>"]
        )
        print("[RT-PROCESSOR] EVENTS stream created/verified")
    except Exception as e:
        print(f"[RT-PROCESSOR] Stream exists or error: {e}")

    # Subscribe to all events
    try:
        await js.subscribe(
            "events.>",
            cb=process_event,
            stream="EVENTS",
            durable="realtime-processor"
        )

        print("[RT-PROCESSOR] Subscribed to events.> stream")
        print("[RT-PROCESSOR] Processing events...")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"[RT-PROCESSOR] Error: {e}")
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(run())
