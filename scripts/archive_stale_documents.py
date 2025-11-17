#!/usr/bin/env python3
"""
Archive Stale Documents - Use Document KG to clean up old docs
Moves superseded/stale documents to archive/ directory
"""

import asyncio
import sys
from pathlib import Path
import shutil
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "document-kg"))
from document_linker import DocumentLinker

async def archive_stale_documents(dry_run=True):
    """
    Archive documents that are:
    1. Marked as superseded in graph
    2. Not updated in 90+ days
    3. Reference old architecture
    """

    linker = DocumentLinker()

    print("Querying Neo4j for stale documents...")

    # Get superseded documents
    async with linker.driver.session() as session:
        result = await session.run("""
            MATCH (old:Document)-[:SUPERSEDED_BY]->(new:Document)
            RETURN old.path as path, new.path as superseded_by
        """)

        superseded_docs = [(record["path"], record["superseded_by"]) async for record in result]

    # Get stale documents (>90 days old)
    stale_docs = await linker.find_stale_docs(days=90)

    # Get documents referencing old architecture
    async with linker.driver.session() as session:
        result = await session.run("""
            MATCH (d:Document)
            WHERE d.path CONTAINS 'OLD_ARCHITECTURE'
               OR d.path CONTAINS 'DEPRECATED'
               OR d.path CONTAINS 'SUPERSEDED'
            RETURN d.path as path
        """)

        old_arch_docs = [record["path"] async for record in result]

    # Combine all candidates
    to_archive = set()

    for path, _ in superseded_docs:
        to_archive.add(path)

    for doc in stale_docs:
        to_archive.add(doc["path"])

    for path in old_arch_docs:
        to_archive.add(path)

    print(f"\nFound {len(to_archive)} documents to archive:")
    print(f"  - Superseded: {len(superseded_docs)}")
    print(f"  - Stale (>90 days): {len(stale_docs)}")
    print(f"  - Old architecture: {len(old_arch_docs)}")

    if not to_archive:
        print("\nNo documents to archive!")
        return

    # Archive documents
    archived_count = 0
    failed_count = 0

    for doc_path in sorted(to_archive):
        try:
            # Determine archive location
            if "superseded" in doc_path.lower() or any(old in doc_path for old, _ in superseded_docs):
                archive_dir = "archive/superseded"
            elif "architecture" in doc_path.lower():
                archive_dir = "archive/old-architecture"
            else:
                archive_dir = "archive/stale"

            # Create archive directory
            archive_path = Path(archive_dir)
            archive_path.mkdir(parents=True, exist_ok=True)

            # Move file
            source = Path(doc_path)

            if not source.exists():
                print(f"  Skipped (not found): {doc_path}")
                continue

            # Preserve directory structure in archive
            relative_path = source.name
            destination = archive_path / relative_path

            if dry_run:
                print(f"  [DRY RUN] Would move: {source} → {destination}")
            else:
                shutil.move(str(source), str(destination))
                print(f"  Archived: {source} → {destination}")

            archived_count += 1

        except Exception as e:
            print(f"  Failed to archive {doc_path}: {e}")
            failed_count += 1

    print(f"\nArchival complete!")
    print(f"  Archived: {archived_count}")
    print(f"  Failed: {failed_count}")

    # Update git
    if not dry_run and archived_count > 0:
        print(f"\nGit commands to commit archival:")
        print(f"  git add archive/")
        print(f"  git commit -m 'chore: Archive {archived_count} stale/superseded documents'")
        print(f"  git push")

    await linker.driver.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually move files (default is dry-run)")
    args = parser.parse_args()

    print("Archive Stale Documents")
    print("=" * 60)

    if args.execute:
        print("MODE: EXECUTE (files will be moved)")
    else:
        print("MODE: DRY RUN (no files will be moved)")
        print("Use --execute to actually archive files")

    print("")

    asyncio.run(archive_stale_documents(dry_run=not args.execute))
