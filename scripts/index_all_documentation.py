#!/usr/bin/env python3
"""
Index All Documentation into Neo4j Knowledge Graph
Populates Document nodes and links to Services/Issues
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "document-kg"))

from document_linker import DocumentLinker

async def index_all_docs():
    """Index all documentation files into Neo4j"""

    linker = DocumentLinker()
    await linker.init_schema()

    print("Indexing documentation into Neo4j...")
    print(f"Neo4j: {linker.driver._pool.address}")

    indexed = 0
    skipped = 0

    # Index Trinity Platform docs
    trinity_root = Path(__file__).parent.parent

    for doc_path in trinity_root.rglob("*.md"):
        # Skip node_modules, .git, etc
        if any(skip in str(doc_path) for skip in ['node_modules', '.git', '__pycache__', 'venv']):
            skipped += 1
            continue

        try:
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
                await linker.index_document(str(doc_path.relative_to(trinity_root)), content)
                indexed += 1

                if indexed % 10 == 0:
                    print(f"  Indexed {indexed} documents...")

        except Exception as e:
            print(f"  Skipped {doc_path}: {e}")
            skipped += 1

    # Index NT-AI-Engine docs
    ntai_root = trinity_root.parent / "NT-AI-Engine"

    if ntai_root.exists():
        print("\nIndexing NT-AI-Engine docs...")
        for doc_path in ntai_root.rglob("*.md"):
            if any(skip in str(doc_path) for skip in ['node_modules', '.git', '__pycache__', 'venv', '_internal']):
                skipped += 1
                continue

            try:
                with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    rel_path = f"NT-AI-Engine/{doc_path.relative_to(ntai_root)}"
                    await linker.index_document(rel_path, content)
                    indexed += 1

                    if indexed % 10 == 0:
                        print(f"  Indexed {indexed} documents...")

            except Exception as e:
                skipped += 1

    print(f"\n✅ Indexing complete!")
    print(f"   Indexed: {indexed} documents")
    print(f"   Skipped: {skipped} files")

    # Show summary
    async with linker.driver.session() as session:
        result = await session.run("""
            MATCH (d:Document)
            RETURN d.category as category, count(*) as count
            ORDER BY count DESC
        """)

        print(f"\nDocuments by category:")
        async for record in result:
            print(f"  {record['category']}: {record['count']}")

        # Show service links
        result = await session.run("""
            MATCH (d:Document)-[:DOCUMENTS]->(s:Service)
            RETURN count(DISTINCT d) as docs, count(DISTINCT s) as services
        """)

        record = await result.single()
        print(f"\nLinked: {record['docs']} documents → {record['services']} services")

    await linker.driver.close()

if __name__ == "__main__":
    asyncio.run(index_all_docs())
