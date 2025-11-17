# Master System Visualization - Complete NT-AI-Engine ↔ Trinity Platform

**Your Comprehensive Knowledge Graph**

**Access:** http://localhost:7474 (neo4j / trinity123)

---

## THE ULTIMATE QUERY - Everything Connected

**Paste this in Neo4j Browser:**

```cypher
MATCH (n)
WHERE labels(n)[0] IN ['Document', 'Service', 'Issue', 'Solution', 'SOP', 'SOPStep', 'Tenant', 'EmailEvent', 'Task']
WITH n LIMIT 500
MATCH (n)-[r]-(connected)
WHERE labels(connected)[0] IN ['Document', 'Service', 'Issue', 'Solution', 'SOP', 'SOPStep']
RETURN n, r, connected
```

**Click "Graph" tab - You'll see:**
- 🔵 Documents (1,596) - What explains the system
- 🟢 Services (247) - What runs the system
- 🔴 Issues (34) - What problems exist
- 🟡 Solutions (11) - How problems were solved
- 🟣 SOPs (5) - How to operate the system
- 🔷 SOP Steps (33) - Step-by-step procedures
- 🟠 Tenants (1) - NT-AI users
- All interconnected!

**Double-click any node** to see properties and expand connections

---

## Focused Views for Deep Understanding

### 1. How NT-AI-Engine Works (Email → Task → Monday.com)
```cypher
MATCH (sop:SOP {name: 'User Onboarding'})
MATCH (sop)-[:APPLIES_TO]->(s:Service)
MATCH (d:Document)-[:DOCUMENTS]->(s)
MATCH (s)-[:HAD_ISSUE]->(i:Issue)
OPTIONAL MATCH (i)-[:RESOLVED_BY]->(sol:Solution)
RETURN sop, s, d, i, sol
```

**Shows:** Onboarding SOP → Services involved → Documentation → Known issues → Solutions

### 2. How Trinity Platform Works (Event → KG → RCA)
```cypher
MATCH (s1:Service {name: 'event-collector'})
MATCH (s2:Service {name: 'kg-projector'})
MATCH (s3:Service {name: 'rca-api'})
MATCH path1 = (s1)-[:DEPENDS_ON|PUBLISHES_TO*0..1]-(s2)
MATCH path2 = (s2)-[:DEPENDS_ON|PROJECTS_TO*0..1]-(s3)
OPTIONAL MATCH (d:Document)-[:DOCUMENTS]->(s1)
OPTIONAL MATCH (d2:Document)-[:DOCUMENTS]->(s2)
OPTIONAL MATCH (d3:Document)-[:DOCUMENTS]->(s3)
RETURN s1, s2, s3, d, d2, d3, path1, path2
```

**Shows:** Trinity's data flow pipeline + documentation for each service

### 3. NT-AI ↔ Trinity Integration
```cypher
// Webhook flow
MATCH (t:Tenant)-[:REPORTED_ISSUE]->(i:Issue)
MATCH (s:Service)-[:HAD_ISSUE]->(i)
MATCH (d:Document)-[:DESCRIBES]->(i)
OPTIONAL MATCH (i)-[:RESOLVED_BY]->(sol:Solution)
RETURN t, i, s, d, sol
```

**Shows:** NT-AI tenant → Issues → Affected services → Documentation → Solutions

### 4. Complete Deployment Workflow
```cypher
MATCH (sop:SOP {name: 'Deployment'})-[:HAS_STEP]->(step)
MATCH (sop)-[:APPLIES_TO]->(service)
MATCH (d:Document)-[:DOCUMENTS]->(service)
WITH sop, step, service, d
ORDER BY step.order
RETURN sop, step, service, d
```

**Shows:** Deployment SOP steps → Services deployed → Documentation

### 5. Issue Resolution Knowledge
```cypher
MATCH (i:Issue)<-[:HAD_ISSUE]-(s:Service)
MATCH (i)-[:RESOLVED_BY]->(sol:Solution)
MATCH (d:Document)-[:DESCRIBES]->(i)
RETURN i, s, sol, d
```

**Shows:** Issues → Services affected → Solutions applied → Documentation

### 6. Services with SOPs and Docs
```cypher
MATCH (s:Service)
WHERE s.name IN ['email_monitor.py', 'event-collector', 'rca-api', 'kg-projector']
OPTIONAL MATCH (sop:SOP)-[:APPLIES_TO]->(s)
OPTIONAL MATCH (d:Document)-[:DOCUMENTS]->(s)
OPTIONAL MATCH (s)-[:HAD_ISSUE]->(i:Issue)
RETURN s, sop, d, i
```

**Shows:** Key services → Their SOPs → Their docs → Their issues

---

## Graph Statistics (Complete System)

**Total Nodes:** 1,994
- 1,596 Documents
- 247 Services
- 102 Commits
- 38 SOPs + Steps
- 34 Issues
- 11 Solutions
- 3 Files
- 1 Tenant

**Total Relationships:** 1,110+
- 866 Document→Service (DOCUMENTS)
- 155 Document→Issue (DESCRIBES)
- 33 SOP→Step (HAS_STEP)
- 28 Step→Step (NEXT_STEP)
- 13 SOP→Service (APPLIES_TO)
- 4 Service→Service (DEPENDS_ON)
- 3 Commit→File (MODIFIES)
- 2 Tenant→Issue (REPORTED_ISSUE)
- 1 Service→Issue (HAD_ISSUE)
- 1 Issue→Solution (RESOLVED_BY)
- 1 SOP→SOP (REQUIRES)

---

## Navigation Tips

**Start Broad, Drill Deep:**

1. **Start:** Run Query #1 (Ultimate Query) - see everything
2. **Click:** Any node to see properties
3. **Expand:** Double-click node to see more connections
4. **Filter:** Click node type to hide/show (e.g., hide Documents to see just services)
5. **Search:** Use Ctrl+F to find specific nodes
6. **Paths:** Click two nodes, then "Find Path" to see how they connect

**Example Drill-down:**
1. See all SOPs (purple nodes)
2. Click "Deployment" SOP
3. Expand to see 10 steps
4. Click "Deploy Container Apps" step
5. See which services it deploys
6. Click "event-collector" service
7. See documentation about it
8. See issues it had
9. See solutions applied

**You can navigate the entire system through the graph!**

---

## Color Scheme (Set in Neo4j Browser)

**Click node type, choose color:**
- Document: Blue (#2196F3)
- Service: Green (#4CAF50)
- Issue: Red (#F44336)
- Solution: Yellow (#FFEB3B)
- SOP: Purple (#9C27B0)
- SOPStep: Light Blue (#03A9F4)
- Tenant: Orange (#FF9800)
- Commit: Gray (#9E9E9E)

---

## Current Graph Contents

**NT-AI-Engine Components:**
- Services: email_monitor.py, task_creator.py, database_manager.py, monday_client.py, knowledge_graph.py
- Tenant: acme-corp (from integration test)
- Issues: 34 total
- Documents: 1,400+ NT-AI docs
- SOPs: User Onboarding applies to NT-AI services

**Trinity Platform Components:**
- Services: event-collector, kg-projector, rca-api, investigation-api, vector-search, api-gateway
- Documents: 196 Trinity docs
- SOPs: Deployment, Rollback, Schema Migration, Incident Response
- Integration: Tenant→Issue→Service connections

**Integration Points Visible:**
- NT-AI webhook → Trinity event-collector (documented)
- Trinity RCA → NT-AI callback (service links)
- Shared knowledge graph (issues from both systems)

---

## Understanding How Systems Work Together

**Query to see complete integration:**

```cypher
// NT-AI services
MATCH (ntai:Service)
WHERE ntai.name IN ['email_monitor.py', 'task_creator.py']

// Trinity services
MATCH (trinity:Service)
WHERE trinity.name IN ['event-collector', 'kg-projector', 'rca-api']

// Integration documentation
MATCH (d:Document)
WHERE d.path CONTAINS 'INTEGRATION' OR d.path CONTAINS 'INFORMATION_FLOW'

// Connect them
OPTIONAL MATCH (d)-[:DOCUMENTS]->(ntai)
OPTIONAL MATCH (d)-[:DOCUMENTS]->(trinity)

RETURN ntai, trinity, d
```

**Shows:** Both systems + integration documentation in one view

---

**Your dream is realized: Complete visual system understanding in Neo4j Browser**

**Start exploring:** http://localhost:7474
