"""
Vector Search Service - Semantic search with embeddings
Provides embedding generation and similarity search capabilities
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from typing import List, Dict, Optional
import json
import redis
import os

app = FastAPI(title="Trinity Vector Search Service")

# Initialize embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')
EMBEDDING_DIM = 384

# Initialize FAISS index
index = faiss.IndexFlatL2(EMBEDDING_DIM)
document_store = []  # Maps index position to document metadata

# Redis for caching embeddings
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

class EmbedRequest(BaseModel):
    text: str

class EmbedResponse(BaseModel):
    embedding: List[float]
    dimension: int

class IndexDocument(BaseModel):
    doc_id: str
    text: str
    metadata: Optional[Dict] = None

class SearchRequest(BaseModel):
    query: str
    k: int = 5
    filter_metadata: Optional[Dict] = None

class SearchResult(BaseModel):
    doc_id: str
    text: str
    score: float
    metadata: Optional[Dict]

class SearchResponse(BaseModel):
    results: List[SearchResult]
    query_embedding: Optional[List[float]] = None

@app.post("/embed", response_model=EmbedResponse)
async def generate_embedding(request: EmbedRequest):
    """Generate embedding for text"""

    # Check cache
    if REDIS_AVAILABLE:
        cache_key = f"embedding:{hash(request.text)}"
        cached = redis_client.get(cache_key)
        if cached:
            embedding = json.loads(cached)
            return EmbedResponse(embedding=embedding, dimension=len(embedding))

    # Generate embedding
    embedding = model.encode(request.text).tolist()

    # Cache result
    if REDIS_AVAILABLE:
        redis_client.setex(cache_key, 3600, json.dumps(embedding))

    return EmbedResponse(embedding=embedding, dimension=len(embedding))

@app.post("/index")
async def index_document(doc: IndexDocument):
    """Add document to vector index"""

    # Generate embedding
    embedding = model.encode(doc.text)

    # Add to FAISS index
    index.add(np.array([embedding]))

    # Store document metadata
    document_store.append({
        "doc_id": doc.doc_id,
        "text": doc.text,
        "metadata": doc.metadata,
        "position": len(document_store)
    })

    return {
        "doc_id": doc.doc_id,
        "indexed": True,
        "total_documents": len(document_store)
    }

@app.post("/index/batch")
async def index_documents_batch(docs: List[IndexDocument]):
    """Batch index multiple documents"""

    # Generate embeddings
    texts = [doc.text for doc in docs]
    embeddings = model.encode(texts)

    # Add to FAISS index
    index.add(embeddings)

    # Store document metadata
    for i, doc in enumerate(docs):
        document_store.append({
            "doc_id": doc.doc_id,
            "text": doc.text,
            "metadata": doc.metadata,
            "position": len(document_store)
        })

    return {
        "indexed": len(docs),
        "total_documents": len(document_store)
    }

@app.post("/search", response_model=SearchResponse)
async def semantic_search(request: SearchRequest):
    """Perform semantic similarity search"""

    if len(document_store) == 0:
        return SearchResponse(results=[])

    # Generate query embedding
    query_embedding = model.encode(request.query)

    # Search FAISS index
    k = min(request.k, len(document_store))
    distances, indices = index.search(np.array([query_embedding]), k)

    # Build results
    results = []
    for i, idx in enumerate(indices[0]):
        if idx < len(document_store):
            doc = document_store[idx]

            # Apply metadata filter if specified
            if request.filter_metadata:
                if not doc.get("metadata"):
                    continue
                match = all(
                    doc["metadata"].get(k) == v
                    for k, v in request.filter_metadata.items()
                )
                if not match:
                    continue

            # Convert L2 distance to similarity score (0-1 range)
            distance = distances[0][i]
            similarity = 1.0 / (1.0 + distance)

            results.append(SearchResult(
                doc_id=doc["doc_id"],
                text=doc["text"],
                score=float(similarity),
                metadata=doc.get("metadata")
            ))

    return SearchResponse(
        results=results,
        query_embedding=query_embedding.tolist()
    )

@app.get("/stats")
async def get_stats():
    """Get index statistics"""
    return {
        "total_documents": len(document_store),
        "index_dimension": EMBEDDING_DIM,
        "model": "all-MiniLM-L6-v2",
        "redis_available": REDIS_AVAILABLE
    }

@app.delete("/index/clear")
async def clear_index():
    """Clear all indexed documents"""
    global index, document_store
    index = faiss.IndexFlatL2(EMBEDDING_DIM)
    document_store = []
    return {"cleared": True}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "documents_indexed": len(document_store),
        "redis": "available" if REDIS_AVAILABLE else "unavailable"
    }
