# LLM Observability SDK - Reference Architecture

**Version:** 1.0
**Date:** 2026-01-10
**Status:** Design / Pre-Implementation

---

## Executive Summary

This document defines the reference architecture for an **LLM Observability SDK** - a thin, opinionated abstraction layer over OpenTelemetry that provides:

1. **Stable semantic contract** for LLM/agent telemetry
2. **Excellent developer experience** through decorators and context managers
3. **Backend flexibility** supporting Arize Phoenix, MLflow, and custom OTLP endpoints
4. **Zero lock-in** - uses OpenTelemetry underneath, no proprietary formats

### The Core Insight

> **We do not abstract OpenTelemetry itself.**
> We only abstract three things above it:
> 1. Semantic contract (what we promise to log)
> 2. Instrumentation surface (how users call our SDK)
> 3. Backend configuration & export policy

Everything below remains pure OpenTelemetry. This keeps the SDK stable, testable, and future-proof.

---

## Design Principles

### 1. **OpenTelemetry is the Foundation, Not the Abstraction**

- Depend directly on `opentelemetry-api`, `opentelemetry-sdk`, OTLP exporters
- Never replace OTel concepts, only use them
- Keep OTel visible internally, invisible externally

### 2. **Semantic Discipline Over Code Flexibility**

- Define a stable, backend-agnostic semantic model
- Flat, JSON-serializable attribute values
- No backend-specific fields in the core contract
- No UI assumptions in attribute design

### 3. **Developer Experience First**

- Decorators and context managers, not raw span objects
- Hard to misuse, easy to onboard
- Automatic nesting and context propagation
- Minimal boilerplate

### 4. **Backend Adapters Should Be Boring**

- Each adapter <200 lines of configuration code
- No business logic in adapters
- Only responsibilities: endpoint config, auth, convention mapping
- If adapters grow large, the semantic contract is leaking

### 5. **What We Won't Do** (Hard-Earned Lessons)

- ❌ Don't expose raw spans to users
- ❌ Don't let users attach arbitrary attributes everywhere
- ❌ Don't let backend-specific options leak into decorators
- ❌ Don't build a "pluggable exporter" abstraction
- ❌ Don't create our own trace context system

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Backend Adapters (thin, replaceable)              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Arize/Phoenix│ │   MLflow     │ │   Custom     │        │
│  │   Adapter    │ │   Adapter    │ │   Adapter    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Developer-Facing API (DX layer)                   │
│  @observe.llm() | @observe.agent() | @observe.tool()       │
│  with observe.retriever() | observe.span()                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Semantic Contract (backend-agnostic)              │
│  Span kinds, attribute names, value formats                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 0: OpenTelemetry (unchanged)                         │
│  TracerProvider | Spans | Context | Exporters              │
└─────────────────────────────────────────────────────────────┘
```

### Layer 0: OpenTelemetry Foundation

**Responsibilities:**
- Trace context propagation
- Span lifecycle management
- Resource attributes
- Export pipeline (processors, exporters)

**Components Used:**
- `opentelemetry-api` - Tracer, Span, Context APIs
- `opentelemetry-sdk` - TracerProvider, SpanProcessor
- `opentelemetry-exporter-otlp-proto-grpc` - OTLP export

**Rule:** Our SDK never replaces these, only configures and uses them.

---

### Layer 1: Semantic Contract

This is the **heart of the SDK** - a stable, backend-agnostic semantic model.

#### Span Kinds

| Span Kind | Description | Parent Patterns |
|-----------|-------------|-----------------|
| `llm.call` | Single LLM API invocation | Top-level or under agent/workflow |
| `llm.agent` | Agent execution (planning, reasoning, tool use) | Top-level |
| `llm.tool` | Tool/function call by LLM or agent | Under agent or llm.call |
| `llm.retriever` | RAG retrieval operation (vector search, keyword) | Under agent or llm.call |
| `llm.embedding` | Embedding generation | Under retriever or standalone |
| `llm.workflow` | Multi-step LLM workflow/chain | Top-level |
| `llm.prompt_registry` | Prompt template rendering | Under any LLM operation |

#### Semantic Attributes

##### Common Attributes (all spans)

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `llm.operation.type` | string | Operation kind | "llm.call", "llm.agent" |
| `llm.operation.name` | string | User-provided operation name | "analyze_logs", "chat_agent" |
| `llm.session.id` | string | Session/conversation ID | UUID or user-defined |

##### LLM Call Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `llm.provider` | string | LLM provider | "openai", "anthropic", "llama-cpp" |
| `llm.model` | string | Model identifier | "gpt-4o", "llama-3.2-3b-instruct" |
| `llm.temperature` | float | Sampling temperature | 0.7 |
| `llm.max_tokens` | int | Max completion tokens | 1024 |
| `llm.top_p` | float | Nucleus sampling | 0.9 |
| `llm.streaming` | bool | Streaming enabled | true |
| `llm.input.messages` | JSON string | Input messages (truncated if large) | "[{\"role\":\"user\",\"content\":\"...\"}]" |
| `llm.output.message` | JSON string | Output message | "{\"role\":\"assistant\",\"content\":\"...\"}" |
| `llm.usage.prompt_tokens` | int | Prompt tokens consumed | 150 |
| `llm.usage.completion_tokens` | int | Completion tokens generated | 75 |
| `llm.usage.total_tokens` | int | Total tokens | 225 |

##### Agent Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `llm.agent.type` | string | Agent architecture | "react", "plan-execute", "conversational" |
| `llm.agent.iterations` | int | Number of reasoning iterations | 3 |
| `llm.agent.tools` | JSON string | Available tools | "[\"search\", \"calculator\"]" |

##### Tool Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `llm.tool.name` | string | Tool identifier | "web_search", "python_repl" |
| `llm.tool.input` | JSON string | Tool input (truncated) | "{\"query\": \"weather\"}" |
| `llm.tool.output` | JSON string | Tool output (truncated) | "{\"result\": \"sunny\"}" |

##### Retriever Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `llm.retriever.type` | string | Retriever type | "vector", "keyword", "hybrid" |
| `llm.retriever.query` | string | Search query | "kubernetes error logs" |
| `llm.retriever.top_k` | int | Number of results requested | 5 |
| `llm.retriever.results_count` | int | Actual results returned | 5 |
| `llm.retriever.source` | string | Data source | "pinecone", "loki", "elasticsearch" |

##### Prompt Registry Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `llm.prompt.id` | string | Prompt template ID | "k8s_log_analysis_v1" |
| `llm.prompt.version` | string | Template version | "v1", "2024-01-10" |
| `llm.prompt.template_hash` | string | Template content hash (8-char) | "a3f8d92c" |
| `llm.prompt.variables_hash` | string | Variables hash | "b4e9c1d7" |
| `llm.prompt.rendered_hash` | string | Rendered content hash | "c5a2f8e3" |

##### Error Attributes

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `llm.error.type` | string | Error category | "rate_limit", "timeout", "invalid_input" |
| `llm.error.message` | string | Error message | "Rate limit exceeded" |
| `llm.error.code` | string | Provider error code | "429" |

#### Attribute Design Rules

1. **Flat structure** - No nested objects, use dots for hierarchy
2. **JSON strings for complex data** - Arrays/objects serialized as JSON
3. **Consistent naming** - `llm.` prefix, snake_case
4. **Truncation policy** - Large inputs/outputs truncated to 4KB with indicator
5. **No PII by default** - Sanitize user content before logging

---

### Layer 2: Developer-Facing API

This is what users import and interact with.

#### Design Goals

- **Declarative** - Describe intent, not implementation
- **Minimal** - Few concepts, hard to misuse
- **Automatic** - Context propagation, nesting, cleanup

#### API Surface

##### 1. Decorators (Primary Pattern)

```python
from llm_observability import observe

# LLM call decoration
@observe.llm(
    name="analyze_logs",
    model="gpt-4o",
    provider="openai"
)
def call_llm(prompt: str, temperature: float = 0.7) -> str:
    response = openai.chat.completions.create(...)

    # SDK automatically captures:
    # - Input/output
    # - Token usage (if available in response)
    # - Model parameters

    return response.choices[0].message.content

# Agent decoration
@observe.agent(
    name="support_agent",
    agent_type="react",
    tools=["search", "calculator"]
)
def run_agent(query: str) -> dict:
    # Agent logic here
    return result

# Tool decoration
@observe.tool(name="web_search")
def search_web(query: str) -> list[dict]:
    results = search_api.query(query)

    # SDK captures input/output automatically
    return results

# Retriever decoration
@observe.retriever(
    name="log_search",
    retriever_type="keyword",
    source="loki"
)
def search_logs(query: str, limit: int = 10) -> list[dict]:
    return loki.query(query, limit=limit)
```

##### 2. Context Managers (Explicit Spans)

```python
# For operations that don't fit decorator pattern
with observe.span(
    "llm.workflow",
    name="multi_step_analysis"
) as span:
    # Step 1
    logs = retrieve_logs()
    span.set_attribute("workflow.step", "retrieve")

    # Step 2
    analysis = analyze(logs)
    span.set_attribute("workflow.step", "analyze")

    # Step 3
    report = generate_report(analysis)
    span.set_attribute("workflow.step", "report")

# Prompt registry pattern
with observe.prompt_render(
    template_id="k8s_log_analysis_v1",
    variables={"logs": logs, "namespace": "default"}
) as prompt:
    rendered = prompt.render()
    # Hash tracking happens automatically
```

##### 3. Manual Instrumentation (Escape Hatch)

```python
# For fine-grained control
span = observe.start_span(
    "llm.call",
    name="streaming_llm_call",
    attributes={
        "llm.model": "gpt-4o",
        "llm.streaming": True
    }
)

try:
    for chunk in stream_llm():
        process(chunk)
    span.set_attribute("llm.usage.completion_tokens", token_count)
finally:
    span.end()
```

##### 4. Async Support

```python
@observe.llm(name="async_call", model="gpt-4o")
async def async_llm_call(prompt: str) -> str:
    response = await openai_async.chat.completions.create(...)
    return response.choices[0].message.content

# Context managers
async with observe.span("llm.agent", name="async_agent") as span:
    result = await agent.run(query)
```

#### Internal Behavior

When a decorator/context manager is invoked:

1. **Create OTel span** with appropriate name and kind
2. **Apply semantic contract** - set required attributes
3. **Capture function signature** - parameters as attributes (if safe)
4. **Handle context propagation** - nested spans work automatically
5. **Capture result/error** - output or exception details
6. **Never expose span objects** to user code (except escape hatch)

---

### Layer 3: Backend Adapters

Backend adapters configure OpenTelemetry to target specific observability platforms.

#### Adapter Responsibilities (Only)

1. **Endpoint configuration** - Set OTLP endpoint URL
2. **Authentication** - Headers, API keys, tokens
3. **Attribute mapping** - Map our contract to backend's conventions
4. **Resource attributes** - Add backend-specific resource fields

#### Arize Phoenix Adapter

**Target:** Arize Phoenix / Arize Platform
**Protocol:** OTLP (gRPC or HTTP)
**Conventions:** OpenInference

```python
from llm_observability.adapters import ArizeAdapter

adapter = ArizeAdapter(
    endpoint="https://phoenix.arize.com:4317",
    api_key="your-api-key",
    project_name="log-analyzer"
)

observe.configure(adapter=adapter)
```

**Attribute Mapping:**

| Our Attribute | OpenInference Attribute |
|---------------|-------------------------|
| `llm.model` | `llm.model_name` |
| `llm.input.messages` | `llm.input_messages` |
| `llm.output.message` | `llm.output_messages` |
| `llm.usage.prompt_tokens` | `llm.token_count.prompt` |
| `llm.usage.completion_tokens` | `llm.token_count.completion` |
| `llm.tool.name` | `tool.name` |

**Implementation (~150 lines):**
- Inherit from base `BackendAdapter`
- Override `_map_attributes(attributes: dict) -> dict`
- Configure OTLP exporter with Phoenix endpoint
- Add Arize-specific resource attributes

#### MLflow Adapter

**Target:** MLflow Tracking
**Protocol:** OTLP (HTTP)
**Conventions:** OTel GenAI Semantic Conventions

```python
from llm_observability.adapters import MLflowAdapter

adapter = MLflowAdapter(
    tracking_uri="http://mlflow:5000",
    experiment_name="log-analyzer-dev"
)

observe.configure(adapter=adapter)
```

**Attribute Mapping:**

| Our Attribute | MLflow/OTel GenAI Attribute |
|---------------|------------------------------|
| `llm.model` | `gen_ai.request.model` |
| `llm.temperature` | `gen_ai.request.temperature` |
| `llm.usage.prompt_tokens` | `gen_ai.usage.prompt_tokens` |
| `llm.usage.completion_tokens` | `gen_ai.usage.completion_tokens` |

**Implementation (~120 lines):**
- Map to OTel GenAI conventions (MLflow compatibility)
- Configure experiment/run context
- Handle MLflow-specific span kinds

#### Custom OTLP Adapter (Default)

**Target:** Any OTLP-compatible backend (Tempo, Jaeger, Honeycomb, etc.)
**Protocol:** OTLP (gRPC or HTTP)
**Conventions:** Our semantic contract (unchanged)

```python
from llm_observability.adapters import OTLPAdapter

adapter = OTLPAdapter(
    endpoint="http://tempo.logging.svc.cluster.local:4317",
    protocol="grpc",
    headers={"x-custom-header": "value"}
)

observe.configure(adapter=adapter)
```

**Implementation (~80 lines):**
- Direct pass-through, no attribute mapping
- Configurable endpoint, protocol, headers
- This is the "reference implementation"

---

## Package Structure

```
llm-observability-sdk/
├── pyproject.toml
├── README.md
├── SEMANTICS.md                    # Semantic contract specification
├── LICENSE
├── src/
│   └── llm_observability/
│       ├── __init__.py             # Public API exports
│       ├── version.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── observer.py         # Main observe object
│       │   ├── decorators.py       # @observe.llm, @observe.agent
│       │   ├── context.py          # Context managers
│       │   ├── span_builder.py     # Span creation logic
│       │   └── attributes.py       # Attribute management
│       │
│       ├── semantic/
│       │   ├── __init__.py
│       │   ├── contract.py         # Attribute name constants
│       │   ├── span_kinds.py       # Span kind definitions
│       │   └── validation.py       # Contract validation
│       │
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py             # BackendAdapter base class
│       │   ├── otlp.py             # OTLPAdapter (default)
│       │   ├── arize.py            # ArizeAdapter
│       │   └── mlflow.py           # MLflowAdapter
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py         # Configuration management
│       │   └── env.py              # Environment variable handling
│       │
│       └── utils/
│           ├── __init__.py
│           ├── serialization.py    # JSON serialization, truncation
│           ├── hashing.py          # Content hashing
│           └── sanitization.py     # PII removal helpers
│
├── tests/
│   ├── unit/
│   │   ├── test_decorators.py
│   │   ├── test_span_builder.py
│   │   ├── test_attributes.py
│   │   └── test_adapters.py
│   ├── integration/
│   │   ├── test_arize_integration.py
│   │   ├── test_mlflow_integration.py
│   │   └── test_otlp_export.py
│   └── fixtures/
│       └── mock_backends.py
│
└── examples/
    ├── basic_usage.py
    ├── agent_instrumentation.py
    ├── async_example.py
    └── backends/
        ├── arize_example.py
        └── mlflow_example.py
```

### Key Files

#### `src/llm_observability/__init__.py`

```python
"""LLM Observability SDK - OpenTelemetry-based LLM telemetry."""

from llm_observability.core.observer import observe
from llm_observability.adapters import (
    OTLPAdapter,
    ArizeAdapter,
    MLflowAdapter,
    BackendAdapter
)
from llm_observability.version import __version__

__all__ = [
    "observe",
    "OTLPAdapter",
    "ArizeAdapter",
    "MLflowAdapter",
    "BackendAdapter",
    "__version__",
]
```

#### `src/llm_observability/semantic/contract.py`

```python
"""Semantic contract - attribute name constants."""

from enum import Enum

class SpanKind(str, Enum):
    """LLM operation span kinds."""
    LLM_CALL = "llm.call"
    AGENT = "llm.agent"
    TOOL = "llm.tool"
    RETRIEVER = "llm.retriever"
    EMBEDDING = "llm.embedding"
    WORKFLOW = "llm.workflow"
    PROMPT_REGISTRY = "llm.prompt_registry"

class Attributes:
    """Semantic attribute name constants."""

    # Common
    OPERATION_TYPE = "llm.operation.type"
    OPERATION_NAME = "llm.operation.name"
    SESSION_ID = "llm.session.id"

    # LLM
    PROVIDER = "llm.provider"
    MODEL = "llm.model"
    TEMPERATURE = "llm.temperature"
    MAX_TOKENS = "llm.max_tokens"
    TOP_P = "llm.top_p"
    STREAMING = "llm.streaming"
    INPUT_MESSAGES = "llm.input.messages"
    OUTPUT_MESSAGE = "llm.output.message"
    USAGE_PROMPT_TOKENS = "llm.usage.prompt_tokens"
    USAGE_COMPLETION_TOKENS = "llm.usage.completion_tokens"
    USAGE_TOTAL_TOKENS = "llm.usage.total_tokens"

    # Agent
    AGENT_TYPE = "llm.agent.type"
    AGENT_ITERATIONS = "llm.agent.iterations"
    AGENT_TOOLS = "llm.agent.tools"

    # Tool
    TOOL_NAME = "llm.tool.name"
    TOOL_INPUT = "llm.tool.input"
    TOOL_OUTPUT = "llm.tool.output"

    # Retriever
    RETRIEVER_TYPE = "llm.retriever.type"
    RETRIEVER_QUERY = "llm.retriever.query"
    RETRIEVER_TOP_K = "llm.retriever.top_k"
    RETRIEVER_RESULTS_COUNT = "llm.retriever.results_count"
    RETRIEVER_SOURCE = "llm.retriever.source"

    # Prompt Registry
    PROMPT_ID = "llm.prompt.id"
    PROMPT_VERSION = "llm.prompt.version"
    PROMPT_TEMPLATE_HASH = "llm.prompt.template_hash"
    PROMPT_VARIABLES_HASH = "llm.prompt.variables_hash"
    PROMPT_RENDERED_HASH = "llm.prompt.rendered_hash"

    # Error
    ERROR_TYPE = "llm.error.type"
    ERROR_MESSAGE = "llm.error.message"
    ERROR_CODE = "llm.error.code"
```

---

## Integration Patterns

### Pattern 1: Full Decorator-Based Instrumentation

```python
from llm_observability import observe

@observe.agent(name="log_analyzer_agent", agent_type="sequential")
def analyze_logs_workflow(time_range: dict, filters: dict):

    @observe.retriever(
        name="query_loki",
        retriever_type="keyword",
        source="loki"
    )
    def query_logs(logql: str, limit: int):
        return loki_client.query(logql, limit=limit)

    @observe.llm(
        name="analyze_with_llm",
        model="gpt-4o",
        provider="openai"
    )
    def call_llm(prompt: str):
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    # Workflow logic
    logs = query_logs(build_logql(filters), limit=50)
    analysis = call_llm(render_prompt(logs))
    return analysis
```

**Result:** Automatic nested span hierarchy:
```
span: llm.agent (log_analyzer_agent)
├─ span: llm.retriever (query_loki)
└─ span: llm.call (analyze_with_llm)
```

### Pattern 2: Mixed Decorator + Context Manager

```python
@observe.agent(name="support_agent")
def run_support_agent(user_query: str):

    # Explicit workflow tracking
    with observe.span("llm.workflow", name="multi_step_support") as workflow:
        workflow.set_attribute("workflow.user_query", user_query)

        # Step 1: Retrieval
        @observe.retriever(name="knowledge_search", source="pinecone")
        def search_kb(query: str):
            return pinecone.query(query, top_k=5)

        docs = search_kb(user_query)
        workflow.set_attribute("workflow.docs_retrieved", len(docs))

        # Step 2: LLM analysis
        @observe.llm(name="generate_response", model="gpt-4o")
        def generate_answer(context: list, question: str):
            prompt = f"Context: {context}\n\nQuestion: {question}"
            return openai.call(prompt)

        answer = generate_answer(docs, user_query)
        return answer
```

### Pattern 3: Prompt Registry Integration

```python
from llm_observability import observe
from llm_observability.utils import hash_content

@observe.llm(name="templated_analysis", model="gpt-4o")
def analyze_with_template(logs: list, namespace: str):

    # Explicit prompt rendering tracking
    with observe.span(
        "llm.prompt_registry",
        name="render_analysis_prompt"
    ) as prompt_span:
        template = load_template("k8s_log_analysis_v1")
        variables = {"logs": logs, "namespace": namespace}

        # Track hashes
        prompt_span.set_attribute("llm.prompt.id", template.id)
        prompt_span.set_attribute("llm.prompt.version", template.version)
        prompt_span.set_attribute("llm.prompt.template_hash",
                                   hash_content(template.content)[:8])
        prompt_span.set_attribute("llm.prompt.variables_hash",
                                   hash_content(str(variables))[:8])

        rendered = template.render(**variables)

        prompt_span.set_attribute("llm.prompt.rendered_hash",
                                   hash_content(rendered)[:8])

    # LLM call (already decorated)
    response = openai.call(rendered)
    return response
```

---

## Migration Path: log-analyzer Refactoring

### Current State

The `log-analyzer` service currently uses **manual OpenTelemetry span creation**:

```python
# Current approach (pipeline.py, main.py)
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("analyze_logs") as span:
    span.set_attribute("namespace", namespace)
    span.set_attribute("log_limit", limit)

    with tracer.start_as_current_span("query_loki") as query_span:
        query_span.set_attribute("logql.query", logql)
        results = loki.query(logql)
        query_span.set_attribute("loki.results_count", len(results))

    with tracer.start_as_current_span("call_llm") as llm_span:
        llm_span.set_attribute("llm.model", model)
        llm_span.set_attribute("llm.streaming", True)
        response = llm_client.call(prompt)
        llm_span.set_attribute("llm.tokens_prompt", tokens)
```

### Target State (After Migration)

```python
# New approach with SDK
from llm_observability import observe

@observe.workflow(name="analyze_logs")
def analyze_logs(time_range: dict, filters: dict, limit: int = 15):

    @observe.retriever(
        name="query_loki",
        retriever_type="keyword",
        source="loki"
    )
    def query_loki_logs(logql: str, limit: int):
        results = loki.query_range(logql, limit=limit)
        # Token usage automatically captured by decorator
        return results

    @observe.llm(
        name="analyze_with_llm",
        model=config.llm_model,
        provider="llama-cpp",
        streaming=True
    )
    def call_llm(prompt: str, temperature: float):
        response = llm_client.call(
            prompt=prompt,
            temperature=temperature,
            stream=True
        )
        # Decorator handles token tracking
        return response

    # Business logic (unchanged)
    logql = build_logql_query(time_range, filters)
    logs = query_loki_logs(logql, limit=limit)

    flattened = flatten_logs(logs)
    normalized = normalize_logs(flattened)

    prompt = render_prompt(template_id="k8s_log_analysis_v1",
                           logs=normalized,
                           namespace=filters.get("namespace"))

    analysis = call_llm(prompt, temperature=0.3)
    return analysis
```

### Migration Steps

1. **Install SDK as dependency** in `log-analyzer/pyproject.toml`
2. **Configure adapter** in `log-analyzer/src/log_analyzer/observability/__init__.py`
3. **Refactor pipeline.py** - replace manual spans with decorators
4. **Refactor main.py** - decorate HTTP endpoint handlers
5. **Update tests** - verify span structure with SDK
6. **Deploy to dev** - validate against Tempo backend
7. **(Optional) Add Arize adapter** - dual-export for comparison

### Configuration (Backend Selection)

```python
# log-analyzer/src/log_analyzer/observability/__init__.py

from llm_observability import observe
from llm_observability.adapters import OTLPAdapter, ArizeAdapter
import os

# Default: OTLP to Tempo (existing setup)
if os.getenv("OBSERVABILITY_BACKEND") == "arize":
    adapter = ArizeAdapter(
        endpoint=os.getenv("ARIZE_ENDPOINT"),
        api_key=os.getenv("ARIZE_API_KEY"),
        project_name="log-analyzer"
    )
else:
    adapter = OTLPAdapter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT",
                           "http://tempo.logging.svc.cluster.local:4317"),
        protocol="grpc"
    )

observe.configure(
    adapter=adapter,
    service_name=os.getenv("LOG_ANALYZER_SERVICE_NAME", "log-analyzer"),
    service_version=os.getenv("LOG_ANALYZER_SERVICE_VERSION", "unknown"),
    deployment_environment=os.getenv("DEPLOYMENT_ENVIRONMENT", "dev")
)
```

**Deployment Change:**
```yaml
# deployment.yaml - add optional backend config
env:
  - name: OBSERVABILITY_BACKEND
    value: "otlp"  # or "arize", "mlflow"
  # - name: ARIZE_ENDPOINT
  #   value: "https://phoenix.arize.com:4317"
  # - name: ARIZE_API_KEY
  #   valueFrom:
  #     secretKeyRef:
  #       name: arize-credentials
  #       key: api-key
```

---

## MVP Implementation Roadmap

### Phase 1: Core SDK Foundation (Week 1)

**Goal:** Minimal working SDK with OTLP export

**Deliverables:**
1. ✅ Package structure (`llm-observability-sdk/`)
2. ✅ Semantic contract definition (`semantic/contract.py`)
3. ✅ Core observer implementation (`core/observer.py`)
4. ✅ Basic decorators: `@observe.llm()`, `@observe.agent()`
5. ✅ OTLP adapter (default backend)
6. ✅ Unit tests for decorators and span creation
7. ✅ `SEMANTICS.md` documentation

**Success Criteria:**
- Can decorate a function and see spans in Tempo
- Attributes match semantic contract
- Tests pass

**Files to Create:**
```
llm-observability-sdk/
├── pyproject.toml
├── SEMANTICS.md
└── src/llm_observability/
    ├── __init__.py
    ├── core/
    │   ├── observer.py
    │   ├── decorators.py
    │   └── span_builder.py
    ├── semantic/
    │   ├── contract.py
    │   └── span_kinds.py
    ├── adapters/
    │   ├── base.py
    │   └── otlp.py
    └── utils/
        └── serialization.py
```

### Phase 2: Remaining Decorators + Context Managers (Week 1-2)

**Goal:** Complete instrumentation API surface

**Deliverables:**
1. ✅ `@observe.tool()` decorator
2. ✅ `@observe.retriever()` decorator
3. ✅ `observe.span()` context manager
4. ✅ `observe.prompt_render()` context manager
5. ✅ Async support for all decorators
6. ✅ Integration tests with mock backends

**Success Criteria:**
- All decorator types work
- Nested spans propagate context correctly
- Async/await works seamlessly

### Phase 3: Backend Adapters (Week 2)

**Goal:** Support Arize and MLflow backends

**Deliverables:**
1. ✅ Arize adapter with OpenInference mapping
2. ✅ MLflow adapter with GenAI conventions
3. ✅ Adapter configuration API
4. ✅ Integration tests against Arize Phoenix (local)
5. ✅ Integration tests against MLflow (local)

**Success Criteria:**
- Same instrumented code exports to all 3 backends
- Attributes map correctly per backend conventions
- Zero user code changes when switching backends

### Phase 4: log-analyzer Migration (Week 2-3)

**Goal:** Refactor log-analyzer to use SDK

**Deliverables:**
1. ✅ Add SDK dependency to `log-analyzer`
2. ✅ Configure OTLP adapter for Tempo
3. ✅ Refactor `pipeline.py` with decorators
4. ✅ Refactor `main.py` HTTP handlers
5. ✅ Update tests
6. ✅ Deploy to dev cluster
7. ✅ Validate spans in Grafana/Tempo

**Success Criteria:**
- Existing Grafana dashboards still work
- Span structure improved (cleaner, more semantic)
- No performance degradation
- All tests pass

### Phase 5: Documentation + Examples (Week 3)

**Goal:** Enable external adoption

**Deliverables:**
1. ✅ README with quickstart
2. ✅ `SEMANTICS.md` (semantic contract spec)
3. ✅ API documentation (docstrings + Sphinx)
4. ✅ Example: Basic LLM instrumentation
5. ✅ Example: Agent with tools
6. ✅ Example: Arize backend configuration
7. ✅ Example: MLflow backend configuration

**Success Criteria:**
- A new developer can instrument an LLM app in <10 minutes
- Backend switching is clear and documented
- Semantic contract is well-understood

---

## Open Questions & Decisions Needed

### 1. **Automatic Input/Output Capture**

**Question:** Should decorators automatically capture function inputs/outputs as span attributes?

**Options:**
- **A)** Auto-capture by default, provide `@observe.llm(capture_io=False)` opt-out
- **B)** Manual capture only, user calls `span.set_input()` / `span.set_output()`
- **C)** Smart capture based on type hints (capture primitives, skip complex objects)

**Recommendation:** Option C with opt-out flag.

**Rationale:**
- Most LLM calls have simple string/dict inputs
- Auto-capture improves DX significantly
- Type-based filtering prevents accidentally logging huge objects
- Opt-out provides safety valve

---

### 2. **PII Sanitization Strategy**

**Question:** How aggressively should we sanitize inputs/outputs for PII?

**Options:**
- **A)** No sanitization (user responsibility)
- **B)** Opt-in sanitization via `@observe.llm(sanitize=True)`
- **C)** Always sanitize, provide raw capture escape hatch

**Recommendation:** Option B.

**Rationale:**
- PII rules vary by domain (healthcare vs. logs vs. chat)
- Default-off prevents surprising behavior
- Provide `llm_observability.utils.sanitize()` helper for common patterns
- Document PII risks clearly in README

---

### 3. **Token Usage Extraction**

**Question:** How do we extract token usage from LLM responses (varies by provider)?

**Options:**
- **A)** User manually calls `observe.record_tokens(prompt=X, completion=Y)`
- **B)** SDK auto-extracts from common response shapes (OpenAI, Anthropic, etc.)
- **C)** Provider-specific extractors (pluggable)

**Recommendation:** Option B with fallback to A.

**Rationale:**
- Auto-extraction for 80% case (OpenAI, Anthropic, Llama.cpp have standard fields)
- Manual recording for custom providers or streaming edge cases
- Keep extractors simple (no provider-specific clients)

**Implementation:**
```python
# In decorator post-processing
def extract_token_usage(response: Any) -> dict[str, int] | None:
    """Extract tokens from common response shapes."""
    if hasattr(response, 'usage'):  # OpenAI-like
        return {
            'prompt': response.usage.prompt_tokens,
            'completion': response.usage.completion_tokens,
            'total': response.usage.total_tokens
        }
    elif hasattr(response, 'metadata') and 'usage' in response.metadata:  # Anthropic
        return {
            'prompt': response.metadata.usage.input_tokens,
            'completion': response.metadata.usage.output_tokens,
            'total': response.metadata.usage.input_tokens + response.metadata.usage.output_tokens
        }
    return None
```

---

### 4. **Streaming LLM Calls**

**Question:** How do we instrument streaming responses where tokens arrive incrementally?

**Options:**
- **A)** User wraps generator, manually updates span at the end
- **B)** SDK provides `observe.stream()` wrapper that auto-updates
- **C)** Decorator detects generator return type, wraps automatically

**Recommendation:** Option B (explicit wrapper).

**Rationale:**
- Streaming has different semantics (can't capture output until done)
- Explicit wrapper makes streaming behavior clear
- Allows tracking metrics like time-to-first-token

**API:**
```python
@observe.llm(name="streaming_call", model="gpt-4o")
def call_llm_streaming(prompt: str):
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    # Wrap generator to track output
    return observe.stream(
        response,
        accumulator=lambda chunks: ''.join(c.choices[0].delta.content for c in chunks)
    )

# Usage
for chunk in call_llm_streaming("Hello"):
    print(chunk)
# Span auto-closes after iteration completes, with full output captured
```

---

### 5. **Error Handling & Failed Spans**

**Question:** How do we mark spans when LLM calls fail (rate limits, timeouts, errors)?

**Options:**
- **A)** Let exception propagate, OTel marks span as error automatically
- **B)** Catch exception, add semantic error attributes, re-raise
- **C)** Provide error categorization (rate_limit, timeout, invalid_input)

**Recommendation:** Option B + C.

**Rationale:**
- OTel's default error tracking is generic (just stack trace)
- LLM-specific error categories enable better observability (dashboards, alerts)
- Re-raising preserves normal exception flow

**Implementation:**
```python
# In decorator error handler
try:
    result = func(*args, **kwargs)
except RateLimitError as e:
    span.set_attribute("llm.error.type", "rate_limit")
    span.set_attribute("llm.error.code", str(e.status_code))
    span.set_attribute("llm.error.message", str(e))
    span.set_status(StatusCode.ERROR, "Rate limit exceeded")
    raise
except TimeoutError as e:
    span.set_attribute("llm.error.type", "timeout")
    span.set_attribute("llm.error.message", str(e))
    span.set_status(StatusCode.ERROR, "Request timeout")
    raise
```

---

## Success Metrics (Post-MVP)

### Developer Experience
- **Onboarding time:** <10 minutes from install to first trace
- **Lines of code:** <5 lines to instrument a basic LLM call
- **Decorator types:** 5-7 total (llm, agent, tool, retriever, embedding, workflow, prompt)

### Stability
- **Semantic contract churn:** <2 breaking changes per year
- **Backend adapter size:** <200 lines per adapter
- **Test coverage:** >85% for core, >70% for adapters

### Adoption (Internal)
- **log-analyzer migration:** Complete in Phase 4
- **Additional services instrumented:** 2+ by end of Q1 2026

---

## Appendix A: Semantic Contract Comparison

### Our Contract vs. OpenInference

| Concept | Our Attribute | OpenInference | Notes |
|---------|---------------|---------------|-------|
| Model name | `llm.model` | `llm.model_name` | Slight naming difference |
| Prompt tokens | `llm.usage.prompt_tokens` | `llm.token_count.prompt` | Hierarchical vs. flat |
| Input messages | `llm.input.messages` | `llm.input_messages` | Identical |
| Tool name | `llm.tool.name` | `tool.name` | Different prefix |

**Adapter Complexity:** ~20 attribute mappings in Arize adapter.

### Our Contract vs. OTel GenAI Conventions

| Concept | Our Attribute | OTel GenAI | Notes |
|---------|---------------|------------|-------|
| Model | `llm.model` | `gen_ai.request.model` | Different prefix |
| Temperature | `llm.temperature` | `gen_ai.request.temperature` | Different prefix |
| Prompt tokens | `llm.usage.prompt_tokens` | `gen_ai.usage.prompt_tokens` | Similar structure |

**Adapter Complexity:** ~15 attribute mappings in MLflow adapter.

---

## Appendix B: Technology Choices

### Why OpenTelemetry?

- ✅ Industry standard for distributed tracing
- ✅ Vendor-neutral, CNCF project
- ✅ Excellent Python SDK with auto-instrumentation
- ✅ Already deployed in our infrastructure (Tempo, Alloy)
- ✅ Future-proof (won't be deprecated)

### Why Not Build on Langchain/LlamaIndex Observability?

- ❌ Tied to specific frameworks (Langchain, LlamaIndex)
- ❌ Custom formats, not OTel-native
- ❌ Backend lock-in (LangSmith, Arize integrations are proprietary)
- ❌ We want framework-agnostic SDK

### Why Python First?

- ✅ Dominant language for LLM/ML workloads
- ✅ log-analyzer is Python
- ✅ Fast iteration for MVP
- 🔮 Future: TypeScript/JavaScript version for Node.js agents

---

## Appendix C: References

### Standards & Specifications
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OpenInference Specification](https://github.com/Arize-ai/openinference)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)

### Backend Documentation
- [Arize Phoenix OTLP Ingestion](https://docs.arize.com/phoenix/tracing/integrations/opentelemetry)
- [MLflow Tracing](https://mlflow.org/docs/latest/llms/tracing/index.html)
- [Grafana Tempo](https://grafana.com/docs/tempo/latest/)

### Inspirations
- [OpenLLMetry](https://github.com/traceloop/openllmetry) - OTel-based LLM instrumentation
- [LangSmith SDK](https://docs.smith.langchain.com/) - Proprietary but good DX patterns
- [Helicone](https://docs.helicone.ai/) - Proxy-based observability (different approach)

---

## Next Steps

1. **Review this architecture** - Gather feedback from team
2. **Make decisions** on open questions (input capture, PII, streaming)
3. **Set up SDK repository** - `llm-observability-sdk/` monorepo
4. **Start Phase 1** - Core SDK foundation (Week 1 goal)
5. **Create SEMANTICS.md** - Detailed semantic contract specification

---

**Document Owner:** Log Analyzer Team
**Last Updated:** 2026-01-10
**Status:** ✅ Ready for Implementation
