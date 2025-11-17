"""
Knowledge Graph Projector - Consumes events from NATS and projects into Neo4j

This is OPERATIONAL CODE - it actually runs and builds the knowledge graph.
"""

import os
import asyncio
import json
import logging
from datetime import datetime, timezone
from nats.aio.client import Client as NATS
from neo4j import GraphDatabase, AsyncGraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity_dev_password")


class KnowledgeGraphProjector:
    """Projects events from NATS into Neo4j knowledge graph"""

    def __init__(self):
        self.nc = None
        self.neo4j = None

    async def start(self):
        """Start projector - connect to NATS and Neo4j"""

        # Connect to NATS
        self.nc = NATS()
        await self.nc.connect(NATS_URL)
        logger.info(f"Connected to NATS at {NATS_URL}")

        # Connect to Neo4j
        self.neo4j = AsyncGraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        logger.info(f"Connected to Neo4j at {NEO4J_URI}")

        # Create constraints and indexes
        await self.setup_neo4j_schema()

        # Subscribe to events
        await self.subscribe_to_events()

        logger.info("KG Projector ready and listening for events")

    async def setup_neo4j_schema(self):
        """Create Neo4j constraints and indexes"""

        async with self.neo4j.session() as session:
            # Constraints
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Commit) REQUIRE c.hash IS UNIQUE")
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (i:Issue) REQUIRE (i.repository, i.number) IS UNIQUE")
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE")

            # Indexes
            await session.run("CREATE INDEX IF NOT EXISTS FOR (c:Commit) ON (c.timestamp)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (i:Issue) ON (i.timestamp)")

            logger.info("Neo4j schema setup complete")

    async def subscribe_to_events(self):
        """Subscribe to all relevant event streams"""

        # Subscribe to git commits
        await self.nc.subscribe("git.commits", cb=self.handle_commit_event)

        # Subscribe to GitHub issues
        await self.nc.subscribe("github.issues.>", cb=self.handle_issue_event)

        # Subscribe to code analysis
        await self.nc.subscribe("code.service.>", cb=self.handle_service_event)

        # Subscribe to NT-AI-Engine events
        await self.nc.subscribe("ntai.>", cb=self.handle_ntai_event)

        logger.info("Subscribed to event streams")

    async def handle_commit_event(self, msg):
        """Project commit event into Neo4j"""

        try:
            # Parse event data
            event_str = msg.data.decode()
            event = json.loads(event_str)  # Secure JSON parsing

            async with self.neo4j.session() as session:
                # Create commit node
                await session.run("""
                    MERGE (c:Commit {hash: $hash})
                    SET c.author = $author,
                        c.author_email = $email,
                        c.message = $message,
                        c.timestamp = datetime($timestamp),
                        c.repository = $repository
                """,
                    hash=event["commit_hash"],
                    author=event["author"],
                    email=event["author_email"],
                    message=event["message"],
                    timestamp=event["timestamp"],
                    repository=event["repository"]
                )

                # Link to modified files
                for file_path in event.get("files_changed", []):
                    await session.run("""
                        MERGE (f:File {path: $path, repository: $repository})
                        MERGE (c:Commit {hash: $hash})
                        MERGE (c)-[:MODIFIES {timestamp: datetime($timestamp)}]->(f)
                    """,
                        path=file_path,
                        repository=event["repository"],
                        hash=event["commit_hash"],
                        timestamp=event["timestamp"]
                    )

                logger.info(f"Projected commit {event['commit_hash'][:7]} to Neo4j")

        except Exception as e:
            logger.error(f"Error projecting commit: {e}")

    async def handle_issue_event(self, msg):
        """Project issue event into Neo4j"""

        try:
            event_str = msg.data.decode()
            event = json.loads(event_str)

            async with self.neo4j.session() as session:
                # Create issue node
                await session.run("""
                    MERGE (i:Issue {repository: $repository, number: $number})
                    SET i.title = $title,
                        i.body = $body,
                        i.labels = $labels,
                        i.timestamp = datetime($timestamp),
                        i.status = CASE
                            WHEN $event_type CONTAINS 'opened' THEN 'open'
                            WHEN $event_type CONTAINS 'closed' THEN 'closed'
                            ELSE 'unknown'
                        END
                """,
                    repository=event["repository"],
                    number=event["issue_number"],
                    title=event["title"],
                    body=event["body"],
                    labels=event["labels"],
                    timestamp=event["timestamp"],
                    event_type=event["event_type"]
                )

                # Link issue to affected services (if service name in title/body)
                # This enables RCA API to find affected services
                services_mentioned = []
                text_to_search = (event.get("title", "") + " " + event.get("body", "")).lower()

                # Extract service names from text (basic keyword matching)
                common_service_keywords = ["email", "calendar", "teams", "auth", "database", "api", "webhook"]
                for keyword in common_service_keywords:
                    if keyword in text_to_search:
                        services_mentioned.append(f"{keyword}_service")

                # Create HAD_ISSUE relationships
                for service_name in services_mentioned:
                    await session.run("""
                        MERGE (s:Service {name: $service})
                        MATCH (i:Issue {repository: $repository, number: $number})
                        MERGE (s)-[:HAD_ISSUE]->(i)
                    """,
                        service=service_name,
                        repository=event["repository"],
                        number=event["issue_number"]
                    )

                # If issue is closed, create Solution node
                if event["event_type"].endswith("closed"):
                    await session.run("""
                        MATCH (i:Issue {repository: $repository, number: $number})
                        MERGE (sol:Solution {id: $solution_id})
                        SET sol.title = 'Resolved: ' + i.title,
                            sol.category = 'issue_resolution',
                            sol.success_rate = 0.8
                        MERGE (i)-[:RESOLVED_BY]->(sol)
                    """,
                        repository=event["repository"],
                        number=event["issue_number"],
                        solution_id=f"sol-{event['repository']}-{event['issue_number']}"
                    )

                logger.info(f"Projected issue #{event['issue_number']} to Neo4j")

        except Exception as e:
            logger.error(f"Error projecting issue: {e}")

    async def handle_service_event(self, msg):
        """Project service event into Neo4j"""

        try:
            event_str = msg.data.decode()
            event = json.loads(event_str)

            async with self.neo4j.session() as session:
                # Create/update service node
                await session.run("""
                    MERGE (s:Service {name: $name})
                    SET s.file_path = $file_path,
                        s.last_modified = datetime($timestamp),
                        s.last_commit = $commit_hash,
                        s.dependencies_changed = $dependencies_changed
                """,
                    name=event["service_name"],
                    file_path=event["file_path"],
                    timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    commit_hash=event.get("commit_hash", "unknown"),
                    dependencies_changed=event.get("dependencies_changed", False)
                )

                # Link to commit
                if event.get("commit_hash"):
                    await session.run("""
                        MATCH (s:Service {name: $service})
                        MATCH (c:Commit {hash: $commit})
                        MERGE (c)-[:MODIFIED_SERVICE]->(s)
                    """,
                        service=event["service_name"],
                        commit=event["commit_hash"]
                    )

                logger.info(f"Projected service {event['service_name']} to Neo4j")

        except Exception as e:
            logger.error(f"Error projecting service: {e}")

    async def handle_ntai_event(self, msg):
        """Project NT-AI-Engine event into Neo4j"""

        try:
            event_str = msg.data.decode()
            event = json.loads(event_str)

            event_type = event.get("event_type", "unknown")
            tenant_id = event.get("tenant_id", "unknown")

            async with self.neo4j.session() as session:
                # Create tenant node if not exists
                await session.run("""
                    MERGE (t:Tenant {id: $tenant_id})
                    SET t.last_activity = datetime($timestamp)
                """,
                    tenant_id=tenant_id,
                    timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat())
                )

                # Handle different NT-AI event types
                if "email" in event_type:
                    await session.run("""
                        MERGE (t:Tenant {id: $tenant_id})
                        MERGE (e:EmailEvent {id: $event_id})
                        SET e.from = $from,
                            e.subject = $subject,
                            e.importance_score = $importance,
                            e.timestamp = datetime($timestamp)
                        MERGE (t)-[:HAD_EMAIL_EVENT]->(e)
                    """,
                        tenant_id=tenant_id,
                        event_id=event.get("email_id", f"email-{datetime.now().timestamp()}"),
                        from_addr=event.get("from", "unknown"),
                        subject=event.get("subject", ""),
                        importance=event.get("importance_score", 0),
                        timestamp=event.get("timestamp")
                    )

                elif "task" in event_type:
                    await session.run("""
                        MERGE (t:Tenant {id: $tenant_id})
                        MERGE (task:Task {id: $task_id})
                        SET task.name = $name,
                            task.created_from = $source,
                            task.timestamp = datetime($timestamp)
                        MERGE (t)-[:CREATED_TASK]->(task)
                    """,
                        tenant_id=tenant_id,
                        task_id=event.get("task_id", f"task-{datetime.now().timestamp()}"),
                        name=event.get("task_name", ""),
                        source=event.get("created_from", ""),
                        timestamp=event.get("timestamp")
                    )

                elif "error" in event_type:
                    # Create Issue node for errors from NT-AI-Engine
                    await session.run("""
                        MERGE (t:Tenant {id: $tenant_id})
                        MERGE (i:Issue {id: $issue_id})
                        SET i.title = $message,
                            i.category = $error_type,
                            i.component = $component,
                            i.severity = 'high',
                            i.status = 'open',
                            i.timestamp = datetime($timestamp)
                        MERGE (t)-[:REPORTED_ISSUE]->(i)
                    """,
                        tenant_id=tenant_id,
                        issue_id=f"ntai-error-{tenant_id}-{datetime.now().timestamp()}",
                        message=event.get("error_message", "Unknown error"),
                        error_type=event.get("error_type", "unknown"),
                        component=event.get("component", "unknown"),
                        timestamp=event.get("timestamp")
                    )

                    # Link to affected service if component known
                    if event.get("component"):
                        issue_id_val = f"ntai-error-{tenant_id}-{datetime.now().timestamp()}"
                        await session.run("""
                            MERGE (s:Service {name: $component})
                            WITH s
                            MATCH (i:Issue {id: $issue_id})
                            MERGE (s)-[:HAD_ISSUE]->(i)
                        """,
                            component=event["component"],
                            issue_id=issue_id_val
                        )

                logger.info(f"Projected NT-AI event: {event_type} (tenant: {tenant_id})")

        except Exception as e:
            logger.error(f"Error projecting NT-AI event: {e}")

    async def run_forever(self):
        """Keep projector running"""
        logger.info("KG Projector running. Press Ctrl+C to stop.")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down projector...")


async def main():
    """Main entry point"""
    projector = KnowledgeGraphProjector()
    await projector.start()
    await projector.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
