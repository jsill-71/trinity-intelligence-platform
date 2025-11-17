# Trinity Platform - Complete Service Dependency Analysis

**All 22 application services mapped backward from outputs to sources**

---

## Service 13: Investigation API

### OUTPUT
```python
InvestigationResponse(
    similar_past_work: list[dict],
    affected_services: list[str],
    known_issues: list[dict],
    recommended_approach: list[str],
    warnings: list[str],
    estimated_effort: str
)
```

### BACKWARD CHAIN
```
OUTPUT: Investigation recommendations
  ↓ FROM: investigate_task() combines 3 sources
    ↓ Source 1: RCA API call (finds similar issues)
      ↓ HTTP POST {RCA_API_URL}/api/rca
        ↓ Returns: similar_issues list
    ↓ Source 2: Neo4j affected services
      ↓ Cypher: MATCH (s:Service {name})-[:DEPENDS_ON*0..2]-(related)
    ↓ Source 3: Neo4j known issues
      ↓ Cypher: MATCH (s:Service)-[:HAD_ISSUE]->(i:Issue) WHERE status='open'
        ↓ INPUT: InvestigationRequest(task_description, component)
          ↓ SOURCE: HTTP POST from external caller
```

### GAPS
1. **RCA API schema mismatch:** Sends {title, description, component} but RCA expects {issue_description, component}
   - **Impact:** RCA API receives wrong field name
   - **Fix:** Use issue_description or update RCA API to accept title
2. **No time_taken field:** Tries to use similar_work[0]["time_taken"] but field doesn't exist
   - **Impact:** Always returns "Unknown" estimated effort
   - **Fix:** Add time_taken to Solution nodes or use fixed estimates
3. **Missing HAD_ISSUE relationships:** Query for known issues returns empty (KG Projector doesn't create these)
   - **Impact:** No known issues ever found
   - **Fix:** KG Projector must create HAD_ISSUE relationships

---

## Service 14: Query Optimizer

### OUTPUT
```python
QueryAnalysis(
    original_query: str,
    optimized_query: Optional[str],
    estimated_cost: str,  # "medium" (hardcoded)
    suggestions: List[str]
)
```

### BACKWARD CHAIN
```
OUTPUT: Optimization suggestions
  ↓ FROM: optimize_cypher_with_ai()
    ↓ Anthropic API: Claude Haiku
      ↓ Prompt: "Optimize this Cypher query..."
        ↓ Response: suggestions (parsed from text)
          ↓ Comment: optimized_query NOT extracted (just returns original)
            ↓ INPUT: Cypher query string
              ↓ SOURCE: External caller
```

### GAPS
1. **Optimized query not extracted:** Line 92 returns original query, not AI-optimized version
   - **Impact:** Optimization suggestions provided but query not actually optimized
   - **Fix:** Parse AI response to extract optimized Cypher
2. **Estimated cost hardcoded:** Always returns "medium"
   - **Impact:** No actual cost estimation
   - **Fix:** Use Neo4j EXPLAIN to get real cost
3. **Simple suggestion parsing:** Splits on newline, filters lines
   - **Impact:** May include irrelevant text from AI response
   - **Fix:** Use structured prompting or JSON mode

---

## Service 15: Backup Service

### OUTPUT
Backup files: postgres_{timestamp}.json, neo4j_{timestamp}.json

### BACKWARD CHAIN
```
OUTPUT: Backup JSON files
  ↓ FROM: APScheduler cron jobs (1 AM, 1:30 AM daily)
    ↓ backup_postgres(): Dumps all tables to JSON
      ↓ SELECT * FROM each table → dict rows
        ↓ json.dump(backup_data, file)
    ↓ backup_neo4j(): Exports all nodes/relationships
      ↓ MATCH (n) RETURN labels, properties
      ↓ MATCH ()-[r]->() RETURN from_id, to_id, type, properties
        ↓ Stores: {nodes: [...], relationships: [...]}
          ↓ SOURCE: Scheduled trigger
```

### GAPS
1. **No verification:** Backups created but never validated
   - **Impact:** Corrupted backups not detected
   - **Fix:** Add restoration test after each backup
2. **Node IDs not stable:** Uses id(a), id(b) which change on restore
   - **Impact:** Relationships broken on restore
   - **Fix:** Use business keys (hash, name) instead of internal IDs
3. **No compression:** Large graphs create huge JSON files
   - **Impact:** Disk space issues
   - **Fix:** gzip compression
4. **Synchronous backup:** Blocks while dumping entire database
   - **Impact:** Long-running backups may timeout
   - **Fix:** Stream to file instead of loading all into memory

---

## Service 16: Health Monitor

### OUTPUT
Health check results in PostgreSQL + Redis

### BACKWARD CHAIN
```
OUTPUT: health_checks table rows
  ↓ FROM: monitor_loop() every CHECK_INTERVAL seconds (30s default)
    ↓ Calls: check_service_health() for each service
      ↓ HTTP GET {service}/health
        ↓ Returns: {status, response_time}
          ↓ Stores: INSERT INTO health_checks
            ↓ Also: Sets Redis health_check:results
              ↓ Triggers alerts: If service degraded → POST to Alert Manager
                ↓ SOURCE: Scheduled monitoring loop
```

### GAPS
1. **Hardcoded service list:** Only monitors 14 services, missing 12 others
   - **Impact:** Half the platform not monitored
   - **Fix:** Dynamic service discovery
2. **State lost on restart:** service_state dict in-memory
   - **Impact:** False recovery alerts after restart
   - **Fix:** Store previous state in Redis or PostgreSQL
3. **health_checks table created on first run:** Not in startup()
   - **Impact:** Race condition if multiple checks run simultaneously
   - **Fix:** Move CREATE TABLE to startup()
4. **No retention policy:** health_checks grows unbounded
   - **Impact:** Disk space issues
   - **Fix:** Delete checks older than 7 days

---

## Service 17: Cache Service

### OUTPUT
```python
{
    "key": str,
    "value": Any,  # msgpack deserialized
    "ttl_remaining": int
}
```

### BACKWARD CHAIN
```
OUTPUT: Cached value
  ↓ FROM: Redis GET operation
    ↓ Deserialize: msgpack.unpackb(bytes)
      ↓ Key: Provided in GET /cache/get/{key}
        ↓ Stored via: POST /cache/set
          ↓ Serialize: msgpack.packb(value)
            ↓ Redis SETEX with TTL
              ↓ INPUT: CacheItem(key, value, ttl)
                ↓ SOURCE: External service caching data
```

### GAPS
1. **No cache consumers:** Service exists but no other services use it
   - **Impact:** Orphaned service
   - **Fix:** Integrate with Vector Search, Query Optimizer, RCA API
2. **TTL=0 creates permanent keys:** Line 47 allows ttl=0 for no expiration
   - **Impact:** Cache fills up with permanent data
   - **Fix:** Enforce minimum TTL or max permanent keys
3. **No namespace isolation:** All services share same key space
   - **Impact:** Key collisions between services
   - **Fix:** Prefix keys with service name
4. **msgpack errors not handled:** Deserialization can fail on corrupted data
   - **Impact:** HTTPException 500 instead of graceful handling
   - **Fix:** Try/except around msgpack operations

---

## Service 18: Rate Limiter

### OUTPUT
```python
{
    "allowed": bool,
    "limit": int,
    "current": int,
    "remaining": int,
    "reset_at": int  # Unix timestamp
}
```

### BACKWARD CHAIN
```
OUTPUT: Rate limit decision
  ↓ FROM: check_rate_limit() with strategy
    ↓ Strategy: sliding_window / token_bucket / fixed_window
      ↓ Redis operations:
        ↓ Sliding: ZSET with timestamps
        ↓ Token bucket: String with {tokens, last_refill}
        ↓ Fixed: Counter with TTL
          ↓ Key: rate_limit:{strategy}:{identifier}:{window}
            ↓ INPUT: RateLimitCheck + RateLimitConfig
              ↓ SOURCE: External caller (API Gateway calls this)
```

### GAPS
1. **No consumers:** Service exists but API Gateway doesn't use it
   - **Impact:** Orphaned service (API Gateway has own rate limiting)
   - **Fix:** Remove duplicate rate limiting from API Gateway, use this service
2. **JSON serialization issue:** token_bucket uses json.dumps/loads but import missing
   - **Impact:** Service crashes on token_bucket strategy
   - **Fix:** Import json (already done in latest version)
3. **No persistence:** Rate limit state lost on Redis restart
   - **Impact:** Users get fresh quotas after Redis restart
   - **Fix:** Persist quota state to PostgreSQL

---

## Service 19: Real-Time Processor

### OUTPUT
Real-time alerts and analytics

### BACKWARD CHAIN
```
OUTPUT: Alerts triggered, stats stored
  ↓ FROM: process_event() for each NATS message
    ↓ Subscribed to: events.> (all events)
      ↓ Pattern detection:
        ↓ issue.created → handle_new_issue()
        ↓ service.health.degraded → handle_service_degradation()
        ↓ error.occurred → check_error_rate()
          ↓ Triggers: POST to notification-service
            ↓ Stores: realtime_stats table
              ↓ SOURCE: NATS EVENTS stream
```

### GAPS
1. **NATS stream creation:** Creates EVENTS stream but Event Collector uses different streams
   - **Impact:** No events received (stream name mismatch)
   - **Fix:** Subscribe to actual streams (GIT_COMMITS, GITHUB_EVENTS)
2. **Auto-investigation loop risk:** High error rate triggers investigation → investigation may error → triggers more investigations
   - **Impact:** Cascade failure
   - **Fix:** Add circuit breaker, max investigations per hour
3. **Table created on first event:** realtime_stats NOT created at startup
   - **Impact:** Race condition
   - **Fix:** Move to startup() function
4. **No event validation:** Assumes all events have expected fields
   - **Impact:** Crashes on malformed events
   - **Fix:** Validate event schema before processing

---

## REMAINING SERVICES (Already Mapped)

- ✅ RCA API (in BACKWARD_DEPENDENCY_MAP.md)
- ✅ Vector Search (in BACKWARD_DEPENDENCY_MAP.md)
- ✅ User Management (in BACKWARD_DEPENDENCY_MAP.md)
- ✅ Data Aggregator (in BACKWARD_DEPENDENCY_MAP.md + column fix noted)
- ✅ Audit Service (in TRINITY_COMPLETE_DEPENDENCY_MAP.md)

---

## COMPLETE TRINITY PLATFORM SUMMARY

### All 22 Services Mapped

**Infrastructure (4):**
- NATS, PostgreSQL, Neo4j, Redis

**Application Services (22):**
1. ✅ Event Collector (P0 security: eval())
2. ✅ KG Projector (P0 security: eval(), missing relationships)
3. ✅ RCA API (hardcoded fallback)
4. ✅ Investigation API (schema mismatch, missing data)
5. ✅ Vector Search (working)
6. ✅ User Management (complete)
7. ✅ Audit Service (complete)
8. ✅ API Gateway (missing circuit breaker)
9. ✅ Agent Orchestrator (orphaned queue)
10. ✅ Workflow Engine (SSRF risk)
11. ✅ Alert Manager (weak fingerprint)
12. ✅ Notification Service (orphaned queue, unconfigured SMTP)
13. ✅ ML Training (in-memory jobs)
14. ✅ Metrics Collector (hardcoded services, driver leak)
15. ✅ Scheduler (no persistence)
16. ✅ Query Optimizer (doesn't use optimized query)
17. ✅ Backup Service (no verification)
18. ✅ Health Monitor (hardcoded services, no retention)
19. ✅ Cache Service (no consumers)
20. ✅ Rate Limiter (no consumers)
21. ✅ Real-Time Processor (stream mismatch)
22. ✅ Data Aggregator (fixed column name)

---

## CRITICAL ISSUES SUMMARY

**P0 SECURITY (FIX IMMEDIATELY - 2 hours):**
1. Event Collector: `eval()` → RCE (line 88, 131, 166)
2. KG Projector: `eval()` → RCE (3 places)
3. Workflow Engine: Unvalidated service URLs → SSRF

**P1 DATA INTEGRITY (FIX THIS WEEK - 24 hours):**
4. Event Collector: `str(dict)` instead of JSON → Unparseable data
5. Event Collector: events table not created → Service crashes
6. KG Projector: Missing Issue→Service, Issue→Solution relationships
7. ML Training: In-memory job tracking → Lost on restart
8. Alert Manager: Weak fingerprint → Collision risk
9. Metrics Collector: Neo4j driver leak → Connection exhaustion
10. Health Monitor: Table created on first run → Race condition
11. Backup Service: No verification → Corrupted backups undetected
12. Query Optimizer: Doesn't use optimized query → Feature broken

**P2 MISSING INTEGRATIONS (FIX THIS SPRINT - 32 hours):**
13. Agent Orchestrator: Redis queue orphaned (no consumer)
14. Notification Service: Redis queue orphaned (no consumer)
15. Cache Service: No consumers (orphaned service)
16. Rate Limiter: No consumers (orphaned service, API Gateway has own)
17. Real-Time Processor: NATS stream name mismatch
18. Investigation API: RCA schema mismatch
19. Health Monitor: Hardcoded service list
20. Metrics Collector: Hardcoded service list
21. Scheduler: No job persistence
22. API Gateway: No circuit breaker

**Total:** 22 issues across 22 services
**Fix time:** 58 hours (1.5 weeks with 1 developer)

---

## ORPHANED SERVICES (Built but unused)

1. **Cache Service** - No service uses POST /cache/set
   - Should be used by: Query Optimizer, Vector Search, RCA API
2. **Rate Limiter** - API Gateway has own rate limiting
   - Should replace: API Gateway's built-in rate_limit() function
3. **Agent Orchestrator Redis queues** - Queued but never consumed
   - Should have: Worker service consuming agent_queue:{priority}
4. **Notification Service Redis queues** - Queued but never sent
   - Should have: Worker service processing notification_queue:{priority}

---

## MISSING DATA FLOWS

1. **Real-time Issue creation:** Events → KG Projector → (missing) → Neo4j Issue nodes
   - Only batch imports create Issues
   - Vector index never updated with new issues
2. **Solution node creation:** Resolved issues never create Solution nodes
   - KG Projector doesn't handle resolution events
   - RCA recommended_solutions always empty
3. **Service dependency discovery:** No way to populate Service DEPENDS_ON relationships
   - Only from batch import
   - Graph never reflects actual dependencies
4. **Alert escalation:** Alert Manager stores escalation_delay but never checks it
   - Scheduler doesn't trigger escalation
   - Feature doesn't work

---

## RECOMMENDED IMPLEMENTATION SEQUENCE (Based on Dependencies)

**Phase 1: Fix P0 Security (Day 1)**
1. Replace `eval()` with `json.loads()` everywhere
2. Validate workflow service URLs
3. Deploy and test

**Phase 2: Fix Data Integrity (Days 2-4)**
4. Fix Event Collector JSON serialization
5. Add events table creation
6. Store ML jobs in PostgreSQL
7. Fix Alert fingerprint
8. Close Neo4j drivers properly
9. Move table creation to startup()

**Phase 3: Add Missing Relationships (Days 5-7)**
10. KG Projector: Create Issue→Service HAD_ISSUE relationships
11. KG Projector: Create Issue→Solution RESOLVED_BY relationships
12. KG Projector: Handle resolution events
13. Investigation API: Fix RCA schema mismatch

**Phase 4: Integrate Orphaned Services (Days 8-10)**
14. Add Cache Service to Query Optimizer
15. Replace API Gateway rate limiting with Rate Limiter service
16. Implement queue consumers for Agent Orchestrator
17. Implement queue consumers for Notification Service

**Phase 5: Dynamic Service Discovery (Days 11-12)**
18. Health Monitor: Query docker-compose for service list
19. Metrics Collector: Query docker-compose for service list
20. Add service registry table

**Phase 6: Production Hardening (Days 13-15)**
21. Backup verification
22. Add circuit breakers
23. Add alert escalation
24. Query Optimizer: Extract optimized queries
25. Comprehensive testing

---

## VALIDATION CHECKLIST

After fixes, validate:

**Security:**
- [ ] No `eval()` anywhere (grep -r "eval(")
- [ ] All service URLs validated (whitelist)
- [ ] All secrets in environment variables (not hardcoded)

**Data Integrity:**
- [ ] All data JSON serialized (no str(dict))
- [ ] All tables created at startup (not on first use)
- [ ] All job state persisted (no in-memory tracking)
- [ ] All fingerprints unique (no collisions)

**Integration:**
- [ ] All producers have consumers
- [ ] All consumers have producers
- [ ] All schemas match between services
- [ ] All queues have workers

**Production Readiness:**
- [ ] All backups verified
- [ ] All services monitored
- [ ] All failures trigger alerts
- [ ] All retries have backoff

---

## NEXT STEPS

1. **Read:** TRINITY_COMPLETE_DEPENDENCY_MAP.md (services 1-12)
2. **Read:** This document (services 13-22)
3. **Prioritize:** Start with P0 security issues
4. **Implement:** Follow recommended sequence
5. **Test:** Each phase before proceeding
6. **Deploy:** With confidence after all fixes

**Total mapping complete:** 100% of Trinity Platform services analyzed
**Total documentation:** 3 comprehensive backward dependency documents
**Ready for:** Systematic fixes based on complete dependency knowledge
