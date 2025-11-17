"""
Document Knowledge Graph - IMPROVED UX
Redesigned based on SME panel feedback for glanceable understanding
"""

import asyncio
from neo4j import AsyncGraphDatabase
import os
from pathlib import Path
from datetime import datetime
import hashlib
import re

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity123")

class ImprovedDocumentLinker:
    """Links documentation with meaningful labels and descriptions"""

    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def extract_title(self, content: str, file_path: str) -> str:
        """Extract meaningful title from document"""

        # Try to find markdown heading
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # Convert filename to readable title
        filename = Path(file_path).stem
        # BACKWARD_DEPENDENCY_ANALYSIS → Backward Dependency Analysis
        title = filename.replace('_', ' ').replace('-', ' ').title()

        # Limit length
        if len(title) > 50:
            title = title[:47] + "..."

        return title

    def extract_description(self, content: str) -> str:
        """Extract first paragraph or summary as description"""

        # Skip markdown headers and frontmatter
        lines = content.split('\n')
        desc_lines = []

        in_paragraph = False

        for line in lines:
            line = line.strip()

            # Skip empty, headers, frontmatter
            if not line or line.startswith('#') or line.startswith('---') or line.startswith('**'):
                if in_paragraph:
                    break  # End of first paragraph
                continue

            if line:
                in_paragraph = True
                desc_lines.append(line)

                # Get first 200 chars
                full_desc = ' '.join(desc_lines)
                if len(full_desc) > 200:
                    return full_desc[:197] + "..."

        desc = ' '.join(desc_lines)
        return desc[:200] if desc else "Documentation"

    def infer_relationship_type(self, doc_category: str, service_name: str) -> str:
        """Infer semantic relationship type instead of generic DOCUMENTS"""

        if doc_category == "sop":
            return "PROVIDES_SOP_FOR"
        elif doc_category == "deployment":
            return "EXPLAINS_DEPLOYMENT_OF"
        elif doc_category == "architecture":
            return "DEFINES_ARCHITECTURE_FOR"
        elif doc_category == "troubleshooting":
            return "TROUBLESHOOTS"
        elif doc_category == "api_reference":
            return "DESCRIBES_API_OF"
        elif "guide" in doc_category or "tutorial" in doc_category:
            return "GUIDES_USAGE_OF"
        else:
            return "DOCUMENTS"

    def calculate_importance(self, content: str, category: str) -> str:
        """Calculate document importance for visual hierarchy"""

        # Strategic docs (large nodes)
        if any(word in content.lower() for word in ["strategy", "architecture", "master", "complete"]):
            return "strategic"

        # Operational docs (medium nodes)
        if category in ["sop", "deployment", "guide"]:
            return "operational"

        # Reference docs (small nodes)
        if category in ["api_reference", "troubleshooting"]:
            return "reference"

        # Archived (tiny nodes)
        if "archive" in content.lower() or "deprecated" in content.lower():
            return "archived"

        return "operational"

    async def init_schema(self):
        """Create improved schema"""

        async with self.driver.session() as session:
            # Constraints
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.path IS UNIQUE")

            # Indexes
            await session.run("CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.title)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.importance)")

    async def index_document(self, file_path: str, content: str):
        """Index document with improved UX"""

        # Extract meaningful properties
        title = self.extract_title(content, file_path)
        description = self.extract_description(content)
        doc_hash = hashlib.md5(content.encode()).hexdigest()
        category = self.categorize_document(file_path)
        importance = self.calculate_importance(content, category)

        # Extract references
        referenced_services = self.extract_service_references(content)
        referenced_issues = self.extract_issue_references(content)

        async with self.driver.session() as session:
            # Create document node with improved properties
            await session.run("""
                MERGE (d:Document {path: $path})
                SET d.title = $title,
                    d.description = $description,
                    d.hash = $hash,
                    d.category = $category,
                    d.importance = $importance,
                    d.last_modified = datetime($timestamp),
                    d.size_bytes = $size,
                    d.line_count = $lines
            """,
                path=file_path,
                title=title,
                description=description,
                hash=doc_hash,
                category=category,
                importance=importance,
                timestamp=datetime.now().isoformat(),
                size=len(content),
                lines=content.count('\n')
            )

            # Link to services with semantic relationships
            for service in referenced_services:
                rel_type = self.infer_relationship_type(category, service)

                await session.run(f"""
                    MATCH (d:Document {{path: $doc_path}})
                    MERGE (s:Service {{name: $service}})
                    MERGE (d)-[:{rel_type}]->(s)
                """,
                    doc_path=file_path,
                    service=service
                )

            # Link to issues
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
        """Categorize document"""
        path_lower = path.lower()

        if "sop" in path_lower:
            return "sop"
        elif "deployment" in path_lower or "azure" in path_lower:
            return "deployment"
        elif "architecture" in path_lower:
            return "architecture"
        elif "issue" in path_lower or "rca" in path_lower or "troubleshoot" in path_lower:
            return "troubleshooting"
        elif "api" in path_lower or "reference" in path_lower:
            return "api_reference"
        elif "guide" in path_lower or "tutorial" in path_lower:
            return "guide"
        else:
            return "general"

    def extract_service_references(self, content: str) -> list:
        """Extract service names"""
        services = []
        common_services = [
            "email_monitor", "task_creator", "database_manager", "monday_client",
            "knowledge_graph", "event-collector", "kg-projector", "rca-api",
            "investigation-api", "vector-search", "user-management", "api-gateway"
        ]

        for service in common_services:
            if service in content or service.replace("-", "_") in content:
                services.append(service)

        return services

    def extract_issue_references(self, content: str) -> list:
        """Extract issue IDs"""
        return re.findall(r'ISSUE-\d+', content)

if __name__ == "__main__":
    async def test():
        linker = ImprovedDocumentLinker()
        await linker.init_schema()

        # Test with sample doc
        sample = """# Mission Complete Final Report

This report summarizes the Trinity Platform deployment achievements.

The platform successfully deployed 26 services with complete backward dependency mapping.
"""

        await linker.index_document("test.md", sample)

        # Verify
        async with linker.driver.session() as session:
            result = await session.run("""
                MATCH (d:Document {path: 'test.md'})
                RETURN d.title, d.description, d.importance
            """)

            record = await result.single()
            print(f"Title: {record['d.title']}")
            print(f"Description: {record['d.description']}")
            print(f"Importance: {record['d.importance']}")

        await linker.driver.close()

    asyncio.run(test())
