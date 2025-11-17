#!/usr/bin/env python3
"""
Index SOPs into Neo4j Knowledge Graph
Creates visual SOP workflow with steps, prerequisites, and service relationships
"""

import asyncio
from neo4j import AsyncGraphDatabase
import os
from pathlib import Path

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity123")

class SOPVisualizer:
    """Visualize SOPs in Neo4j"""

    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    async def init_schema(self):
        """Create SOP schema in Neo4j"""

        async with self.driver.session() as session:
            # Constraints
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:SOP) REQUIRE s.name IS UNIQUE")
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (step:SOPStep) REQUIRE step.id IS UNIQUE")

            # Indexes
            await session.run("CREATE INDEX IF NOT EXISTS FOR (s:SOP) ON (s.category)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (step:SOPStep) ON (step.order)")

    async def create_sop(self, name, category, description, file_path, steps, prerequisites=None, applies_to=None):
        """Create SOP node with steps and relationships"""

        async with self.driver.session() as session:
            # Create SOP node
            await session.run("""
                MERGE (sop:SOP {name: $name})
                SET sop.category = $category,
                    sop.description = $description,
                    sop.file_path = $file_path,
                    sop.step_count = $step_count,
                    sop.last_updated = datetime()
            """,
                name=name,
                category=category,
                description=description,
                file_path=file_path,
                step_count=len(steps)
            )

            # Create step nodes
            for idx, step in enumerate(steps):
                step_id = f"{name}-step-{idx+1}"

                await session.run("""
                    MERGE (step:SOPStep {id: $step_id})
                    SET step.title = $title,
                        step.description = $description,
                        step.order = $order,
                        step.estimated_time = $time
                """,
                    step_id=step_id,
                    title=step.get("title"),
                    description=step.get("description", ""),
                    order=idx + 1,
                    time=step.get("time", "unknown")
                )

                # Link step to SOP
                await session.run("""
                    MATCH (sop:SOP {name: $sop_name})
                    MATCH (step:SOPStep {id: $step_id})
                    MERGE (sop)-[:HAS_STEP {order: $order}]->(step)
                """,
                    sop_name=name,
                    step_id=step_id,
                    order=idx + 1
                )

                # Link step to next step
                if idx > 0:
                    prev_step_id = f"{name}-step-{idx}"
                    await session.run("""
                        MATCH (prev:SOPStep {id: $prev_id})
                        MATCH (current:SOPStep {id: $current_id})
                        MERGE (prev)-[:NEXT_STEP]->(current)
                    """,
                        prev_id=prev_step_id,
                        current_id=step_id
                    )

            # Link to prerequisite SOPs
            if prerequisites:
                for prereq in prerequisites:
                    await session.run("""
                        MATCH (sop:SOP {name: $sop_name})
                        MATCH (prereq:SOP {name: $prereq_name})
                        MERGE (sop)-[:REQUIRES]->(prereq)
                    """,
                        sop_name=name,
                        prereq_name=prereq
                    )

            # Link to services this SOP applies to
            if applies_to:
                for service_name in applies_to:
                    await session.run("""
                        MATCH (sop:SOP {name: $sop_name})
                        MERGE (s:Service {name: $service_name})
                        MERGE (sop)-[:APPLIES_TO]->(s)
                    """,
                        sop_name=name,
                        service_name=service_name
                    )

    async def index_all_sops(self):
        """Index all SOPs from both systems"""

        await self.init_schema()

        print("Indexing SOPs into Neo4j...")

        # User Onboarding SOP
        await self.create_sop(
            name="User Onboarding",
            category="Operations",
            description="Onboard new users to NT-AI-Engine",
            file_path="claudedocs/SOPs/NT_AI_ENGINE_USER_ONBOARDING_SOP.md",
            steps=[
                {"title": "Create user account", "time": "2 min"},
                {"title": "Send invitation email", "time": "1 min"},
                {"title": "User accepts OAuth consent", "time": "5 min"},
                {"title": "Initial data scrape", "time": "15 min"},
                {"title": "Build knowledge graph", "time": "10 min"},
                {"title": "Validate onboarding complete", "time": "5 min"}
            ],
            applies_to=["user-management", "email_monitor", "calendar_scraper", "knowledge_graph"]
        )

        # Deployment SOP
        await self.create_sop(
            name="Deployment",
            category="DevOps",
            description="Deploy Trinity Platform to Azure Container Apps",
            file_path="claudedocs/SOPs/DEPLOYMENT_SOP.md",
            steps=[
                {"title": "Pre-deployment validation", "time": "15 min"},
                {"title": "Build Docker images", "time": "20 min"},
                {"title": "Push to ACR", "time": "15 min"},
                {"title": "Run database migrations", "time": "10 min"},
                {"title": "Deploy Container Apps", "time": "30 min"},
                {"title": "Health check validation", "time": "15 min"},
                {"title": "Integration testing", "time": "20 min"},
                {"title": "Enable monitoring", "time": "10 min"},
                {"title": "Traffic cutover", "time": "Coordinated"},
                {"title": "Post-deployment validation", "time": "30 min"}
            ],
            applies_to=["event-collector", "kg-projector", "rca-api", "api-gateway"]
        )

        # Rollback SOP
        await self.create_sop(
            name="Rollback",
            category="DevOps",
            description="Rollback failed deployments",
            file_path="claudedocs/SOPs/ROLLBACK_SOP.md",
            prerequisites=["Deployment"],
            steps=[
                {"title": "Identify rollback level needed", "time": "5 min"},
                {"title": "Container App revision rollback", "time": "5 min"},
                {"title": "Database migration rollback", "time": "15 min"},
                {"title": "Full environment rollback", "time": "30 min"},
                {"title": "Validation after rollback", "time": "15 min"}
            ],
            applies_to=["all-services"]
        )

        # Schema Migration SOP
        await self.create_sop(
            name="Schema Migration",
            category="Database",
            description="Safe database schema changes",
            file_path="claudedocs/SOPs/SCHEMA_MIGRATION_SOP.md",
            prerequisites=None,
            steps=[
                {"title": "Design migration", "time": "30 min"},
                {"title": "Test locally", "time": "1 hour"},
                {"title": "Peer review", "time": "30 min"},
                {"title": "Deploy to staging", "time": "15 min"},
                {"title": "Validate", "time": "30 min"},
                {"title": "Deploy to production", "time": "Scheduled"}
            ],
            applies_to=["database_manager", "postgres", "cosmos-db"]
        )

        # Incident Response SOP
        await self.create_sop(
            name="Incident Response",
            category="Operations",
            description="Handle production incidents",
            file_path="claudedocs/SOPs/INCIDENT_RESPONSE_SOP.md",
            steps=[
                {"title": "Detection", "time": "Immediate"},
                {"title": "Triage", "time": "5-15 min"},
                {"title": "Mitigation", "time": "Immediate for P0/P1"},
                {"title": "Communication", "time": "Every 30 min"},
                {"title": "Resolution", "time": "Varies"},
                {"title": "Post-mortem", "time": "Within 24 hours"}
            ],
            applies_to=["all-services"]
        )

        print(f"Indexed 5 SOPs with {sum([6, 10, 5, 6, 6])} total steps")

        # Show what was created
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (sop:SOP)
                RETURN sop.name as name, sop.category as category, sop.step_count as steps
                ORDER BY category, name
            """)

            print("\nSOPs in graph:")
            async for record in result:
                print(f"  {record['category']}: {record['name']} ({record['steps']} steps)")

        await self.driver.close()

if __name__ == "__main__":
    async def main():
        viz = SOPVisualizer()
        await viz.index_all_sops()

    asyncio.run(main())
