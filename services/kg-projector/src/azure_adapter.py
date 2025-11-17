"""
Azure Adapter for KG Projector
Replaces NATS with Service Bus, Neo4j with Cosmos DB
"""

from azure.servicebus.aio import ServiceBusClient
from azure.cosmos.aio import CosmosClient
import os

class AzureKGAdapter:
    """Adapter for Azure managed services"""

    def __init__(self):
        self.use_azure = os.getenv("AZURE_DEPLOYMENT", "false").lower() == "true"
        self.servicebus_connection = os.getenv("SERVICEBUS_CONNECTION")
        self.cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
        self.cosmos_key = os.getenv("COSMOS_KEY")

    async def subscribe_to_events(self, callback):
        """Subscribe to events from Service Bus topics"""

        if not self.use_azure:
            # Use NATS for local development
            from nats.aio.client import Client as NATS
            nc = NATS()
            await nc.connect(os.getenv("NATS_URL", "nats://localhost:4222"))
            await nc.subscribe("git.commits", cb=callback)
            await nc.subscribe("github.issues.>", cb=callback)
            await nc.subscribe("ntai.>", cb=callback)
            return nc

        # Azure Service Bus for production
        client = ServiceBusClient.from_connection_string(self.servicebus_connection)

        # Subscribe to topics
        for topic in ["git-commits", "github-events", "ntai-events"]:
            receiver = client.get_subscription_receiver(
                topic_name=topic,
                subscription_name="kg-projector"
            )

            # Process messages
            async with receiver:
                async for message in receiver:
                    await callback(message)
                    await receiver.complete_message(message)

    async def get_graph_client(self):
        """Get graph database client (Neo4j or Cosmos DB)"""

        if not self.use_azure:
            # Use Neo4j for local
            from neo4j import AsyncGraphDatabase
            return AsyncGraphDatabase.driver(
                os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
            )

        # Use Cosmos DB for Azure (MongoDB API or Gremlin API)
        cosmos_client = CosmosClient(
            self.cosmos_endpoint,
            credential=self.cosmos_key
        )

        database = cosmos_client.get_database_client("trinity")
        container = cosmos_client.get_container_client(
            database="trinity",
            container="knowledge_graph"
        )

        return container
