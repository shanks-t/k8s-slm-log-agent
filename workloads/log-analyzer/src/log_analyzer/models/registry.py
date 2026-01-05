"""Pydantic models for Prompt Registry."""

from typing import Any
from datetime import datetime

from pydantic import BaseModel, Field

PromptRegistry = dict[str, "PromptTemplate"]


class PromptMetadata(BaseModel):
    """Metadata for a prompt."""

    id: str = Field(..., description="Unique identifier for the prompt")
    content_hash: str = Field(..., description="Hash of the prompt content")
    description: str = Field(..., description="Description of the prompt's purpose")
    loaded_at: datetime = Field(..., description="Timestamp when the prompt was loaded")


class PromptTemplate(BaseModel):
    """Template for a prompt."""

    # Core identity (from YAML + computed)
    id: str = Field(..., description="Prompt ID (from filename)")
    description: str = Field(..., description="Human-readable description")
    template_hash: str = Field(..., description="SHA256 of system + user templates")
    # template content
    system_template: str = Field(
        ..., description="The prompt template with placeholders"
    )
    user_template: str = Field(
        ..., description="The user prompt template with placeholders"
    )
    # variable definitions
    required_inputs: list[str] = Field(
        ..., description="List of inputs in the template"
    )
    optional_inputs: dict[str, Any] = Field(
        ..., description="dictionary of optional inputs in the template"
    )
    # model configuration
    llm_config: dict[str, Any] | None = Field(
        None, description="Optional model configuration parameters"
    )


class RenderedPrompt(BaseModel):
    """Rendered prompt with variables filled in."""

    id: str = Field(..., description="Identifier of the prompt template used")
    template_hash: str = Field(..., description="Hash of the prompt template")
    rendered_hash: str = Field(..., description="Hash of the rendered prompt content")
    variables_hash: str = Field(
        ..., description="Hash of the variables used for rendering"
    )
    messages: list[dict[str, str]] = Field(
        ..., description="Rendered messages [{'role': 'system', 'content': '...'}, ...]"
    )
    # model config from template
    llm_config: dict[str, Any] | None = Field(
        None, description="Model configuration parameters for the LLM"
    )
