"""Arize Phoenix adapter - maps SDK contract to OpenInference conventions.

This adapter translates the SDK's semantic contract to OpenInference attributes
expected by Arize Phoenix and Arize Platform.
"""

from typing import Any, Optional

from llm_observability.adapters.base import BackendAdapter


class ArizeAdapter(BackendAdapter):
    """Arize Phoenix adapter with OpenInference attribute mapping.

    This adapter maps the SDK's semantic contract to OpenInference conventions
    used by Arize Phoenix and Arize Platform.

    References:
        - OpenInference Spec: https://github.com/Arize-ai/openinference
        - Arize Phoenix: https://docs.arize.com/phoenix

    Example:
        >>> from llm_observability import observe
        >>> from llm_observability.adapters import ArizeAdapter
        >>>
        >>> adapter = ArizeAdapter(
        >>>     endpoint="https://phoenix.arize.com:4317",
        >>>     api_key="your-api-key",
        >>>     project_name="log-analyzer"
        >>> )
        >>> observe.configure(adapter=adapter)
    """

    # Attribute mapping: SDK → OpenInference
    ATTRIBUTE_MAPPING = {
        # LLM attributes
        "llm.model": "llm.model_name",
        "llm.input.messages": "llm.input_messages",
        "llm.output.message": "llm.output_messages",
        "llm.usage.prompt_tokens": "llm.token_count.prompt",
        "llm.usage.completion_tokens": "llm.token_count.completion",
        "llm.usage.total_tokens": "llm.token_count.total",
        # Tool attributes
        "llm.tool.name": "tool.name",
        "llm.tool.input": "tool.parameters",
        # Keep other attributes unchanged
    }

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        project_name: Optional[str] = None,
        space: Optional[str] = None,
        protocol: str = "grpc",
    ) -> None:
        """Initialize Arize adapter.

        Args:
            endpoint: Arize Phoenix endpoint (e.g., "https://phoenix.arize.com:4317")
            api_key: Arize API key (if using Arize Platform)
            project_name: Project name for Arize
            space: Arize space name
            protocol: Protocol ("grpc" or "http", default: "grpc")
        """
        headers = {}
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"

        super().__init__(endpoint=endpoint, protocol=protocol, headers=headers)

        self.project_name = project_name
        self.space = space

    def map_attributes(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Map SDK attributes to OpenInference conventions.

        Args:
            attributes: SDK semantic attributes

        Returns:
            Mapped attributes for Arize Phoenix

        Example:
            >>> mapped = adapter.map_attributes({
            >>>     "llm.model": "gpt-4o",
            >>>     "llm.usage.prompt_tokens": 150
            >>> })
            >>> # Returns: {
            >>> #     "llm.model_name": "gpt-4o",
            >>> #     "llm.token_count.prompt": 150
            >>> # }
        """
        mapped = {}
        for key, value in attributes.items():
            # Use mapping if exists, otherwise keep original key
            mapped_key = self.ATTRIBUTE_MAPPING.get(key, key)
            mapped[mapped_key] = value

        return mapped

    def get_resource_attributes(self) -> dict[str, str]:
        """Get Arize-specific resource attributes.

        Returns:
            Dictionary of Arize resource attributes
        """
        attrs = {}
        if self.project_name:
            attrs["arize.project_name"] = self.project_name
        if self.space:
            attrs["arize.space"] = self.space
        return attrs
