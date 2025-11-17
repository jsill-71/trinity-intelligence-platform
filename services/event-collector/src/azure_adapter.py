"""
Azure Adapter for Event Collector
Replaces NATS with Azure Service Bus for production deployment
"""

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
import os
import json

class AzureServiceBusAdapter:
    """Adapter to use Azure Service Bus instead of NATS"""

    def __init__(self):
        self.connection_string = os.getenv("SERVICEBUS_CONNECTION")
        self.client = None

    async def connect(self):
        """Connect to Azure Service Bus"""
        if self.connection_string:
            self.client = ServiceBusClient.from_connection_string(self.connection_string)
        else:
            raise ValueError("SERVICEBUS_CONNECTION not configured")

    async def publish(self, topic: str, message: bytes):
        """Publish message to Service Bus topic"""

        if not self.client:
            await self.connect()

        # Map NATS subjects to Service Bus topics
        # git.commits → git-commits
        # github.issues.opened → github-events
        # ntai.error.occurred → ntai-events

        if topic.startswith("git.commits"):
            topic_name = "git-commits"
        elif topic.startswith("github."):
            topic_name = "github-events"
        elif topic.startswith("ntai."):
            topic_name = "ntai-events"
        else:
            topic_name = "events"

        async with self.client:
            sender = self.client.get_topic_sender(topic_name=topic_name)
            async with sender:
                sb_message = ServiceBusMessage(message)
                await sender.send_messages(sb_message)

    async def close(self):
        """Close Service Bus connection"""
        if self.client:
            await self.client.close()

# Factory function to get message bus (NATS locally, Service Bus in Azure)
async def get_message_bus():
    """
    Returns appropriate message bus for environment

    Local: NATS
    Azure: Service Bus
    """
    if os.getenv("AZURE_DEPLOYMENT", "false").lower() == "true":
        return AzureServiceBusAdapter()
    else:
        # Return NATS client
        from nats.aio.client import Client as NATS
        nc = NATS()
        await nc.connect(os.getenv("NATS_URL", "nats://localhost:4222"))
        return nc
