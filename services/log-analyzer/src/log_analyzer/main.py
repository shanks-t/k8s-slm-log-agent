"""FastAPI application for log analysis and extraction."""

import httpx
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from log_analyzer.models.requests import AnalyzeRequest

LOKI_URL = "http://localhost:3100"
LLAMA_URL = "http://localhost:8080"
MODEL_NAME = "llama-3.2-3b-instruct"


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
    # ignore loki logs
    labels.append('container!="loki"')
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
    else:
        # Default: only get errors and warnings
        query += ' |~ "(?i)(error|warn|failed|exception|panic|fatal)"'

    return query


def normalize_log(entry):
    labels = entry["labels"]
    return {
        "time": entry["timestamp"],
        "source": f"{labels.get('namespace')}/{labels.get('container')}",
        "pod": labels.get("pod"),
        "node": labels.get("node"),
        "message": entry["message"],
    }


def build_llm_prompt(normalized_logs, time_range):
    header = (
        f"Cluster: homelab\n"
        f"Time window: {time_range.start.isoformat()} → {time_range.end.isoformat()}\n\n"
        "Logs:\n"
    )

    lines = []
    for log in normalized_logs:
        lines.append(
            f"[{log['time']}] {log['source']} "
            f"(pod={log.get('pod')}, node={log.get('node')})\n"
            f"{log['message']}"
        )

    return header + "\n\n".join(lines)


async def call_llm(prompt: str):
    timeout = httpx.Timeout(
        connect=5.0,
        write=5.0,
        pool=5.0,
        read=180.0,
    )
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Kubernetes reliability engineer. "
                    "Analyze logs and identify root cause, severity, "
                    "and recommended actions."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "max_tokens": 150,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


@app.post("/v1/analyze")
async def analyze_logs(request: AnalyzeRequest):
    query = build_logql_query(request.filters)

    params = {
        "query": query,
        "limit": request.limit,
        "start": int(request.time_range.start.timestamp() * 1e9),
        "end": int(request.time_range.end.timestamp() * 1e9),
        "direction": "backward",
    }

    # --- Query Loki ---
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("data", {}).get("result", [])
    if not results:
        return JSONResponse(
            status_code=404,
            content={"error": "No logs found"},
        )

    # --- Flatten logs ---
    logs = []
    for result in results:
        labels = result["stream"]
        for ts_ns, line in result["values"]:
            logs.append(
                {
                    "timestamp": datetime.utcfromtimestamp(int(ts_ns) / 1e9).isoformat()
                    + "Z",
                    "message": line.strip(),
                    "labels": labels,
                }
            )

    if not logs:
        return JSONResponse(
            status_code=404,
            content={"error": "No logs found"},
        )

    # --- Normalize ---
    normalized = [normalize_log(l) for l in logs]

    # --- Prompt ---
    prompt = build_llm_prompt(normalized, request.time_range)

    # --- LLM ---
    analysis = await call_llm(prompt)

    return {
        "log_count": len(normalized),
        "analysis": analysis,
        "logs": normalized,  # optional: remove later
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
