"""LLM Observability SDK - OpenTelemetry-based LLM telemetry.

This SDK provides a thin, opinionated abstraction over OpenTelemetry for
instrumenting LLM applications with support for multiple observability backends.

Example:
    >>> from llm_observability import observe
    >>> from llm_observability.adapters import OTLPAdapter
    >>>
    >>> # Configure backend
    >>> adapter = OTLPAdapter(endpoint="http://tempo:4317")
    >>> observe.configure(adapter=adapter)
    >>>
    >>> # Instrument LLM calls
    >>> @observe.llm(name="summarize", model="gpt-4o")
    >>> def summarize(text: str) -> str:
    >>>     return openai.call(text)
"""

from llm_observability.adapters import ArizeAdapter, BackendAdapter, MLflowAdapter, OTLPAdapter
from llm_observability.core.observer import observe

__version__ = "0.1.0"

__all__ = [
    "observe",
    "OTLPAdapter",
    "ArizeAdapter",
    "MLflowAdapter",
    "BackendAdapter",
    "__version__",
]
