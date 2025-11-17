"""
Document Knowledge Graph - Link Documents to Code/Issues/Services
Extends KG Projector to index documentation
"""

import asyncio
from neo4j import AsyncGraphDatabase
import os
from pathlib import Path
from datetime import datetime
import hashlib

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity123")

class DocumentLinker:
    """Links documentation to code entities in knowledge graph"""

    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    async def init_schema(self):
        """Create document node schema"""

        async with self.driver.session() as session:
            # Document nodes
            await session.run("""
                CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document)
                REQUIRE d.path IS UNIQUE
            """)

            # Indexes
            await session.run("CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.category)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.last_modified)")

    async def index_document(self, file_path: str, content: str):
        """Index a documentation file"""

        # Extract metadata
        doc_hash = hashlib.md5(content.encode()).hexdigest()
        category = self.categorize_document(file_path)
        referenced_services = self.extract_service_references(content)
        referenced_issues = self.extract_issue_references(content)

        async with self.driver.session() as session:
            # Create document node
            await session.run("""
                MERGE (d:Document {path: $path})
                SET d.hash = $hash,
                    d.category = $category,
                    d.last_modified = datetime($timestamp),
                    d.size_bytes = $size,
                    d.line_count = $lines
            """,
                path=file_path,
                hash=doc_hash,
                category=category,
                timestamp=datetime.now().isoformat(),
                size=len(content),
                lines=content.count('\n')
            )

            # Link to referenced services
            for service in referenced_services:
                await session.run("""
                    MATCH (d:Document {path: $doc_path})
                    MERGE (s:Service {name: $service})
                    MERGE (d)-[:DOCUMENTS]->(s)
                """,
                    doc_path=file_path,
                    service=service
                )

            # Link to referenced issues
            for issue in referenced_issues:
                await session.run("""
                    MATCH (d:Document {path: $doc_path})
                    MERGE (i:Issue {id: $issue})
                    MERGE (d)-[:DESCRIBES]->(i)
                """,
                    doc_path=file_path,
                    issue=issue
                )

    def categorize_document(self, path: str) -> str:
        """Categorize document by path/name"""

        path_lower = path.lower()

        if "architecture" in path_lower:
            return "architecture"
        elif "deployment" in path_lower or "azure" in path_lower:
            return "deployment"
        elif "sop" in path_lower:
            return "sop"
        elif "issue" in path_lower or "rca" in path_lower:
            return "troubleshooting"
        elif "api" in path_lower or "reference" in path_lower:
            return "api_reference"
        elif "guide" in path_lower or "tutorial" in path_lower:
            return "guide"
        else:
            return "general"

    def extract_service_references(self, content: str) -> list:
        """Extract service names mentioned in document"""

        services = []
        common_services = [
            "email_monitor", "task_creator", "database_manager", "monday_client",
            "knowledge_graph", "event-collector", "kg-projector", "rca-api",
            "investigation-api", "vector-search", "user-management"
        ]

        for service in common_services:
            if service in content or service.replace("-", "_") in content:
                services.append(service)

        return services

    def extract_issue_references(self, content: str) -> list:
        """Extract issue IDs mentioned in document"""

        import re
        return re.findall(r'ISSUE-\d+', content)

    async def find_related_docs(self, service_name: str) -> list:
        """Find all documents that reference a service"""

        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (d:Document)-[:DOCUMENTS]->(s:Service {name: $service})
                RETURN d.path as path, d.category as category, d.last_modified as modified
                ORDER BY d.last_modified DESC
            """, service=service_name)

            return [dict(record) async for record in result]

    async def find_stale_docs(self, days: int = 90) -> list:
        """Find documents not updated in N days"""

        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (d:Document)
                WHERE d.last_modified < datetime() - duration({days: $days})
                RETURN d.path as path, d.category as category, d.last_modified as modified
                ORDER BY d.last_modified ASC
            """, days=days)

            return [dict(record) async for record in result]

    async def mark_document_superseded(self, old_path: str, new_path: str):
        """Mark old document as superseded by new one"""

        async with self.driver.session() as session:
            await session.run("""
                MATCH (old:Document {path: $old_path})
                MERGE (new:Document {path: $new_path})
                MERGE (old)-[:SUPERSEDED_BY]->(new)
                SET old.status = 'superseded'
            """,
                old_path=old_path,
                new_path=new_path
            )

    async def get_current_architecture_docs(self) -> list:
        """Get current (not superseded) architecture documents"""

        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (d:Document)
                WHERE d.category = 'architecture'
                  AND NOT (d)-[:SUPERSEDED_BY]->()
                RETURN d.path as path, d.last_modified as modified
                ORDER BY d.last_modified DESC
            """)

            return [dict(record) async for record in result]

if __name__ == "__main__":
    async def demo():
        linker = DocumentLinker()
        await linker.init_schema()

        # Index a document
        with open("docs/CURRENT_ARCHITECTURE_VERSION.txt", 'r') as f:
            await linker.index_document(
                "docs/CURRENT_ARCHITECTURE_VERSION.txt",
                f.read()
            )

        # Find related docs
        related = await linker.find_related_docs("email_monitor")
        print(f"Documents about email_monitor: {len(related)}")

        # Find stale docs
        stale = await linker.find_stale_docs(90)
        print(f"Stale documents (>90 days): {len(stale)}")

    asyncio.run(demo())
