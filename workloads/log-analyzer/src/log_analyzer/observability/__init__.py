"""OpenTelemetry tracing and observability setup."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanProcessor, SpanExportResult
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.context import Context


class FilterSpanProcessor(SpanProcessor):
    """
    Span processor that filters out noisy spans from streaming responses.

    FastAPI instrumentation creates an "http.send" span for each chunk
    in a streaming response, which creates hundreds of tiny spans.
    This processor filters them out to keep traces clean.
    """

    def __init__(self, next_processor: SpanProcessor):
        self.next_processor = next_processor

    def on_start(self, span: ReadableSpan, parent_context: Context = None) -> None:
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


def setup_telemetry(app, service_name: str = "log-analyzer", service_version: str = "0.1.0"):
    """
    Initialize OpenTelemetry instrumentation for the FastAPI application.

    This function:
    - Configures the OTLP exporter to send traces to Tempo
    - Sets up resource attributes (service name, version, environment)
    - Instruments FastAPI to automatically trace HTTP requests
    - Instruments httpx to trace outgoing HTTP calls (to Loki and LLM)

    Args:
        app: The FastAPI application instance
        service_name: Name of the service (appears in Grafana)
        service_version: Version of the service
    """
    # Get OTLP endpoint from environment variable (defaults to localhost for local dev)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    environment = os.getenv("DEPLOYMENT_ENVIRONMENT", "local")

    # Create resource attributes - these appear as tags in Grafana
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        DEPLOYMENT_ENVIRONMENT: environment,
        "service.namespace": "log-analyzer",
    })

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
        excluded_urls="",  # Can exclude specific paths if needed
        # Note: http.send spans from streaming are still created but less noisy
    )

    # Auto-instrument httpx - traces calls to Loki and LLM
    HTTPXClientInstrumentor().instrument()

    print(f"✓ OpenTelemetry initialized: {service_name} → {otlp_endpoint}")


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
