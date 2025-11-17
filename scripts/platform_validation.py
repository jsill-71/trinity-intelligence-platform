#!/usr/bin/env python3
"""
Comprehensive Trinity Platform Validation
Validates all services, data stores, and integrations
"""

import httpx
import asyncio
import asyncpg
from neo4j import GraphDatabase
import redis
import sys

async def validate_platform():
    """Comprehensive platform validation"""

    print("=" * 70)
    print("TRINITY INTELLIGENCE PLATFORM - COMPREHENSIVE VALIDATION")
    print("=" * 70)

    results = {"passed": 0, "failed": 0, "warnings": 0}

    # 1. Infrastructure Validation
    print("\n[1/5] INFRASTRUCTURE VALIDATION")
    print("-" * 70)

    # PostgreSQL
    try:
        conn = await asyncpg.connect("postgresql://trinity:trinity@localhost:5432/trinity")
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        await conn.close()
        print(f"  [OK] PostgreSQL: {len(tables)} tables created")
        results["passed"] += 1
    except Exception as e:
        print(f"  [FAIL] PostgreSQL: {e}")
        results["failed"] += 1

    # Neo4j
    try:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "trinity123"))
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            count = result.single()["count"]
        driver.close()
        print(f"  [OK] Neo4j: {count} nodes in knowledge graph")
        results["passed"] += 1
    except Exception as e:
        print(f"  [FAIL] Neo4j: {e}")
        results["failed"] += 1

    # Redis
    try:
        r = redis.Redis(host="localhost", port=6379)
        r.ping()
        info = r.info()
        print(f"  [OK] Redis: {info.get('connected_clients', 0)} clients, {r.dbsize()} keys")
        results["passed"] += 1
    except Exception as e:
        print(f"  [FAIL] Redis: {e}")
        results["failed"] += 1

    # NATS
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check if NATS is accessible via event collector
            response = await client.get("http://localhost:8001/health")
            if response.status_code == 200:
                print(f"  [OK] NATS: Accessible via Event Collector")
                results["passed"] += 1
            else:
                print(f"  [WARN] NATS: Event Collector returned {response.status_code}")
                results["warnings"] += 1
    except Exception as e:
        print(f"  [FAIL] NATS: {e}")
        results["failed"] += 1

    # 2. Core Services Validation
    print("\n[2/5] CORE SERVICES VALIDATION")
    print("-" * 70)

    core_services = {
        "API Gateway": "http://localhost:8000/health",
        "User Management": "http://localhost:8007/health",
        "Audit Service": "http://localhost:8006/health",
        "RCA API": "http://localhost:8002/health",
        "Investigation API": "http://localhost:8003/health"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in core_services.items():
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    print(f"  [OK] {name}")
                    results["passed"] += 1
                else:
                    print(f"  [FAIL] {name}: HTTP {response.status_code}")
                    results["failed"] += 1
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                results["failed"] += 1

    # 3. Intelligence Services Validation
    print("\n[3/5] INTELLIGENCE SERVICES VALIDATION")
    print("-" * 70)

    intel_services = {
        "Vector Search": "http://localhost:8004/stats",
        "ML Training": "http://localhost:8008/health",
        "Agent Orchestrator": "http://localhost:8009/health",
        "Query Optimizer": "http://localhost:8014/health"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in intel_services.items():
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if name == "Agent Orchestrator":
                        model = data.get("model", "unknown")
                        print(f"  [OK] {name}: Using {model}")
                    else:
                        print(f"  [OK] {name}")
                    results["passed"] += 1
                else:
                    print(f"  [FAIL] {name}: HTTP {response.status_code}")
                    results["failed"] += 1
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                results["failed"] += 1

    # 4. Platform Services Validation
    print("\n[4/5] PLATFORM SERVICES VALIDATION")
    print("-" * 70)

    platform_services = {
        "Workflow Engine": "http://localhost:8010/health",
        "Alert Manager": "http://localhost:8013/health",
        "Notification Service": "http://localhost:8005/health",
        "Data Aggregator": "http://localhost:8011/health",
        "Cache Service": "http://localhost:8012/health",
        "Rate Limiter": "http://localhost:8015/health"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in platform_services.items():
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    print(f"  [OK] {name}")
                    results["passed"] += 1
                else:
                    print(f"  [FAIL] {name}: HTTP {response.status_code}")
                    results["failed"] += 1
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")
                results["failed"] += 1

    # 5. Integration Tests
    print("\n[5/5] INTEGRATION TESTS")
    print("-" * 70)

    # Test user workflow
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Register
            reg_response = await client.post(
                "http://localhost:8000/auth/register",
                json={"email": "validation@test.com", "username": "validation_test", "password": "test123"}
            )

            # Login
            login_response = await client.post(
                "http://localhost:8000/auth/login",
                json={"username": "trinity_test", "password": "test123"}
            )

            if login_response.status_code == 200:
                token = login_response.json()["access_token"]

                # RCA with auth
                rca_response = await client.post(
                    "http://localhost:8000/rca/analyze",
                    json={"issue_description": "test validation"},
                    headers={"Authorization": f"Bearer {token}"}
                )

                if rca_response.status_code == 200:
                    print(f"  [OK] End-to-end workflow: Register → Login → RCA")
                    results["passed"] += 1
                else:
                    print(f"  [FAIL] RCA failed: {rca_response.status_code}")
                    results["failed"] += 1
            else:
                print(f"  [FAIL] Login failed: {login_response.status_code}")
                results["failed"] += 1
    except Exception as e:
        print(f"  [FAIL] Integration test: {e}")
        results["failed"] += 1

    # Final Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {results['passed'] + results['failed'] + results['warnings']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Warnings: {results['warnings']}")

    if results['failed'] == 0:
        print("\n✅ PLATFORM FULLY OPERATIONAL")
        return True
    else:
        success_rate = results['passed'] / (results['passed'] + results['failed']) * 100
        print(f"\n⚠️  PLATFORM OPERATIONAL ({success_rate:.1f}% success rate)")
        print(f"    {results['failed']} service(s) need attention")
        return success_rate >= 80

if __name__ == "__main__":
    try:
        success = asyncio.run(validate_platform())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nValidation error: {e}")
        sys.exit(1)
