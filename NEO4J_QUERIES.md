# Neo4j Knowledge Graph - Visualization Queries

**Access:** http://localhost:7474
**Credentials:** `neo4j` / `trinity123`

---

## Quick Visualizations

### 1. Complete Knowledge Graph Overview
```cypher
MATCH (n)
RETURN n
LIMIT 100
```
Shows 100 nodes with all relationships.

### 2. Service Dependencies
```cypher
MATCH p=(s:Service)-[:DEPENDS_ON]->(dep:Service)
RETURN p
LIMIT 50
```
Visualizes which services depend on others.

### 3. Issue Resolution Flow
```cypher
MATCH p=(i:Issue)-[:RESOLVED_BY]->(sol:Solution)
RETURN p
```
Shows issues and their solutions.

### 4. Service Issues
```cypher
MATCH p=(s:Service)-[:HAD_ISSUE]->(i:Issue)
RETURN p
```
Shows which services had which issues.

### 5. Email Monitor Dependencies
```cypher
MATCH p=(s:Service {name: 'email_monitor.py'})-[:DEPENDS_ON*1..3]-(related)
RETURN p
```
Shows email_monitor.py and all dependencies (1-3 hops).

### 6. All Relationships by Type
```cypher
MATCH ()-[r]->()
RETURN type(r) as relationship, count(*) as count
ORDER BY count DESC
```
Counts relationships by type.

### 7. Node Statistics
```cypher
MATCH (n)
RETURN labels(n)[0] as type, count(*) as count
ORDER BY count DESC
```
Shows node counts by type:
- Services: 236
- Commits: 102
- Solutions: 11
- Issues: 7
- Files: 3

### 8. Find Critical Issues
```cypher
MATCH (i:Issue)
WHERE i.severity IN ['critical', 'high']
RETURN i.id, i.title, i.severity, i.status
ORDER BY i.severity
```

### 9. Most Connected Services
```cypher
MATCH (s:Service)
OPTIONAL MATCH (s)-[r]-()
RETURN s.name, count(r) as connection_count
ORDER BY connection_count DESC
LIMIT 10
```
Shows services with most relationships.

### 10. Solution Success Rates
```cypher
MATCH (sol:Solution)
RETURN sol.id, sol.title, sol.success_rate, sol.category
ORDER BY sol.success_rate DESC
```

---

## Information Flow Visualization

### NT-AI-Engine Event Flow
```cypher
// Create example event flow (run this to see structure)
MATCH (email:Service {name: 'email_monitor.py'})
MATCH (auth:Service {name: 'auth_service.py'})
MATCH (task:Service {name: 'task_creator.py'})
MATCH p=((email)-[:DEPENDS_ON]->(auth)),
      ((task)-[:DEPENDS_ON]->(email))
RETURN p
```

### Full System Architecture
```cypher
MATCH (n)
WHERE labels(n)[0] IN ['Service', 'Issue', 'Solution']
OPTIONAL MATCH (n)-[r]-(related)
RETURN n, r, related
LIMIT 200
```

---

## Advanced Queries

### Find Root Cause Paths
```cypher
MATCH path = (i:Issue)-[:CAUSED_BY*1..3]->(root)
RETURN path
```

### Service Impact Analysis
```cypher
MATCH (s:Service {name: $serviceName})
MATCH path = (s)-[:DEPENDS_ON|USED_BY*1..2]-(impacted)
RETURN path
```
**Usage:** Set parameter `serviceName` = "email_monitor.py"

### Temporal Analysis (Commits over time)
```cypher
MATCH (c:Commit)
WHERE c.timestamp IS NOT NULL
RETURN c.timestamp, c.message
ORDER BY c.timestamp DESC
LIMIT 20
```

### Cross-System Integration Points
```cypher
// Shows services that interface between systems
MATCH (s:Service)
WHERE s.name CONTAINS 'integration' OR s.name CONTAINS 'webhook'
RETURN s
```

---

## Useful Filters

### By Technology Stack
```cypher
MATCH (s:Service)
WHERE s.technology CONTAINS 'Python'
RETURN s.name, s.technology
LIMIT 20
```

### By Status
```cypher
MATCH (i:Issue)
WHERE i.status = 'resolved'
RETURN i.id, i.title, i.severity
```

### By Severity
```cypher
MATCH (i:Issue)
WHERE i.severity = 'critical'
RETURN i.id, i.title, i.category
```

---

## Maintenance Queries

### Count All Nodes
```cypher
MATCH (n)
RETURN count(n) as total_nodes
```
**Current:** 359 nodes

### Count All Relationships
```cypher
MATCH ()-[r]->()
RETURN count(r) as total_relationships
```
**Current:** 12 relationships

### Database Info
```cypher
CALL db.stats.retrieve('GRAPH COUNTS')
YIELD data
RETURN data
```

---

## Export Data

### Export to JSON (via HTTP API)
```bash
curl -u neo4j:trinity123 \
  -H "Content-Type: application/json" \
  -X POST http://localhost:7474/db/neo4j/tx/commit \
  -d '{
    "statements": [{
      "statement": "MATCH (n) RETURN n LIMIT 10"
    }]
  }'
```

---

## Tips

1. **Click nodes** to see properties
2. **Double-click nodes** to expand relationships
3. **Use visualization settings** to customize node colors by label
4. **Save queries** for frequently used visualizations
5. **Export to PNG** via browser screenshot tool

**Most useful for NT-AI-Engine/Trinity integration:**
- Query #5 (email_monitor dependencies)
- Query #2 (service dependencies)
- Query #10 (full system architecture)
