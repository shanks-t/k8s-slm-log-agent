"""OTLP adapter - default backend for any OTLP-compatible endpoint.

This adapter provides direct OTLP export without attribute mapping,
making it suitable for generic OTLP backends like Tempo, Jaeger, Honeycomb, etc.
"""

from typing import Any, Optional

from llm_observability.adapters.base import BackendAdapter


class OTLPAdapter(BackendAdapter):
    """OTLP adapter for generic OTLP-compatible backends.

    This is the default adapter and performs no attribute mapping - it sends
    the SDK's semantic contract directly to the backend. Use this for:

    - Grafana Tempo
    - Jaeger
    - Honeycomb
    - Any OTLP-compatible backend

    Example:
        >>> from llm_observability import observe
        >>> from llm_observability.adapters import OTLPAdapter
        >>>
        >>> adapter = OTLPAdapter(
        >>>     endpoint="http://tempo.logging.svc.cluster.local:4317",
        >>>     protocol="grpc"
        >>> )
        >>> observe.configure(adapter=adapter)
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        protocol: str = "grpc",
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Initialize OTLP adapter.

        Args:
            endpoint: OTLP endpoint URL (default: http://localhost:4317)
            protocol: Protocol ("grpc" or "http", default: "grpc")
            headers: Optional HTTP headers for authentication
        """
        super().__init__(endpoint=endpoint, protocol=protocol, headers=headers)

    def map_attributes(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Pass-through: no attribute mapping for generic OTLP.

        The SDK's semantic contract is sent directly to the backend without
        any translation.

        Args:
            attributes: SDK semantic attributes

        Returns:
            Unchanged attributes
        """
        return attributes

    def get_resource_attributes(self) -> dict[str, str]:
        """Get resource attributes for OTLP backend.

        Returns:
            Empty dict (no backend-specific resource attributes)
        """
        return {}
