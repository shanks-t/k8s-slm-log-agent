"""FastAPI application for log analysis and extraction."""

from contextlib import asynccontextmanager
import httpx
from datetime import datetime, UTC


from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

from log_analyzer.models.requests import AnalyzeRequest
from log_analyzer.observability import setup_telemetry, get_tracer
from log_analyzer.observability.logging import setup_logging, get_logger
from log_analyzer.loki import build_logql_query
from log_analyzer.pipeline import normalize_log, build_llm_prompt, build_text_header
from log_analyzer.llm import stream_llm, call_llm
from log_analyzer.config import settings

# Initialize structured logging with trace context
setup_logging(level="INFO")
logger = get_logger(__name__)

# Get tracer for manual span creation
tracer = get_tracer(__name__)


@asynccontextmanager
async def check_dependencies(app: FastAPI):
    # startup phase
    async with httpx.AsyncClient(timeout=2) as client:
        await client.get(f"{settings.loki_url}/ready")
        await client.get(f"{settings.llm_url}/v1/models")

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


@app.post("/v1/analyze")
async def analyze_logs(request: AnalyzeRequest):
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
            return JSONResponse(
                status_code=404,
                content={"error": "No logs found"},
            )

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
            return JSONResponse(
                status_code=404,
                content={"error": "No logs found"},
            )

        # --- Normalize ---
        with tracer.start_as_current_span("normalize_logs"):
            normalized = [normalize_log(l) for l in logs]
            logger.info(
                "Logs normalized",
                extra={"extra_fields": {"log_count": len(normalized)}},
            )

        # --- Build prompt ---
        prompt = build_llm_prompt(normalized, request.time_range)

        # --- LLM ---
        analysis = await call_llm(prompt)

        logger.info("Log analysis complete")

        return {
            "log_count": len(normalized),
            "analysis": analysis,
            "logs": normalized,  # optional: remove later
        }


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
