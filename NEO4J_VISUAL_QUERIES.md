# Document Dependency Graph - VISUAL Queries for Neo4j Browser

**Access:** http://localhost:7474
**Credentials:** neo4j / trinity123

**Important:** These queries return GRAPHS (visual), not tables. Click the graph tab in Neo4j Browser.

---

## Core Visual Queries

### 1. COMPLETE DOCUMENT DEPENDENCY WEB
```cypher
MATCH path = (d:Document)-[:DOCUMENTS|DESCRIBES*1..2]-(entity)
RETURN path
LIMIT 100
```
**Shows:** Documents connected to Services/Issues in visual network

### 2. BACKWARD DEPENDENCY MAPS → SERVICES
```cypher
MATCH (d:Document)
WHERE d.path CONTAINS 'BACKWARD'
MATCH (s:Service)
WHERE toLower(s.name) IN ['event-collector', 'kg-projector', 'rca-api', 'email_monitor', 'task_creator']
MATCH path = (d)-[:DOCUMENTS]->(s)
RETURN path
```
**Shows:** Which backward dependency docs analyze which services

### 3. SERVICE DEPENDENCY CHAIN WITH DOCS
```cypher
MATCH path1 = (d:Document)-[:DOCUMENTS]->(s1:Service)
MATCH path2 = (s1)-[:DEPENDS_ON]->(s2:Service)
RETURN path1, path2
LIMIT 50
```
**Shows:** Docs → Services → Dependencies (3-level visual)

### 4. ISSUE RESOLUTION NETWORK WITH DOCS
```cypher
MATCH path1 = (d:Document)-[:DESCRIBES]->(i:Issue)
MATCH path2 = (s:Service)-[:HAD_ISSUE]->(i)
OPTIONAL MATCH path3 = (i)-[:RESOLVED_BY]->(sol:Solution)
RETURN path1, path2, path3
```
**Shows:** Complete issue ecosystem with documentation

### 5. DOCUMENT CATEGORIES (Visual Distribution)
```cypher
MATCH (d:Document)
WITH d.category as category, collect(d)[0..10] as docs
UNWIND docs as doc
RETURN doc
```
**Shows:** Sample documents from each category as graph nodes

### 6. STALE DOCS CONNECTED TO ACTIVE SERVICES
```cypher
MATCH (d:Document)
WHERE d.last_modified < datetime() - duration({days: 90})
MATCH path = (d)-[:DOCUMENTS]->(s:Service)-[:HAD_ISSUE]->(i:Issue)
WHERE i.status = 'open'
RETURN path
```
**Shows:** OLD docs about services with CURRENT issues (problem!)

### 7. CURRENT ARCHITECTURE DOC NETWORK
```cypher
MATCH (d:Document)
WHERE d.category = 'architecture' AND NOT (d)-[:SUPERSEDED_BY]->()
MATCH path = (d)-[:DOCUMENTS]->(s:Service)
RETURN path
LIMIT 30
```
**Shows:** Current (not superseded) architecture docs and what they describe

### 8. SUPERSEDED DOCUMENT CHAINS (Visual Timeline)
```cypher
MATCH path = (old:Document)-[:SUPERSEDED_BY*1..5]->(current:Document)
WHERE NOT (current)-[:SUPERSEDED_BY]->()
RETURN path
```
**Shows:** Document evolution chains (old → newer → newest)

### 9. SERVICES WITHOUT DOCUMENTATION
```cypher
MATCH (s:Service)
WHERE NOT (s)<-[:DOCUMENTS]-(:Document)
RETURN s
LIMIT 20
```
**Shows:** Services that have NO documentation (gaps!)

### 10. COMPLETE SYSTEM OVERVIEW
```cypher
MATCH (d:Document)
WITH d
LIMIT 50
MATCH (d)-[r]-(connected)
RETURN d, r, connected
```
**Shows:** Sample of documents with all their connections

---

## Specific Use Cases

### "What docs explain email_monitor?"
```cypher
MATCH (s:Service)
WHERE s.name CONTAINS 'email'
MATCH path = (d:Document)-[:DOCUMENTS]->(s)
RETURN path
```

### "Show me the backward dependency analysis network"
```cypher
MATCH (d:Document)
WHERE d.path CONTAINS 'BACKWARD_DEPENDENCY'
MATCH (d)-[r:DOCUMENTS]->(s:Service)
MATCH (s)-[r2:HAD_ISSUE|DEPENDS_ON]-(related)
RETURN d, r, s, r2, related
LIMIT 50
```

### "Which services does TRINITY_COMPLETE_DEPENDENCY_MAP document?"
```cypher
MATCH (d:Document)
WHERE d.path CONTAINS 'TRINITY_COMPLETE_DEPENDENCY_MAP'
MATCH path = (d)-[:DOCUMENTS]->(s:Service)
RETURN path
```

### "Show document→service→issue→solution full chain"
```cypher
MATCH path = (d:Document)-[:DOCUMENTS]->(s:Service)-[:HAD_ISSUE]->(i:Issue)-[:RESOLVED_BY]->(sol:Solution)
RETURN path
LIMIT 20
```

---

## Visual Styling Tips

**In Neo4j Browser:**
1. Click the ⚙️ icon
2. Customize node colors:
   - Document: Blue
   - Service: Green
   - Issue: Red
   - Solution: Yellow
3. Adjust node size by property (e.g., document size)
4. Enable relationship labels

**Better Visualization:**
- Use graph view (not table)
- Expand nodes by double-clicking
- Right-click → "Expand" to see more connections
- Use Ctrl+drag to arrange layout

---

## Current Graph Stats

**Run to see distribution:**
```cypher
MATCH (d:Document)
RETURN d.category as category, count(*) as count
ORDER BY count DESC
```

**Relationships:**
```cypher
MATCH ()-[r]->()
RETURN type(r) as relationship, count(*) as count
ORDER BY count DESC
```

---

## Fix for Missing Relationships

If documents don't show connections:

```cypher
// Manually link BACKWARD_DEPENDENCY_MAP to analyzed services
MATCH (d:Document {path: 'BACKWARD_DEPENDENCY_MAP.md'})
MATCH (s:Service) WHERE s.name IN ['rca-api', 'vector-search', 'user-management', 'data-aggregator']
MERGE (d)-[:DOCUMENTS]->(s)
```

---

**The graph is populated with 1,596 documents. Visualize it NOW in Neo4j Browser!**
