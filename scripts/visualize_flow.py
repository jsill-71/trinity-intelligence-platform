#!/usr/bin/env python3
"""
Visualize information flow between NT-AI-Engine and Trinity Platform
Shows how data flows through both systems
"""

print("""
================================================================================
NT-AI-ENGINE & TRINITY INTELLIGENCE PLATFORM - INFORMATION FLOW
================================================================================

SYSTEM ARCHITECTURE:
├─ NT-AI-Engine (Multi-tenant AI Platform)
│  ├─ Microsoft Graph Integration → Email/Calendar/Teams monitoring
│  ├─ Monday.com Integration → Task management
│  ├─ User onboarding → OAuth flow
│  └─ Event generation → Sends to Trinity Platform
│
└─ Trinity Intelligence Platform (Event-Driven Intelligence)
   ├─ Event ingestion → Processes NT-AI-Engine events
   ├─ Knowledge graph → Builds relationships
   ├─ RCA analysis → Root cause detection
   └─ Insights → Feeds back to NT-AI-Engine

================================================================================
INFORMATION FLOW PATH:
================================================================================

[NT-AI-ENGINE] User Action
    │
    ├─→ Email Monitor detects important email
    │   └─→ EVENT: email.important_received
    │
    ├─→ Calendar Monitor detects meeting
    │   └─→ EVENT: calendar.meeting_scheduled
    │
    ├─→ Teams Monitor detects mention
    │   └─→ EVENT: teams.mention_received
    │
    └─→ Monday.com creates task
        └─→ EVENT: task.created

                    ↓ (All events flow to Trinity)

[TRINITY PLATFORM] Event Collector (port 8001)
    │
    └─→ Receives GitHub webhook OR NT-AI-Engine events
        └─→ Publishes to NATS JetStream
            │
            ├─→ STREAM: events.github.*
            ├─→ STREAM: events.ntai.*
            └─→ STREAM: events.system.*

                    ↓

[TRINITY] Event Projectors (Multiple consumers)
    │
    ├─→ KG Projector
    │   └─→ Projects events → Neo4j Knowledge Graph
    │       ├─ Creates Service nodes
    │       ├─ Creates Issue nodes
    │       ├─ Creates Solution nodes
    │       └─ Creates relationships (DEPENDS_ON, RESOLVES, etc.)
    │
    ├─→ Real-Time Processor
    │   └─→ Detects patterns → Triggers alerts
    │       └─→ Critical issues → Notification Service → NT-AI-Engine
    │
    └─→ PostgreSQL Event Store
        └─→ Immutable event log for audit/replay

                    ↓

[TRINITY] Intelligence Services
    │
    ├─→ RCA API (port 8002)
    │   ├─ Query: "Why is email processing slow?"
    │   ├─ Vector Search → Find similar issues (semantic)
    │   ├─ Neo4j → Find affected services (graph traversal)
    │   └─ RESPONSE: Root causes + solutions + affected services
    │
    ├─→ Investigation API (port 8003)
    │   ├─ Query: "Before implementing feature X"
    │   ├─ Neo4j → Find similar past work
    │   ├─ Vector Search → Semantic matches
    │   └─ RESPONSE: Recommendations + warnings + effort estimate
    │
    └─→ Agent Orchestrator (port 8009)
        ├─ Uses Claude Haiku 4.5
        ├─ Executes: "Analyze issue pattern"
        └─ RESPONSE: AI-generated insights

                    ↓

[TRINITY → NT-AI-ENGINE] Feedback Loop
    │
    ├─→ RCA Results
    │   └─→ Monday.com task update: "Root cause identified: X"
    │
    ├─→ Critical Alerts
    │   └─→ Email notification to user
    │
    └─→ Workflow Recommendations
        └─→ Creates Monday.com tasks with action items

================================================================================
DATA STORES - CURRENT STATE:
================================================================================

[PostgreSQL] Event Store
    ├─ events: 1 row (git.commit.received)
    ├─ audit_log: 10 rows (API requests tracked)
    ├─ users: 3 rows (trinity_test, testuser, e2e_test)
    ├─ agent_tasks: 0 rows (ready for AI execution)
    ├─ workflows: 0 rows (ready for automation)
    ├─ alerts: 0 rows (ready for alerting)
    └─ health_checks: N rows (continuous monitoring)

[Neo4j] Knowledge Graph
    ├─ Services: 236 nodes (from GitHub analysis)
    ├─ Commits: 102 nodes (git history)
    ├─ Issues: 7 nodes (from analysis)
    ├─ Solutions: 11 nodes (resolution patterns)
    ├─ Files: 3 nodes
    └─ Relationships: 12 (DEPENDS_ON, RESOLVES, etc.)

[Redis] Cache & Queues
    ├─ Vector embeddings: Cached with 3600s TTL
    ├─ Rate limits: Per-user sliding windows
    ├─ Notification queue: By priority
    └─ Session data: JWT tokens

[FAISS] Vector Index
    ├─ Documents: 168 indexed
    ├─ Model: all-MiniLM-L6-v2 (384-dim)
    └─ Types: Issues, Solutions, Services

================================================================================
INTEGRATION POINTS:
================================================================================

NT-AI-Engine → Trinity:
    ├─ Webhook endpoint: POST /webhook/ntai
    ├─ Event format: {event_type, tenant_id, data, timestamp}
    └─ Response: {event_id, queued: true}

Trinity → NT-AI-Engine:
    ├─ RCA insights: Via API callback
    ├─ Critical alerts: Via notification service
    └─ Task creation: Direct Monday.com API

Shared Resources:
    ├─ Knowledge Graph: Unified view of both systems
    ├─ Vector Search: Cross-system similarity
    └─ Audit Trail: Complete activity log

================================================================================
EXAMPLE FLOW - EMAIL PROCESSING ISSUE:
================================================================================

1. [NT-AI-ENGINE] EmailMonitor detects slow processing
   └─ Sends event to Trinity: {type: "email.processing.slow", tenant: "acme"}

2. [TRINITY] Event Collector receives event
   └─ Publishes to NATS: events.ntai.email.processing.slow

3. [TRINITY] KG Projector consumes event
   └─ Creates Issue node in Neo4j
   └─ Links to EmailService node
   └─ Creates EXPERIENCES relationship

4. [TRINITY] Real-Time Processor detects pattern
   └─ Triggers alert (3rd occurrence in 1 hour)
   └─ Calls Alert Manager

5. [TRINITY] Alert Manager
   └─ Checks deduplication (5-min window)
   └─ Sends notification to NT-AI-Engine

6. [NT-AI-ENGINE] Receives alert
   └─ Creates Monday.com task
   └─ Emails user: "Email processing degraded - investigating"

7. [TRINITY] RCA API called (manual or auto)
   └─ Vector search finds similar issues
   └─ Neo4j traverses EmailService dependencies
   └─ Returns: "Database connection pool exhausted"

8. [NT-AI-ENGINE] Receives RCA results
   └─ Updates Monday.com task with root cause
   └─ Applies suggested fix (scale DB connections)
   └─ Monitors for resolution

9. [TRINITY] Tracks resolution
   └─ Updates Issue node: status="resolved"
   └─ Creates Solution node
   └─ Links: Issue -[RESOLVED_BY]-> Solution

10. [KNOWLEDGE GRAPH] Pattern learned
    └─ Future similar issues: Instant RCA match
    └─ Recommendation: "Scale DB connections (95% success rate)"

================================================================================
CURRENT DEPLOYMENT STATUS:
================================================================================

Trinity Platform: ✅ OPERATIONAL (26/26 services)
NT-AI-Engine: ⏳ SEPARATE deployment (not integrated yet)

Next Steps:
1. Configure NT-AI-Engine webhook to Trinity Event Collector
2. Add Trinity RCA callback to NT-AI-Engine
3. Unified monitoring dashboard
4. Cross-system knowledge graph enrichment

================================================================================
""")

if __name__ == "__main__":
    pass
