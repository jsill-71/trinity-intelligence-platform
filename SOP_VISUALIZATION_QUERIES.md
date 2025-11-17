# SOP Visualization in Neo4j - Your Dream Realized

**Access:** http://localhost:7474 (neo4j / trinity123)

---

## Visual SOP Queries

### 1. ALL SOPs with Steps (Complete Workflow Visualization)
```cypher
MATCH (sop:SOP)-[r:HAS_STEP]->(step:SOPStep)
RETURN sop, r, step
```
**Shows:** 5 SOP nodes connected to all their steps (visual workflow)

### 2. SOP Dependency Chain (Prerequisites)
```cypher
MATCH path = (sop:SOP)-[:REQUIRES*]->(prereq:SOP)
RETURN path
```
**Shows:** Which SOPs must complete before others (Deployment → Rollback)

### 3. SOP Step Flow (Sequential Steps)
```cypher
MATCH (sop:SOP {name: 'Deployment'})-[:HAS_STEP]->(step)
MATCH path = (step)-[:NEXT_STEP*0..]->(next)
RETURN path
```
**Shows:** Step-by-step flow for Deployment SOP (visual timeline)

### 4. SOPs Applied to Services
```cypher
MATCH path = (sop:SOP)-[:APPLIES_TO]->(s:Service)
RETURN path
```
**Shows:** Which SOPs affect which services (operational impact map)

### 5. Complete SOP Ecosystem
```cypher
MATCH (sop:SOP)
MATCH (sop)-[r]-(connected)
RETURN sop, r, connected
```
**Shows:** Complete SOP network (steps, prerequisites, services)

### 6. User Onboarding Flow (Full Journey)
```cypher
MATCH (sop:SOP {name: 'User Onboarding'})-[:HAS_STEP]->(step)
MATCH (sop)-[:APPLIES_TO]->(service)
RETURN sop, step, service
```
**Shows:** Onboarding steps + affected services in one view

### 7. Incident Response Workflow
```cypher
MATCH (sop:SOP {name: 'Incident Response'})-[:HAS_STEP]->(step:SOPStep)
WITH sop, step
ORDER BY step.order
RETURN sop, step
```
**Shows:** Incident response steps in order

### 8. SOPs by Category
```cypher
MATCH (sop:SOP)
RETURN sop.category as category, collect(sop.name) as procedures
```
**Table view:** Operations, DevOps, Database categories

### 9. Critical Path (Deployment + Rollback)
```cypher
MATCH (deploy:SOP {name: 'Deployment'})
MATCH (rollback:SOP)-[:REQUIRES]->(deploy)
MATCH (deploy)-[:HAS_STEP]->(deploy_step)
MATCH (rollback)-[:HAS_STEP]->(rollback_step)
RETURN deploy, rollback, deploy_step, rollback_step
```
**Shows:** Deployment + Rollback workflows together

### 10. SOP Service Impact
```cypher
MATCH (sop:SOP)-[:APPLIES_TO]->(s:Service)-[:HAD_ISSUE]->(i:Issue)
RETURN sop, s, i
```
**Shows:** Which SOPs affect services with known issues

---

## Current SOPs in Graph

1. **User Onboarding** (6 steps)
   - Create account → Send invite → OAuth → Scrape → Build KG → Validate

2. **Deployment** (10 steps)
   - Validate → Build → Push → Migrate → Deploy → Test → Monitor → Cutover

3. **Rollback** (5 steps)
   - Identify level → Container rollback → DB rollback → Full rollback → Validate

4. **Schema Migration** (6 steps)
   - Design → Test → Review → Stage → Validate → Production

5. **Incident Response** (6 steps)
   - Detect → Triage → Mitigate → Communicate → Resolve → Post-mortem

**Total:** 33 steps across 5 SOPs, all visually connected

---

## Visual Styling

**Node Colors (customize in Neo4j Browser):**
- SOP: Purple
- SOPStep: Light blue
- Service: Green
- Issue: Red

**Relationship Labels:**
- HAS_STEP: SOP → Steps
- NEXT_STEP: Step → Next Step
- REQUIRES: SOP → Prerequisite SOP
- APPLIES_TO: SOP → Service

---

## Example: See Deployment Workflow

```cypher
MATCH (sop:SOP {name: 'Deployment'})
MATCH path1 = (sop)-[:HAS_STEP]->(step)
MATCH path2 = (step)-[:NEXT_STEP]->(next)
RETURN path1, path2
```

**Result:** Complete deployment workflow as visual flowchart

---

**Your dream: REALIZED. SOPs are now visual workflows in Neo4j.**
