# LLM Observability SDK - Semantic Contract Specification

**Version:** 1.0.0
**Date:** 2026-01-10
**Status:** Draft

---

## Overview

This document defines the **semantic contract** for the LLM Observability SDK - the stable, backend-agnostic specification of span kinds, attribute names, value formats, and behavioral requirements that all implementations must follow.

### What is a Semantic Contract?

A semantic contract is:
- **A promise to users** about what we will log and how
- **A specification for backends** to understand our telemetry
- **A stability guarantee** that attribute names and meanings won't change
- **NOT an implementation detail** - how we capture data can change, what we capture should not

### Design Goals

1. **Backend Agnostic** - No Arize, MLflow, or vendor-specific attributes
2. **Stable** - Breaking changes require major version bump
3. **Flat Structure** - No nested objects, use dot notation for hierarchy
4. **JSON Serializable** - All values can be serialized to JSON
5. **Human Readable** - Attribute names are self-documenting
6. **Precise** - Clear semantics, no ambiguity

---

## Span Kinds

### Taxonomy

```
llm.call         - Single LLM API invocation
llm.agent        - Agent execution (planning, reasoning, tool orchestration)
llm.tool         - Tool/function call by LLM or agent
llm.retriever    - RAG retrieval operation (vector search, keyword search)
llm.embedding    - Embedding generation (vectorization)
llm.workflow     - Multi-step LLM workflow or chain
llm.prompt_registry - Prompt template rendering
```

### Span Kind Definitions

#### `llm.call`

**Description:** A single invocation of an LLM API (completion, chat, or generation).

**Typical Duration:** 100ms - 30s

**Required Attributes:**
- `llm.operation.type` = `"llm.call"`
- `llm.operation.name` - User-provided operation name
- `llm.model` - Model identifier
- `llm.provider` - Provider name

**Optional Attributes:**
- `llm.temperature`, `llm.max_tokens`, `llm.top_p`, `llm.streaming`
- `llm.input.messages`, `llm.output.message`
- `llm.usage.prompt_tokens`, `llm.usage.completion_tokens`, `llm.usage.total_tokens`

**Parent Span Patterns:**
- Top-level (direct user invocation)
- Under `llm.agent` (agent reasoning step)
- Under `llm.workflow` (chain step)

**Example:**
```python
span_name: "generate_analysis"
span_kind: "llm.call"
attributes:
  llm.operation.type: "llm.call"
  llm.operation.name: "generate_analysis"
  llm.model: "gpt-4o"
  llm.provider: "openai"
  llm.temperature: 0.3
  llm.usage.total_tokens: 225
```

---

#### `llm.agent`

**Description:** An agent execution involving planning, reasoning, tool selection, and orchestration.

**Typical Duration:** 1s - 5m

**Required Attributes:**
- `llm.operation.type` = `"llm.agent"`
- `llm.operation.name` - Agent name

**Optional Attributes:**
- `llm.agent.type` - Agent architecture (e.g., "react", "plan-execute")
- `llm.agent.iterations` - Number of reasoning loops
- `llm.agent.tools` - JSON array of available tool names

**Child Span Patterns:**
- Multiple `llm.call` spans (reasoning steps)
- Multiple `llm.tool` spans (tool executions)
- Optional `llm.retriever` spans (knowledge lookups)

**Example:**
```python
span_name: "support_agent"
span_kind: "llm.agent"
attributes:
  llm.operation.type: "llm.agent"
  llm.operation.name: "support_agent"
  llm.agent.type: "react"
  llm.agent.iterations: 3
  llm.agent.tools: "[\"search\", \"calculator\", \"weather\"]"
```

---

#### `llm.tool`

**Description:** A tool or function call made by an LLM or agent (e.g., web search, API call, code execution).

**Typical Duration:** 100ms - 10s

**Required Attributes:**
- `llm.operation.type` = `"llm.tool"`
- `llm.tool.name` - Tool identifier

**Optional Attributes:**
- `llm.tool.input` - JSON string of tool input
- `llm.tool.output` - JSON string of tool output

**Parent Span Patterns:**
- Under `llm.agent` (tool selected by agent)
- Under `llm.call` (function calling)

**Example:**
```python
span_name: "web_search"
span_kind: "llm.tool"
attributes:
  llm.operation.type: "llm.tool"
  llm.tool.name: "web_search"
  llm.tool.input: "{\"query\": \"kubernetes pod crash\"}"
  llm.tool.output: "{\"results\": [{\"title\": \"...\", \"url\": \"...\"}]}"
```

---

#### `llm.retriever`

**Description:** A retrieval operation for RAG (Retrieval-Augmented Generation), including vector search, keyword search, or hybrid retrieval.

**Typical Duration:** 50ms - 5s

**Required Attributes:**
- `llm.operation.type` = `"llm.retriever"`
- `llm.retriever.query` - Search query
- `llm.retriever.source` - Data source identifier

**Optional Attributes:**
- `llm.retriever.type` - Retrieval method ("vector", "keyword", "hybrid")
- `llm.retriever.top_k` - Number of results requested
- `llm.retriever.results_count` - Actual results returned

**Parent Span Patterns:**
- Under `llm.agent` (knowledge lookup)
- Under `llm.workflow` (preprocessing step)
- Top-level (standalone search)

**Example:**
```python
span_name: "vector_search_knowledge_base"
span_kind: "llm.retriever"
attributes:
  llm.operation.type: "llm.retriever"
  llm.retriever.query: "how to debug kubernetes pods"
  llm.retriever.type: "vector"
  llm.retriever.source: "pinecone"
  llm.retriever.top_k: 5
  llm.retriever.results_count: 5
```

---

#### `llm.embedding`

**Description:** Generation of embeddings (vector representations) from text.

**Typical Duration:** 50ms - 2s

**Required Attributes:**
- `llm.operation.type` = `"llm.embedding"`
- `llm.model` - Embedding model

**Optional Attributes:**
- `llm.provider` - Provider name
- `llm.embedding.input_count` - Number of texts embedded
- `llm.embedding.dimensions` - Vector dimensions

**Parent Span Patterns:**
- Under `llm.retriever` (query embedding)
- Standalone (indexing operation)

**Example:**
```python
span_name: "embed_query"
span_kind: "llm.embedding"
attributes:
  llm.operation.type: "llm.embedding"
  llm.model: "text-embedding-ada-002"
  llm.provider: "openai"
  llm.embedding.input_count: 1
  llm.embedding.dimensions: 1536
```

---

#### `llm.workflow`

**Description:** A multi-step workflow or chain involving multiple LLM operations.

**Typical Duration:** 1s - 10m

**Required Attributes:**
- `llm.operation.type` = `"llm.workflow"`
- `llm.operation.name` - Workflow name

**Optional Attributes:**
- `llm.workflow.steps` - JSON array of step names
- `llm.workflow.current_step` - Current step (updated during execution)

**Child Span Patterns:**
- Multiple `llm.call`, `llm.retriever`, or `llm.agent` spans

**Example:**
```python
span_name: "document_qa_workflow"
span_kind: "llm.workflow"
attributes:
  llm.operation.type: "llm.workflow"
  llm.operation.name: "document_qa_workflow"
  llm.workflow.steps: "[\"retrieve\", \"rerank\", \"generate\"]"
```

---

#### `llm.prompt_registry`

**Description:** Rendering a prompt from a template registry (versioned, hashed prompts).

**Typical Duration:** 1ms - 100ms

**Required Attributes:**
- `llm.operation.type` = `"llm.prompt_registry"`
- `llm.prompt.id` - Template identifier

**Optional Attributes:**
- `llm.prompt.version` - Template version
- `llm.prompt.template_hash` - Hash of template content (8 chars)
- `llm.prompt.variables_hash` - Hash of input variables (8 chars)
- `llm.prompt.rendered_hash` - Hash of rendered output (8 chars)

**Parent Span Patterns:**
- Under `llm.call` (prompt construction)
- Under `llm.workflow` (templating step)

**Example:**
```python
span_name: "render_k8s_analysis_prompt"
span_kind: "llm.prompt_registry"
attributes:
  llm.operation.type: "llm.prompt_registry"
  llm.prompt.id: "k8s_log_analysis_v1"
  llm.prompt.version: "v1"
  llm.prompt.template_hash: "a3f8d92c"
  llm.prompt.variables_hash: "b4e9c1d7"
  llm.prompt.rendered_hash: "c5a2f8e3"
```

---

## Attribute Specifications

### Naming Conventions

1. **Prefix:** All attributes start with `llm.`
2. **Case:** snake_case (lowercase with underscores)
3. **Hierarchy:** Use dots for grouping (e.g., `llm.usage.prompt_tokens`)
4. **Clarity:** Self-documenting names (no abbreviations unless standard)

### Common Attributes

These attributes apply to **all span kinds**.

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `llm.operation.type` | string | ✅ | Span kind identifier | `"llm.call"` |
| `llm.operation.name` | string | ✅ | User-provided operation name | `"analyze_logs"` |
| `llm.session.id` | string | ❌ | Session/conversation ID | `"sess_abc123"` |

---

### LLM Call Attributes

Attributes for `llm.call` spans.

#### Model & Provider

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `llm.provider` | string | ✅ | LLM provider | `"openai"`, `"anthropic"`, `"llama-cpp"` |
| `llm.model` | string | ✅ | Model identifier | `"gpt-4o"`, `"claude-3-opus"` |

#### Inference Parameters

| Attribute | Type | Required | Description | Example | Valid Range |
|-----------|------|----------|-------------|---------|-------------|
| `llm.temperature` | float | ❌ | Sampling temperature | `0.7` | `0.0 - 2.0` |
| `llm.max_tokens` | int | ❌ | Max completion tokens | `1024` | `> 0` |
| `llm.top_p` | float | ❌ | Nucleus sampling | `0.9` | `0.0 - 1.0` |
| `llm.top_k` | int | ❌ | Top-K sampling | `40` | `> 0` |
| `llm.frequency_penalty` | float | ❌ | Frequency penalty | `0.5` | `-2.0 - 2.0` |
| `llm.presence_penalty` | float | ❌ | Presence penalty | `0.0` | `-2.0 - 2.0` |
| `llm.streaming` | bool | ❌ | Streaming enabled | `true` | `true/false` |

#### Input & Output

| Attribute | Type | Required | Description | Format | Truncation |
|-----------|------|----------|-------------|--------|------------|
| `llm.input.messages` | string | ❌ | Input messages | JSON array string | 4KB max |
| `llm.output.message` | string | ❌ | Output message | JSON object string | 4KB max |

**Format Example (OpenAI-style):**
```json
// llm.input.messages
"[{\"role\": \"system\", \"content\": \"You are a helpful assistant.\"}, {\"role\": \"user\", \"content\": \"Hello!\"}]"

// llm.output.message
"{\"role\": \"assistant\", \"content\": \"Hi! How can I help you today?\"}"
```

**Truncation Behavior:**
- If serialized JSON > 4KB, truncate content field with indicator
- Example: `"{\"role\": \"user\", \"content\": \"[TRUNCATED: 15234 chars]...\"}"`

#### Token Usage

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `llm.usage.prompt_tokens` | int | ❌ | Tokens in prompt | `150` |
| `llm.usage.completion_tokens` | int | ❌ | Tokens in completion | `75` |
| `llm.usage.total_tokens` | int | ❌ | Total tokens | `225` |

**Extraction Behavior:**
- If available from LLM response, auto-populate
- If streaming, update after stream completes
- If unavailable, omit (don't set to 0)

---

### Agent Attributes

Attributes for `llm.agent` spans.

| Attribute | Type | Required | Description | Example | Valid Values |
|-----------|------|----------|-------------|---------|--------------|
| `llm.agent.type` | string | ❌ | Agent architecture | `"react"` | `"react"`, `"plan-execute"`, `"conversational"`, custom |
| `llm.agent.iterations` | int | ❌ | Reasoning iterations | `3` | `> 0` |
| `llm.agent.tools` | string | ❌ | Available tools | `"[\"search\", \"calc\"]"` | JSON array string |

---

### Tool Attributes

Attributes for `llm.tool` spans.

| Attribute | Type | Required | Description | Format | Truncation |
|-----------|------|----------|-------------|--------|------------|
| `llm.tool.name` | string | ✅ | Tool identifier | String | N/A |
| `llm.tool.input` | string | ❌ | Tool input | JSON string | 2KB max |
| `llm.tool.output` | string | ❌ | Tool output | JSON string | 2KB max |

**Example:**
```python
attributes = {
    "llm.tool.name": "web_search",
    "llm.tool.input": "{\"query\": \"kubernetes crashloopbackoff\", \"limit\": 10}",
    "llm.tool.output": "{\"results\": [{\"title\": \"...\", \"url\": \"...\"}], \"count\": 10}"
}
```

---

### Retriever Attributes

Attributes for `llm.retriever` spans.

| Attribute | Type | Required | Description | Example | Valid Values |
|-----------|------|----------|-------------|---------|--------------|
| `llm.retriever.type` | string | ❌ | Retrieval method | `"vector"` | `"vector"`, `"keyword"`, `"hybrid"`, custom |
| `llm.retriever.query` | string | ✅ | Search query | `"kubernetes errors"` | String |
| `llm.retriever.top_k` | int | ❌ | Results requested | `5` | `> 0` |
| `llm.retriever.results_count` | int | ❌ | Actual results returned | `5` | `>= 0` |
| `llm.retriever.source` | string | ✅ | Data source | `"pinecone"` | String (db name, index name, etc.) |

---

### Embedding Attributes

Attributes for `llm.embedding` spans.

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `llm.embedding.input_count` | int | ❌ | Number of inputs embedded | `10` |
| `llm.embedding.dimensions` | int | ❌ | Vector dimensions | `1536` |

---

### Prompt Registry Attributes

Attributes for `llm.prompt_registry` spans.

| Attribute | Type | Required | Description | Example | Format |
|-----------|------|----------|-------------|---------|--------|
| `llm.prompt.id` | string | ✅ | Template ID | `"k8s_log_analysis_v1"` | String |
| `llm.prompt.version` | string | ❌ | Template version | `"v1"`, `"2024-01-10"` | Semver or date |
| `llm.prompt.template_hash` | string | ❌ | Template content hash | `"a3f8d92c"` | SHA-256 (8 chars) |
| `llm.prompt.variables_hash` | string | ❌ | Variables hash | `"b4e9c1d7"` | SHA-256 (8 chars) |
| `llm.prompt.rendered_hash` | string | ❌ | Rendered content hash | `"c5a2f8e3"` | SHA-256 (8 chars) |

**Hashing Behavior:**
- Use SHA-256, truncate to first 8 characters (hex)
- Template hash: hash of raw template content
- Variables hash: hash of JSON-serialized variables (sorted keys)
- Rendered hash: hash of final rendered string

**Purpose:**
- Detect prompt drift over time
- Enable prompt version comparison
- Debug rendering issues

---

### Error Attributes

Attributes for failed operations (any span kind).

| Attribute | Type | Required | Description | Example | Valid Values |
|-----------|------|----------|-------------|---------|--------------|
| `llm.error.type` | string | ❌ | Error category | `"rate_limit"` | `"rate_limit"`, `"timeout"`, `"invalid_input"`, `"auth"`, custom |
| `llm.error.message` | string | ❌ | Error message | `"Rate limit exceeded"` | String |
| `llm.error.code` | string | ❌ | Provider error code | `"429"` | String (HTTP code, provider code) |

**OTel Integration:**
- Also call `span.set_status(StatusCode.ERROR, description)`
- Record exception with `span.record_exception(exception)`

---

## Value Type Specifications

### String

**Encoding:** UTF-8
**Max Length:** Attribute-dependent (see individual specs)
**Truncation:** Indicated with `[TRUNCATED: N chars]...`

### Integer

**Type:** 64-bit signed integer
**Range:** Attribute-dependent (see individual specs)

### Float

**Type:** 64-bit floating point
**Precision:** As provided by language runtime
**Special Values:** Avoid NaN/Infinity (use omission instead)

### Boolean

**Values:** `true` or `false`
**Serialization:** Language-native boolean

### JSON String

**Purpose:** Represent arrays/objects as attribute values
**Format:** Valid JSON, serialized to string
**Truncation:** Apply to serialized string, not object

**Example:**
```python
# Object
tools = ["search", "calculator", "weather"]

# JSON string attribute
attributes["llm.agent.tools"] = json.dumps(tools)
# Result: "[\"search\", \"calculator\", \"weather\"]"
```

---

## Behavioral Requirements

### 1. Attribute Population

**Required Attributes:**
- MUST be present on all spans of the relevant kind
- If unavailable, span creation should fail or warn

**Optional Attributes:**
- MAY be present if data is available
- If unavailable, MUST be omitted (not set to null/empty)

**Example:**
```python
# ✅ Correct
attributes = {
    "llm.model": "gpt-4o",
    "llm.temperature": 0.7
    # llm.usage.total_tokens omitted (not available yet)
}

# ❌ Incorrect
attributes = {
    "llm.model": "gpt-4o",
    "llm.temperature": 0.7,
    "llm.usage.total_tokens": None  # Don't set to None
}
```

---

### 2. Input/Output Capture

**Default Behavior:**
- Auto-capture function inputs/outputs when safe (type-based filtering)
- Primitives (str, int, float, bool): auto-capture
- Dicts/Lists: auto-capture if serializable and <4KB
- Complex objects: omit by default

**Opt-Out:**
```python
@observe.llm(name="call", model="gpt-4o", capture_io=False)
def call_llm(prompt: str):
    ...
```

**Sanitization:**
```python
@observe.llm(name="call", model="gpt-4o", sanitize=True)
def call_llm(user_input: str):
    # SDK applies PII sanitization before logging
    ...
```

---

### 3. Span Lifecycle

**Creation:**
- Span starts when decorated function/context manager enters
- Required attributes set immediately

**Updates:**
- Optional attributes added during execution (e.g., token counts after response)
- Use `span.set_attribute()` for deferred population

**Completion:**
- Span ends when function returns or context manager exits
- Output captured (if enabled)
- Token usage finalized (if applicable)

**Error Handling:**
- Exception triggers error attributes
- Span marked with ERROR status
- Exception re-raised (SDK doesn't suppress)

---

### 4. Context Propagation

**Automatic Nesting:**
- Decorated functions/context managers automatically nest under active span
- No manual context passing required

**Example:**
```python
@observe.agent(name="my_agent")
def run_agent():

    @observe.retriever(name="search")
    def search():
        ...

    @observe.llm(name="generate")
    def generate():
        ...

    search()   # Automatically nested under my_agent
    generate() # Automatically nested under my_agent
```

**Result:**
```
span: llm.agent (my_agent)
├─ span: llm.retriever (search)
└─ span: llm.call (generate)
```

---

### 5. Async Support

**Requirement:**
- All decorators and context managers MUST support async/await
- Context propagation works across async boundaries

**Example:**
```python
@observe.llm(name="async_call", model="gpt-4o")
async def async_llm():
    response = await openai_async.call()
    return response

async with observe.span("llm.workflow", name="async_workflow"):
    result = await async_llm()
```

---

## Backend Adapter Requirements

### Adapter Contract

Backend adapters MUST implement:

1. **Attribute Mapping**
   - Map SDK attributes to backend-specific conventions
   - Preserve semantics (don't change meanings)

2. **Endpoint Configuration**
   - Set OTLP endpoint URL
   - Configure protocol (gRPC/HTTP)
   - Set authentication headers

3. **Resource Attributes**
   - Add backend-specific resource attributes
   - Example: `arize.project_name`, `mlflow.experiment_id`

### Adapter MUST NOT

- ❌ Change span kinds
- ❌ Filter/drop spans
- ❌ Add business logic
- ❌ Modify span lifecycle

### Example Mapping (Arize Adapter)

```python
# SDK attribute → OpenInference attribute
ATTRIBUTE_MAPPING = {
    "llm.model": "llm.model_name",
    "llm.input.messages": "llm.input_messages",
    "llm.output.message": "llm.output_messages",
    "llm.usage.prompt_tokens": "llm.token_count.prompt",
    "llm.usage.completion_tokens": "llm.token_count.completion",
    "llm.tool.name": "tool.name",
}

def map_attributes(self, attributes: dict) -> dict:
    """Map SDK attributes to OpenInference."""
    return {
        ATTRIBUTE_MAPPING.get(k, k): v
        for k, v in attributes.items()
    }
```

---

## Versioning & Stability

### Semantic Versioning

This specification follows [SemVer 2.0.0](https://semver.org/):

- **MAJOR:** Breaking changes (attribute renames, removals)
- **MINOR:** Additions (new attributes, span kinds)
- **PATCH:** Clarifications, fixes (no contract changes)

### Stability Guarantees

**Stable (MUST NOT change):**
- Attribute names (e.g., `llm.model`)
- Attribute types (e.g., string, int)
- Required vs. optional status
- Span kind names

**Can Change (MINOR version):**
- Add new optional attributes
- Add new span kinds
- Expand valid value ranges
- Add new error types

**Breaking Changes (MAJOR version):**
- Rename attributes
- Remove attributes
- Change attribute types
- Change required/optional status

### Deprecation Policy

When an attribute must change:

1. **Deprecation (MINOR version):**
   - Mark old attribute as deprecated (docs)
   - Add new attribute alongside
   - SDK populates both for compatibility

2. **Removal (MAJOR version, ≥6 months later):**
   - Remove deprecated attribute
   - Migration guide provided

**Example:**
```
v1.5.0: Add llm.model.name (new), deprecate llm.model
v1.6.0-v1.9.0: Both attributes populated
v2.0.0: Remove llm.model, only llm.model.name remains
```

---

## Extensions & Custom Attributes

### When to Extend

Extend the contract when:
- You have domain-specific needs (e.g., medical, legal)
- Upstream hasn't standardized your use case
- Experimenting with new patterns

### Extension Guidelines

1. **Use Custom Prefix**
   - Don't pollute `llm.*` namespace
   - Example: `myapp.llm.custom_field`

2. **Document Extensions**
   - Maintain your own `EXTENSIONS.md`
   - Specify type, format, purpose

3. **Don't Override Standard Attributes**
   - If `llm.model` exists, use it
   - Don't create `myapp.model`

**Example:**
```python
# Custom domain-specific attributes
attributes = {
    # Standard attributes
    "llm.model": "gpt-4o",
    "llm.usage.total_tokens": 225,

    # Custom extensions (medical domain)
    "medical.patient_id": "P12345",  # Your extension
    "medical.diagnosis_code": "ICD10-Z00.00"  # Your extension
}
```

---

## Compliance & Validation

### How to Validate Compliance

Implementations SHOULD provide a validator:

```python
from llm_observability.validation import validate_span

# In tests
span = get_test_span()
validate_span(span, expected_kind="llm.call")
# Raises ValidationError if non-compliant
```

### Validation Checks

1. **Required Attributes Present**
2. **Attribute Types Correct**
3. **Value Ranges Valid**
4. **JSON Strings Parseable**
5. **No Reserved Attribute Misuse**

---

## Examples

### Example 1: Simple LLM Call

```python
Span {
    name: "generate_summary",
    kind: INTERNAL,
    attributes: {
        "llm.operation.type": "llm.call",
        "llm.operation.name": "generate_summary",
        "llm.provider": "openai",
        "llm.model": "gpt-4o",
        "llm.temperature": 0.7,
        "llm.max_tokens": 500,
        "llm.streaming": false,
        "llm.input.messages": "[{\"role\": \"user\", \"content\": \"Summarize: ...\"}]",
        "llm.output.message": "{\"role\": \"assistant\", \"content\": \"Summary: ...\"}",
        "llm.usage.prompt_tokens": 150,
        "llm.usage.completion_tokens": 75,
        "llm.usage.total_tokens": 225
    },
    status: OK
}
```

---

### Example 2: Agent with Tools

```python
Span {
    name: "research_agent",
    kind: INTERNAL,
    attributes: {
        "llm.operation.type": "llm.agent",
        "llm.operation.name": "research_agent",
        "llm.agent.type": "react",
        "llm.agent.iterations": 3,
        "llm.agent.tools": "[\"web_search\", \"calculator\"]"
    },
    children: [
        Span {
            name: "search_web",
            kind: INTERNAL,
            attributes: {
                "llm.operation.type": "llm.tool",
                "llm.tool.name": "web_search",
                "llm.tool.input": "{\"query\": \"AI safety\"}",
                "llm.tool.output": "{\"results\": [...], \"count\": 10}"
            }
        },
        Span {
            name: "reason_about_results",
            kind: INTERNAL,
            attributes: {
                "llm.operation.type": "llm.call",
                "llm.operation.name": "reason_about_results",
                "llm.model": "gpt-4o",
                "llm.provider": "openai",
                ...
            }
        }
    ]
}
```

---

### Example 3: RAG Workflow

```python
Span {
    name: "rag_qa_workflow",
    kind: INTERNAL,
    attributes: {
        "llm.operation.type": "llm.workflow",
        "llm.operation.name": "rag_qa_workflow",
        "llm.workflow.steps": "[\"retrieve\", \"rerank\", \"generate\"]"
    },
    children: [
        Span {
            name: "retrieve_docs",
            attributes: {
                "llm.operation.type": "llm.retriever",
                "llm.retriever.query": "kubernetes networking",
                "llm.retriever.type": "vector",
                "llm.retriever.source": "pinecone",
                "llm.retriever.top_k": 10,
                "llm.retriever.results_count": 10
            }
        },
        Span {
            name: "generate_answer",
            attributes: {
                "llm.operation.type": "llm.call",
                "llm.model": "gpt-4o",
                "llm.provider": "openai",
                ...
            }
        }
    ]
}
```

---

## Changelog

### Version 1.0.0 (2026-01-10)

**Initial Release**
- Defined 7 span kinds
- 50+ semantic attributes
- Backend adapter requirements
- Versioning policy

---

## References

- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OpenInference Specification](https://github.com/Arize-ai/openinference)

---

**Maintained By:** LLM Observability SDK Team
**License:** Apache 2.0
**Status:** ✅ Ready for Implementation
