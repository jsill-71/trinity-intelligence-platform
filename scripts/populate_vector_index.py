#!/usr/bin/env python3
"""
Populate vector search index with knowledge graph data
Extracts issues, solutions, and services from Neo4j and indexes them
"""

import httpx
from neo4j import GraphDatabase
import asyncio
import sys

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "trinity123"
VECTOR_SEARCH_URL = "http://localhost:8004"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

async def populate_index():
    """Extract data from Neo4j and populate vector index"""

    print("Connecting to Neo4j...")
    with driver.session() as session:
        # Get all issues
        print("\nIndexing issues...")
        result = session.run("""
            MATCH (i:Issue)
            RETURN i.id as id, i.title as title, i.category as category, i.status as status
        """)

        issues = []
        for record in result:
            issues.append({
                "doc_id": record["id"],
                "text": f"{record['title']} - {record['category'] if record['category'] else ''}",
                "metadata": {
                    "type": "issue",
                    "status": record["status"]
                }
            })

        # Get all solutions
        print("Indexing solutions...")
        result = session.run("""
            MATCH (s:Solution)
            RETURN s.id as id, s.title as title, s.category as category
        """)

        solutions = []
        for record in result:
            solutions.append({
                "doc_id": record["id"],
                "text": f"{record['title']} - {record['category'] if record['category'] else ''}",
                "metadata": {
                    "type": "solution"
                }
            })

        # Get all services
        print("Indexing services...")
        result = session.run("""
            MATCH (s:Service)
            RETURN s.name as name, s.description as description, s.technology as technology
            LIMIT 200
        """)

        services = []
        for record in result:
            desc = record["description"] if record["description"] else ""
            tech = record["technology"] if record["technology"] else ""
            services.append({
                "doc_id": f"service-{record['name']}",
                "text": f"{record['name']} - {desc} {tech}",
                "metadata": {
                    "type": "service"
                }
            })

    print(f"\nTotal documents to index:")
    print(f"  Issues: {len(issues)}")
    print(f"  Solutions: {len(solutions)}")
    print(f"  Services: {len(services)}")

    # Index all documents
    all_docs = issues + solutions + services

    if len(all_docs) == 0:
        print("\nNo documents found in Neo4j. Run import_analysis_data.py first.")
        return

    print(f"\nIndexing {len(all_docs)} documents...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Batch index
        batch_size = 50
        for i in range(0, len(all_docs), batch_size):
            batch = all_docs[i:i+batch_size]
            try:
                response = await client.post(
                    f"{VECTOR_SEARCH_URL}/index/batch",
                    json=batch
                )
                if response.status_code == 200:
                    result = response.json()
                    print(f"  Indexed batch {i//batch_size + 1}: {result['indexed']} documents (total: {result['total_documents']})")
                else:
                    print(f"  ERROR indexing batch {i//batch_size + 1}: {response.status_code}")
            except Exception as e:
                print(f"  ERROR indexing batch {i//batch_size + 1}: {e}")

        # Get final stats
        try:
            response = await client.get(f"{VECTOR_SEARCH_URL}/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"\nVector index stats:")
                print(f"  Total documents: {stats['total_documents']}")
                print(f"  Model: {stats['model']}")
                print(f"  Dimension: {stats['index_dimension']}")
                print(f"  Redis: {stats['redis_available']}")
        except Exception as e:
            print(f"\nERROR getting stats: {e}")

    print("\n[OK] Vector index populated")

if __name__ == "__main__":
    try:
        asyncio.run(populate_index())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
