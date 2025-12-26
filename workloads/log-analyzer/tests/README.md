# Testing Guide

This directory contains behavior-driven tests for the log analyzer service, following the principles outlined in `docs/test-principles.md`.

## Test Organization

We have two types of tests:

### 🚀 Unit Tests (Fast, Mocked Dependencies)
- **File**: `test_unit.py`
- **Fixtures**: Use `test_client` with `MockTransport`
- **Purpose**: Verify API behavior with predictable, fast test doubles
- **When to use**: Default for TDD, regression testing, CI/CD
- **Organization**: Tests are grouped by endpoint with clear section markers

### 🌐 Integration Tests (Real Services)
- **File**: `test_integration.py`
- **Fixtures**: Use `integration_client` with real HTTP calls
- **Purpose**: Verify end-to-end behavior with actual Loki and llama.cpp
- **When to use**: Before releases, after infrastructure changes, debugging
- **Note**: Each test is comprehensive and validates multiple aspects (status, structure, LLM output, limits, filters) in a single test run for efficiency

## Running Tests

### From Repository Root (Recommended)

Use these `just` commands from anywhere in the repo:

```bash
# Run unit tests (fast, default)
just test

# Run integration tests (requires 'just dev' running)
just test-int

# Run all tests (unit + integration)
just test-all
```

### From workloads/log-analyzer Directory

If you're already in the `workloads/log-analyzer` directory:

```bash
# Fast feedback loop - runs in ~0.1s
uv run pytest

# Explicit unit tests
uv run pytest -m unit -v

# Integration tests (requires port-forwarding)
uv run pytest -m integration -v

# All tests
uv run pytest -m "" -v
```

## Integration Test Prerequisites

Integration tests require real Kubernetes services to be accessible:

1. **Start port-forwarding** (from repo root):
   ```bash
   just dev
   ```
   This forwards:
   - Loki: `localhost:3100`
   - llama.cpp: `localhost:8080`

2. **Verify services are ready**:
   ```bash
   curl http://localhost:3100/ready
   curl http://localhost:8080/v1/models
   ```

3. **Run integration tests** (from repo root):
   ```bash
   just test-int
   ```

### What if services aren't running?

Integration tests will **automatically skip** with a helpful message:
```
SKIPPED [1] tests/conftest.py:246: Loki not available at http://localhost:3100.
Run 'just dev' to start port-forwarding.
```

### Why consolidate integration tests?

Integration tests hit real services and are slow (~10-40s each). We consolidate related assertions into comprehensive tests because:
- ✅ Reduces total test time (fewer service calls)
- ✅ Less code duplication and maintenance
- ✅ Tests complete user workflows, not isolated behaviors
- ✅ Multiple assertions about the same integration scenario make sense

This differs from unit tests, which should remain focused and test one behavior each.

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
def test_new_endpoint_behavior(test_client):
    """
    BEHAVIOR: What the API should do.

    Why this matters to users.
    """
    response = test_client.post("/v1/endpoint", json={...})
    assert response.status_code == 200

    # Unit tests should focus on ONE specific behavior
    data = response.json()
    assert "expected_field" in data
```

### Adding an Integration Test
```python
import pytest
from datetime import datetime, UTC

@pytest.mark.integration
def test_new_endpoint_integration(integration_client):
    """
    INTEGRATION: Verify /v1/new-endpoint works end-to-end.

    This test verifies:
    - Status codes (200/404)
    - Response structure
    - Data validation
    - Any filters or parameters
    """
    response = integration_client.post("/v1/endpoint", json={...})

    assert response.status_code in [200, 404], \
        f"Expected 200 or 404, got {response.status_code}: {response.text}"

    if response.status_code == 200:
        data = response.json()
        # Multiple related assertions are fine for integration tests
        assert "field1" in data
        assert "field2" in data
        assert len(data["items"]) <= limit
```

## Test Philosophy

From `docs/test-principles.md`:

✅ **Focus on behavior** - Test what the API does, not how it does it
✅ **From user perspective** - Tests are your API consumers
✅ **Minimal mocking** - Use test doubles (MockTransport) or real services
✅ **Enable refactoring** - Internal changes shouldn't break tests

### Example: Why Two Test Types?

**Unit Test** (`test_unit.py`):
- Verifies: Individual behaviors like "POST /v1/analyze returns JSON structure"
- Uses: Mocked Loki and LLM responses
- Speed: ~0.01s per test
- Assertions: Focused on ONE specific behavior per test
- Organization: Grouped by endpoint in single file
- When: Every code change, TDD loop, CI pipeline

**Integration Test** (`test_integration.py`):
- Verifies: "Full pipeline works with real Loki and llama.cpp"
- Uses: Actual K8s services via port-forward
- Speed: ~10-40s per test (depends on LLM)
- Assertions: Comprehensive, covering multiple aspects in one test
- When: Before deploys, debugging issues, validating infrastructure

Both follow behavior-driven principles - they differ in dependencies and assertion scope.

## Troubleshooting

### "Module not found" errors
```bash
# From repo root
just test

# Or navigate to the workload
cd workloads/log-analyzer
uv run pytest
```

### Integration tests always skip
```bash
# Check if port-forwarding is running
ps aux | grep "port-forward"

# Restart port-forwarding
just stop
just dev
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
  run: just test

# Integration tests (requires K8s cluster)
- name: Run integration tests
  run: |
    just dev &  # Start port-forwarding in background
    sleep 5     # Wait for services to be ready
    just test-int
```

Or using direct `uv run pytest` commands:

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
