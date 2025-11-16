"""
Investigation API - Pre-task investigation service

Provides investigation before Trinity starts work to prevent repeated mistakes.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neo4j import AsyncGraphDatabase
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trinity Investigation API")

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "trinity_dev_password")
RCA_API_URL = os.getenv("RCA_API_URL", "http://rca-api:8000")

# Neo4j driver
driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


class InvestigationRequest(BaseModel):
    task_description: str
    component: str | None = None


class InvestigationResponse(BaseModel):
    similar_past_work: list[dict]
    affected_services: list[str]
    known_issues: list[dict]
    recommended_approach: list[str]
    warnings: list[str]
    estimated_effort: str


@app.on_event("shutdown")
async def shutdown():
    await driver.close()


@app.post("/api/investigate", response_model=InvestigationResponse)
async def investigate_task(request: InvestigationRequest):
    """
    Investigate task before execution

    Returns: Similar past work, affected services, recommendations
    """

    # 1. Call RCA API to find similar issues
    similar_work = []
    try:
        async with httpx.AsyncClient() as client:
            rca_response = await client.post(
                f"{RCA_API_URL}/api/rca",
                json={
                    "title": request.task_description,
                    "description": request.task_description,
                    "component": request.component or "unknown"
                },
                timeout=30.0
            )
            if rca_response.status_code == 200:
                rca_data = rca_response.json()
                similar_work = rca_data.get("similar_issues", [])
    except Exception as e:
        logger.warning(f"RCA API unavailable: {e}")

    # 2. Query Neo4j for affected services
    affected_services = []
    if request.component:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (s:Service {name: $component})-[:DEPENDS_ON*0..2]-(related:Service)
                RETURN DISTINCT related.name as service
                LIMIT 10
            """, component=request.component)

            affected_services = [record["service"] async for record in result]

    # 3. Check for known issues in affected services
    known_issues = []
    if affected_services:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (s:Service)-[:HAD_ISSUE]->(i:Issue)
                WHERE s.name IN $services AND i.status = 'open'
                RETURN i.number as issue_number, i.title as title, s.name as service
                LIMIT 5
            """, services=affected_services)

            known_issues = [dict(record) async for record in result]

    # 4. Generate recommendations
    recommendations = []
    if similar_work:
        recommendations.append(f"Similar work found: Review {len(similar_work)} past issues")
        if similar_work[0].get("resolution"):
            recommendations.append(f"Apply pattern: {similar_work[0]['resolution']}")

    if not similar_work:
        recommendations.append("No similar past work found - proceed with caution")

    # 5. Generate warnings
    warnings = []
    if known_issues:
        warnings.append(f"{len(known_issues)} unresolved issues in affected services")

    if not affected_services:
        warnings.append("Could not identify affected services - may have hidden dependencies")

    # 6. Estimate effort
    if similar_work and similar_work[0].get("time_taken"):
        estimated_effort = similar_work[0]["time_taken"]
    else:
        estimated_effort = "Unknown (no similar past work)"

    return InvestigationResponse(
        similar_past_work=similar_work[:3],  # Top 3
        affected_services=affected_services,
        known_issues=known_issues,
        recommended_approach=recommendations,
        warnings=warnings,
        estimated_effort=estimated_effort
    )


@app.get("/health")
async def health():
    """Health check"""
    try:
        async with driver.session() as session:
            await session.run("RETURN 1")
        neo4j_connected = True
    except:
        neo4j_connected = False

    return {
        "status": "healthy" if neo4j_connected else "degraded",
        "neo4j_connected": neo4j_connected
    }


@app.get("/")
async def root():
    return {
        "service": "Trinity Investigation API",
        "version": "0.1.0",
        "endpoints": {
            "investigate": "POST /api/investigate",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }
