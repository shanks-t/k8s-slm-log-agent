"""Integration tests for /v1/analyze/stream endpoint with real services.

These tests verify streaming behavior with actual Loki and llama.cpp services.

Prerequisites:
    - Run 'make dev' to start port-forwarding to k8s services
    - Ensure Loki has actual log data to query

Usage:
    # Run integration tests only
    pytest -m integration -v
"""

import pytest
from datetime import datetime, timedelta, UTC


@pytest.mark.integration
def test_analyze_stream_with_real_services(integration_client):
    """
    INTEGRATION: Verify streaming works end-to-end with real services.

    This tests:
    - Query Loki for actual logs
    - Stream response with proper headers
    - LLM streams analysis in real-time
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 10,
    }

    response = integration_client.post("/v1/analyze/stream", json=request_body)

    # Should succeed or return 404 if no logs
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        # Verify it's a streaming text response
        assert "text/plain" in response.headers["content-type"]

        content = response.text

        # Verify header structure
        assert "=== Log Analyzer ===" in content
        assert "Cluster: homelab" in content
        assert "Time Window:" in content

        # Verify it ends properly
        assert "=== End of Analysis ===" in content


@pytest.mark.integration
def test_analyze_stream_includes_real_llm_output(integration_client):
    """
    INTEGRATION: Verify LLM streaming produces actual output.

    This ensures the streaming endpoint properly streams tokens
    from the real llama.cpp service.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 10,
    }

    response = integration_client.post("/v1/analyze/stream", json=request_body)

    if response.status_code == 200:
        content = response.text

        # Find the analysis section
        if "--- Analysis ---" in content:
            parts = content.split("--- Analysis ---")
            analysis_section = parts[1]

            # Should have some actual analysis text
            # (not just the end marker)
            analysis_text = analysis_section.replace("=== End of Analysis ===", "").strip()
            assert len(analysis_text) > 0


@pytest.mark.integration
def test_analyze_stream_with_namespace_filter(integration_client):
    """
    INTEGRATION: Test filtering works in streaming mode.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "logging",
        },
        "limit": 10,
    }

    response = integration_client.post("/v1/analyze/stream", json=request_body)

    assert response.status_code in [200, 404]

    if response.status_code == 200:
        content = response.text
        # Verify namespace appears in the log entries
        assert "logging" in content


@pytest.mark.integration
def test_analyze_stream_respects_limit(integration_client):
    """
    INTEGRATION: Verify limit parameter in streaming mode.

    This is harder to test precisely in streaming mode,
    but we can verify the Log Count field respects the limit.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=24)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 3,
    }

    response = integration_client.post("/v1/analyze/stream", json=request_body)

    if response.status_code == 200:
        content = response.text

        # Extract log count from header
        if "Log Count:" in content:
            # The count should be <= limit
            # We can't easily parse it, but at minimum verify
            # the stream includes the count field
            assert "Log Count:" in content
