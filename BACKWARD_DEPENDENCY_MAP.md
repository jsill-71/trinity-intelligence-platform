# Trinity Platform - Backward Dependency Analysis

**Analysis Method:** Start from OUTPUT responses, map backward to SOURCE data
**Purpose:** Identify schema mismatches, hardcoded values, missing integrations, orphaned data

---

## OUTPUT 1: RCA API Response (services/rca-api/src/main.py)

### Desired Output
```python
RCAResponse(
    similar_issues: List[SimilarIssue],
    affected_services: List[str],
    recommended_solutions: List[Dict],
    estimated_time: str,
    confidence: float
)
```

### Backward Trace

**LAYER 1: RCA API Response Construction (main.py:103-109)**
```python
return RCAResponse(
    similar_issues=similar_issues,          # FROM: Neo4j query or vector search
    affected_services=affected_services,    # FROM: Neo4j graph traversal
    recommended_solutions=recommended_solutions,  # FROM: Neo4j Solution nodes
    estimated_time="30 minutes" if similar_issues else "2-4 hours",  # ⚠️ HARDCODED
    confidence=0.85 if similar_issues else 0.3   # ⚠️ HARDCODED
)
```

**GAPS IDENTIFIED:**
- ❌ `estimated_time`: Hardcoded strings, not calculated from historical data
- ❌ `confidence`: Hardcoded 0.85/0.3, not based on actual match quality
- ❌ No fallback when both vector search AND keyword search fail

**LAYER 2: Similar Issues Population (main.py:49-106)**

**Attempt 1: Vector Search (NEW)**
```python
vector_response = await client.post(
    f"{VECTOR_SEARCH_URL}/search",
    json={
        "query": request.issue_description,
        "k": 5,
        "filter_metadata": {"type": "issue"}  # ⚠️ ASSUMES metadata exists
    }
)
```

**DEPENDENCIES:**
- ✅ VECTOR_SEARCH_URL environment variable
- ✅ Vector Search service at http://vector-search:8000
- ❓ Vector index populated with issue documents
- ❓ Metadata field "type" exists on indexed documents

**Attempt 2: Fallback Keyword Search**
```python
result = await session.run("""
    MATCH (i:Issue)
    WHERE toLower(i.title) CONTAINS toLower($keyword)
    RETURN i.id as id, i.title as title, i.status as status
    LIMIT 5
""", keyword=request.issue_description.split()[0])
```

**DEPENDENCIES:**
- ✅ Neo4j connection
- ❓ Issue nodes exist in Neo4j
- ❓ Issue nodes have properties: id, title, status
- ❌ Only searches first word (poor matching)
- ❌ No similarity calculation (all results equally "similar")

**LAYER 3: Neo4j Issue Nodes**

**Where do Issue nodes come from?**
- ✅ Populated by: scripts/import_analysis_data.py
- ✅ Source data: TEAM1_ISSUE_ROOT_CAUSE_ANALYSIS.json
- ❓ Real-time population: MISSING (only batch import)
- ❌ KG Projector doesn't create Issue nodes from events

**Schema in Neo4j:**
```cypher
(:Issue {
    id: str,           # FROM: JSON "issue_id"
    title: str,        # FROM: JSON "title"
    category: str,     # FROM: JSON "category"
    severity: str,     # FROM: JSON "severity"
    status: str        # FROM: JSON "status"
})
```

**Schema in Vector Index:**
```python
{
    "doc_id": issue["id"],                    # ⚠️ ASSUMES "id" field exists
    "text": f"{issue['title']} - {issue['category']}",
    "metadata": {
        "type": "issue",
        "status": issue["status"]             # ⚠️ ASSUMES "status" exists
    }
}
```

**GAPS:**
- ❌ **MAJOR GAP**: No real-time Issue creation (only batch import)
- ❌ KG Projector (services/kg-projector/) doesn't handle issue events
- ❌ Event Collector doesn't accept issue creation webhooks
- ⚠️ populate_vector_index.py assumes all fields exist (no error handling)

---

## OUTPUT 2: Vector Search Results (services/vector-search/src/main.py)

### Desired Output
```python
SearchResponse(
    results: List[SearchResult],
    query_embedding: Optional[List[float]]
)

SearchResult(
    doc_id: str,
    text: str,
    score: float,
    metadata: Optional[Dict]
)
```

### Backward Trace

**LAYER 1: Search Endpoint (main.py:99-130)**
```python
# Generate query embedding
query_embedding = model.encode(request.query)  # ✅ sentence-transformers

# Search FAISS index
distances, indices = index.search(np.array([query_embedding]), k)

# Convert distance to similarity
similarity = 1.0 / (1.0 + distance)  # ✅ Actual calculation
```

**DEPENDENCIES:**
- ✅ sentence-transformers model loaded at startup
- ✅ FAISS index in memory
- ✅ document_store array populated

**LAYER 2: Index Population (main.py:73-92, scripts/populate_vector_index.py)**

**Runtime indexing:**
```python
@app.post("/index/batch")
async def index_documents_batch(docs: List[IndexDocument]):
    texts = [doc.text for doc in docs]
    embeddings = model.encode(texts)  # ✅ Batch encoding
    index.add(embeddings)             # ✅ FAISS add
    document_store.append(...)        # ✅ Metadata storage
```

**Batch population:**
```python
# scripts/populate_vector_index.py
# Queries Neo4j for issues, solutions, services
# Indexes them into vector search

async with driver.session() as session:
    result = session.run("MATCH (i:Issue) RETURN i.id, i.title, i.category, i.status")
```

**DEPENDENCIES:**
- ✅ Neo4j populated with 359 nodes
- ✅ Script successfully ran (168 docs indexed)
- ❓ Schema assumptions: i.title, i.category exist
- ⚠️ First batch failed (422 error - metadata mismatch)

**LAYER 3: Neo4j Data Source**

**Where did 359 nodes come from?**
- ✅ scripts/import_analysis_data.py (batch import)
- ✅ Source files: TEAM2_SERVICE_CATALOG_QUICK.json, etc.
- ❌ **MISSING**: Real-time population from events
- ❌ KG Projector doesn't create Service/Issue/Solution nodes from events

**GAPS:**
- ❌ **CRITICAL**: Vector index only has batch-imported data
- ❌ New issues/services from events never get indexed
- ❌ No automatic re-indexing when Neo4j updated
- ⚠️ Schema mismatch caused first batch to fail (metadata filter issue)

---

## OUTPUT 3: Data Aggregator System Overview (services/data-aggregator/src/main.py)

### Desired Output
```python
{
    "postgresql": {
        "total_events": int,
        "total_audit_logs": int,
        "total_users": int,
        "recent_events_24h": List[...]
    },
    "knowledge_graph": {
        "nodes_by_type": Dict[str, int],
        "total_nodes": int,
        "top_relationships": List[...]
    }
}
```

### Backward Trace

**LAYER 1: PostgreSQL Queries (main.py:55-68)**
```python
async with pg_pool.acquire() as conn:
    total_events = await conn.fetchval("SELECT COUNT(*) FROM events")
    total_audits = await conn.fetchval("SELECT COUNT(*) FROM audit_log")
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users")

    recent_events = await conn.fetch("""
        SELECT event_type, COUNT(*) as count
        FROM events
        WHERE timestamp > NOW() - INTERVAL '24 hours'  # ⚠️ COLUMN NAME
        GROUP BY event_type
    """)
```

**SCHEMA DEPENDENCY:**
- ✅ Table: `events` (created by event-collector)
- ✅ Table: `audit_log` (created by audit-service)
- ✅ Table: `users` (created by user-management)
- ❌ **MISMATCH**: Query uses `timestamp`, but error showed "created_at does not exist"
- ❌ Actual column is `timestamp` in events table (event-collector creates it)
- ✅ **FIXED**: Changed from `created_at` to `timestamp`

**LAYER 2: Events Table Schema (services/event-collector/src/main.py)**
```python
await conn.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        event_id VARCHAR(100) UNIQUE,
        event_type VARCHAR(100),
        payload JSONB,
        timestamp TIMESTAMP DEFAULT NOW()  # ✅ Correct name
    )
""")
```

**LAYER 3: Event Population**

**Where do events come from?**
- ✅ POST /webhook/github (event-collector)
- ✅ Stores to PostgreSQL
- ✅ Publishes to NATS
- ❌ **GAP**: Very few events (only 1 in database currently)
- ❌ No bulk event ingestion from NT-AI-Engine

**GAPS:**
- ⚠️ Column name was mismatched (fixed in this session)
- ❌ Minimal event data (only 1 event vs expected hundreds)
- ❌ No NT-AI-Engine webhook integration yet

---

## OUTPUT 4: User Authentication JWT (services/user-management/src/main.py)

### Desired Output
```python
Token(
    access_token: str,  # JWT token
    token_type: str,    # "bearer"
    expires_at: datetime
)
```

### Backward Trace

**LAYER 1: Token Creation (main.py:42-49)**
```python
def create_access_token(user_id: int, username: str) -> str:
    expires = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode = {
        "sub": str(user_id),
        "username": username,
        "exp": expires
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
```

**DEPENDENCIES:**
- ✅ JWT_SECRET environment variable
- ✅ JWT_ALGORITHM = "HS256"
- ✅ User ID and username from database

**LAYER 2: User Verification (main.py:115-141)**
```python
async with conn.fetchrow("""
    SELECT id, username, password_hash, is_active
    FROM users
    WHERE username = $1
""", credentials.username)
```

**SCHEMA DEPENDENCY:**
- ✅ Table: `users` (created at startup)
- ✅ Columns: id, username, password_hash, is_active, email, full_name, roles, created_at
- ✅ Password hashing: bcrypt via passlib
- ✅ Validation: Checks is_active before allowing login

**LAYER 3: User Registration (main.py:84-110)**
```python
await conn.fetchval("""
    INSERT INTO users (email, username, password_hash, full_name)
    VALUES ($1, $2, $3, $4)
    RETURNING id
""", user.email, user.username, password_hash, user.full_name)
```

**DEPENDENCIES:**
- ✅ Password hashing function
- ✅ Unique constraints on email and username
- ✅ Default values: is_active=true, roles=['user']

**GAPS:**
- ✅ **COMPLETE CHAIN**: This one works end-to-end!
- ✅ Validated: User registration → PostgreSQL → Login → JWT → API Gateway accepts token
- ✅ All schema names consistent (username, password_hash, is_active)

---

## CRITICAL FINDINGS: Schema Gaps in Trinity Platform

### Issue 1: RCA API Hardcoded Values

**Problem:**
```python
# services/rca-api/src/main.py:85
similar_issues.append(SimilarIssue(
    issue_id=record["id"],
    title=record["title"],
    similarity=result["score"],  # ✅ From vector search
    resolution=record["resolution"],
    status=record["status"] if record["status"] else "unknown"
))

# BUT in fallback (line 105):
similarity=0.5,  # ❌ HARDCODED when vector search fails
```

**Backward Trace:**
- Vector search fails → falls back to keyword search
- Keyword search has NO similarity metric
- Returns hardcoded 0.5 for all results
- **Impact:** User sees "50% similar" for everything when vector search down

**Fix Required:**
- Calculate actual similarity for keyword matches (Levenshtein distance, TF-IDF)
- Or: Return confidence=0 and estimated_time="unknown" when using fallback

### Issue 2: Data Aggregator Column Mismatch (FIXED)

**Problem (WAS):**
```python
# services/data-aggregator/src/main.py:64
WHERE created_at > NOW() - INTERVAL '24 hours'  # ❌ Column doesn't exist
```

**Fix Applied:**
```python
WHERE timestamp > NOW() - INTERVAL '24 hours'   # ✅ Matches events table
```

**Backward Trace:**
- events table created by event-collector
- Column is named `timestamp` (line 34 of event-collector/src/main.py)
- Data aggregator was using wrong column name
- **Status:** FIXED in this session

### Issue 3: Vector Index Metadata Filter

**Problem:**
```python
# services/rca-api/src/main.py:59
"filter_metadata": {"type": "issue"}  # ⚠️ ASSUMES this metadata exists
```

**Backward Trace:**
- Vector search filters by metadata.type == "issue"
- Metadata set in scripts/populate_vector_index.py:
```python
"metadata": {
    "type": "issue",        # ✅ Set correctly
    "status": record["status"]  # ⚠️ ASSUMES status exists
}
```
- First batch failed (422 error) because some documents had incompatible metadata
- **Status:** PARTIAL - works for issues, may fail for other types

### Issue 4: Neo4j Schema Assumptions

**Problem:**
```python
# scripts/populate_vector_index.py:26-28
result = session.run("""
    MATCH (i:Issue)
    RETURN i.id as id, i.title as title, i.category as category, i.status as status
""")
```

**Backward Trace:**
- Assumes Issue nodes have: id, title, category, status
- Actual Issue nodes from import_analysis_data.py have: id, title, category, severity, status
- **Mismatch:** Some properties may be NULL
- Warning in logs: "property key does not exist: description, technology"

**Fix Required:**
- Use COALESCE or null checks: `COALESCE(i.category, 'general') as category`
- Handle missing properties gracefully

### Issue 5: Service Environment URLs

**Problem:**
```python
# services/rca-api/src/main.py:18
VECTOR_SEARCH_URL = os.getenv("VECTOR_SEARCH_URL", "http://vector-search:8000")

# But docker-compose-working.yml doesn't set this variable
```

**Backward Trace:**
- RCA API container has no VECTOR_SEARCH_URL env var
- Falls back to default "http://vector-search:8000"
- This works because Docker Compose service name resolution
- **Status:** Works by accident, should be explicit

**Fix:**
```yaml
# docker-compose-working.yml
rca-api:
  environment:
    VECTOR_SEARCH_URL: http://vector-search:8000  # ✅ Explicit
```

---

## Complete Backward Chains

### Chain 1: RCA Analysis

```
[SOURCE] GitHub Webhook
    ↓ POST /webhook/github
[Event Collector] Receives webhook
    ↓ Publishes to NATS: events.github.commit
[KG Projector] Consumes NATS event
    ↓ Projects to Neo4j
[Neo4j] Stores Commit node
    ↓ (No Issue nodes created from events)
[Import Script] Batch imports Issues
    ↓ CREATE (:Issue {...})
[Vector Index Script] Reads Issues from Neo4j
    ↓ Indexes 7 issues into FAISS
[RCA API] Receives query
    ↓ Calls Vector Search
[Vector Search] Returns top 5 matches
    ↓ similarity scores from FAISS L2 distance
[RCA API] Queries Neo4j for full Issue details
    ↓ Returns SimilarIssue objects
[OUTPUT] RCA Response with 0-5 similar issues
```

**GAPS IN CHAIN:**
- ❌ No runtime Issue creation (only batch import)
- ❌ Vector index not updated when Neo4j changes
- ⚠️ Fallback has hardcoded similarity
- ❌ No Issue→Solution→Service graph traversal

### Chain 2: User Authentication

```
[SOURCE] User submits credentials
    ↓ POST /auth/login (API Gateway)
[API Gateway] Proxies to User Management
    ↓ POST /users/login
[User Management] Queries users table
    ↓ SELECT * FROM users WHERE username = ?
[PostgreSQL] Returns user row
    ↓ {id, username, password_hash, is_active, roles}
[User Management] Verifies password (bcrypt)
    ↓ passlib.verify(plain, hash)
[User Management] Creates JWT
    ↓ jwt.encode({sub, username, exp}, SECRET)
[OUTPUT] Token(access_token, token_type, expires_at)
    ↓ User receives JWT
[Subsequent Requests] Include "Authorization: Bearer {token}"
    ↓ API Gateway validates
[API Gateway] Decodes JWT
    ↓ jwt.decode(token, SECRET)
[API Gateway] Fetches user from database
    ↓ SELECT * FROM users WHERE id = {token.sub}
[OUTPUT] Authenticated request proceeds to service
```

**GAPS IN CHAIN:**
- ✅ COMPLETE - This chain works end-to-end!
- ✅ All schemas match
- ✅ Validated in testing (user registered, logged in, made authenticated RCA call)

### Chain 3: System Metrics

```
[SOURCE] Service /health endpoints
    ↓ GET /health (each service)
[Metrics Collector] Polls every 15s
    ↓ services/metrics-collector/src/collector.py
[Prometheus Metrics] Exposes on port 9090
    ↓ trinity_services_up, trinity_kg_nodes_total, etc.
[OUTPUT] Prometheus metrics endpoint
    ↓ GET localhost:9090/metrics
```

**Chain works, but:**
- ⚠️ Only 11 services monitored (should be 14+)
- ❌ Metrics collector hardcoded service list (not dynamic)
- ❌ New services require code change to add monitoring

---

## Naming Convention Analysis

### Consistent Naming (✅ Good)
- **User identifiers:** `username` (consistent across user-management, api-gateway, audit)
- **Timestamps:** `timestamp` in events, `created_at` in users/audit (intentional distinction)
- **Primary keys:** `id` (all tables use SERIAL PRIMARY KEY named `id`)
- **Status fields:** `status` (consistent: users.is_active is boolean, others use status string)

### Inconsistent Naming (⚠️ Needs standardization)
- **Issue identifiers:**
  - Neo4j: `i.id`
  - Vector search: `doc_id`
  - Could be: `issue_id` for clarity

- **Service URLs:**
  - Some: `RCA_API_URL`
  - Some: `VECTOR_SEARCH_URL`
  - Some: Missing (rely on defaults)
  - Should: All explicit in docker-compose

### Orphaned Data (❌ Collected but unused)
- **Neo4j `severity` field:** Issues have severity, but RCA API doesn't use it for ranking
- **events.payload JSONB:** Stored but never queried (could be used for better analysis)
- **audit_log.metadata:** Collected but data aggregator doesn't expose it

---

## Priority Fixes

### Critical (Must Fix for Production)
1. **Remove hardcoded similarity scores in fallback** (30 min)
   - Calculate real similarity or return confidence=0

2. **Add explicit environment variables** (15 min)
   - All service URLs in docker-compose

3. **Error handling for missing Neo4j properties** (1 hour)
   - Use COALESCE in Cypher queries
   - Handle NULL gracefully in Python

### High (Improves reliability)
4. **Real-time Issue creation** (4-6 hours)
   - Add issue.created event type
   - KG Projector creates Issue nodes from events
   - Auto-index in vector search

5. **Dynamic service discovery for metrics** (2 hours)
   - Query docker-compose or service registry
   - Don't hardcode service list

### Medium (Quality improvements)
6. **Use orphaned data** (3-4 hours)
   - events.payload for richer analysis
   - audit_log.metadata for debugging
   - Issue.severity for priority ranking

---

## Validation Checklist

**To verify backward chains are complete:**

- [ ] Can trace every response field to its data source
- [ ] All assumed database columns actually exist
- [ ] All assumed Neo4j properties actually exist
- [ ] No hardcoded business logic values (similarity, time estimates, confidence)
- [ ] All service URLs explicitly configured
- [ ] Error handling for missing/null data at every layer
- [ ] Integration tests cover complete data flow (source → output)
- [ ] New data automatically flows through pipeline (no manual imports)

**Current Status:**
- [x] User auth chain: COMPLETE
- [x] Metrics chain: WORKING (with limitations)
- [~] RCA chain: PARTIAL (vector search works, fallback has gaps)
- [~] Data aggregator: PARTIAL (fixed column name, minimal data)

---

## Summary

Trinity Platform has **good architectural separation** but suffers from:
1. **Hardcoded placeholders** in business logic (similarity, confidence, time)
2. **Batch-only data population** (no real-time event→graph→index flow)
3. **Schema assumptions** without null handling
4. **Static service discovery** (hardcoded lists)

**Good news:** Most gaps are in newer services (rca-api, data-aggregator) - core platform (auth, events, kg) works correctly.

**Recommendation:** Fix critical issues (1-3), then add real-time Issue creation (#4) to complete the loop.
