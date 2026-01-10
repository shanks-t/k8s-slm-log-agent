# Log Analyzer Migration Guide

**Migrating from Manual OpenTelemetry to LLM Observability SDK**

---

## Overview

This guide walks through migrating the `log-analyzer` service from manual OpenTelemetry instrumentation to the new LLM Observability SDK.

### Migration Benefits

✅ **Cleaner Code** - Replace manual span creation with decorators
✅ **Semantic Attributes** - Standardized LLM-specific attributes
✅ **Backend Flexibility** - Easy to add Arize, MLflow alongside Tempo
✅ **Automatic Nesting** - No manual context propagation
✅ **Future-Proof** - Stable semantic contract, easy upgrades

---

## Before & After

### Before: Manual OpenTelemetry

```python
# Current: pipeline.py
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def analyze_logs_pipeline(time_range, filters, limit):
    with tracer.start_as_current_span("analyze_logs") as span:
        span.set_attribute("namespace", filters.get("namespace"))
        span.set_attribute("log_limit", limit)

        # Query Loki
        with tracer.start_as_current_span("query_loki") as query_span:
            query_span.set_attribute("logql.query", logql)
            results = loki.query(logql)
            query_span.set_attribute("loki.results_count", len(results))

        # Flatten logs
        with tracer.start_as_current_span("flatten_logs") as flatten_span:
            flattened = flatten_logs(results)
            flatten_span.set_attribute("logs.flattened_count", len(flattened))

        # Call LLM
        with tracer.start_as_current_span("call_llm") as llm_span:
            llm_span.set_attribute("llm.model", model)
            llm_span.set_attribute("llm.streaming", True)
            response = llm_client.call(prompt)
            llm_span.set_attribute("llm.tokens_prompt", tokens)

        return response
```

### After: LLM Observability SDK

```python
# New: pipeline.py
from llm_observability import observe

@observe.retriever(
    name="query_loki",
    retriever_type="keyword",
    source="loki"
)
def query_loki(logql: str, limit: int):
    results = loki.query_range(logql, limit=limit)
    # SDK automatically captures query, limit, results_count
    return results

@observe.llm(
    name="analyze_with_llm",
    model=config.llm_model,
    provider="llama-cpp",
    streaming=True
)
def call_llm(prompt: str, temperature: float = 0.3):
    response = llm_client.call(
        prompt=prompt,
        temperature=temperature,
        stream=True
    )
    # SDK automatically captures model, tokens, input/output
    return response

@observe.workflow(name="analyze_logs")
def analyze_logs_pipeline(time_range, filters, limit=15):
    # Build query
    logql = build_logql_query(time_range, filters)

    # Query Loki (automatic nested span)
    logs = query_loki(logql, limit=limit)

    # Process logs
    flattened = flatten_logs(logs)
    normalized = normalize_logs(flattened)

    # Render prompt
    prompt = render_prompt(template_id="k8s_log_analysis_v1",
                          logs=normalized,
                          namespace=filters.get("namespace"))

    # Call LLM (automatic nested span)
    analysis = call_llm(prompt, temperature=0.3)

    return analysis
```

**Key Improvements:**
- 📉 **50% less code** - No manual span management
- 🏷️ **Standardized attributes** - `llm.model`, `llm.usage.tokens`, etc.
- 🔗 **Automatic nesting** - Decorators handle context propagation
- 🎯 **Semantic clarity** - `@observe.llm` is self-documenting

---

## Migration Steps

### Step 1: Add SDK Dependency

**File:** `workloads/log-analyzer/pyproject.toml`

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "llm-observability>=0.1.0",
]
```

**Install:**
```bash
cd workloads/log-analyzer
pip install -e ".[dev]"
```

---

### Step 2: Configure SDK in Observability Module

**File:** `workloads/log-analyzer/src/log_analyzer/observability/__init__.py`

**Before:**
```python
# Current observability/__init__.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

import os

# Initialize tracer provider
resource = Resource(attributes={
    "service.name": os.getenv("LOG_ANALYZER_SERVICE_NAME", "log-analyzer"),
    "service.version": os.getenv("LOG_ANALYZER_SERVICE_VERSION", "unknown"),
    "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "dev"),
})

provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)

# Configure OTLP exporter
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    insecure=True,
)

# Add span processor
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Auto-instrument FastAPI and HTTPx
FastAPIInstrumentor.instrument()
HTTPXClientInstrumentor.instrument()
```

**After:**
```python
# New observability/__init__.py
from llm_observability import observe
from llm_observability.adapters import OTLPAdapter, ArizeAdapter
import os

# Determine backend from environment
backend = os.getenv("OBSERVABILITY_BACKEND", "otlp")

if backend == "arize":
    adapter = ArizeAdapter(
        endpoint=os.getenv("ARIZE_ENDPOINT", "https://phoenix.arize.com:4317"),
        api_key=os.getenv("ARIZE_API_KEY"),
        project_name="log-analyzer"
    )
else:
    # Default: OTLP to Tempo
    adapter = OTLPAdapter(
        endpoint=os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://tempo.logging.svc.cluster.local:4317"
        ),
        protocol="grpc"
    )

# Configure SDK
observe.configure(
    adapter=adapter,
    service_name=os.getenv("LOG_ANALYZER_SERVICE_NAME", "log-analyzer"),
    service_version=os.getenv("LOG_ANALYZER_SERVICE_VERSION", "unknown"),
    deployment_environment=os.getenv("DEPLOYMENT_ENVIRONMENT", "dev")
)

# Note: FastAPI and HTTPx auto-instrumentation remains the same
# (SDK doesn't interfere with existing OTel instrumentation)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

FastAPIInstrumentor.instrument()
HTTPXClientInstrumentor.instrument()
```

---

### Step 3: Refactor `pipeline.py`

**File:** `workloads/log-analyzer/src/log_analyzer/pipeline.py`

**Changes:**

1. **Remove manual tracer import:**
   ```python
   # DELETE THIS
   from opentelemetry import trace
   tracer = trace.get_tracer(__name__)
   ```

2. **Add SDK import:**
   ```python
   from llm_observability import observe
   ```

3. **Refactor `query_loki_logs()` function:**

   **Before:**
   ```python
   def query_loki_logs(loki_url, logql, limit):
       with tracer.start_as_current_span("query_loki") as span:
           span.set_attribute("logql.query", logql)
           span.set_attribute("logql.limit", limit)

           response = httpx.post(...)
           data = response.json()

           span.set_attribute("loki.results_count", len(data["data"]["result"]))
           return data
   ```

   **After:**
   ```python
   @observe.retriever(
       name="query_loki",
       retriever_type="keyword",
       source="loki"
   )
   def query_loki_logs(loki_url: str, logql: str, limit: int):
       response = httpx.post(...)
       data = response.json()

       # SDK automatically captures:
       # - llm.retriever.query (from logql param if captured)
       # - llm.retriever.source ("loki")
       # - llm.retriever.type ("keyword")
       # - We can manually add results_count if needed:
       # observe.current_span().set_attribute("llm.retriever.results_count", len(data["data"]["result"]))

       return data
   ```

4. **Refactor `call_llm()` function:**

   **Before:**
   ```python
   def call_llm(llm_url, model, prompt, max_tokens, temperature, stream=False):
       with tracer.start_as_current_span("call_llm") as span:
           span.set_attribute("llm.model", model)
           span.set_attribute("llm.streaming", stream)
           span.set_attribute("llm.provider", "llama-cpp")

           response = httpx.post(...)
           data = response.json()

           span.set_attribute("llm.tokens_prompt", data["usage"]["prompt_tokens"])
           span.set_attribute("llm.tokens_completion", data["usage"]["completion_tokens"])

           return data
   ```

   **After:**
   ```python
   @observe.llm(
       name="analyze_logs_with_llm",
       model=None,  # Will be set dynamically from config
       provider="llama-cpp",
       streaming=False  # Or True, depending on call
   )
   def call_llm(llm_url: str, model: str, prompt: str, max_tokens: int, temperature: float, stream: bool = False):
       response = httpx.post(...)
       data = response.json()

       # SDK automatically extracts token usage from response
       # (if response has standard "usage" field with prompt_tokens, completion_tokens)

       return data
   ```

   **Note:** If `model` is dynamic, you can either:
   - Option A: Create multiple decorated functions (one per model)
   - Option B: Use context manager instead: `with observe.span("llm.call", name=..., attributes={"llm.model": model})`

5. **Refactor `analyze_logs()` orchestrator:**

   **Before:**
   ```python
   def analyze_logs(time_range, filters, limit):
       with tracer.start_as_current_span("analyze_logs") as span:
           span.set_attribute("namespace", filters.get("namespace"))
           # ... manual span management ...
   ```

   **After:**
   ```python
   @observe.workflow(name="analyze_logs")
   def analyze_logs(time_range: dict, filters: dict, limit: int = 15):
       # No manual span management needed!
       # Decorated functions automatically nest under this workflow span

       logql = build_logql_query(time_range, filters)
       logs = query_loki_logs(loki_url, logql, limit)

       flattened = flatten_logs(logs)
       normalized = normalize_logs(flattened)

       prompt = render_prompt(template_id, normalized, filters)

       analysis = call_llm(llm_url, model, prompt, max_tokens, temperature)

       return analysis
   ```

---

### Step 4: Refactor `main.py` (Optional)

**File:** `workloads/log-analyzer/src/log_analyzer/main.py`

You can optionally decorate the FastAPI endpoint handlers:

```python
from llm_observability import observe

@app.post("/v1/analyze")
@observe.workflow(name="http_analyze_logs")
async def analyze_endpoint(request: AnalyzeRequest):
    # This creates a top-level workflow span
    # All pipeline operations nest under it
    result = analyze_logs(
        time_range=request.time_range,
        filters=request.filters,
        limit=request.limit
    )
    return result
```

**Note:** This is optional since FastAPI auto-instrumentation already creates HTTP spans.

---

### Step 5: Update Tests

**File:** `workloads/log-analyzer/tests/test_pipeline.py`

**Changes:**

1. **Mock the SDK configuration:**
   ```python
   import pytest
   from llm_observability import observe
   from llm_observability.adapters import OTLPAdapter

   @pytest.fixture(autouse=True)
   def configure_observability():
       """Auto-configure SDK for all tests."""
       adapter = OTLPAdapter(endpoint="http://localhost:4317")
       observe.configure(adapter=adapter, service_name="test")
   ```

2. **Verify span attributes:**
   ```python
   def test_query_loki_creates_span(mocker):
       # Mock OTel span recording
       mock_span = mocker.patch("opentelemetry.trace.Span")

       # Call function
       result = query_loki_logs(...)

       # Assert SDK created span with correct attributes
       mock_span.set_attribute.assert_any_call("llm.retriever.source", "loki")
       mock_span.set_attribute.assert_any_call("llm.retriever.type", "keyword")
   ```

---

### Step 6: Update Deployment Configuration

**File:** `workloads/log-analyzer/deployment.yaml`

**Add optional backend selection:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-analyzer
spec:
  template:
    spec:
      containers:
      - name: log-analyzer
        env:
        # Existing env vars...

        # NEW: Backend selection (optional)
        - name: OBSERVABILITY_BACKEND
          value: "otlp"  # Options: "otlp", "arize", "mlflow"

        # NEW: Arize configuration (if using Arize)
        # - name: ARIZE_ENDPOINT
        #   value: "https://phoenix.arize.com:4317"
        # - name: ARIZE_API_KEY
        #   valueFrom:
        #     secretKeyRef:
        #       name: arize-credentials
        #       key: api-key
```

---

### Step 7: Deploy and Validate

1. **Build new image:**
   ```bash
   cd workloads/log-analyzer
   docker build -t log-analyzer:migration .
   ```

2. **Update Kustomization:**
   ```bash
   # Update image tag in deployment.yaml or kustomization.yaml
   kubectl set image deployment/log-analyzer log-analyzer=log-analyzer:migration -n log-analyzer
   ```

3. **Validate spans in Grafana:**
   - Navigate to Grafana → Explore → Tempo
   - Search for traces from `log-analyzer` service
   - Verify new span structure:
     ```
     span: llm.workflow (analyze_logs)
     ├─ span: llm.retriever (query_loki)
     │  ├─ llm.retriever.source: "loki"
     │  └─ llm.retriever.type: "keyword"
     └─ span: llm.call (analyze_logs_with_llm)
        ├─ llm.model: "llama-3.2-3b-instruct"
        ├─ llm.provider: "llama-cpp"
        └─ llm.usage.total_tokens: 225
     ```

4. **Check for regressions:**
   - Run smoke tests against `/v1/analyze` endpoint
   - Verify logs still appear correctly
   - Confirm no performance degradation

---

## Rollback Plan

If issues arise, rollback is simple:

1. **Revert deployment:**
   ```bash
   kubectl rollout undo deployment/log-analyzer -n log-analyzer
   ```

2. **Remove SDK dependency** (if needed):
   ```bash
   # In pyproject.toml, remove llm-observability
   # Rebuild image with old code
   ```

The SDK is additive and doesn't break existing OTel instrumentation.

---

## Expected Outcomes

### Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Lines of instrumentation code** | ~80 lines | ~40 lines | -50% |
| **Manual span.set_attribute() calls** | ~25 | ~5 | -80% |
| **Trace accuracy** | Same | Same | = |
| **Performance overhead** | <5ms | <5ms | = |

### Code Quality

✅ **Readability** - Decorators are self-documenting
✅ **Maintainability** - Semantic contract is stable
✅ **Testability** - Easier to mock SDK than raw OTel spans
✅ **Extensibility** - Easy to add Arize, MLflow backends

---

## Troubleshooting

### Issue: Spans not appearing in Tempo

**Diagnosis:**
```bash
# Check if OTLP endpoint is reachable
kubectl exec -it deployment/log-analyzer -n log-analyzer -- curl http://tempo.logging.svc.cluster.local:4317
```

**Solution:**
- Verify `OTEL_EXPORTER_OTLP_ENDPOINT` env var is correct
- Check Tempo is running: `kubectl get pods -n logging`
- Review log-analyzer logs for export errors

### Issue: Missing attributes on spans

**Diagnosis:**
- Check decorator parameters are correct
- Verify function signature matches decorator expectations

**Solution:**
```python
# Ensure model is provided
@observe.llm(name="call", model="gpt-4o")  # ✅ Correct
@observe.llm(name="call")  # ❌ Missing required model
```

### Issue: Duplicate spans

**Diagnosis:**
- Check if function is decorated multiple times
- Verify FastAPI auto-instrumentation isn't conflicting

**Solution:**
- Remove duplicate decorators
- SDK and FastAPI instrumentation should coexist peacefully

---

## Next Steps

After successful migration:

1. **Add Arize backend** (optional):
   - Deploy Arize Phoenix locally or use Arize Platform
   - Update `OBSERVABILITY_BACKEND=arize` env var
   - Dual-export to both Tempo and Arize

2. **Extend instrumentation**:
   - Add `@observe.prompt_render()` for prompt registry
   - Add `@observe.embedding()` if adding RAG

3. **Create Grafana dashboards**:
   - Use new semantic attributes for better visualization
   - Example queries:
     ```
     # Total tokens by model
     sum by(llm.model) (llm.usage.total_tokens)

     # LLM call latency
     histogram_quantile(0.95, llm.call)
     ```

---

## Questions?

Reach out to the team or open an issue in the `llm-observability-sdk` repository.

**Document Owner:** LLM Observability Team
**Last Updated:** 2026-01-10
