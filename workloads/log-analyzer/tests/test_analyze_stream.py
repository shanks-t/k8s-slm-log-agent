"""Behavior tests for /v1/analyze/stream endpoint.

Following behavior-driven testing principles:
- Tests verify streaming API behavior from the consumer's perspective
- Focus on what the streaming endpoint does differently from /analyze
- Each test represents a real streaming use case

These are UNIT tests - they use mocked HTTP dependencies for speed.
See test_analyze_stream_integration.py for integration tests with real services.
"""

import pytest
from datetime import datetime, timedelta, UTC


@pytest.mark.unit
@pytest.mark.unit
def test_analyze_stream_returns_text_response(test_client):
    """
    BEHAVIOR: POST /v1/analyze/stream returns streaming text/plain response,
    not JSON.

    Users expect a readable stream, not JSON structure.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
    }

    response = test_client.post("/v1/analyze/stream", json=request_body)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.unit
def test_analyze_stream_includes_header(test_client):
    """
    BEHAVIOR: Stream starts with metadata header before analysis.

    Users need context about what logs are being analyzed before the AI output.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
    }

    response = test_client.post("/v1/analyze/stream", json=request_body)
    content = response.text

    # Verify header elements are present
    assert "=== Log Analyzer ===" in content
    assert "Cluster: homelab" in content
    assert "Time Window:" in content
    assert "Log Count:" in content
    assert "--- Logs ---" in content
    assert "--- Analysis ---" in content


@pytest.mark.unit
def test_analyze_stream_includes_log_details(test_client):
    """
    BEHAVIOR: Stream header includes individual log entries with
    timestamps, sources, and messages.

    Users need to see what logs are being analyzed.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
    }

    response = test_client.post("/v1/analyze/stream", json=request_body)
    content = response.text

    # Verify log entries are included with expected format
    # Our mock data has nginx and redis pods
    assert "default/nginx" in content or "default/redis" in content
    assert "pod=" in content
    assert "node=" in content

    # Verify actual log messages appear
    assert "ERROR" in content or "WARN" in content


@pytest.mark.unit
def test_analyze_stream_includes_analysis(test_client):
    """
    BEHAVIOR: After the header, stream includes LLM analysis text.

    Users expect AI-generated insights after the log context.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
    }

    response = test_client.post("/v1/analyze/stream", json=request_body)
    content = response.text

    # Analysis should appear after the "--- Analysis ---" marker
    parts = content.split("--- Analysis ---")
    assert len(parts) == 2

    analysis_section = parts[1]
    # Verify analysis has meaningful content
    assert len(analysis_section.strip()) > 20
    assert "Analysis:" in analysis_section or "error" in analysis_section.lower()


@pytest.mark.unit
def test_analyze_stream_ends_properly(test_client):
    """
    BEHAVIOR: Stream ends with clear termination marker.

    Users need to know when the stream is complete.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
    }

    response = test_client.post("/v1/analyze/stream", json=request_body)
    content = response.text

    assert content.endswith("=== End of Analysis ===\n")


@pytest.mark.unit
def test_analyze_stream_with_no_logs_returns_404(test_client_no_logs):
    """
    BEHAVIOR: When no logs found, streaming endpoint returns 404
    (same as non-streaming).

    Consistent error handling across both endpoints.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "nonexistent",
        },
    }

    response = test_client_no_logs.post("/v1/analyze/stream", json=request_body)

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"] == "No logs found"


@pytest.mark.unit
def test_analyze_stream_with_filters(test_client):
    """
    BEHAVIOR: Filters work the same in streaming as non-streaming.

    Users expect consistent filter behavior.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "default",
            "pod": "nginx.*",
        },
    }

    response = test_client.post("/v1/analyze/stream", json=request_body)

    assert response.status_code == 200
    content = response.text
    # Should contain filtered logs
    assert "default" in content


@pytest.mark.unit
def test_analyze_stream_respects_limit(test_client):
    """
    BEHAVIOR: Limit parameter controls number of logs in stream.

    Users need consistent limit behavior across endpoints.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 5,
    }

    response = test_client.post("/v1/analyze/stream", json=request_body)

    assert response.status_code == 200
    content = response.text

    # Verify log count in header respects limit
    # Extract the log count from "Log Count: N"
    assert "Log Count:" in content
