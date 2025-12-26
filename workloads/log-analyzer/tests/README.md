# Testing Guide

This directory contains behavior-driven tests for the log analyzer service, following the principles outlined in `docs/test-principles.md`.

## Test Organization

We have two types of tests:

### 🚀 Unit Tests (Fast, Mocked Dependencies)
- **Files**: `test_analyze.py`, `test_analyze_stream.py`
- **Fixtures**: Use `test_client` with `MockTransport`
- **Purpose**: Verify API behavior with predictable, fast test doubles
- **When to use**: Default for TDD, regression testing, CI/CD

### 🌐 Integration Tests (Real Services)
- **Files**: `test_analyze_integration.py`, `test_analyze_stream_integration.py`
- **Fixtures**: Use `integration_client` with real HTTP calls
- **Purpose**: Verify end-to-end behavior with actual Loki and llama.cpp
- **When to use**: Before releases, after infrastructure changes, debugging

## Running Tests

### Run Unit Tests Only (Default)
```bash
# Fast feedback loop - runs in ~0.1s
uv run pytest

# Explicit
uv run pytest -m unit -v
```

### Run Integration Tests Only
```bash
# Prerequisites: Start port-forwarding first!
make dev

# In another terminal
uv run pytest -m integration -v
```

### Run All Tests
```bash
# Start services first
make dev

# Run everything (unit + integration)
uv run pytest -m "" -v
```

## Integration Test Prerequisites

Integration tests require real Kubernetes services to be accessible:

1. **Start port-forwarding**:
   ```bash
   make dev
   ```
   This forwards:
   - Loki: `localhost:3100`
   - llama.cpp: `localhost:8080`

2. **Verify services are ready**:
   ```bash
   curl http://localhost:3100/ready
   curl http://localhost:8080/v1/models
   ```

3. **Run integration tests**:
   ```bash
   uv run pytest -m integration -v
   ```

### What if services aren't running?

Integration tests will **automatically skip** with a helpful message:
```
SKIPPED [1] tests/conftest.py:246: Loki not available at http://localhost:3100.
Run 'make dev' to start port-forwarding.
```

## Test Markers

Configured in `pyproject.toml`:

- `@pytest.mark.unit` - Fast tests with mocked dependencies
- `@pytest.mark.integration` - Tests requiring real services

## Writing New Tests

### Adding a Unit Test
```python
import pytest
from datetime import datetime, UTC

@pytest.mark.unit
def test_new_behavior(test_client):
    """BEHAVIOR: What the API should do."""
    response = test_client.post("/v1/endpoint", json={...})
    assert response.status_code == 200
```

### Adding an Integration Test
```python
import pytest
from datetime import datetime, UTC

@pytest.mark.integration
def test_new_integration(integration_client):
    """INTEGRATION: Verify with real services."""
    response = integration_client.post("/v1/endpoint", json={...})
    assert response.status_code == 200
```

## Test Philosophy

From `docs/test-principles.md`:

✅ **Focus on behavior** - Test what the API does, not how it does it
✅ **From user perspective** - Tests are your API consumers
✅ **Minimal mocking** - Use test doubles (MockTransport) or real services
✅ **Enable refactoring** - Internal changes shouldn't break tests

### Example: Why Two Test Types?

**Unit Test** (`test_analyze.py`):
- Verifies: "POST /v1/analyze returns log_count, analysis, logs"
- Uses: Mocked Loki and LLM responses
- Speed: ~0.01s per test
- When: Every code change, TDD loop, CI pipeline

**Integration Test** (`test_analyze_integration.py`):
- Verifies: "Full pipeline works with real Loki and llama.cpp"
- Uses: Actual K8s services via port-forward
- Speed: ~2-5s per test (depends on LLM)
- When: Before deploys, debugging issues, validating infrastructure

Both follow the same behavior-driven principles - they just differ in their dependencies.

## Troubleshooting

### "Module not found" errors
```bash
cd /path/to/log-analyzer
uv run pytest
```

### Integration tests always skip
```bash
# Check if port-forwarding is running
ps aux | grep "port-forward"

# Restart port-forwarding
make stop
make dev
```

### Tests fail after code changes
Good! The tests caught a behavior change. Options:
1. Fix the code if behavior should be preserved
2. Update the test if behavior intentionally changed

### Need more debug output
```bash
# Show print statements and full diffs
uv run pytest -vv -s

# Show why tests were skipped
uv run pytest -v -rs
```

## CI/CD Integration

Example GitHub Actions:

```yaml
# Unit tests (fast, no dependencies)
- name: Run unit tests
  run: |
    cd workloads/log-analyzer
    uv run pytest -m unit

# Integration tests (requires K8s cluster)
- name: Run integration tests
  run: |
    kubectl port-forward svc/loki 3100:3100 &
    kubectl port-forward svc/llama-cpp 8080:8080 &
    cd workloads/log-analyzer
    uv run pytest -m integration
```
