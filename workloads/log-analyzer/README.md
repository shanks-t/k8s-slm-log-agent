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

- **Streaming log analysis:** Real-time LLM-powered log analysis with streaming responses
- **OpenTelemetry instrumentation:** Distributed tracing with custom spans for Loki queries and LLM calls
- **Structured logging:** JSON logs with automatic trace context injection (trace_id, span_id)
- **Trace-to-logs correlation:** Bidirectional linking between traces and logs in Grafana
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

### `POST /v1/analyze/stream`

Streaming endpoint that analyzes logs and returns results in real-time.

**Request:**
```json
{
  "time_range": {
    "start": "2025-12-26T00:00:00Z",
    "end": "2025-12-27T00:00:00Z"
  },
  "filters": {
    "namespace": "log-analyzer",
    "pod": "log-analyzer-.*",  // Regex pattern
    "container": "log-analyzer",
    "node": "node-1"
  },
  "limit": 15  // Max logs to analyze (default: 15, max: 200)
}
```

**Response:** Streaming text with log summary and LLM analysis

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

The service emits distributed traces with the following span structure:

```
POST /v1/analyze/stream
├── analyze_logs_stream (custom span with namespace, log_limit attributes)
│   ├── query_loki (custom span with logql.query attribute)
│   ├── flatten_logs (custom span with logs.flattened_count)
│   ├── normalize_logs (custom span)
│   └── call_llm (custom span with llm.model, llm.tokens_generated)
```

**Key Design:** All spans are created inside the generator function (`event_stream()`) to maintain span context during streaming. This ensures child spans properly attach and logs capture the trace_id.

**Span Filtering:** The service filters out noisy "http send" spans from streaming responses using a custom `FilterSpanProcessor`.

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

## Observability in Grafana

### Viewing Traces

1. Navigate to **Explore** → **Tempo**
2. Search for service: `log-analyzer`
3. Click on a `POST /v1/analyze/stream` trace
4. Expand spans to see:
   - `analyze_logs_stream` (root)
   - `query_loki` (with LogQL query)
   - `call_llm` (with model and token count)
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

Check the time range and filters in your request. The service filters logs to only include errors/warnings by default:

```logql
{namespace="..."} |~ "(?i)(error|warn|failed|exception|panic|fatal)"
```

To see all logs, provide a custom `log_filter` in the request.

### Traces Not Appearing in Tempo

1. Verify Tempo is running: `kubectl get pods -n logging | grep tempo`
2. Check OTLP endpoint: `OTEL_EXPORTER_OTLP_ENDPOINT` in ConfigMap
3. View service logs for OTLP export errors

## Next Steps

- [ ] Add `/v2/analyze` endpoint with vector database retrieval (Phase 3B)
- [ ] Implement evaluation framework with golden dataset
- [ ] Add Grafana dashboards for extraction accuracy metrics
- [ ] Expose via Envoy Gateway HTTPRoute with authentication
