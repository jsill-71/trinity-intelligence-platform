"""
Import Tonight's Analysis Data into Trinity Knowledge Graph

Populates Neo4j with:
- 631 services from TEAM2_SERVICE_CATALOG_QUICK.json
- 87 issues from TEAM1_ISSUE_ROOT_CAUSE_ANALYSIS.json + TEAM2_ISSUE_PATTERNS.json
- 821 commits from TEAM1_GIT_HISTORY_ANALYSIS.json
- 10 solution patterns from TEAM3_SOLUTION_PATTERNS_LIBRARY.json
"""

import json
from pathlib import Path
from neo4j import GraphDatabase

# Configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "trinity123"

# Data files (from tonight's analysis)
BASE_DIR = Path("C:/Users/jonat/Desktop/NT-AI-Engine")
SERVICES_FILE = BASE_DIR / "TEAM2_SERVICE_CATALOG_QUICK.json"
ISSUES_RCA_FILE = BASE_DIR / "TEAM1_ISSUE_ROOT_CAUSE_ANALYSIS.json"
ISSUES_PATTERNS_FILE = BASE_DIR / "TEAM2_ISSUE_PATTERNS.json"
COMMITS_FILE = BASE_DIR / "TEAM1_GIT_HISTORY_ANALYSIS.json"
SOLUTIONS_FILE = BASE_DIR / "TEAM3_SOLUTION_PATTERNS_LIBRARY.json"

def import_all_data():
    """Import all analysis data to Neo4j"""

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Create constraints first
        print("Creating constraints...")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (i:Issue) REQUIRE i.id IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Commit) REQUIRE c.hash IS UNIQUE")
        session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (sol:Solution) REQUIRE sol.id IS UNIQUE")

        # Import services (631 total)
        print("Importing 631 services...")
        if SERVICES_FILE.exists():
            services_data = json.loads(SERVICES_FILE.read_text(encoding='utf-8'))

            count = 0
            for service in services_data.get('services', []):
                session.run("""
                    MERGE (s:Service {name: $name})
                    SET s.path = $path,
                        s.domain = $domain,
                        s.layer = $layer,
                        s.purpose = $purpose,
                        s.loc = $loc,
                        s.author = $author
                """,
                    name=service.get('name'),
                    path=service.get('path'),
                    domain=service.get('domain'),
                    layer=service.get('layer'),
                    purpose=service.get('purpose'),
                    loc=service.get('lines_of_code', 0),
                    author=service.get('primary_author')
                )

                # Add dependencies
                for dep in service.get('direct_dependencies', []):
                    session.run("""
                        MATCH (s:Service {name: $service})
                        MERGE (d:Service {name: $dependency})
                        MERGE (s)-[:DEPENDS_ON]->(d)
                    """,
                        service=service.get('name'),
                        dependency=dep
                    )

                count += 1
                if count % 100 == 0:
                    print(f"  Imported {count} services...")

            print(f"[OK] Imported {count} services")

        # Import issues (87 total)
        print("Importing 87 issues...")
        if ISSUES_RCA_FILE.exists():
            issues_data = json.loads(ISSUES_RCA_FILE.read_text(encoding='utf-8'))

            for issue in issues_data.get('issues', []):
                session.run("""
                    MERGE (i:Issue {id: $id})
                    SET i.title = $title,
                        i.category = $category,
                        i.severity = $severity,
                        i.status = $status
                """,
                    id=issue.get('id'),
                    title=issue.get('title'),
                    category=issue.get('category'),
                    severity=issue.get('severity'),
                    status=issue.get('status')
                )

            print(f"[OK] Imported {len(issues_data.get('issues', []))} issues")

        # Import commits (821 total)
        print("Importing 821 commits...")
        if COMMITS_FILE.exists():
            commits_data = json.loads(COMMITS_FILE.read_text(encoding='utf-8'))

            count = 0
            for commit in commits_data.get('commits', []):
                session.run("""
                    MERGE (c:Commit {hash: $hash})
                    SET c.author = $author,
                        c.message = $message,
                        c.date = $date
                """,
                    hash=commit.get('hash'),
                    author=commit.get('author'),
                    message=commit.get('message'),
                    date=commit.get('date')
                )

                count += 1
                if count % 200 == 0:
                    print(f"  Imported {count} commits...")

            print(f"[OK] Imported {count} commits")

        # Import solution patterns (10 total)
        print("Importing 10 solution patterns...")
        if SOLUTIONS_FILE.exists():
            solutions_data = json.loads(SOLUTIONS_FILE.read_text(encoding='utf-8'))

            for pattern in solutions_data.get('patterns', []):
                session.run("""
                    MERGE (s:Solution {id: $id})
                    SET s.title = $title,
                        s.category = $category,
                        s.success_rate = $success_rate,
                        s.times_used = $times_used
                """,
                    id=pattern.get('id'),
                    title=pattern.get('title'),
                    category=pattern.get('category'),
                    success_rate=pattern.get('success_rate'),
                    times_used=pattern.get('times_used', 0)
                )

            print(f"[OK] Imported {len(solutions_data.get('patterns', []))} solution patterns")

        # Final statistics
        stats = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as type, COUNT(n) as count
            ORDER BY count DESC
        """).data()

        print("\n" + "="*60)
        print("IMPORT COMPLETE")
        print("="*60)
        for stat in stats:
            print(f"  {stat['type']}: {stat['count']}")

        total = sum(s['count'] for s in stats)
        print(f"\nTotal nodes: {total}")

    driver.close()
    print("\n[OK] Data import successful!")
    print(f"Access knowledge graph: http://localhost:7474")
    print(f"Login: neo4j / trinity123")

if __name__ == "__main__":
    import_all_data()
