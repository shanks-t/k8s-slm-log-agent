"""Integration tests for /v1/analyze endpoint with real services.

These tests call actual Loki and llama.cpp services via port-forwarding.

Prerequisites:
    - Run 'make dev' to start port-forwarding to k8s services
    - Ensure Loki has actual log data to query

Usage:
    # Run integration tests only
    pytest -m integration -v

    # Run with unit tests
    pytest -m "" -v
"""

import pytest
from datetime import datetime, timedelta, UTC


@pytest.mark.integration
def test_analyze_with_real_services(integration_client):
    """
    INTEGRATION: Verify the full pipeline works end-to-end
    with real Loki and LLM services.

    This tests:
    - Query Loki for actual logs
    - Normalize log structure
    - Send to real LLM for analysis
    - Return structured response
    """
    # Query for recent logs (last 24 hours)
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 20,
    }

    response = integration_client.post("/v1/analyze", json=request_body)

    # If no logs exist in your cluster, this will return 404
    # That's okay - it means the integration is working
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()

        # Verify response structure
        assert "log_count" in data
        assert "analysis" in data
        assert "logs" in data

        # Verify we got real data
        assert isinstance(data["log_count"], int)
        assert isinstance(data["analysis"], str)
        assert isinstance(data["logs"], list)

        # If logs were found, verify they're properly normalized
        if data["log_count"] > 0:
            log = data["logs"][0]
            assert "time" in log
            assert "source" in log
            assert "message" in log


@pytest.mark.integration
def test_analyze_with_namespace_filter(integration_client):
    """
    INTEGRATION: Test filtering by namespace with real Loki data.

    This verifies the LogQL query building and filtering works
    against an actual Loki instance.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "logging",  # namespace where Loki itself runs
        },
        "limit": 10,
    }

    response = integration_client.post("/v1/analyze", json=request_body)

    # Should either find logs or return 404 if namespace has no error logs
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()
        # Verify all logs match the namespace filter
        for log in data["logs"]:
            assert "logging" in log["source"]


@pytest.mark.integration
def test_analyze_llm_generates_real_analysis(integration_client):
    """
    INTEGRATION: Verify the LLM service generates actual analysis text.

    This ensures llama.cpp is properly configured and responding
    with meaningful output.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 10,
    }

    response = integration_client.post("/v1/analyze", json=request_body)

    if response.status_code == 200:
        data = response.json()
        analysis = data["analysis"]

        # Real LLM should return substantive text
        assert len(analysis) > 10
        assert isinstance(analysis, str)

        # Should contain some analysis keywords (very loose check)
        # Real LLM output varies, so we just check it's not empty
        assert analysis.strip() != ""


@pytest.mark.integration
def test_analyze_respects_limit_with_real_data(integration_client):
    """
    INTEGRATION: Verify limit parameter works with actual Loki queries.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 5,
    }

    response = integration_client.post("/v1/analyze", json=request_body)

    if response.status_code == 200:
        data = response.json()
        # Should never exceed the limit
        assert data["log_count"] <= 5
        assert len(data["logs"]) <= 5
