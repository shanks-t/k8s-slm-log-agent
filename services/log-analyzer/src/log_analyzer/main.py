"""FastAPI application for log analysis and extraction."""

from datetime import datetime, timedelta
import httpx

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from log_analyzer.models.requests import AnalyzeRequest

LOKI_URL = "http://localhost:3100"

app = FastAPI(
    title="Log Analyzer Service",
    description="LLM-powered log analysis and structured extraction",
    version="0.1.0",
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "log-analyzer"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "service": "log-analyzer",
        "version": "0.1.0",
    }


def build_logql_query(filters) -> str:
    """Build LogQL query from filters."""
    # Build label selector
    labels = []
    if filters.namespace:
        labels.append(f'namespace="{filters.namespace}"')
    if filters.pod:
        labels.append(f'pod=~"{filters.pod}"')  # Use regex match
    if filters.container:
        labels.append(f'container="{filters.container}"')
    if filters.node:
        labels.append(f'node="{filters.node}"')

    # Start with label matcher
    query = "{" + ",".join(labels) + "}" if labels else '{job=~".+"}'

    # Add log line filter if provided
    if filters.log_filter:
        query += f' |~ "{filters.log_filter}"'

    return query


@app.post("/v1/analyze")
async def analyze_logs(request: AnalyzeRequest):
    """Query Loki API for log entries."""
    query = build_logql_query(request.filters)

    params = {
        "query": query,
        "limit": request.limit,
        "start": int(request.time_range.start.timestamp() * 1e9),  # Nanoseconds
        "end": int(request.time_range.end.timestamp() * 1e9),
        "direction": "backward",  # Most recent first
    }

    try:
        response = httpx.get(
            f"{LOKI_URL}/loki/api/v1/query_range", params=params, timeout=10
        )
        response.raise_for_status()
        return {"raw_loki_response": response.json()}
    except httpx.HTTPError as exc:
        print(f"HTTP Exception for {exc.request.url} - {exc}")
        return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
