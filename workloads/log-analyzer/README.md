# Log Analyzer Service

A small, Unix‑style log analysis service that transforms Kubernetes logs into human‑readable diagnoses using an LLM.

This project intentionally favors **simple data flow over heavy abstractions**. Modules, models, and directories are introduced only when sustained usage creates real pressure — not in anticipation of future features.

---

## Design Philosophy

This service is designed like a Unix tool:

* **Do one thing well**: fetch logs, normalize them, and analyze them with an LLM
* **Favor pipelines over frameworks**: Loki → normalize → prompt → LLM → output
* **Treat text as the primary interface**: LLM output is plain text by default
* **Delay contracts**: API schemas and response models are added only when behavior stabilizes
* **Let pressure shape structure**: directories and abstractions exist only if actively used

FastAPI is used as a thin HTTP wrapper around this pipeline — not as the driver of the architecture.

---

## High‑Level Architecture

**Node Assignment:** Node 1 (lightweight workload)
**Namespace:** `log-analyzer`

**External Dependencies:**

* **Loki** (`logging` namespace) — log storage and retrieval
* **LLaMA.cpp** (`llm` namespace) — local LLM inference
* **Tempo** (`logging` namespace) — distributed tracing backend

At runtime, the service behaves like a single transformation program:

```
Loki logs → normalization → prompt construction → LLM → analysis text
```

---

## Repository Layout

```
log_analyzer/
├── main.py        # HTTP wiring and lifecycle management
├── pipeline.py    # Core log → analysis pipeline
├── loki.py        # Loki query construction and retrieval
├── llm.py         # LLM invocation (sync + streaming)
├── config.py      # Environment‑driven configuration
├── models/        # Request schemas only (responses are intentionally untyped)
└── observability/ # Logging + OpenTelemetry setup
```

### Why this structure

* **`main.py`** is glue — it should be readable top‑to‑bottom
* **`pipeline.py`** is the program — callable without HTTP
* **`loki.py` and `llm.py`** are adapters at the edges
* **`models/`** contains only *input* contracts (Pydantic request validation)
* **`observability/`** is a stable cross‑cutting concern

Unused directories (clients, services, evaluation) are intentionally removed until real demand emerges.

---

## API Overview

### `POST /v1/analyze`

Non‑streaming endpoint for programmatic log analysis.

**Request**

```json
{
  "time_range": {
    "start": "2025-12-26T00:00:00Z",
    "end": "2025-12-27T00:00:00Z"
  },
  "filters": {
    "namespace": "log-analyzer",
    "pod": "log-analyzer-.*"
  },
  "limit": 15
}
```

**Response**

The response is intentionally **not bound to a strict schema**. The current output reflects real behavior, not a promised contract:

```json
{
  "log_count": 15,
  "analysis": "Based on the provided logs, there is no apparent issue...",
  "logs": [
    {
      "time": "2025-12-27T17:45:18.492042Z",
      "source": "llm/llama-server",
      "message": "request: POST /v1/chat/completions 200",
      "pod": "llama-cpp-77c6884846-2rj47",
      "node": "node-2"
    }
  ]
}
```

The shape may evolve as structured extraction is enforced.

---

### `POST /v1/analyze/stream`

Streaming endpoint for interactive use (CLI tools, dashboards).

Returns formatted plain text as it is generated:

```
=== Log Analyzer ===
Cluster: homelab
Time Window: 2025-12-26 → 2025-12-27
Log Count: 15

--- Logs ---
[2025-12-27T17:45:18.492042Z] llm/llama-server (pod=llama-cpp-77c6884846-2rj47)
request: POST /v1/chat/completions 200

--- Analysis ---
Based on the provided logs, there is no apparent issue...

=== End of Analysis ===
```

This endpoint treats text as the primary interface — similar to a Unix command writing to stdout.

---

## Why There Are No Response Models

Response schemas are intentionally omitted at this stage.

Reasons:

* LLM output is probabilistic and evolving
* The service currently serves humans, not downstream machines
* Premature schemas create false guarantees
* Observability (traces + logs) provides better truth than OpenAPI during exploration

Response models will be introduced **only when**:

* Structured LLM output is enforced and validated
* Clients depend on stable fields
* Backward compatibility matters

---

## Configuration

All configuration is environment‑driven, following the [12-factor app methodology](https://12factor.net/config). This allows the same code to run in both Kubernetes and local development with different runtime configurations.

### Environment Variables

All settings use the `LOG_ANALYZER_` prefix and are defined in [`config.py`](src/log_analyzer/config.py):

* `LOG_ANALYZER_LOKI_URL` — Loki service endpoint (default: `http://loki.logging.svc.cluster.local:3100`)
* `LOG_ANALYZER_LLM_URL` — LLaMA.cpp endpoint (default: `http://llama-cpp.llm.svc.cluster.local:8080`)
* `LOG_ANALYZER_SERVICE_NAME` — Service name for telemetry (default: `log-analyzer`)
* `LOG_ANALYZER_LOG_LEVEL` — Logging level (default: `INFO`)
* `LOG_ANALYZER_OTEL_ENABLED` — Enable OpenTelemetry (default: `true`)

### Local Development Setup

For local development with `just dev`, create a `.env` file in the `workloads/log-analyzer/` directory:

```bash
# workloads/log-analyzer/.env
LOG_ANALYZER_LOKI_URL=http://localhost:3100
LOG_ANALYZER_LLM_URL=http://localhost:8080
```

The `just dev` command port-forwards Kubernetes services to localhost, so the local FastAPI server needs to use `localhost` URLs instead of Kubernetes DNS names.

### Kubernetes Deployment

In Kubernetes, the default values use cluster DNS (e.g., `loki.logging.svc.cluster.local`), which are automatically resolved by the cluster's DNS service. No `.env` file is needed — configuration is injected via ConfigMaps or the deployment manifest.

---

## Observability

The service emits rich OpenTelemetry traces and structured logs.

Each request produces spans for:

* Loki query execution
* Log normalization
* LLM inference (including token counts)

Streaming spans are scoped inside the generator to preserve trace context throughout the response lifecycle.

Logs include trace and span IDs for full trace‑to‑logs correlation in Grafana.

---

## Development

### Local Development (Kubernetes‑backed)

```bash
just dev
cd workloads/log-analyzer
uv run fastapi dev src/log_analyzer/main.py
```

### Testing

```bash
just test-stream
just test-stream namespace=log-analyzer
```

---

## Kubernetes Deployment

Build and deploy locally to k8s:
```sh
just release
```
This will use justfile recipe to deploy:
[../../justfile#L234](../../justfile#L234)

---

## When Structure Will Grow

New modules or models will be added **only when justified by usage**, such as:

* Prompt templates becoming first‑class artifacts
* Enforced JSON extraction from the LLM
* Offline evaluation becoming a production concern
* Multiple LLM backends or routing strategies

Until then, the service remains intentionally small, inspectable, and honest about what it does today.
