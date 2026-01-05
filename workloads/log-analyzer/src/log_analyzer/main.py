"""FastAPI application for log analysis and extraction."""

from contextlib import asynccontextmanager
import httpx
from datetime import datetime, UTC

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse

from log_analyzer.models.requests import AnalyzeRequest
from log_analyzer.models.registry import PromptRegistry
from log_analyzer.observability import setup_telemetry, get_tracer
from log_analyzer.observability.logging import setup_logging, get_logger
from opentelemetry import trace
from log_analyzer.loki import build_logql_query
from log_analyzer.pipeline import normalize_log, build_text_header
from log_analyzer.llm import stream_llm, call_llm
from log_analyzer.config import settings
from log_analyzer.registry import (
    list_prompt_metadata,
    load_prompt_registry,
    render_prompt,
)

# Initialize structured logging with trace context
setup_logging(level="INFO")
logger = get_logger(__name__)

# Get tracer for manual span creation
tracer = get_tracer(__name__)


@asynccontextmanager
async def check_dependencies(app: FastAPI):
    # In async context managers, code before yield is "setup", code after is "teardown".
    # The yield keyword turns a function into a generator with lifecycle hooks.
    # This pattern ensures resources are properly cleaned up, even if the app crashes -
    # Python guarantees the code after yield runs when the context exits

    # === STARTUP PHASE ===
    # 1. Check external dependencies
    async with httpx.AsyncClient(timeout=2) as client:
        await client.get(f"{settings.loki_url}/ready")
        await client.get(f"{settings.llm_url}/v1/models")

    # 2. Load prompt registry (internal artifacts)
    try:
        app.state.prompt_registry = load_prompt_registry(settings.prompts_dir)
    except Exception as e:
        # Fail fast: app should not start with broken prompts
        raise RuntimeError(f"Failed to load prompt registry: {e}") from e

    # 3. Initialize telemetry (only when app actually starts, not during test imports)
    # OpenTelemetry is initialized in the lifespan context manager above
    # This ensures it only runs when the app actually starts, not during test imports
    setup_telemetry(app)

    # === RUN PHASE ===
    yield

    # === SHUTDOWN PHASE ===
    # Clean up telemetry background threads
    try:
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

        provider = trace.get_tracer_provider()
        # Only SDK providers have shutdown(), not the default proxy provider
        if isinstance(provider, SDKTracerProvider):
            provider.shutdown()
    except Exception as e:
        logger.warning(f"Failed to shutdown telemetry: {e}")


app = FastAPI(
    title="Log Analyzer Service",
    description="LLM-powered log analysis and structured extraction",
    version="0.1.0",
    lifespan=check_dependencies,
)


def get_prompt_registry(request: Request) -> PromptRegistry:
    return request.app.state.prompt_registry


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


@app.get("/prompts")
def list_prompts(request: Request):
    return list_prompt_metadata(request.app.state.prompt_registry)


@app.post("/v1/analyze")
async def analyze_logs(request: AnalyzeRequest, registry=Depends(get_prompt_registry)):
    with tracer.start_as_current_span("analyze_logs") as span:
        # Add request attributes to span for debugging
        span.set_attribute("namespace", request.filters.namespace or "all")
        span.set_attribute("log_limit", request.limit)
        span.set_attribute(
            "time_range_hours",
            (request.time_range.end - request.time_range.start).total_seconds() / 3600,
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

        # Log the actual LogQL query for debugging severity filters
        logger.info(
            "Executing LogQL query",
            extra={
                "extra_fields": {
                    "query": query,
                    "severity": request.filters.severity,
                }
            },
        )

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
                    f"{settings.loki_url}/loki/api/v1/query_range",
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
            raise HTTPException(status_code=404, detail="No logs found")

        # --- Flatten logs ---
        with tracer.start_as_current_span("flatten_logs") as flatten_span:
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

            flatten_span.set_attribute("logs.flattened_count", len(logs))

        if not logs:
            raise HTTPException(status_code=404, detail="No logs found")

        # --- Normalize ---
        with tracer.start_as_current_span("normalize_logs"):
            normalized = [normalize_log(l) for l in logs]
            logger.info(
                "Logs normalized",
                extra={"extra_fields": {"log_count": len(normalized)}},
            )

        # --- Build prompt ---
        inputs = {
            "logs": normalized,
            "namespace": request.filters.namespace,
            "time_range": request.time_range,
        }

        rendered_prompt = render_prompt(registry, settings.analyze_prompt_id, inputs)

        # --- LLM ---
        analysis = await call_llm(rendered_prompt)

        logger.info("Log analysis complete")

        return {
            "log_count": len(normalized),
            "analysis": analysis,
            "logs": normalized,  # optional: remove later
        }


@app.post("/v1/analyze/stream")
async def analyze_logs_stream(
    request: AnalyzeRequest, registry=Depends(get_prompt_registry)
):
    # Pre-flight validation: Query Loki and check for logs BEFORE streaming
    # This allows us to return proper HTTP status codes (404 when no logs found)
    with tracer.start_as_current_span("analyze_logs_stream_preflight") as span:
        span.set_attribute("namespace", request.filters.namespace or "all")
        span.set_attribute("log_limit", request.limit)
        span.set_attribute(
            "time_range_hours",
            (request.time_range.end - request.time_range.start).total_seconds() / 3600,
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

        logger.info(
            "Executing LogQL query",
            extra={
                "extra_fields": {
                    "query": query,
                    "severity": request.filters.severity,
                }
            },
        )

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
                    f"{settings.loki_url}/loki/api/v1/query_range",
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
            raise HTTPException(status_code=404, detail="No logs found")

        # --- Flatten logs ---
        with tracer.start_as_current_span("flatten_logs") as flatten_span:
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

            flatten_span.set_attribute("logs.flattened_count", len(logs))

        if not logs:
            raise HTTPException(status_code=404, detail="No logs found")

        # --- Normalize ---
        with tracer.start_as_current_span("normalize_logs"):
            normalized = [normalize_log(l) for l in logs]
            logger.info(
                "Logs normalized",
                extra={"extra_fields": {"log_count": len(normalized)}},
            )

        # Build prompt and header
        # prompt = build_llm_prompt(normalized, request.time_range)
        header = build_text_header(normalized, request.time_range)
        # --- Build prompt ---
        inputs = {
            "logs": normalized,
            "namespace": request.filters.namespace,
            "time_range": request.time_range,
        }

        rendered_prompt = render_prompt(registry, settings.analyze_prompt_id, inputs)

    # Now we know we have logs - create the streaming response
    async def event_stream():
        with tracer.start_as_current_span("stream_llm_output"):
            # Send header immediately
            yield header + "\n"

            # --- Stream LLM output ---
            async for chunk in stream_llm(rendered_prompt):
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
