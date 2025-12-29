# Log Analyzer Service

FastAPI service for LLM-powered log analysis with OpenTelemetry instrumentation for distributed tracing and structured logging.

## Architecture

**Node Assignment:** Node 1 (lightweight workload)
**Namespace:** `log-analyzer`
**Dependencies:**
- Loki (`logging` namespace) - Log storage and retrieval
- LLaMA.cpp (`llm` namespace) - LLM inference
- Tempo (`logging` namespace) - Distributed tracing backend

## Features

- **Dual API endpoints:** Streaming (real-time) and JSON (programmatic) log analysis
- **OpenTelemetry instrumentation:** Distributed tracing with custom spans for Loki queries and LLM calls
- **Structured logging:** JSON logs with automatic trace context injection (trace_id, span_id)
- **Trace-to-logs correlation:** Bidirectional linking between traces and logs in Grafana
- **Evaluation framework:** Automated LLM quality validation comparing analysis with raw logs
- **Kubernetes-native:** ConfigMap-based configuration, health checks, resource limits

## Development

### Local Development (Port-Forwarding)

For local development with the Kubernetes-deployed services:

```bash
# From repo root - port-forward Loki, LLaMA, and Tempo
just dev

# In another terminal - run the service locally
cd workloads/log-analyzer
uv run fastapi dev src/log_analyzer/main.py
```

This starts the FastAPI app locally with hot-reload while connecting to services in Kubernetes.

### Testing Locally

```bash
# Test the streaming endpoint (default: kube-system namespace)
just test-stream

# Analyze a specific namespace
just test-stream namespace=log-analyzer
```

## Kubernetes Deployment

### Building and Deploying

**Prerequisites:**
- Docker Desktop running
- SSH access to node1

**Build and deploy:**

```bash
# From workloads/log-analyzer directory
# 1. Build AMD64 image for K8s nodes
docker build --platform linux/amd64 -t log-analyzer:latest .

# 2. Export and transfer to node1
docker save log-analyzer:latest -o /tmp/log-analyzer.tar
scp /tmp/log-analyzer.tar node1:/tmp/

# 3. Load into k3s and restart
ssh node1 "sudo cp /tmp/log-analyzer.tar /var/lib/rancher/k3s/agent/images/ && sudo systemctl restart k3s"

# 4. Deploy Kubernetes manifests
kubectl apply -f k8s/

# 5. Verify deployment
kubectl get pods -n log-analyzer
kubectl logs -n log-analyzer -l app=log-analyzer --tail=20
```

### Kubernetes Manifests

- **00-namespace.yaml** - Creates `log-analyzer` namespace
- **01-configmap.yaml** - Environment configuration (Loki/LLaMA/Tempo URLs)
- **02-deployment.yaml** - Deployment with node selector for Node 1
- **03-service.yaml** - ClusterIP service on port 8000

### Testing the Deployed Service

**Option 1: Test from inside the cluster**

```bash
just test-k8s                    # Default: log-analyzer namespace
just test-k8s namespace=llm      # Analyze llm namespace logs
```

This creates a temporary curl pod to test the service using internal Kubernetes DNS.

**Option 2: Test via port-forward**

```bash
# Terminal 1 - Start port-forward
just dev-k8s

# Terminal 2 - Test the service
just test-k8s-local namespace=log-analyzer
```

## API Endpoints

### `POST /v1/analyze`

JSON endpoint for programmatic log analysis. Returns structured data suitable for automation and evaluation.

**Request:**
```json
{
  "time_range": {
    "start": "2025-12-26T00:00:00Z",
    "end": "2025-12-27T00:00:00Z"
  },
  "filters": {
    "namespace": "log-analyzer",
    "pod": "log-analyzer-.*",  // Regex pattern (optional)
    "container": "log-analyzer",  // Optional
    "node": "node-1"  // Optional
  },
  "limit": 15  // Max logs to analyze (default: 15, max: 200)
}
```

**Response:**
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

**Use cases:** Evaluation scripts, CI/CD pipelines, automated monitoring

### `POST /v1/analyze/stream`

Streaming endpoint that analyzes logs and returns results in real-time. Same request format as `/v1/analyze`.

**Response:** Streaming text with formatted header, logs, and LLM analysis:
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

**Use cases:** Interactive CLI tools, web dashboards, real-time monitoring

### `GET /health`

Health check endpoint returning service status and version.

## Configuration

Environment variables (set via ConfigMap in Kubernetes):

- `LOKI_URL` - Loki service URL (default: `http://localhost:3100`)
- `LLAMA_URL` - LLaMA.cpp service URL (default: `http://localhost:8080`)
- `MODEL_NAME` - LLM model name (default: `llama-3.2-3b-instruct`)
- `OTEL_EXPORTER_OTLP_ENDPOINT` - Tempo OTLP endpoint (default: `http://localhost:4317`)
- `DEPLOYMENT_ENVIRONMENT` - Environment name (default: `local`)

## OpenTelemetry Instrumentation

Both endpoints emit distributed traces with comprehensive instrumentation:

### `/v1/analyze` (JSON endpoint)
```
POST /v1/analyze
└── analyze_logs (root span)
    ├── Attributes: namespace, log_limit, time_range_hours
    ├── query_loki
    │   └── Attributes: logql.query, logql.limit, loki.results_count
    ├── flatten_logs
    │   └── Attributes: logs.flattened_count
    ├── normalize_logs
    └── call_llm
        └── Attributes: llm.model, llm.max_tokens, llm.temperature,
                        llm.streaming=false, llm.tokens_prompt,
                        llm.tokens_completion, llm.tokens_total
```

### `/v1/analyze/stream` (Streaming endpoint)
```
POST /v1/analyze/stream
└── analyze_logs_stream (root span)
    ├── Attributes: namespace, log_limit, time_range_hours
    ├── query_loki
    │   └── Attributes: logql.query, logql.limit, loki.results_count
    ├── flatten_logs
    │   └── Attributes: logs.flattened_count
    ├── normalize_logs
    └── stream_llm (call_llm span)
        └── Attributes: llm.model, llm.max_tokens, llm.temperature,
                        llm.streaming=true, llm.tokens_generated
```

**Key Design:** All spans in the streaming endpoint are created inside the generator function (`event_stream()`) to maintain span context during streaming. This ensures child spans properly attach and logs capture the trace_id.

**Span Filtering:** The service filters out noisy "http send" spans from streaming responses using a custom `FilterSpanProcessor`.

**Token Tracking:** Both endpoints track LLM token usage in spans, enabling cost analysis and performance optimization.

## Structured Logging

Logs are emitted in JSON format with automatic trace context injection:

```json
{
  "timestamp": "2025-12-27 01:13:09,947",
  "level": "INFO",
  "logger": "log_analyzer.main",
  "message": "Starting log analysis",
  "trace_id": "51c9c4f72d2acc07a18f0c080b1da96e",
  "span_id": "025fa416bc10b378",
  "trace_flags": 1,
  "namespace": "log-analyzer",
  "limit": 15
}
```

These logs are scraped by Grafana Alloy and stored in Loki, enabling trace-to-logs correlation in Grafana.

## Evaluation Framework

The service includes an automated evaluation system that compares LLM analysis quality against raw logs.

### Running Evaluations

From the repo root:

```bash
# Evaluate last 30 minutes of llm namespace
just evaluate llm 30m

# Evaluate last 1 hour of kube-system namespace
just evaluate kube-system 1h

# Evaluate last 24 hours of log-analyzer namespace (default)
just evaluate log-analyzer 24h
```

### How It Works

The evaluation script (`helpers/evaluate.py`):

1. **Queries both endpoints** with identical parameters:
   - `/v1/analyze` (LLM analysis)
   - Loki API directly (raw logs)

2. **Saves side-by-side comparison** to `tmp/evaluation-<timestamp>.json`:
   ```json
   {
     "metadata": {
       "timestamp": "20251227-202234",
       "namespace": "llm",
       "duration": "30m",
       "time_range": { "start": "...", "end": "..." }
     },
     "llm_analysis": {
       "output": "Based on the provided logs...",
       "char_count": 3624
     },
     "raw_logs": {
       "count": 15,
       "logs": [ /* Full log entries with labels */ ]
     },
     "comparison": {
       "logs_analyzed": 15,
       "analysis_length": 3624,
       "has_error_in_analysis": false,
       "has_no_logs": false
     }
   }
   ```

3. **Enables validation** of:
   - Did the LLM hallucinate logs that don't exist?
   - Did the LLM miss important logs?
   - Is the analysis quality improving over time?

### Use Cases

- **Prompt tuning:** Compare before/after when changing system prompts
- **Model selection:** Evaluate different models on the same dataset
- **Regression testing:** Ensure code changes don't degrade analysis quality
- **Golden dataset creation:** Build a library of evaluation cases

### Implementation Details

- **Single Python script:** `helpers/evaluate.py` (no bash dependencies)
- **UV integration:** Uses `uv run` for hermetic Python environment
- **Port-forward management:** Automatically sets up and tears down connections
- **Time range parsing:** Supports `5m`, `2h`, `24h` duration formats

## Observability in Grafana

### Viewing Traces

1. Navigate to **Explore** → **Tempo**
2. Search for service: `log-analyzer`
3. Click on a `POST /v1/analyze` or `POST /v1/analyze/stream` trace
4. Expand spans to see:
   - `analyze_logs` or `analyze_logs_stream` (root)
   - `query_loki` (with LogQL query)
   - `call_llm` or `stream_llm` (with model and token count)
5. Click **"Logs for this span"** to see correlated logs

### Viewing Logs

1. Navigate to **Explore** → **Loki**
2. Query: `{namespace="log-analyzer"} | json`
3. Logs with `trace_id` fields have clickable links to traces in Tempo

## Resource Configuration

**Requests:**
- CPU: 200m (0.2 cores)
- Memory: 256Mi

**Limits:**
- CPU: 1000m (1 core)
- Memory: 1Gi

## Troubleshooting

### Context Size Exceeded Errors

If you see `"the request exceeds the available context size"` errors in LLM logs:

**Cause:** Too many logs sent to LLM, exceeding the 4096 token context window.

**Solution:** Reduce the `limit` parameter in your request (default is 15, which fits comfortably in the context window).

### No Logs Found

Check the time range and filters in your request. The service no longer applies restrictive default filters - noise filtering happens upstream at the Alloy ingestion level.

**Noise filtering strategy:**
- **Alloy (ingestion)**: Drops health checks, successful access logs (200), and k8s probes before storage
- **Log-analyzer (retrieval)**: Retrieves all logs unless a custom `log_filter` is specified

If you still see "no logs found", the namespace may genuinely have no logs in the specified time range, or Alloy's drop filters may be too aggressive.

To see ALL logs including those dropped by Alloy, temporarily remove the `stage.drop` blocks from `platform/o11y/03-alloy-values.yaml` and redeploy.

### Traces Not Appearing in Tempo

1. Verify Tempo is running: `kubectl get pods -n logging | grep tempo`
2. Check OTLP endpoint: `OTEL_EXPORTER_OTLP_ENDPOINT` in ConfigMap
3. View service logs for OTLP export errors

## Next Steps

- [ ] Build golden dataset library from evaluation runs
- [ ] Add Grafana dashboards for LLM quality metrics (accuracy, hallucination rate)
- [ ] Implement `/v2/analyze` endpoint with vector database retrieval (Phase 3B)
- [ ] Add automated evaluation in CI/CD pipeline
- [ ] Expose via Envoy Gateway HTTPRoute with authentication
