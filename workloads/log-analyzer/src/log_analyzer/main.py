"""FastAPI application for log analysis and extraction."""

from contextlib import asynccontextmanager
import json
import os
import httpx
from datetime import datetime, UTC


from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

from log_analyzer.models.requests import AnalyzeRequest
from log_analyzer.observability import setup_telemetry, get_tracer
from log_analyzer.observability.logging import setup_logging, get_logger

# Read from environment variables (set by k8s ConfigMap or default to localhost for local dev)
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
LLAMA_URL = os.getenv("LLAMA_URL", "http://localhost:8080")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.2-3b-instruct")

# Initialize structured logging with trace context
setup_logging(level="INFO")
logger = get_logger(__name__)

# Get tracer for manual span creation
tracer = get_tracer(__name__)


@asynccontextmanager
async def check_dependencies(app: FastAPI):
    # startup phase
    async with httpx.AsyncClient(timeout=2) as client:
        await client.get(f"{LOKI_URL}/ready")
        await client.get(f"{LLAMA_URL}/v1/models")

    # hand conrol back to FastAPI
    yield


app = FastAPI(
    title="Log Analyzer Service",
    description="LLM-powered log analysis and structured extraction",
    version="0.1.0",
    lifespan=check_dependencies,
)

# Initialize OpenTelemetry tracing
setup_telemetry(app, service_name="log-analyzer", service_version="0.1.0")


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
        # TODO: need to review how logs are classified to make sure i am not filtering out important logs
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
                    "timestamp": datetime.fromtimestamp(int(ts_ns) / 1e9, UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
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


def build_text_header(normalized_logs, time_range):
    lines = [
        "=== Log Analyzer ===",
        "Cluster: homelab",
        f"Time Window: {time_range.start.date()} → {time_range.end.date()}",
        f"Log Count: {len(normalized_logs)}",
        "",
        "--- Logs ---",
    ]

    for log in normalized_logs:
        lines.append(
            f"[{log['time']}] {log['source']} "
            f"(pod={log.get('pod')}, node={log.get('node')})"
        )
        lines.append(log["message"])
        lines.append("")

    lines.append("--- Analysis ---")
    lines.append("")  # blank line before streaming starts
    return "\n".join(lines)


async def stream_llm(prompt: str):
    # Create a span to trace the LLM streaming call
    with tracer.start_as_current_span("call_llm") as llm_span:
        # Add LLM-specific attributes for debugging
        llm_span.set_attribute("llm.model", MODEL_NAME)
        llm_span.set_attribute("llm.max_tokens", 200)
        llm_span.set_attribute("llm.temperature", 0.3)
        llm_span.set_attribute("llm.streaming", True)
        llm_span.set_attribute("llm.provider", "llama-cpp")

        logger.info(
            "Calling LLM for analysis",
            extra={
                "extra_fields": {
                    "model": MODEL_NAME,
                    "max_tokens": 200,
                    "temperature": 0.3,
                }
            },
        )

        timeout = httpx.Timeout(
            connect=5.0,
            write=5.0,
            pool=5.0,
            read=None,  # IMPORTANT: disable read timeout for streaming
        )

        tokens_generated = 0

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{LLAMA_URL}/v1/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "stream": True,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a Kubernetes reliability engineer.\n"
                                "Analyze logs and identify whether action is required.\n"
                                "If logs are informational, clearly say so.\n"
                                "Write plain text, not Markdown."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue

                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break

                    payload = json.loads(data)
                    delta = payload["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        tokens_generated += 1
                        yield content

        # Record total tokens generated
        llm_span.set_attribute("llm.tokens_generated", tokens_generated)

        logger.info(
            "LLM streaming complete",
            extra={"extra_fields": {"tokens_generated": tokens_generated}},
        )


@app.post("/v1/analyze/stream")
async def analyze_logs_stream(request: AnalyzeRequest):
    async def event_stream():
        # IMPORTANT: All work must happen inside this generator
        # to keep the span context alive during streaming

        with tracer.start_as_current_span("analyze_logs_stream") as span:
            # Add request attributes to span for debugging
            span.set_attribute("namespace", request.filters.namespace or "all")
            span.set_attribute("log_limit", request.limit)
            span.set_attribute(
                "time_range_hours",
                (request.time_range.end - request.time_range.start).total_seconds()
                / 3600,
            )

            logger.info(
                "Starting log analysis",
                extra={
                    "extra_fields": {
                        "namespace": request.filters.namespace,
                        "limit": request.limit,
                    }
                },
            )

            query = build_logql_query(request.filters)

            params = {
                "query": query,
                "limit": request.limit,
                "start": int(request.time_range.start.timestamp() * 1e9),
                "end": int(request.time_range.end.timestamp() * 1e9),
                "direction": "backward",
            }

            # --- Query Loki ---
            with tracer.start_as_current_span("query_loki") as loki_span:
                loki_span.set_attribute("logql.query", query)
                loki_span.set_attribute("logql.limit", request.limit)

                logger.info("Querying Loki", extra={"extra_fields": {"query": query}})

                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        f"{LOKI_URL}/loki/api/v1/query_range",
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                results = data.get("data", {}).get("result", [])
                loki_span.set_attribute("loki.results_count", len(results))

                logger.info(
                    "Loki query complete",
                    extra={"extra_fields": {"results_count": len(results)}},
                )

            if not results:
                logger.warning("No logs found in Loki")
                yield '{"error": "No logs found"}\n'
                return

            # --- Flatten logs ---
            with tracer.start_as_current_span("flatten_logs") as flatten_span:
                logs = []
                for result in results:
                    labels = result["stream"]
                    for ts_ns, line in result["values"]:
                        logs.append(
                            {
                                "timestamp": datetime.fromtimestamp(
                                    int(ts_ns) / 1e9, UTC
                                )
                                .isoformat()
                                .replace("+00:00", "Z"),
                                "message": line.strip(),
                                "labels": labels,
                            }
                        )

                flatten_span.set_attribute("logs.flattened_count", len(logs))

            if not logs:
                yield '{"error": "No logs found"}\n'
                return

            # --- Normalize ---
            with tracer.start_as_current_span("normalize_logs"):
                normalized = [normalize_log(l) for l in logs]
                logger.info(
                    "Logs normalized",
                    extra={"extra_fields": {"log_count": len(normalized)}},
                )

            # --- Build prompt and header ---
            prompt = build_llm_prompt(normalized, request.time_range)
            header = build_text_header(normalized, request.time_range)

            # Send header immediately
            yield header + "\n"

            # --- Stream LLM output ---
            # The stream_llm spans will be children of analyze_logs_stream
            async for chunk in stream_llm(prompt):
                yield chunk

            yield "\n\n=== End of Analysis ===\n"

            logger.info("Log analysis complete")

    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
