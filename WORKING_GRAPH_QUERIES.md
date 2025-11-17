# Working Visual Queries - Based on Actual Graph Data

**Neo4j Browser:** http://localhost:7474 (neo4j / trinity123)

**IMPORTANT:** Click "Graph" tab after running query (not "Table")

---

## Queries That ACTUALLY WORK

### 1. Document → Service Links (GUARANTEED TO WORK)
```cypher
MATCH (d:Document)-[:DOCUMENTS]->(s:Service)
RETURN d, s
LIMIT 30
```
**Shows:** 30 document nodes visually connected to services they document

### 2. Services with Issues
```cypher
MATCH (s:Service)-[:HAD_ISSUE]->(i:Issue)
RETURN s, i
```
**Shows:** Which services have which issues (visual network)

### 3. Services Dependencies
```cypher
MATCH (s1:Service)-[:DEPENDS_ON]->(s2:Service)
RETURN s1, s2
LIMIT 20
```
**Shows:** Service dependency chain

### 4. Email Monitor Ecosystem
```cypher
MATCH (s:Service)
WHERE s.name = 'email_monitor'
MATCH (s)-[r]-(connected)
RETURN s, r, connected
```
**Shows:** Everything connected to email_monitor

### 5. All Document Categories (Visual)
```cypher
MATCH (d:Document)
RETURN d
LIMIT 100
```
**Shows:** 100 document nodes (color by category in settings)

### 6. Documents About Specific Service
```cypher
MATCH path = (d:Document)-[:DOCUMENTS]->(s:Service {name: 'email_monitor'})
RETURN path
```
**Shows:** All docs explaining email_monitor

### 7. Full System Overview
```cypher
MATCH (n)
WHERE labels(n)[0] IN ['Document', 'Service', 'Issue', 'Solution']
RETURN n
LIMIT 200
```
**Shows:** Mix of all node types (documents, services, issues, solutions)

### 8. Documents + Services + Issues (3 levels)
```cypher
MATCH (d:Document)-[:DOCUMENTS]->(s:Service)
MATCH (s)-[:HAD_ISSUE]->(i:Issue)
RETURN d, s, i
LIMIT 20
```
**Shows:** Documents → Services → Issues chain

---

## Current Graph Statistics

**Run this to see what's actually in the graph:**
```cypher
MATCH (n)
RETURN labels(n)[0] as type, count(*) as count
ORDER BY count DESC
```

**Current counts:**
- Document: 1,596
- Service: 247
- Commit: 102
- Issue: 34
- Solution: 11

**Actual relationships that exist:**
- DOCUMENTS (Document → Service)
- HAD_ISSUE (Service → Issue)
- DEPENDS_ON (Service → Service)
- MODIFIES (Commit → File)
- RESOLVED_BY (Issue → Solution) - if any exist
- IMPLEMENTS
- FIXES

---

## Visual Styling

**Make it look better:**
1. Click node type (e.g., "Document")
2. Choose color (blue for Document, green for Service, red for Issue)
3. Adjust size
4. Enable relationship labels (Settings → Show relationship type)

---

**Start with Query #1 - it's guaranteed to show visual document-service connections.**
