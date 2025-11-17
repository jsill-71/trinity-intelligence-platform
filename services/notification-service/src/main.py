"""
Notification Service - Multi-channel notifications (email, webhook, Slack)
Handles alert delivery and notification preferences
"""

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional, Literal
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
import redis
import json
import os
from jinja2 import Template

app = FastAPI(title="Trinity Notification Service")

# Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "trinity@example.com")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

class EmailNotification(BaseModel):
    to: List[EmailStr]
    subject: str
    body: str
    html: Optional[bool] = False
    template: Optional[str] = None
    template_data: Optional[Dict] = None

class WebhookNotification(BaseModel):
    url: str
    payload: Dict
    headers: Optional[Dict] = None
    retry: Optional[int] = 3

class SlackNotification(BaseModel):
    webhook_url: str
    channel: Optional[str] = None
    text: str
    blocks: Optional[List[Dict]] = None

class Notification(BaseModel):
    channel: Literal["email", "webhook", "slack"]
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    notification_data: EmailNotification | WebhookNotification | SlackNotification

class NotificationPreference(BaseModel):
    user_id: str
    channels: List[str]
    min_priority: str = "medium"

# Email templates
RCA_ALERT_TEMPLATE = Template("""
<html>
<body>
<h2>RCA Alert: {{ issue_title }}</h2>
<p><strong>Severity:</strong> {{ severity }}</p>
<p><strong>Description:</strong> {{ description }}</p>
<h3>Similar Issues Found:</h3>
<ul>
{% for issue in similar_issues %}
<li>{{ issue.title }} ({{ issue.similarity }}% match)</li>
{% endfor %}
</ul>
<h3>Recommended Actions:</h3>
<ol>
{% for action in actions %}
<li>{{ action }}</li>
{% endfor %}
</ol>
</body>
</html>
""")

async def send_email_notification(notification: EmailNotification):
    """Send email via SMTP"""

    if not SMTP_USER or not SMTP_PASSWORD:
        return {"status": "skipped", "reason": "SMTP not configured"}

    # Render template if specified
    body = notification.body
    if notification.template and notification.template_data:
        if notification.template == "rca_alert":
            body = RCA_ALERT_TEMPLATE.render(**notification.template_data)

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = notification.subject
    msg['From'] = FROM_EMAIL
    msg['To'] = ', '.join(notification.to)

    if notification.html:
        msg.attach(MIMEText(body, 'html'))
    else:
        msg.attach(MIMEText(body, 'plain'))

    # Send
    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True
        )
        return {"status": "sent", "to": notification.to}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

async def send_webhook_notification(notification: WebhookNotification):
    """Send webhook HTTP POST"""

    headers = notification.headers or {}
    headers["Content-Type"] = "application/json"

    for attempt in range(notification.retry):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    notification.url,
                    json=notification.payload,
                    headers=headers
                )

                if response.status_code < 300:
                    return {"status": "sent", "attempt": attempt + 1, "response_code": response.status_code}

        except Exception as e:
            if attempt == notification.retry - 1:
                return {"status": "failed", "error": str(e), "attempts": attempt + 1}

    return {"status": "failed", "reason": "max retries exceeded"}

async def send_slack_notification(notification: SlackNotification):
    """Send Slack webhook"""

    payload = {
        "text": notification.text
    }

    if notification.channel:
        payload["channel"] = notification.channel

    if notification.blocks:
        payload["blocks"] = notification.blocks

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                notification.webhook_url,
                json=payload
            )

            if response.status_code == 200:
                return {"status": "sent"}
            else:
                return {"status": "failed", "response_code": response.status_code}

    except Exception as e:
        return {"status": "failed", "error": str(e)}

@app.post("/notify")
async def send_notification(notification: Notification, background_tasks: BackgroundTasks):
    """Send notification via specified channel"""

    # Queue notification
    if REDIS_AVAILABLE:
        queue_key = f"notification_queue:{notification.priority}"
        redis_client.rpush(queue_key, json.dumps(notification.model_dump()))

    # Send based on channel
    if notification.channel == "email":
        result = await send_email_notification(notification.notification_data)
    elif notification.channel == "webhook":
        result = await send_webhook_notification(notification.notification_data)
    elif notification.channel == "slack":
        result = await send_slack_notification(notification.notification_data)
    else:
        return {"error": "Unknown channel"}

    return {
        "notification_id": f"notif-{hash(str(notification))}",
        "channel": notification.channel,
        "priority": notification.priority,
        "result": result
    }

@app.post("/preferences")
async def set_notification_preferences(pref: NotificationPreference):
    """Set user notification preferences"""

    if REDIS_AVAILABLE:
        key = f"notification_pref:{pref.user_id}"
        redis_client.set(key, json.dumps(pref.model_dump()))

    return {"user_id": pref.user_id, "updated": True}

@app.get("/preferences/{user_id}")
async def get_notification_preferences(user_id: str):
    """Get user notification preferences"""

    if REDIS_AVAILABLE:
        key = f"notification_pref:{user_id}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)

    return {"channels": ["email"], "min_priority": "medium"}

@app.get("/queue/stats")
async def get_queue_stats():
    """Get notification queue statistics"""

    if not REDIS_AVAILABLE:
        return {"error": "Redis unavailable"}

    stats = {}
    for priority in ["low", "medium", "high", "critical"]:
        queue_key = f"notification_queue:{priority}"
        count = redis_client.llen(queue_key)
        stats[priority] = count

    return {"queues": stats, "total": sum(stats.values())}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "smtp_configured": bool(SMTP_USER and SMTP_PASSWORD),
        "redis": "available" if REDIS_AVAILABLE else "unavailable"
    }
