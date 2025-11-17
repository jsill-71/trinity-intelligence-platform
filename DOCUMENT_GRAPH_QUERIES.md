# Document Dependency Graph - Visualization Queries

**Access:** http://localhost:7474
**Credentials:** neo4j / trinity123

---

## Quick Start: View Document Graph

### 1. See All Documents
```cypher
MATCH (d:Document)
RETURN d
LIMIT 50
```

### 2. Documents Linked to Services
```cypher
MATCH (d:Document)-[:DOCUMENTS]->(s:Service)
RETURN d, s
LIMIT 30
```

### 3. Documents Describing Issues
```cypher
MATCH (d:Document)-[:DESCRIBES]->(i:Issue)
RETURN d, i
```

### 4. Current Architecture Documents
```cypher
MATCH (d:Document)
WHERE d.category = 'architecture'
  AND NOT (d)-[:SUPERSEDED_BY]->()
RETURN d.path, d.last_modified
ORDER BY d.last_modified DESC
```

### 5. Superseded Document Chain
```cypher
MATCH path = (old:Document)-[:SUPERSEDED_BY*]->(current:Document)
WHERE NOT (current)-[:SUPERSEDED_BY]->()
RETURN path
```

### 6. Stale Documents (>90 days)
```cypher
MATCH (d:Document)
WHERE d.last_modified < datetime() - duration({days: 90})
RETURN d.path, d.category, d.last_modified
ORDER BY d.last_modified ASC
```

### 7. Find All Docs About a Service
```cypher
MATCH (d:Document)-[:DOCUMENTS]->(s:Service {name: 'email_monitor'})
RETURN d.path, d.category, d.last_modified
```

### 8. Document by Category
```cypher
MATCH (d:Document)
WHERE d.category = 'deployment'
RETURN d.path, d.last_modified
ORDER BY d.last_modified DESC
```

---

## Initialize Document Graph

**Run this first to index documentation:**

```bash
cd /c/Users/jonat/Desktop/trinity-intelligence-platform
python services/document-kg/document_linker.py
```

Or manually index a document:

```python
from services.document_kg.document_linker import DocumentLinker
import asyncio

async def index_docs():
    linker = DocumentLinker()
    await linker.init_schema()
    
    # Index all markdown docs
    for doc in Path("docs/").rglob("*.md"):
        with open(doc, 'r') as f:
            await linker.index_document(str(doc), f.read())
    
    print("Documentation indexed!")

asyncio.run(index_docs())
```

---

## Current Document Graph Location

**Local Neo4j:** http://localhost:7474
- Already has 359 nodes (Services, Commits, Issues, Solutions)
- Document nodes will be added when you run document_linker.py
- All in same graph - can query relationships between docs and code

**What's Currently Indexed:**
```cypher
MATCH (n)
RETURN labels(n)[0] as type, count(*) as count
ORDER BY count DESC
```

Current result:
- Service: 236
- Commit: 102
- Solution: 11
- Issue: 7
- File: 3
- Document: 0 (not yet indexed - run document_linker.py to populate)

---

## Visualize Full System

**Complete dependency graph (docs + code + issues):**

```cypher
MATCH (d:Document)-[r1]->(entity)
OPTIONAL MATCH (entity)-[r2]-(related)
RETURN d, r1, entity, r2, related
LIMIT 100
```

This shows:
- Documents → What they document (Service, Issue)
- Services → Their issues
- Issues → Their solutions
- Complete dependency web

---

## Export Options

**1. GraphML Export (for Gephi/yEd):**
```cypher
CALL apoc.export.graphml.all("document-graph.graphml", {})
```

**2. JSON Export:**
```cypher
CALL apoc.export.json.all("document-graph.json", {})
```

**3. CSV Export:**
```cypher
MATCH (d:Document)-[:DOCUMENTS]->(s:Service)
RETURN d.path as document, s.name as service, d.category as category
```

---

## Integration with Backward Dependency Maps

**The backward dependency analysis documents are themselves indexed:**

```cypher
// Find all backward dependency docs
MATCH (d:Document)
WHERE d.path CONTAINS 'BACKWARD_DEPENDENCY'
RETURN d.path, d.category
```

**Link dependency docs to services they analyze:**

```cypher
// Example: BACKWARD_DEPENDENCY_MAP.md documents RCA API
MATCH (d:Document {path: 'BACKWARD_DEPENDENCY_MAP.md'})
MATCH (s:Service {name: 'rca-api'})
MERGE (d)-[:DOCUMENTS]->(s)
```

---

## Current State (Before Indexing)

**Documents exist in filesystem:**
- NT-AI-Engine: 3,034 documents
- Trinity Platform: 100+ analysis documents
- Total: 3,134+ documents

**Not yet in graph:** Need to run document_linker.py to index

**After indexing:**
- All 3,134+ documents as Document nodes
- Links to 236 Services
- Links to 7 Issues  
- Links to 102 Commits
- Superseded relationships tracked
- Stale detection automated

---

**To populate the graph now:**

```bash
cd /c/Users/jonat/Desktop/trinity-intelligence-platform
python services/document-kg/document_linker.py

# Or run full indexing
python scripts/index_all_documentation.py
```

Then refresh Neo4j Browser and run the queries above.
