# Reindex Documents with Improved UX

**Current Problem:** Document nodes show "NT_AI_E..." (unusable)

**Solution:** Reindex with improved linker

**Steps:**

1. **Backup current graph:**
```bash
# Export current graph
docker-compose -f docker-compose-working.yml exec neo4j cypher-shell -u neo4j -p trinity123 < export_backup.cypher
```

2. **Clear old Document nodes:**
```cypher
MATCH (d:Document)
DELETE d
```

3. **Reindex with improved linker:**
```bash
cd /c/Users/jonat/Desktop/trinity-intelligence-platform

python -c "
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, 'services/document-kg')
from document_linker_improved import ImprovedDocumentLinker

async def reindex():
    linker = ImprovedDocumentLinker()
    await linker.init_schema()
    
    count = 0
    for doc in Path('.').rglob('*.md'):
        if 'node_modules' not in str(doc) and '.git' not in str(doc):
            try:
                with open(doc, 'r', encoding='utf-8') as f:
                    await linker.index_document(str(doc), f.read())
                    count += 1
                    if count % 50 == 0:
                        print(f'Indexed {count}...')
            except:
                pass
    
    print(f'Complete: {count} documents')
    await linker.driver.close()

asyncio.run(reindex())
"
```

4. **Verify improvement:**
```cypher
MATCH (d:Document)
RETURN d.title, d.description, d.importance
LIMIT 10
```

**Expected:** Readable titles, descriptions, importance levels

**Time:** 10 minutes to reindex ~1,600 documents

**After reindexing, graph will show:**
- "Mission Complete Report" (not "NT_AI_E...")
- "Deployment SOP for Azure" (not truncated path)
- Relationship: "EXPLAINS_DEPLOYMENT_OF" (not generic "DOCUMENTS")
