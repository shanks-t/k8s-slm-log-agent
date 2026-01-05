from log_analyzer.models.registry import RenderedPrompt
import httpx
import json

from log_analyzer.observability.logging import setup_logging, get_logger
from log_analyzer.observability import get_tracer
from log_analyzer.config import settings


# Initialize structured logging with trace context
setup_logging(level="INFO")
logger = get_logger(__name__)

# Get tracer for manual span creation
tracer = get_tracer(__name__)


# spec = render_prompt()
async def call_llm(prompt: RenderedPrompt) -> str:
    # Create a span to trace the LLM call
    with tracer.start_as_current_span("call_llm") as llm_span:
        # Add LLM-specific attributes for debugging
        llm_config = prompt.llm_config or {}
        llm_span.set_attribute("llm.model", settings.llm_model)
        llm_span.set_attribute("llm.max_tokens", llm_config.get("max_tokens", 150))
        llm_span.set_attribute("llm.temperature", llm_config.get("temperature", 0.3))
        llm_span.set_attribute("llm.streaming", False)
        llm_span.set_attribute("llm.provider", "llama-cpp")

        logger.info(
            "Calling LLM for analysis",
            extra={
                "extra_fields": {
                    "model": settings.llm_model,
                    "max_tokens": llm_config.get("max_tokens", 150),
                    "temperature": llm_config.get("temperature", 0.3),
                }
            },
        )

        timeout = httpx.Timeout(
            connect=5.0,
            write=5.0,
            pool=5.0,
            read=180.0,
        )
        # Use pre-rendered messages and config from the prompt template
        payload = {
            "model": settings.llm_model,
            "messages": prompt.messages,
            **(prompt.llm_config or {}),  # Merge template's LLM config (temp, max_tokens, etc.)
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.llm_url}/v1/chat/completions",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]

        # Record tokens used (if available in response)
        if "usage" in data:
            llm_span.set_attribute(
                "llm.tokens_prompt", data["usage"].get("prompt_tokens", 0)
            )
            llm_span.set_attribute(
                "llm.tokens_completion", data["usage"].get("completion_tokens", 0)
            )
            llm_span.set_attribute(
                "llm.tokens_total", data["usage"].get("total_tokens", 0)
            )

        logger.info(
            "LLM call complete",
            extra={"extra_fields": {"response_length": len(content)}},
        )

        return content


async def stream_llm(prompt: RenderedPrompt):
    # Create a span to trace the LLM streaming call
    with tracer.start_as_current_span("call_llm") as llm_span:
        # Add LLM-specific attributes for debugging
        llm_config = prompt.llm_config or {}
        llm_span.set_attribute("llm.model", settings.llm_model)
        llm_span.set_attribute("llm.max_tokens", llm_config.get("max_tokens", 200))
        llm_span.set_attribute("llm.temperature", llm_config.get("temperature", 0.3))
        llm_span.set_attribute("llm.streaming", True)
        llm_span.set_attribute("llm.provider", "llama-cpp")

        logger.info(
            "Calling LLM for analysis",
            extra={
                "extra_fields": {
                    "model": settings.llm_model,
                    "max_tokens": llm_config.get("max_tokens", 200),
                    "temperature": llm_config.get("temperature", 0.3),
                }
            },
        )

        timeout = httpx.Timeout(
            connect=5.0,
            write=5.0,
            pool=5.0,
            read=None,  # IMPORTANT: disable read timeout for streaming
        )

        tokens_generated = 0

        async with httpx.AsyncClient(timeout=timeout) as client:
            # Use pre-rendered messages and config from the prompt template
            payload = {
                "model": settings.llm_model,
                "stream": True,
                "messages": prompt.messages,
                **(prompt.llm_config or {}),  # Merge template's LLM config
            }
            async with client.stream(
                "POST",
                f"{settings.llm_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue

                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break

                    payload = json.loads(data)
                    delta = payload["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        tokens_generated += 1
                        yield content

        # Record total tokens generated
        llm_span.set_attribute("llm.tokens_generated", tokens_generated)

        logger.info(
            "LLM streaming complete",
            extra={"extra_fields": {"tokens_generated": tokens_generated}},
        )
