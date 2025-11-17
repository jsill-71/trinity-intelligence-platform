"""
Backup Service - Automated backup and restore for PostgreSQL and Neo4j
Scheduled backups with retention policies
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncpg
from neo4j import GraphDatabase
import asyncio
import os
import subprocess
from datetime import datetime
import json

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://trinity:trinity@postgres:5432/trinity")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity123")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/backups")

BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))

os.makedirs(BACKUP_DIR, exist_ok=True)

scheduler = AsyncIOScheduler()

async def backup_postgres():
    """Backup PostgreSQL database"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"postgres_{timestamp}.sql")

    print(f"[BACKUP] Starting PostgreSQL backup: {backup_file}")

    try:
        # Export schema and data
        conn = await asyncpg.connect(POSTGRES_URL)

        # Get table list
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
        """)

        backup_data = {
            "timestamp": timestamp,
            "tables": {}
        }

        for table in tables:
            table_name = table["tablename"]
            rows = await conn.fetch(f"SELECT * FROM {table_name}")

            backup_data["tables"][table_name] = [dict(row) for row in rows]

        await conn.close()

        # Save backup
        with open(backup_file + ".json", "w") as f:
            json.dump(backup_data, f, default=str, indent=2)

        print(f"[BACKUP] PostgreSQL backup complete: {len(backup_data['tables'])} tables")

    except Exception as e:
        print(f"[BACKUP] PostgreSQL backup failed: {e}")

async def backup_neo4j():
    """Backup Neo4j knowledge graph"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"neo4j_{timestamp}.cypher")

    print(f"[BACKUP] Starting Neo4j backup: {backup_file}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Export all nodes
            result = session.run("""
                MATCH (n)
                RETURN labels(n) as labels, properties(n) as props
            """)

            nodes = []
            for record in result:
                nodes.append({
                    "labels": record["labels"],
                    "properties": record["props"]
                })

            # Export all relationships
            result = session.run("""
                MATCH (a)-[r]->(b)
                RETURN id(a) as from_id, id(b) as to_id, type(r) as rel_type, properties(r) as props
            """)

            relationships = []
            for record in result:
                relationships.append({
                    "from": record["from_id"],
                    "to": record["to_id"],
                    "type": record["rel_type"],
                    "properties": record["props"]
                })

            backup_data = {
                "timestamp": timestamp,
                "nodes": nodes,
                "relationships": relationships
            }

            # Save backup
            with open(backup_file + ".json", "w") as f:
                json.dump(backup_data, f, default=str, indent=2)

            print(f"[BACKUP] Neo4j backup complete: {len(nodes)} nodes, {len(relationships)} relationships")

    except Exception as e:
        print(f"[BACKUP] Neo4j backup failed: {e}")
    finally:
        driver.close()

async def cleanup_old_backups():
    """Remove backups older than retention period"""

    print("[BACKUP] Cleaning up old backups...")

    cutoff = datetime.now().timestamp() - (BACKUP_RETENTION_DAYS * 86400)
    removed = 0

    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)

        if os.path.isfile(filepath):
            file_time = os.path.getmtime(filepath)

            if file_time < cutoff:
                os.remove(filepath)
                removed += 1

    print(f"[BACKUP] Removed {removed} old backups")

async def setup():
    """Initialize backup service"""

    print("[BACKUP SERVICE] Starting Trinity Backup Service")
    print(f"[BACKUP SERVICE] Backup directory: {BACKUP_DIR}")
    print(f"[BACKUP SERVICE] Retention: {BACKUP_RETENTION_DAYS} days")

    # Schedule daily backups
    scheduler.add_job(
        backup_postgres,
        CronTrigger(hour=1, minute=0),  # 1 AM daily
        id="postgres_backup",
        name="PostgreSQL Daily Backup"
    )

    scheduler.add_job(
        backup_neo4j,
        CronTrigger(hour=1, minute=30),  # 1:30 AM daily
        id="neo4j_backup",
        name="Neo4j Daily Backup"
    )

    scheduler.add_job(
        cleanup_old_backups,
        CronTrigger(hour=2, minute=30),  # 2:30 AM daily
        id="backup_cleanup",
        name="Backup Cleanup"
    )

    scheduler.start()
    print(f"[BACKUP SERVICE] Scheduler started with {len(scheduler.get_jobs())} backup jobs")

    # Run initial backup
    print("[BACKUP SERVICE] Running initial backup...")
    await backup_postgres()
    await backup_neo4j()

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("[BACKUP SERVICE] Shutting down...")
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(setup())
