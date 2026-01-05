"""OpenTelemetry tracing and observability setup."""

import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan, Span
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.resources import (
    Resource,
    SERVICE_NAME,
    SERVICE_VERSION,
    DEPLOYMENT_ENVIRONMENT,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.context import Context

from log_analyzer.config import settings

logger = logging.getLogger(__name__)


class FilterSpanProcessor(SpanProcessor):
    """
    Span processor implement SpanProcessor interface out noisy spans from streaming responses.

    FastAPI instrumentation creates an "http.send" span for each chunk
    in a streaming response, which creates hundreds of tiny spans.
    This processor filters them out to keep traces clean. It also filters
    out health check spans.

    Span creation is cheap, export serialization, network I/O and storage are expensive.
    We allow the span to be created so we have span deatils for filtering, but we prevent
    serialization, export and storage of noisy spans

    FilterSpanProcessor is passive middleware used by OTel sdk. When we call provider.add_span_processor(filter_processor)
    1. SDK creates Span object
    2. SDK loops through all registed processors
    3. call processor.on_start(span, parent_context) when span starts
    4. processor.on_end(span) is called, span data is complete, name and attributes are set
    5. shutdown() when process exits and force_flush() when SDK wants all spans flushed to immediately


    OTel has two Span types:
    - API Span: public abstraction used by instrumentation not tied to library
    - SDK Span: actual implementation used by SDK internally (we almost never type against this directly)
    """

    def __init__(self, next_processor: SpanProcessor):
        self.next_processor = next_processor

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        # Let the next processor handle span start
        self.next_processor.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        # Filter out http.send spans from streaming responses
        span_name = span.name
        if "http send" in span_name.lower():
            # Don't send this span to the exporter
            return

        # Pass everything else to the next processor
        self.next_processor.on_end(span)

    def shutdown(self) -> None:
        self.next_processor.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.next_processor.force_flush(timeout_millis)


def setup_telemetry(app):
    """
    Initialize OpenTelemetry instrumentation for the FastAPI application.

    This function:
    - Configures the OTLP exporter to send traces to Tempo
    - Sets up resource attributes (service name, version, environment)
    - Instruments FastAPI to automatically trace HTTP requests
    - Instruments httpx to trace outgoing HTTP calls (to Loki and LLM)

    All configuration is read from settings (config.py), which can be
    overridden via environment variables with LOG_ANALYZER_ prefix.

    Args:
        app: The FastAPI application instance
    """
    # Check if telemetry is disabled via config
    if not settings.otel_enabled:
        # Create a no-op tracer provider so get_tracer() still works
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        logger.info("✓ Telemetry disabled (no-op provider set)")
        return

    # Telemetry is enabled - set up OTLP exporter and instrumentation
    try:
        # Use settings as single source of truth
        otlp_endpoint = settings.otel_endpoint
        environment = settings.deployment_environment

        # Create resource attributes - these appear as tags in Grafana
        resource = Resource(
            attributes={
                SERVICE_NAME: settings.service_name,
                SERVICE_VERSION: settings.service_version,
                DEPLOYMENT_ENVIRONMENT: environment,
                "service.namespace": "log-analyzer",
            }
        )

        # Configure the tracer provider with our resource
        provider = TracerProvider(resource=resource)

        # Configure OTLP exporter to send traces to Tempo
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True,  # No TLS for homelab (use TLS in production!)
        )

        # Use BatchSpanProcessor to batch traces before sending (more efficient)
        batch_processor = BatchSpanProcessor(otlp_exporter)

        # Wrap in FilterSpanProcessor to remove noisy http.send spans
        filter_processor = FilterSpanProcessor(batch_processor)

        provider.add_span_processor(filter_processor)

        # Set as the global tracer provider
        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI - traces all HTTP requests
        # Exclude http.send spans to reduce noise from streaming responses
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/heath",  # exclude specific paths if needed
        )

        # Auto-instrument httpx - traces calls to Loki and LLM
        HTTPXClientInstrumentor().instrument()
    except Exception as e:
        logger.error(f"✗ OpenTelemetry initialization failed: {e}")
    else:
        logger.info(
            f"✓ OpenTelemetry initialized: {settings.service_name} → {otlp_endpoint}"
        )


def get_tracer(name: str):
    """
    Get a tracer instance for manual span creation.

    Use this to create custom spans for specific operations:

    Example:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("process_logs"):
            # Your code here
            pass

    Args:
        name: Name of the tracer (typically __name__)

    Returns:
        A Tracer instance
    """
    return trace.get_tracer(name)
