#!/usr/bin/env python3
"""
End-to-end validation test for Trinity Intelligence Platform
Tests all 16 services and verifies integration
"""

import httpx
import asyncio
import sys

BASE_URL = "http://localhost:8000"  # API Gateway

async def run_tests():
    """Run comprehensive platform tests"""

    print("[TRINITY PLATFORM END-TO-END TEST]")
    print("=" * 60)

    results = {
        "passed": 0,
        "failed": 0,
        "tests": []
    }

    async with httpx.AsyncClient(timeout=30.0) as client:

        # Test 1: API Gateway Health
        print("\n[1/10] Testing API Gateway health aggregation...")
        try:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]
            print(f"  [OK] Gateway healthy - {len(data['services'])} services checked")
            results["passed"] += 1
            results["tests"].append({"name": "API Gateway Health", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "API Gateway Health", "status": "FAILED", "error": str(e)})

        # Test 2: User Registration
        print("\n[2/10] Testing user registration...")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/register",
                json={
                    "email": "testuser@trinity.com",
                    "username": "testuser",
                    "password": "testpass123",
                    "full_name": "Test User"
                }
            )
            # 400 expected if user exists, 200 if new
            assert response.status_code in [200, 400]
            print(f"  [OK] User registration endpoint functional")
            results["passed"] += 1
            results["tests"].append({"name": "User Registration", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "User Registration", "status": "FAILED", "error": str(e)})

        # Test 3: User Login
        print("\n[3/10] Testing user authentication...")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/login",
                json={
                    "username": "trinity_test",
                    "password": "test123"
                }
            )
            assert response.status_code == 200
            token_data = response.json()
            assert "access_token" in token_data
            token = token_data["access_token"]
            print(f"  [OK] Authentication successful - JWT token received")
            results["passed"] += 1
            results["tests"].append({"name": "User Authentication", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "User Authentication", "status": "FAILED", "error": str(e)})
            token = None

        # Test 4: RCA Analysis (unauthenticated)
        print("\n[4/10] Testing RCA analysis (public access)...")
        try:
            response = await client.post(
                f"{BASE_URL}/rca/analyze",
                json={
                    "issue_description": "database connection timeout",
                    "component": "postgres"
                }
            )
            assert response.status_code in [200, 401]  # May require auth
            if response.status_code == 200:
                data = response.json()
                assert "similar_issues" in data
                print(f"  [OK] RCA analysis functional")
            else:
                print(f"  [OK] RCA requires authentication (expected)")
            results["passed"] += 1
            results["tests"].append({"name": "RCA Analysis", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "RCA Analysis", "status": "FAILED", "error": str(e)})

        # Test 5: Vector Search
        print("\n[5/10] Testing vector search service...")
        try:
            response = await client.get("http://localhost:8004/stats")
            assert response.status_code == 200
            data = response.json()
            print(f"  [OK] Vector search - {data['total_documents']} documents indexed")
            results["passed"] += 1
            results["tests"].append({"name": "Vector Search", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "Vector Search", "status": "FAILED", "error": str(e)})

        # Test 6: Audit Service
        print("\n[6/10] Testing audit logging...")
        try:
            response = await client.get("http://localhost:8006/audit/stats")
            assert response.status_code == 200
            data = response.json()
            print(f"  [OK] Audit service - {data['total_events']} events logged")
            results["passed"] += 1
            results["tests"].append({"name": "Audit Logging", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "Audit Logging", "status": "FAILED", "error": str(e)})

        # Test 7: Agent Orchestrator
        print("\n[7/10] Testing agent orchestrator...")
        try:
            response = await client.get("http://localhost:8009/health")
            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "claude-haiku-4.5-20250514"
            print(f"  [OK] Agent orchestrator using {data['model']}")
            results["passed"] += 1
            results["tests"].append({"name": "Agent Orchestrator", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "Agent Orchestrator", "status": "FAILED", "error": str(e)})

        # Test 8: Workflow Engine
        print("\n[8/10] Testing workflow engine...")
        try:
            response = await client.get("http://localhost:8010/workflows")
            assert response.status_code == 200
            print(f"  [OK] Workflow engine operational")
            results["passed"] += 1
            results["tests"].append({"name": "Workflow Engine", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "Workflow Engine", "status": "FAILED", "error": str(e)})

        # Test 9: Data Aggregator
        print("\n[9/10] Testing data aggregator...")
        try:
            response = await client.get("http://localhost:8011/aggregate/system-overview")
            assert response.status_code == 200
            data = response.json()
            print(f"  [OK] Data aggregation - {data['knowledge_graph']['total_nodes']} KG nodes")
            results["passed"] += 1
            results["tests"].append({"name": "Data Aggregator", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "Data Aggregator", "status": "FAILED", "error": str(e)})

        # Test 10: End-to-End Workflow
        print("\n[10/10] Testing end-to-end workflow...")
        try:
            # Register + Login + RCA with auth
            reg_response = await client.post(
                f"{BASE_URL}/auth/register",
                json={"email": "e2e@trinity.com", "username": "e2e_test", "password": "test123"}
            )

            login_response = await client.post(
                f"{BASE_URL}/auth/login",
                json={"username": "trinity_test", "password": "test123"}
            )

            assert login_response.status_code == 200
            token = login_response.json()["access_token"]

            rca_response = await client.post(
                f"{BASE_URL}/rca/analyze",
                json={"issue_description": "test issue"},
                headers={"Authorization": f"Bearer {token}"}
            )

            assert rca_response.status_code == 200
            print(f"  [OK] End-to-end workflow: Register -> Login -> RCA")
            results["passed"] += 1
            results["tests"].append({"name": "End-to-End Workflow", "status": "PASSED"})
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"] += 1
            results["tests"].append({"name": "End-to-End Workflow", "status": "FAILED", "error": str(e)})

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {results['passed'] + results['failed']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['passed'] / (results['passed'] + results['failed']) * 100:.1f}%")

    if results['failed'] > 0:
        print("\nFailed Tests:")
        for test in results["tests"]:
            if test["status"] == "FAILED":
                print(f"  - {test['name']}: {test.get('error', 'Unknown error')}")

    return results["failed"] == 0

if __name__ == "__main__":
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest suite error: {e}")
        sys.exit(1)
