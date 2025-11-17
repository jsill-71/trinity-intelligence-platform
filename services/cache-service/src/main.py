"""
Cache Service - Distributed caching with Redis
Provides high-performance caching for Trinity services
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
import redis
import msgpack
import os
import json
from datetime import datetime

app = FastAPI(title="Trinity Cache Service")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
DEFAULT_TTL = int(os.getenv("DEFAULT_TTL", "3600"))

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=False  # Binary mode for msgpack
)

class CacheItem(BaseModel):
    key: str
    value: Any
    ttl: Optional[int] = None

class CacheQuery(BaseModel):
    pattern: str

@app.post("/cache/set")
async def set_cache(item: CacheItem):
    """Set cache value with optional TTL"""

    # Serialize with msgpack for efficiency
    value_bytes = msgpack.packb(item.value)

    ttl = item.ttl if item.ttl is not None else DEFAULT_TTL

    if ttl > 0:
        redis_client.setex(item.key, ttl, value_bytes)
    else:
        redis_client.set(item.key, value_bytes)

    return {
        "key": item.key,
        "cached": True,
        "ttl": ttl,
        "size_bytes": len(value_bytes)
    }

@app.get("/cache/get/{key}")
async def get_cache(key: str):
    """Get cached value"""

    value_bytes = redis_client.get(key)

    if value_bytes is None:
        raise HTTPException(status_code=404, detail="Key not found")

    # Deserialize
    value = msgpack.unpackb(value_bytes, raw=False)

    # Get TTL
    ttl = redis_client.ttl(key)

    return {
        "key": key,
        "value": value,
        "ttl_remaining": ttl
    }

@app.delete("/cache/delete/{key}")
async def delete_cache(key: str):
    """Delete cache key"""

    deleted = redis_client.delete(key)

    return {
        "key": key,
        "deleted": deleted > 0
    }

@app.post("/cache/search")
async def search_cache(query: CacheQuery):
    """Search cache keys by pattern"""

    keys = redis_client.keys(query.pattern)

    return {
        "pattern": query.pattern,
        "keys": [k.decode() for k in keys],
        "count": len(keys)
    }

@app.post("/cache/invalidate")
async def invalidate_pattern(query: CacheQuery):
    """Invalidate cache keys matching pattern"""

    keys = redis_client.keys(query.pattern)

    if keys:
        deleted = redis_client.delete(*keys)
    else:
        deleted = 0

    return {
        "pattern": query.pattern,
        "invalidated": deleted
    }

@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""

    info = redis_client.info()

    return {
        "total_keys": redis_client.dbsize(),
        "memory_used_mb": info.get("used_memory", 0) / 1024 / 1024,
        "memory_peak_mb": info.get("used_memory_peak", 0) / 1024 / 1024,
        "hit_rate": info.get("keyspace_hits", 0) / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1)),
        "connected_clients": info.get("connected_clients", 0),
        "uptime_seconds": info.get("uptime_in_seconds", 0)
    }

@app.post("/cache/flush")
async def flush_cache():
    """Flush all cache (use with caution)"""

    redis_client.flushdb()

    return {"flushed": True}

@app.get("/health")
async def health():
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except:
        return {"status": "unhealthy", "redis": "disconnected"}
