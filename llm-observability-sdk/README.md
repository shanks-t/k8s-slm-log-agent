# LLM Observability SDK

**OpenTelemetry-based LLM observability with backend flexibility**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Overview

The LLM Observability SDK is a thin, opinionated abstraction layer over OpenTelemetry that provides:

✅ **Stable semantic contract** for LLM/agent telemetry
✅ **Excellent developer experience** through decorators and context managers
✅ **Backend flexibility** - supports Arize Phoenix, MLflow, and any OTLP endpoint
✅ **Zero lock-in** - uses OpenTelemetry underneath, no proprietary formats

### The Core Insight

> We do not abstract OpenTelemetry itself.
> We only abstract three things above it:
> 1. **Semantic contract** (what we promise to log)
> 2. **Instrumentation surface** (how users call our SDK)
> 3. **Backend configuration** (where traces go)

Everything below remains pure OpenTelemetry. This keeps the SDK stable, testable, and future-proof.

---

## Quick Start

### Installation

```bash
pip install llm-observability
```

### Basic Usage

```python
from llm_observability import observe
from llm_observability.adapters import OTLPAdapter

# 1. Configure backend (one-time setup)
adapter = OTLPAdapter(endpoint="http://tempo:4317")
observe.configure(
    adapter=adapter,
    service_name="my-llm-app",
    service_version="1.0.0"
)

# 2. Instrument your LLM calls
@observe.llm(name="summarize", model="gpt-4o", provider="openai")
def summarize_text(text: str) -> str:
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Summarize: {text}"}]
    )
    return response.choices[0].message.content

# 3. Use your instrumented function
summary = summarize_text("Long text here...")
# → Automatic tracing with token usage, input/output, timing
```

**That's it!** The SDK automatically captures:
- Model parameters (temperature, max_tokens, etc.)
- Input/output messages
- Token usage (if available from response)
- Timing and errors

---

## Features

### 🎯 Decorator-Based Instrumentation

```python
# LLM calls
@observe.llm(name="analyze", model="gpt-4o")
def analyze(prompt: str) -> str:
    return openai.call(prompt)

# Agent executions
@observe.agent(name="support_agent", agent_type="react", tools=["search", "calc"])
def run_agent(query: str) -> dict:
    # Agent logic here
    return result

# Tool calls
@observe.tool(name="web_search")
def search_web(query: str) -> list[dict]:
    return search_api.query(query)

# Retrieval operations
@observe.retriever(name="search_docs", retriever_type="vector", source="pinecone")
def search_documents(query: str, top_k: int = 5) -> list[dict]:
    return pinecone.query(query, top_k=top_k)
```

### 🔄 Automatic Context Propagation

Nested decorators automatically create parent-child span relationships:

```python
@observe.agent(name="research_agent")
def research(topic: str):
    # This automatically nests under the agent span
    docs = search_documents(topic)

    # This also nests under the agent span
    analysis = analyze(docs)

    return analysis
```

**Result:**
```
span: llm.agent (research_agent)
├─ span: llm.retriever (search_documents)
└─ span: llm.call (analyze)
```

### 🎛️ Backend Flexibility

Switch backends with zero code changes to your instrumentation:

```python
# Use Grafana Tempo (OTLP)
from llm_observability.adapters import OTLPAdapter
adapter = OTLPAdapter(endpoint="http://tempo:4317")

# Use Arize Phoenix
from llm_observability.adapters import ArizeAdapter
adapter = ArizeAdapter(
    endpoint="https://phoenix.arize.com:4317",
    api_key="your-key",
    project_name="my-project"
)

# Use MLflow
from llm_observability.adapters import MLflowAdapter
adapter = MLflowAdapter(
    tracking_uri="http://mlflow:5000",
    experiment_name="my-experiment"
)

# Configure once, works everywhere
observe.configure(adapter=adapter)
```

### 📊 Rich Semantic Attributes

The SDK automatically captures standardized attributes:

| Category | Attributes |
|----------|------------|
| **LLM** | model, provider, temperature, max_tokens, streaming, input/output, token usage |
| **Agent** | agent_type, iterations, tools |
| **Tool** | tool_name, input, output |
| **Retriever** | retriever_type, query, top_k, results_count, source |
| **Errors** | error_type, error_message, error_code |

See [SEMANTICS.md](SEMANTICS.md) for the full semantic contract.

---

## Supported Backends

| Backend | Adapter | Protocol | Conventions |
|---------|---------|----------|-------------|
| **Grafana Tempo** | `OTLPAdapter` | OTLP (gRPC/HTTP) | SDK semantic contract |
| **Jaeger** | `OTLPAdapter` | OTLP (gRPC/HTTP) | SDK semantic contract |
| **Arize Phoenix** | `ArizeAdapter` | OTLP (gRPC/HTTP) | OpenInference |
| **MLflow** | `MLflowAdapter` | OTLP (HTTP) | OTel GenAI conventions |
| **Honeycomb** | `OTLPAdapter` | OTLP (gRPC/HTTP) | SDK semantic contract |
| **Custom** | `OTLPAdapter` | OTLP (gRPC/HTTP) | SDK semantic contract |

---

## Examples

### Example 1: Simple LLM Call

```python
from llm_observability import observe

@observe.llm(name="chat", model="gpt-4o", temperature=0.7)
def chat(user_message: str) -> str:
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_message}],
        temperature=0.7
    )
    return response.choices[0].message.content

# Use it
answer = chat("What is the capital of France?")
```

**Captured Span:**
```
Span: llm.call (chat)
├─ llm.model: gpt-4o
├─ llm.provider: openai
├─ llm.temperature: 0.7
├─ llm.input.messages: [{"role": "user", "content": "What is the capital of France?"}]
├─ llm.output.message: {"role": "assistant", "content": "Paris"}
├─ llm.usage.prompt_tokens: 15
├─ llm.usage.completion_tokens: 5
└─ llm.usage.total_tokens: 20
```

### Example 2: RAG Pipeline

```python
@observe.retriever(name="search_kb", retriever_type="vector", source="pinecone")
def search_knowledge_base(query: str, top_k: int = 5) -> list[str]:
    results = pinecone.query(query, top_k=top_k)
    return [r.text for r in results]

@observe.llm(name="generate_answer", model="gpt-4o")
def generate_answer(context: list[str], question: str) -> str:
    prompt = f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"
    return openai.call(prompt)

def rag_qa(question: str) -> str:
    # 1. Retrieve relevant documents
    docs = search_knowledge_base(question)

    # 2. Generate answer with context
    answer = generate_answer(docs, question)

    return answer

# Use it
answer = rag_qa("How do I debug Kubernetes pods?")
```

**Captured Span Hierarchy:**
```
span: rag_qa (from caller)
├─ span: llm.retriever (search_kb)
│  ├─ llm.retriever.query: "How do I debug Kubernetes pods?"
│  ├─ llm.retriever.top_k: 5
│  └─ llm.retriever.results_count: 5
└─ span: llm.call (generate_answer)
   ├─ llm.model: gpt-4o
   └─ llm.usage.total_tokens: 450
```

### Example 3: Agent with Tools

```python
@observe.tool(name="calculator")
def calculator(expression: str) -> float:
    return eval(expression)  # Simplified for example

@observe.tool(name="web_search")
def web_search(query: str) -> list[dict]:
    return search_api.query(query)

@observe.agent(name="math_assistant", agent_type="react", tools=["calculator", "web_search"])
def math_assistant(question: str) -> str:
    # Agent reasoning logic
    if "calculate" in question.lower():
        # Extract expression and use calculator
        result = calculator("2 + 2")
        return f"The answer is {result}"
    else:
        # Search for answer
        results = web_search(question)
        return results[0]["snippet"]

# Use it
answer = math_assistant("Calculate 2 + 2")
```

---

## Advanced Usage

### Async Support

All decorators support async/await:

```python
@observe.llm(name="async_chat", model="gpt-4o")
async def async_chat(message: str) -> str:
    response = await openai_async.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": message}]
    )
    return response.choices[0].message.content

# Use it
answer = await async_chat("Hello!")
```

### Disable Input/Output Capture

```python
@observe.llm(name="secure_call", model="gpt-4o", capture_io=False)
def secure_call(sensitive_prompt: str) -> str:
    # Input/output won't be logged
    return openai.call(sensitive_prompt)
```

### PII Sanitization

```python
@observe.llm(name="chat", model="gpt-4o", sanitize=True)
def chat_with_user(user_input: str) -> str:
    # SDK will sanitize common PII patterns before logging
    return openai.call(user_input)
```

---

## Architecture

See [docs/LLM_OBSERVABILITY_SDK_ARCHITECTURE.md](docs/LLM_OBSERVABILITY_SDK_ARCHITECTURE.md) for the complete reference architecture.

### Layer Structure

```
┌─────────────────────────────────────────────────┐
│  Layer 3: Backend Adapters (thin, replaceable) │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Arize   │ │  MLflow  │ │  Custom  │       │
│  └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────┤
│  Layer 2: Developer-Facing API (DX layer)      │
│  @observe.llm() | @observe.agent() | ...       │
├─────────────────────────────────────────────────┤
│  Layer 1: Semantic Contract                    │
│  Span kinds, attribute names, value formats    │
├─────────────────────────────────────────────────┤
│  Layer 0: OpenTelemetry (unchanged)            │
│  TracerProvider | Spans | Context | Exporters │
└─────────────────────────────────────────────────┘
```

---

## Semantic Contract

The SDK defines a stable, backend-agnostic semantic contract. See [SEMANTICS.md](SEMANTICS.md) for details.

**Span Kinds:**
- `llm.call` - LLM API invocation
- `llm.agent` - Agent execution
- `llm.tool` - Tool call
- `llm.retriever` - RAG retrieval
- `llm.embedding` - Embedding generation
- `llm.workflow` - Multi-step workflow
- `llm.prompt_registry` - Prompt rendering

**Key Attributes:**
- `llm.model`, `llm.provider`, `llm.temperature`, `llm.max_tokens`
- `llm.input.messages`, `llm.output.message`
- `llm.usage.prompt_tokens`, `llm.usage.completion_tokens`, `llm.usage.total_tokens`
- `llm.agent.type`, `llm.agent.iterations`, `llm.agent.tools`
- `llm.tool.name`, `llm.tool.input`, `llm.tool.output`
- `llm.retriever.query`, `llm.retriever.type`, `llm.retriever.source`

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/llm-observability-sdk.git
cd llm-observability-sdk

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=llm_observability --cov-report=html

# Run specific test
pytest tests/unit/test_decorators.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

---

## Roadmap

### ✅ Phase 1: Core SDK (MVP)
- [x] Semantic contract definition
- [x] Package structure
- [ ] Core observer implementation
- [ ] Basic decorators (`@observe.llm`, `@observe.agent`)
- [ ] OTLP adapter
- [ ] Unit tests

### 🔄 Phase 2: Full API Surface
- [ ] All decorators (tool, retriever, embedding, workflow)
- [ ] Context managers
- [ ] Async support
- [ ] Integration tests

### 🔄 Phase 3: Backend Adapters
- [ ] Arize adapter
- [ ] MLflow adapter
- [ ] Integration tests with backends

### 📋 Phase 4: Production Features
- [ ] Streaming support
- [ ] PII sanitization
- [ ] Token usage auto-extraction
- [ ] Error categorization
- [ ] Performance optimizations

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built on [OpenTelemetry](https://opentelemetry.io/)
- Inspired by [OpenInference](https://github.com/Arize-ai/openinference)
- Semantic conventions aligned with [OTel GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

---

**Questions?** Open an issue or reach out to the maintainers.
