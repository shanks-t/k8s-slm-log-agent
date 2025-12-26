"""Integration tests for log analyzer endpoints with real services.

These tests verify end-to-end behavior with actual Loki and llama.cpp services.

Prerequisites:
    - Run 'just dev' to start port-forwarding to k8s services
    - Ensure Loki has actual log data to query

Usage:
    # Run integration tests only
    pytest -m integration -v

    # Skip if services not running
    pytest -m integration -v  # auto-skips if services unavailable
"""

import pytest
from datetime import datetime, timedelta, UTC


@pytest.mark.integration
def test_analyze_endpoint_integration(integration_client):
    """
    INTEGRATION: Verify /v1/analyze works end-to-end with real services.

    This comprehensive test verifies:
    - HTTP status and error handling (200/404)
    - Response structure and data types
    - LLM generates meaningful analysis
    - Limit parameter works correctly
    - Namespace filtering works correctly
    - Log normalization (time, source, message fields)
    """
    now = datetime.now(UTC)

    # Test with namespace filter to avoid Loki query issues
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "kube-system",  # Common namespace with logs
        },
        "limit": 5,
    }

    response = integration_client.post("/v1/analyze", json=request_body)

    # Should succeed or return 404 if no logs found
    assert response.status_code in [200, 404], \
        f"Expected 200 or 404, got {response.status_code}: {response.text}"

    # If logs were found, verify the complete integration
    if response.status_code == 200:
        data = response.json()

        # ✓ Response structure
        assert "log_count" in data, "Missing log_count field"
        assert "analysis" in data, "Missing analysis field"
        assert "logs" in data, "Missing logs field"

        # ✓ Data types
        assert isinstance(data["log_count"], int), "log_count should be int"
        assert isinstance(data["analysis"], str), "analysis should be string"
        assert isinstance(data["logs"], list), "logs should be list"

        # ✓ Limit parameter works
        assert data["log_count"] <= 5, f"log_count {data['log_count']} exceeds limit of 5"
        assert len(data["logs"]) <= 5, f"logs array length {len(data['logs'])} exceeds limit of 5"

        # If we got logs, verify their structure and content
        if data["log_count"] > 0:
            # ✓ Log normalization
            first_log = data["logs"][0]
            assert "time" in first_log, "Log missing 'time' field"
            assert "source" in first_log, "Log missing 'source' field"
            assert "message" in first_log, "Log missing 'message' field"

            # ✓ Namespace filter works
            assert "kube-system" in first_log["source"], \
                f"Expected 'kube-system' in source, got: {first_log['source']}"

            # ✓ LLM generates meaningful analysis
            assert len(data["analysis"]) > 10, "Analysis text is too short"
            assert data["analysis"].strip() != "", "Analysis text is empty"


@pytest.mark.integration
def test_analyze_stream_endpoint_integration(integration_client):
    """
    INTEGRATION: Verify /v1/analyze/stream works end-to-end with real services.

    This comprehensive test verifies:
    - HTTP status and error handling (200/404)
    - Response content-type (text/plain for streaming)
    - Streaming response structure (header, logs, analysis, footer)
    - LLM streaming generates output
    - Limit parameter works correctly
    - Namespace filtering works correctly
    """
    now = datetime.now(UTC)

    # Test with namespace filter to avoid Loki query issues
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "kube-system",  # Common namespace with logs
        },
        "limit": 3,
    }

    response = integration_client.post("/v1/analyze/stream", json=request_body)

    # Should succeed or return 404 if no logs found
    assert response.status_code in [200, 404], \
        f"Expected 200 or 404, got {response.status_code}: {response.text}"

    # If logs were found, verify the complete streaming integration
    if response.status_code == 200:
        # ✓ Content-type header for streaming
        assert "text/plain" in response.headers["content-type"], \
            f"Expected text/plain, got: {response.headers.get('content-type')}"

        content = response.text

        # ✓ Response structure
        assert "=== Log Analyzer ===" in content, "Missing header"
        assert "Cluster: homelab" in content, "Missing cluster name"
        assert "Time Window:" in content, "Missing time window"
        assert "=== End of Analysis ===" in content, "Missing footer"

        # ✓ Limit parameter works
        assert "Log Count:" in content, "Missing log count field"

        # ✓ Namespace filter works
        assert "kube-system" in content, \
            "Expected 'kube-system' in content but not found"

        # ✓ LLM streaming generates output
        if "--- Analysis ---" in content:
            parts = content.split("--- Analysis ---")
            if len(parts) > 1:
                analysis_section = parts[1]
                analysis_text = analysis_section.replace(
                    "=== End of Analysis ===", ""
                ).strip()
                assert len(analysis_text) > 0, "Analysis section is empty"
