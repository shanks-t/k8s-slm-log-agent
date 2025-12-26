# Log Analyzer Service

FastAPI service for LLM-powered log analysis and structured extraction.

## Development

```bash
# From repo root
uv sync

# Run the service
cd services/log-analyzer
uv run fastapi dev src/log_analyzer/main.py

# Or with uvicorn
uv run uvicorn log_analyzer.main:app --reload
```

## Docker Build

```bash
docker build -t log-analyzer:latest .
```

## Deployment

See `k8s/log-analyzer/` for Kubernetes manifests.
