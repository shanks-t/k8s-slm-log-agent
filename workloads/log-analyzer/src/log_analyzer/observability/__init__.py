"""OpenTelemetry tracing and observability setup."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


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
    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)

    # Set as the global tracer provider
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI - traces all HTTP requests
    FastAPIInstrumentor.instrument_app(app)

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
