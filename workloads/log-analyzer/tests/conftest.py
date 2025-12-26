"""Test fixtures for log analyzer tests."""

import json
from datetime import datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

# Constants for service endpoints
LOKI_URL = "http://localhost:3100"
LLAMA_URL = "http://localhost:8080"


class MockTransport(httpx.MockTransport):
    """Custom mock transport that handles both sync and async requests."""

    def __init__(self, handler):
        super().__init__(handler)
        self._handler = handler

    async def handle_async_request(self, request):
        """Handle async requests by calling the sync handler."""
        response = self._handler(request)
        return response


def create_loki_response(logs_data):
    """Helper to create a Loki API response."""
    return httpx.Response(
        status_code=200,
        json={
            "status": "success",
            "data": {
                "resultType": "streams",
                "result": logs_data,
            }
        }
    )


def create_llm_response(content):
    """Helper to create an LLM completion response."""
    return httpx.Response(
        status_code=200,
        json={
            "id": "test-completion",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "llama-3.2-3b-instruct",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": "stop",
                }
            ],
        }
    )


def create_llm_stream_response(content):
    """Helper to create an LLM streaming response."""
    lines = []

    # Split content into chunks
    words = content.split()
    for word in words:
        chunk = {
            "id": "test-stream",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": "llama-3.2-3b-instruct",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": word + " "},
                    "finish_reason": None,
                }
            ],
        }
        lines.append(f"data: {json.dumps(chunk)}\n")

    # Final chunk
    lines.append("data: [DONE]\n")

    return httpx.Response(
        status_code=200,
        content="".join(lines).encode(),
        headers={"content-type": "text/event-stream"},
    )


@pytest.fixture
def sample_loki_logs():
    """Sample Loki log entries for testing."""
    return [
        {
            "stream": {
                "namespace": "default",
                "pod": "nginx-deployment-abc123",
                "container": "nginx",
                "node": "node1",
            },
            "values": [
                ["1703001600000000000", "ERROR: Connection failed to database"],
                ["1703001500000000000", "WARN: Retry attempt 3/5"],
            ],
        },
        {
            "stream": {
                "namespace": "default",
                "pod": "redis-xyz789",
                "container": "redis",
                "node": "node2",
            },
            "values": [
                ["1703001400000000000", "ERROR: Out of memory"],
            ],
        },
    ]


@pytest.fixture
def mock_transport(sample_loki_logs):
    """Mock HTTP transport for Loki and LLM requests."""

    def handler(request: httpx.Request):
        # Handle Loki ready check
        if "/ready" in str(request.url):
            return httpx.Response(status_code=200, json={"status": "ready"})

        # Handle LLM models endpoint
        if "/v1/models" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"data": [{"id": "llama-3.2-3b-instruct"}]}
            )

        # Handle Loki query
        if "/loki/api/v1/query_range" in str(request.url):
            return create_loki_response(sample_loki_logs)

        # Handle LLM completion (non-streaming)
        if "/v1/chat/completions" in str(request.url) and request.method == "POST":
            body = json.loads(request.content)

            # Check if streaming is requested
            if body.get("stream"):
                return create_llm_stream_response(
                    "Analysis: Multiple errors detected. Database connectivity issue in nginx pod. Redis memory exhaustion on node2. Recommend checking DB credentials and increasing Redis memory limits."
                )
            else:
                return create_llm_response(
                    "Analysis: Multiple errors detected. Database connectivity issue in nginx pod. Redis memory exhaustion on node2. Recommend checking DB credentials and increasing Redis memory limits."
                )

        return httpx.Response(status_code=404)

    return MockTransport(handler)


@pytest.fixture
def mock_transport_no_logs():
    """Mock transport that returns no logs from Loki."""

    def handler(request: httpx.Request):
        # Handle health checks
        if "/ready" in str(request.url):
            return httpx.Response(status_code=200, json={"status": "ready"})

        if "/v1/models" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"data": [{"id": "llama-3.2-3b-instruct"}]}
            )

        # Handle Loki query with empty results
        if "/loki/api/v1/query_range" in str(request.url):
            return create_loki_response([])

        return httpx.Response(status_code=404)

    return MockTransport(handler)


@pytest.fixture
def test_client(mock_transport, monkeypatch):
    """FastAPI test client with mocked HTTP dependencies."""
    # Patch httpx.AsyncClient to use our mock transport
    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs['transport'] = mock_transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", mock_async_client)

    # Import after patching to ensure the app uses mocked client
    from log_analyzer.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_client_no_logs(mock_transport_no_logs, monkeypatch):
    """FastAPI test client that returns no logs."""
    original_async_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs['transport'] = mock_transport_no_logs
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", mock_async_client)

    from log_analyzer.main import app

    with TestClient(app) as client:
        yield client


# ==================== Integration Test Fixtures ====================


def check_service_available(url: str, timeout: float = 2.0) -> bool:
    """Check if a service is available at the given URL."""
    try:
        response = httpx.get(url, timeout=timeout)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@pytest.fixture(scope="session")
def validate_loki():
    """Validate that Loki is available via port-forward.

    Skips integration tests if Loki is not reachable.
    Run 'make dev' to start port-forwarding before running integration tests.
    """
    if not check_service_available(f"{LOKI_URL}/ready"):
        pytest.skip(
            f"Loki not available at {LOKI_URL}. "
            "Run 'make dev' to start port-forwarding."
        )


@pytest.fixture(scope="session")
def validate_llama():
    """Validate that llama.cpp is available via port-forward.

    Skips integration tests if LLM service is not reachable.
    Run 'make dev' to start port-forwarding before running integration tests.
    """
    if not check_service_available(f"{LLAMA_URL}/v1/models"):
        pytest.skip(
            f"LLM service not available at {LLAMA_URL}. "
            "Run 'make dev' to start port-forwarding."
        )


@pytest.fixture
def integration_client(validate_loki, validate_llama):
    """FastAPI test client for integration tests with real services.

    This client makes actual HTTP calls to Loki and llama.cpp.
    Requires services to be running via 'make dev'.
    """
    # Import FastAPI and create app WITHOUT lifespan check for tests
    # The lifespan check would fail during test setup if services aren't ready
    from fastapi import FastAPI
    from log_analyzer.main import (
        root,
        health,
        analyze_logs,
        analyze_logs_stream,
    )

    # Create app without lifespan dependency check
    test_app = FastAPI(
        title="Log Analyzer Service",
        description="LLM-powered log analysis and structured extraction",
        version="0.1.0",
    )

    # Register routes
    test_app.get("/")(root)
    test_app.get("/health")(health)
    test_app.post("/v1/analyze")(analyze_logs)
    test_app.post("/v1/analyze/stream")(analyze_logs_stream)

    # Don't use mocks - let the app make real HTTP calls
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client
