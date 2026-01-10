"""Semantic contract - attribute name constants and span kinds.

This module defines the stable, backend-agnostic semantic model for LLM observability.
All attribute names and span kinds are defined here to ensure consistency.
"""

from enum import Enum


class SpanKind(str, Enum):
    """LLM operation span kinds.

    These define the types of operations we instrument in LLM applications.
    """

    LLM_CALL = "llm.call"
    """Single LLM API invocation (completion, chat, generation)."""

    AGENT = "llm.agent"
    """Agent execution involving planning, reasoning, and tool orchestration."""

    TOOL = "llm.tool"
    """Tool or function call made by an LLM or agent."""

    RETRIEVER = "llm.retriever"
    """RAG retrieval operation (vector search, keyword search, hybrid)."""

    EMBEDDING = "llm.embedding"
    """Embedding generation (vectorization of text)."""

    WORKFLOW = "llm.workflow"
    """Multi-step LLM workflow or chain."""

    PROMPT_REGISTRY = "llm.prompt_registry"
    """Prompt template rendering from a versioned registry."""


class Attributes:
    """Semantic attribute name constants.

    All attributes follow the naming convention:
    - Prefix: llm.
    - Case: snake_case
    - Hierarchy: dot-separated (e.g., llm.usage.prompt_tokens)
    """

    # ============================================================================
    # Common Attributes (all span kinds)
    # ============================================================================

    OPERATION_TYPE = "llm.operation.type"
    """Span kind identifier (required)."""

    OPERATION_NAME = "llm.operation.name"
    """User-provided operation name (required)."""

    SESSION_ID = "llm.session.id"
    """Session or conversation ID (optional)."""

    # ============================================================================
    # LLM Call Attributes
    # ============================================================================

    # Model & Provider
    PROVIDER = "llm.provider"
    """LLM provider (e.g., 'openai', 'anthropic', 'llama-cpp')."""

    MODEL = "llm.model"
    """Model identifier (e.g., 'gpt-4o', 'claude-3-opus')."""

    # Inference Parameters
    TEMPERATURE = "llm.temperature"
    """Sampling temperature (0.0-2.0)."""

    MAX_TOKENS = "llm.max_tokens"
    """Maximum completion tokens."""

    TOP_P = "llm.top_p"
    """Nucleus sampling parameter (0.0-1.0)."""

    TOP_K = "llm.top_k"
    """Top-K sampling parameter."""

    FREQUENCY_PENALTY = "llm.frequency_penalty"
    """Frequency penalty (-2.0 to 2.0)."""

    PRESENCE_PENALTY = "llm.presence_penalty"
    """Presence penalty (-2.0 to 2.0)."""

    STREAMING = "llm.streaming"
    """Whether streaming is enabled (boolean)."""

    # Input & Output
    INPUT_MESSAGES = "llm.input.messages"
    """Input messages as JSON string (max 4KB)."""

    OUTPUT_MESSAGE = "llm.output.message"
    """Output message as JSON string (max 4KB)."""

    # Token Usage
    USAGE_PROMPT_TOKENS = "llm.usage.prompt_tokens"
    """Tokens consumed in the prompt."""

    USAGE_COMPLETION_TOKENS = "llm.usage.completion_tokens"
    """Tokens generated in the completion."""

    USAGE_TOTAL_TOKENS = "llm.usage.total_tokens"
    """Total tokens (prompt + completion)."""

    # ============================================================================
    # Agent Attributes
    # ============================================================================

    AGENT_TYPE = "llm.agent.type"
    """Agent architecture (e.g., 'react', 'plan-execute', 'conversational')."""

    AGENT_ITERATIONS = "llm.agent.iterations"
    """Number of reasoning iterations."""

    AGENT_TOOLS = "llm.agent.tools"
    """Available tools as JSON array string."""

    # ============================================================================
    # Tool Attributes
    # ============================================================================

    TOOL_NAME = "llm.tool.name"
    """Tool identifier."""

    TOOL_INPUT = "llm.tool.input"
    """Tool input as JSON string (max 2KB)."""

    TOOL_OUTPUT = "llm.tool.output"
    """Tool output as JSON string (max 2KB)."""

    # ============================================================================
    # Retriever Attributes
    # ============================================================================

    RETRIEVER_TYPE = "llm.retriever.type"
    """Retrieval method ('vector', 'keyword', 'hybrid')."""

    RETRIEVER_QUERY = "llm.retriever.query"
    """Search query string."""

    RETRIEVER_TOP_K = "llm.retriever.top_k"
    """Number of results requested."""

    RETRIEVER_RESULTS_COUNT = "llm.retriever.results_count"
    """Actual number of results returned."""

    RETRIEVER_SOURCE = "llm.retriever.source"
    """Data source identifier (e.g., 'pinecone', 'loki', 'elasticsearch')."""

    # ============================================================================
    # Embedding Attributes
    # ============================================================================

    EMBEDDING_INPUT_COUNT = "llm.embedding.input_count"
    """Number of texts embedded."""

    EMBEDDING_DIMENSIONS = "llm.embedding.dimensions"
    """Vector dimensions."""

    # ============================================================================
    # Workflow Attributes
    # ============================================================================

    WORKFLOW_STEPS = "llm.workflow.steps"
    """Workflow steps as JSON array string."""

    WORKFLOW_CURRENT_STEP = "llm.workflow.current_step"
    """Current step being executed."""

    # ============================================================================
    # Prompt Registry Attributes
    # ============================================================================

    PROMPT_ID = "llm.prompt.id"
    """Prompt template ID."""

    PROMPT_VERSION = "llm.prompt.version"
    """Prompt template version."""

    PROMPT_TEMPLATE_HASH = "llm.prompt.template_hash"
    """Hash of template content (SHA-256, 8 chars)."""

    PROMPT_VARIABLES_HASH = "llm.prompt.variables_hash"
    """Hash of input variables (SHA-256, 8 chars)."""

    PROMPT_RENDERED_HASH = "llm.prompt.rendered_hash"
    """Hash of rendered output (SHA-256, 8 chars)."""

    # ============================================================================
    # Error Attributes
    # ============================================================================

    ERROR_TYPE = "llm.error.type"
    """Error category ('rate_limit', 'timeout', 'invalid_input', 'auth')."""

    ERROR_MESSAGE = "llm.error.message"
    """Error message."""

    ERROR_CODE = "llm.error.code"
    """Provider-specific error code."""
