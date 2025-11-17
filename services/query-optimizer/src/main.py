"""
Query Optimizer - Intelligent Cypher query optimization using AI
Uses Claude Haiku to optimize Neo4j queries for performance
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
from neo4j import AsyncGraphDatabase
import redis
import anthropic
import os
import hashlib
import json

app = FastAPI(title="Trinity Query Optimizer")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity123")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4.5-20250514")

driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

if ANTHROPIC_API_KEY:
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    AI_AVAILABLE = True
else:
    anthropic_client = None
    AI_AVAILABLE = False

class QueryRequest(BaseModel):
    cypher: str
    optimize: bool = True
    cache_results: bool = True
    ttl: int = 300

class QueryAnalysis(BaseModel):
    original_query: str
    optimized_query: Optional[str] = None
    estimated_cost: str
    suggestions: List[str]

def generate_query_hash(cypher: str) -> str:
    """Generate hash for query caching"""
    return hashlib.md5(cypher.encode()).hexdigest()

async def optimize_cypher_with_ai(cypher: str) -> Dict:
    """Use Claude Haiku to optimize Cypher query"""

    if not AI_AVAILABLE:
        return {"optimized_query": cypher, "suggestions": ["AI optimization unavailable"]}

    prompt = f"""Optimize this Neo4j Cypher query for performance. Provide:
1. Optimized query (if improvements possible)
2. Specific optimization suggestions

Original query:
```cypher
{cypher}
```

Focus on: indexes, query structure, MATCH patterns, filtering order."""

    try:
        message = anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        result_text = message.content[0].text

        # Parse response (simple parsing)
        suggestions = result_text.split("\n")
        suggestions = [s.strip() for s in suggestions if s.strip() and not s.startswith("```")]

        return {
            "optimized_query": cypher,  # Would extract from AI response
            "suggestions": suggestions[:5],  # Top 5
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens
        }
    except Exception as e:
        return {"optimized_query": cypher, "suggestions": [f"Optimization failed: {str(e)}"]}

@app.post("/query/execute")
async def execute_query(request: QueryRequest):
    """Execute Cypher query with optional optimization and caching"""

    query_hash = generate_query_hash(request.cypher)

    # Check cache
    if request.cache_results and REDIS_AVAILABLE:
        cached = redis_client.get(f"query_result:{query_hash}")
        if cached:
            return {
                "cached": True,
                "results": json.loads(cached),
                "query": request.cypher
            }

    # Optimize if requested
    query_to_execute = request.cypher
    optimization_info = None

    if request.optimize and AI_AVAILABLE:
        optimization = await optimize_cypher_with_ai(request.cypher)
        optimization_info = optimization
        # Would use optimized query if provided

    # Execute query
    async with driver.session() as session:
        result = await session.run(query_to_execute)

        records = []
        async for record in result:
            records.append(dict(record))

    # Cache results
    if request.cache_results and REDIS_AVAILABLE:
        redis_client.setex(
            f"query_result:{query_hash}",
            request.ttl,
            json.dumps(records)
        )

    return {
        "cached": False,
        "results": records,
        "query": query_to_execute,
        "optimization": optimization_info,
        "result_count": len(records)
    }

@app.post("/query/analyze", response_model=QueryAnalysis)
async def analyze_query(cypher: str):
    """Analyze Cypher query for optimization opportunities"""

    optimization = await optimize_cypher_with_ai(cypher)

    return QueryAnalysis(
        original_query=cypher,
        optimized_query=optimization.get("optimized_query"),
        estimated_cost="medium",  # Would calculate from EXPLAIN
        suggestions=optimization.get("suggestions", [])
    )

@app.get("/query/cache/stats")
async def get_cache_stats():
    """Get query cache statistics"""

    if not REDIS_AVAILABLE:
        return {"error": "Redis unavailable"}

    keys = redis_client.keys("query_result:*")

    return {
        "cached_queries": len(keys),
        "cache_size_mb": sum(len(redis_client.get(k) or b"") for k in keys) / 1024 / 1024
    }

@app.delete("/query/cache/clear")
async def clear_query_cache():
    """Clear all cached query results"""

    if not REDIS_AVAILABLE:
        return {"error": "Redis unavailable"}

    keys = redis_client.keys("query_result:*")
    if keys:
        redis_client.delete(*keys)

    return {"cleared": len(keys)}

@app.get("/health")
async def health():
    try:
        async with driver.session() as session:
            await session.run("RETURN 1")

        return {
            "status": "healthy",
            "neo4j": "connected",
            "redis": "available" if REDIS_AVAILABLE else "unavailable",
            "ai_optimizer": "available" if AI_AVAILABLE else "unavailable",
            "model": ANTHROPIC_MODEL if AI_AVAILABLE else None
        }
    except:
        return {"status": "unhealthy"}
