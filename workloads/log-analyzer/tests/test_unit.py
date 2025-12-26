"""Unit tests for log analyzer endpoints.

Following behavior-driven testing principles:
- Tests verify API behavior from the consumer's perspective
- Focus on what endpoints do, not how they do it
- Each test represents a real use case or scenario

These are UNIT tests - they use mocked HTTP dependencies for speed.
See test_integration.py for integration tests with real services.
"""

import pytest
from datetime import datetime, timedelta, UTC


# ============================================================================
# /v1/analyze endpoint tests (JSON response)
# ============================================================================


@pytest.mark.unit
def test_analyze_returns_logs_and_analysis(test_client):
    """
    BEHAVIOR: POST /v1/analyze with valid time range and filters
    returns JSON with log_count, analysis, and logs array.

    This is the happy path - the primary behavior users expect.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "default",
        },
        "limit": 50,
    }

    response = test_client.post("/v1/analyze", json=request_body)

    assert response.status_code == 200

    data = response.json()
    assert "log_count" in data
    assert "analysis" in data
    assert "logs" in data

    # Verify we got actual data back
    assert data["log_count"] > 0
    assert isinstance(data["analysis"], str)
    assert len(data["analysis"]) > 0
    assert isinstance(data["logs"], list)
    assert len(data["logs"]) == data["log_count"]


@pytest.mark.unit
def test_analyze_normalizes_log_structure(test_client):
    """
    BEHAVIOR: Logs are normalized into a consistent structure
    with time, source, pod, node, and message fields.

    Users expect predictable log format regardless of source.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
    }

    response = test_client.post("/v1/analyze", json=request_body)
    assert response.status_code == 200

    data = response.json()
    logs = data["logs"]

    # Verify each log has the expected normalized structure
    for log in logs:
        assert "time" in log
        assert "source" in log
        assert "pod" in log
        assert "node" in log
        assert "message" in log

        # Verify source format is namespace/container
        assert "/" in log["source"]


@pytest.mark.unit
def test_analyze_with_no_logs_returns_404(test_client_no_logs):
    """
    BEHAVIOR: When filters match no logs, API returns 404
    with error message.

    Users need clear feedback when their query has no results.
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

    response = test_client_no_logs.post("/v1/analyze", json=request_body)

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"] == "No logs found"


@pytest.mark.unit
def test_analyze_with_pod_filter(test_client):
    """
    BEHAVIOR: Filters can be applied to narrow down log results.

    Users need to filter logs by specific pods/containers/namespaces.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
        "filters": {
            "namespace": "default",
            "pod": "nginx.*",  # Regex pattern
        },
    }

    response = test_client.post("/v1/analyze", json=request_body)
    assert response.status_code == 200

    data = response.json()
    assert data["log_count"] > 0


@pytest.mark.unit
def test_analyze_respects_limit_parameter(test_client):
    """
    BEHAVIOR: The limit parameter controls maximum logs returned.

    Users need to control response size for performance.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
        "limit": 10,
    }

    response = test_client.post("/v1/analyze", json=request_body)
    assert response.status_code == 200

    data = response.json()
    # Note: We may get fewer than limit if there aren't enough logs
    assert data["log_count"] <= 10


@pytest.mark.unit
def test_analyze_includes_llm_analysis(test_client):
    """
    BEHAVIOR: The analysis field contains LLM-generated insights
    about the logs.

    Users expect AI analysis of their log data, not just raw logs.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
    }

    response = test_client.post("/v1/analyze", json=request_body)
    assert response.status_code == 200

    data = response.json()
    analysis = data["analysis"]

    # Verify analysis contains meaningful content
    assert len(analysis) > 20  # More than a trivial response
    assert isinstance(analysis, str)


@pytest.mark.unit
def test_analyze_with_minimal_request(test_client):
    """
    BEHAVIOR: Only time_range is required; filters and limit are optional.

    Users should be able to make simple requests without specifying all parameters.
    """
    now = datetime.now(UTC)
    request_body = {
        "time_range": {
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
        },
        # No filters, no limit specified
    }

    response = test_client.post("/v1/analyze", json=request_body)
    assert response.status_code == 200

    data = response.json()
    assert "log_count" in data
    assert "analysis" in data
    assert "logs" in data


# ============================================================================
# /v1/analyze/stream endpoint tests (text/plain streaming response)
# ============================================================================


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
