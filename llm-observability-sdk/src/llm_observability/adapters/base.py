"""Base backend adapter interface.

All backend adapters must inherit from BackendAdapter and implement
the required methods for attribute mapping and configuration.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BackendAdapter(ABC):
    """Base class for backend adapters.

    Backend adapters configure OpenTelemetry to target specific observability
    platforms (Arize, MLflow, custom OTLP endpoints). They are responsible for:

    1. Endpoint configuration (URL, protocol, auth)
    2. Attribute mapping (SDK contract → backend conventions)
    3. Resource attributes (backend-specific metadata)

    Adapters should NOT:
    - Change span kinds
    - Filter or drop spans
    - Add business logic
    - Modify span lifecycle
    """

    def __init__(
        self,
        endpoint: str,
        protocol: str = "grpc",
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            endpoint: OTLP endpoint URL (e.g., "http://tempo:4317")
            protocol: Protocol ("grpc" or "http")
            headers: Optional HTTP headers for authentication
        """
        self.endpoint = endpoint
        self.protocol = protocol
        self.headers = headers or {}

    @abstractmethod
    def map_attributes(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Map SDK attributes to backend-specific conventions.

        This method translates attribute names from the SDK's semantic contract
        to the backend's expected format (e.g., OpenInference, OTel GenAI).

        Args:
            attributes: SDK semantic attributes

        Returns:
            Mapped attributes for the backend

        Example:
            >>> # SDK attribute → OpenInference attribute
            >>> mapped = adapter.map_attributes({
            >>>     "llm.model": "gpt-4o",
            >>>     "llm.usage.prompt_tokens": 150
            >>> })
            >>> # Returns: {"llm.model_name": "gpt-4o", "llm.token_count.prompt": 150}
        """
        pass

    @abstractmethod
    def get_resource_attributes(self) -> dict[str, str]:
        """Get backend-specific resource attributes.

        Resource attributes are metadata about the service/deployment that
        are attached to all spans.

        Returns:
            Dictionary of resource attributes

        Example:
            >>> # Arize adapter might return
            >>> {"arize.project_name": "log-analyzer", "arize.space": "production"}
        """
        pass

    def get_exporter_kwargs(self) -> dict[str, Any]:
        """Get keyword arguments for OTLP exporter initialization.

        Returns:
            Dictionary of kwargs for OTLPSpanExporter

        Example:
            >>> kwargs = adapter.get_exporter_kwargs()
            >>> exporter = OTLPSpanExporter(**kwargs)
        """
        return {
            "endpoint": self.endpoint,
            "headers": self.headers,
        }
