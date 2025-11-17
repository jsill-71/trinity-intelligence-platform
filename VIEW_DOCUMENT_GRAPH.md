# VIEW DOCUMENT DEPENDENCY GRAPH RIGHT NOW

**1. Open:** http://localhost:7474
**2. Login:** neo4j / trinity123
**3. Paste this query:**

```cypher
MATCH path = (d:Document)-[:DOCUMENTS]->(s:Service)-[:HAD_ISSUE]->(i:Issue)
RETURN path
LIMIT 50
```

**4. Click:** "Graph" tab (not Table)
**5. See:** Visual network of Documents → Services → Issues

---

## What You'll See

**Nodes (colored):**
- Blue circles: Documents (1,596)
- Green circles: Services (247)
- Red circles: Issues (34)

**Arrows:**
- Document →DOCUMENTS→ Service
- Service →HAD_ISSUE→ Issue

**Click any node** to see properties (file path, service name, issue details)

---

**Current graph has 1,596 documents indexed and linked to 247 services.**

Try the queries in NEO4J_VISUAL_QUERIES.md for different views.
