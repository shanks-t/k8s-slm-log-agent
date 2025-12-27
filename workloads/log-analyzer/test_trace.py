#!/usr/bin/env python3
"""Send a test trace to Tempo to verify the pipeline."""

import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Configure the tracer
resource = Resource(attributes={
    SERVICE_NAME: "test-service",
})

provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(
    endpoint="http://localhost:4317",
    insecure=True,
)
processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Create a test trace
tracer = trace.get_tracer(__name__)

print("Sending test trace to Tempo...")
with tracer.start_as_current_span("test-operation") as span:
    span.set_attribute("test.attribute", "hello-tempo")
    time.sleep(0.1)
    print("✓ Span created")

# Force flush to ensure spans are sent
provider.force_flush()
print("✓ Trace sent to Tempo at http://localhost:4317")
print("\nCheck Grafana Tempo datasource:")
print("  1. Go to http://10.0.0.102/grafana")
print("  2. Explore → Tempo")
print("  3. Search → Service Name: test-service")
print("  4. Run Query")
