# NT-AI-Engine & Trinity Platform - Information Flow

**System Architecture:** Two separate but integrated platforms

---

## System Overview

### NT-AI-Engine (Multi-Tenant AI Platform)
**Location:** `C:\Users\jonat\Desktop\NT-AI-Engine`
**Purpose:** User-facing AI assistant for Microsoft 365
**Components:**
- Email Monitor (Microsoft Graph API)
- Calendar Monitor (Microsoft Graph API)
- Teams Monitor (Microsoft Graph API)
- Monday.com Task Integration
- User onboarding (OAuth flow)
- Tenant management

### Trinity Platform (Intelligence & Analytics)
**Location:** `C:\Users\jonat\Desktop\trinity-intelligence-platform`
**Purpose:** Event-driven intelligence, RCA, and knowledge graph
**Components:** 26 microservices (see below)

---

## Information Flow: NT-AI-Engine → Trinity → NT-AI-Engine

```
[NT-AI-ENGINE] User Action
    |
    +-> Email Monitor detects important email
    |   |-> EVENT: email.important_received
    |   |-> Payload: {tenant_id, from, subject, importance_score}
    |
    +-> Calendar Monitor detects meeting
    |   |-> EVENT: calendar.meeting_scheduled
    |   |-> Payload: {tenant_id, title, attendees, start_time}
    |
    +-> Teams Monitor detects mention
    |   |-> EVENT: teams.mention_received
    |   |-> Payload: {tenant_id, channel, user, message}
    |
    +-> Monday.com creates task
        |-> EVENT: task.created
        |-> Payload: {tenant_id, board_id, task_name, assignee}

                    | HTTP POST /webhook/ntai
                    v

[TRINITY] Event Collector (port 8001)
    |
    +-> Validates event schema
    +-> Publishes to NATS JetStream
        |
        +-> STREAM: events.ntai.email.*
        +-> STREAM: events.ntai.calendar.*
        +-> STREAM: events.ntai.teams.*
        +-> STREAM: events.ntai.tasks.*

                    | Multiple consumers
                    v

[TRINITY] Event Processing (3 parallel consumers)
    |
    +-> PostgreSQL Event Store
    |   |-> Writes to events table
    |   |-> Creates immutable audit trail
    |   |-> Enables event replay
    |
    +-> KG Projector
    |   |-> Consumes events from NATS
    |   |-> Projects to Neo4j Knowledge Graph
    |   |   |-> Creates nodes: Issue, Service, User, Task
    |   |   |-> Creates relationships: EXPERIENCES, DEPENDS_ON, ASSIGNED_TO
    |   |-> Builds relationships between entities
    |
    +-> Real-Time Processor
        |-> Detects patterns (e.g., 3 failures in 1 hour)
        |-> Triggers critical alerts
        |-> Calls Alert Manager

                    | Pattern detected
                    v

[TRINITY] Alert Manager (port 8013)
    |
    +-> Deduplication check (5-min window via Redis)
    +-> Severity classification
    +-> Notification routing
        |
        +-> Notification Service (port 8005)
            |
            +-> Email notification
            +-> Webhook to NT-AI-Engine
            +-> Slack alert (if configured)

                    | HTTP callback to NT-AI-Engine
                    v

[NT-AI-ENGINE] Receives Alert
    |
    +-> Creates Monday.com task
    |   |-> Title: "Email processing degraded - investigating"
    |   |-> Priority: High
    |   |-> Assignee: User
    |
    +-> Sends email notification
        |-> To: User
        |-> Subject: "Alert: System issue detected"
        |-> Body: Issue details + suggested actions

                    | User or system triggers RCA
                    v

[TRINITY] RCA API (port 8002)
    |
    +-> Receives query: "Why is email processing slow?"
    |
    +-> Vector Search (port 8004)
    |   |-> Generates query embedding (384-dim)
    |   |-> Searches 168 indexed documents
    |   |-> Returns top 5 similar issues (semantic)
    |
    +-> Neo4j Knowledge Graph Query
    |   |-> Cypher: MATCH (service:EmailService)-[:DEPENDS_ON*1..3]-(dep)
    |   |-> Returns affected services (graph traversal)
    |   |-> Finds historical issues on same services
    |
    +-> ML Training Service (port 8008) [Optional]
    |   |-> Predicts root cause from past patterns
    |   |-> Confidence score based on training data
    |
    +-> Response Generation
        |-> Similar issues: 3 found (85-92% similarity)
        |-> Affected services: [EmailService, DatabasePool, RedisCache]
        |-> Root cause: "Database connection pool exhausted"
        |-> Solutions: 2 found (90% success rate)
        |-> Estimated time: 30 minutes

                    | HTTP response to NT-AI-Engine
                    v

[NT-AI-ENGINE] Receives RCA Results
    |
    +-> Updates Monday.com task
    |   |-> Status: "In Progress"
    |   |-> Description: Adds root cause + solution steps
    |   |-> Estimated completion: 30 minutes
    |
    +-> Applies recommended solution
    |   |-> Scale database connection pool (auto-remediation)
    |   |-> Monitor for 5 minutes
    |
    +-> Validates resolution
        |-> If resolved: Updates task → Done
        |-> If not resolved: Escalates to human

                    | Resolution event
                    v

[TRINITY] Knowledge Graph Update
    |
    +-> KG Projector receives resolution event
    |
    +-> Updates Neo4j
        |-> Issue node: status = "resolved"
        |-> Creates Solution node
        |-> Creates relationship: Issue -[RESOLVED_BY]-> Solution
        |-> Updates success_rate on Solution
        |
    +-> Vector Search updates
        |-> Indexes resolution for future searches
        |
    +-> ML Training Service
        |-> Adds to training dataset
        |-> Improves future predictions

                    | Learning complete
                    v

[KNOWLEDGE GRAPH] Pattern Learned
    |
    +-> Future similar issues
        |-> Instant RCA match (95% similarity)
        |-> Recommended solution: "Scale DB connections"
        |-> Success rate: 95% (updated from actual results)
        |
    +-> Preventive insights
        |-> Alert if connection pool > 80% capacity
        |-> Proactive scaling before failure

```

---

## Current Data State

### Trinity Platform (Deployed)

**Neo4j Knowledge Graph:**
- Services: 236 nodes
- Commits: 102 nodes
- Issues: 7 nodes
- Solutions: 11 nodes
- Files: 3 nodes
- **Total:** 359 nodes, 12 relationships

**PostgreSQL Tables:**
- `events` - 1 row (git.commit.received)
- `audit_log` - 10 rows (API requests)
- `users` - 3 rows (trinity_test, testuser, e2e_test)
- `agent_tasks` - 0 rows (ready for AI execution)
- `workflows` - 0 rows
- `alerts` - 0 rows
- `health_checks` - Multiple rows (continuous monitoring)
- **Total:** 11 tables across services

**Vector Search:**
- Documents indexed: 168
- Model: all-MiniLM-L6-v2 (384 dimensions)
- Types: Issues (7), Solutions (11), Services (150)

**Redis:**
- Vector embedding cache
- Rate limit windows
- Session data
- Notification queues

### NT-AI-Engine (Separate Deployment)

**Database:** Separate PostgreSQL
**Integration:** Not yet connected to Trinity
**Status:** Operational independently

---

## Integration Points (Planned)

### NT-AI-Engine → Trinity

**Webhook Endpoint:**
```
POST https://trinity.example.com/webhook/ntai
Content-Type: application/json

{
  "event_type": "email.processing.slow",
  "tenant_id": "acme-corp",
  "timestamp": "2025-11-17T06:00:00Z",
  "data": {
    "service": "EmailMonitor",
    "error_rate": 0.15,
    "avg_latency_ms": 2500
  }
}

Response: {
  "event_id": "evt-12345",
  "queued": true,
  "processing": true
}
```

### Trinity → NT-AI-Engine

**RCA Callback:**
```
POST https://ntai.example.com/api/rca-results
Authorization: Bearer {jwt}
Content-Type: application/json

{
  "request_id": "rca-67890",
  "root_cause": "Database connection pool exhausted",
  "confidence": 0.92,
  "affected_services": ["EmailService", "DatabasePool"],
  "recommended_solutions": [
    {
      "solution_id": "sol-001",
      "title": "Scale database connections",
      "success_rate": 0.95,
      "estimated_time": "30 minutes"
    }
  ],
  "similar_issues": [
    {
      "issue_id": "iss-042",
      "title": "Email processing timeout",
      "similarity": 0.89,
      "resolution": "Scaled from 10 to 50 connections"
    }
  ]
}
```

**Monday.com Task Update (via Trinity):**
```
POST https://api.monday.com/v2
Authorization: Bearer {monday_token}

mutation {
  change_simple_column_value(
    item_id: 12345,
    board_id: 67890,
    column_id: "status",
    value: "Root cause identified: DB pool exhaustion"
  ) { id }
}
```

---

## Shared Knowledge Graph

**Unified View:** Both systems contribute to single knowledge graph

**NT-AI-Engine Contributions:**
- User behavior patterns
- Email/Calendar/Teams activity
- Task completion rates
- Integration usage metrics
- Tenant-specific patterns

**Trinity Contributions:**
- Code commit history (102 commits)
- Service dependencies (236 services)
- Issue patterns (7 issues, 11 solutions)
- Performance metrics
- RCA insights

**Relationship Types:**
- `DEPENDS_ON` - Service dependencies (4)
- `MODIFIES` - Code changes to services (3)
- `IMPLEMENTS` - Solutions implementing fixes (2)
- `HAD_ISSUE` - Services experiencing issues (1)
- `RESOLVED_BY` - Issues resolved by solutions (1)
- `FIXES` - Commits fixing issues (1)

---

## Example: Complete Flow (Email Processing Issue)

### Step 1: Detection (NT-AI-Engine)
```
EmailMonitor detects slow processing (avg 2.5s vs normal 200ms)
Triggers event: email.processing.slow
```

### Step 2: Event Ingestion (Trinity)
```
Event Collector receives webhook
Publishes to NATS: events.ntai.email.processing.slow
```

### Step 3: Parallel Processing (Trinity)
```
PostgreSQL: Stores event for audit
KG Projector: Creates Issue node, links to EmailService
Real-Time Processor: Detects 3rd occurrence in 1 hour → triggers alert
```

### Step 4: Alerting (Trinity → NT-AI-Engine)
```
Alert Manager: Checks deduplication (pass)
Notification Service: Sends webhook to NT-AI-Engine
```

### Step 5: User Notification (NT-AI-Engine)
```
Creates Monday.com task: "Email processing degraded"
Emails user: "System issue detected - investigating"
```

### Step 6: RCA Analysis (Trinity)
```
User or system calls RCA API
Vector Search: Finds similar issues (89% match: "Email processing timeout")
Neo4j: Traverses EmailService dependencies → finds DatabasePool
Returns: "Root cause: DB pool exhausted" (92% confidence)
```

### Step 7: Resolution Application (NT-AI-Engine)
```
Receives RCA results via webhook
Updates Monday.com task with root cause
Auto-applies solution: Scale DB pool from 10 to 50 connections
Monitors for 5 minutes
```

### Step 8: Validation & Learning (Trinity)
```
Resolution event received
Updates Issue node: status="resolved"
Creates Solution node with success_rate=0.95
Links: Issue -[RESOLVED_BY]-> Solution
Indexes solution for future searches
```

### Step 9: Future Benefit
```
Next similar issue: Instant RCA match
Recommendation: "Scale DB connections (95% success rate)"
Preventive: Alert when pool > 80% capacity
```

---

## Current Integration Status

**Trinity Platform:** OPERATIONAL (26/26 services)
- Ready to receive events
- RCA API functional
- Knowledge graph populated (359 nodes)
- Vector search operational (168 docs)

**NT-AI-Engine:** SEPARATE DEPLOYMENT
- Not yet integrated with Trinity
- Operates independently
- Ready for webhook integration

**Next Steps for Integration:**
1. Configure NT-AI-Engine webhook URL → Trinity Event Collector
2. Add Trinity RCA callback endpoint to NT-AI-Engine
3. Shared authentication (JWT tokens)
4. Unified monitoring dashboard
5. Cross-system knowledge graph enrichment

---

## Benefits of Integration

**For NT-AI-Engine:**
- Root cause analysis for all system issues
- Predictive intelligence from pattern learning
- Automated issue resolution
- Reduced MTTR (Mean Time To Resolution)

**For Trinity:**
- Real-world event data from NT-AI-Engine users
- User behavior patterns for ML training
- Production system telemetry
- Validation of RCA accuracy

**Combined Value:**
- Closed-loop learning system
- Automatic issue detection → RCA → resolution → validation
- Knowledge graph grows with every incident
- Success rates improve over time
- Cross-tenant pattern recognition
