"""MLflow adapter - maps SDK contract to OTel GenAI conventions.

This adapter translates the SDK's semantic contract to OpenTelemetry GenAI
semantic conventions used by MLflow.
"""

from typing import Any, Optional

from llm_observability.adapters.base import BackendAdapter


class MLflowAdapter(BackendAdapter):
    """MLflow adapter with OTel GenAI attribute mapping.

    This adapter maps the SDK's semantic contract to OpenTelemetry GenAI
    semantic conventions expected by MLflow.

    References:
        - OTel GenAI: https://opentelemetry.io/docs/specs/semconv/gen-ai/
        - MLflow Tracing: https://mlflow.org/docs/latest/llms/tracing/

    Example:
        >>> from llm_observability import observe
        >>> from llm_observability.adapters import MLflowAdapter
        >>>
        >>> adapter = MLflowAdapter(
        >>>     tracking_uri="http://mlflow:5000",
        >>>     experiment_name="log-analyzer-dev"
        >>> )
        >>> observe.configure(adapter=adapter)
    """

    # Attribute mapping: SDK → OTel GenAI
    ATTRIBUTE_MAPPING = {
        # LLM attributes
        "llm.model": "gen_ai.request.model",
        "llm.provider": "gen_ai.system",
        "llm.temperature": "gen_ai.request.temperature",
        "llm.max_tokens": "gen_ai.request.max_tokens",
        "llm.top_p": "gen_ai.request.top_p",
        "llm.usage.prompt_tokens": "gen_ai.usage.prompt_tokens",
        "llm.usage.completion_tokens": "gen_ai.usage.completion_tokens",
        # Keep other attributes unchanged
    }

    def __init__(
        self,
        tracking_uri: str = "http://localhost:5000",
        experiment_name: Optional[str] = None,
        protocol: str = "http",
    ) -> None:
        """Initialize MLflow adapter.

        Args:
            tracking_uri: MLflow tracking server URI (default: http://localhost:5000)
            experiment_name: MLflow experiment name
            protocol: Protocol ("grpc" or "http", default: "http")
        """
        # MLflow typically uses HTTP protocol for OTLP
        # Endpoint is tracking_uri + "/api/2.0/mlflow/traces"
        endpoint = f"{tracking_uri}/api/2.0/mlflow/traces"

        super().__init__(endpoint=endpoint, protocol=protocol)

        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name

    def map_attributes(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Map SDK attributes to OTel GenAI conventions.

        Args:
            attributes: SDK semantic attributes

        Returns:
            Mapped attributes for MLflow

        Example:
            >>> mapped = adapter.map_attributes({
            >>>     "llm.model": "gpt-4o",
            >>>     "llm.temperature": 0.7
            >>> })
            >>> # Returns: {
            >>> #     "gen_ai.request.model": "gpt-4o",
            >>> #     "gen_ai.request.temperature": 0.7
            >>> # }
        """
        mapped = {}
        for key, value in attributes.items():
            # Use mapping if exists, otherwise keep original key
            mapped_key = self.ATTRIBUTE_MAPPING.get(key, key)
            mapped[mapped_key] = value

        return mapped

    def get_resource_attributes(self) -> dict[str, str]:
        """Get MLflow-specific resource attributes.

        Returns:
            Dictionary of MLflow resource attributes
        """
        attrs = {}
        if self.experiment_name:
            attrs["mlflow.experiment_name"] = self.experiment_name
        return attrs
