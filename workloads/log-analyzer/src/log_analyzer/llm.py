from log_analyzer.observability.logging import setup_logging, get_logger
from log_analyzer.observability import get_tracer
from log_analyzer.config import settings
import httpx
import json


# Initialize structured logging with trace context
setup_logging(level="INFO")
logger = get_logger(__name__)

# Get tracer for manual span creation
tracer = get_tracer(__name__)

MODEL_NAME = settings.llm_model
LLAMA_URL = settings.llm_url


async def call_llm(prompt: str):
    # Create a span to trace the LLM call
    with tracer.start_as_current_span("call_llm") as llm_span:
        # Add LLM-specific attributes for debugging
        llm_span.set_attribute("llm.model", MODEL_NAME)
        llm_span.set_attribute("llm.max_tokens", 150)
        llm_span.set_attribute("llm.temperature", 0.3)
        llm_span.set_attribute("llm.streaming", False)
        llm_span.set_attribute("llm.provider", "llama-cpp")

        logger.info(
            "Calling LLM for analysis",
            extra={
                "extra_fields": {
                    "model": MODEL_NAME,
                    "max_tokens": 150,
                    "temperature": 0.3,
                }
            },
        )

        timeout = httpx.Timeout(
            connect=5.0,
            write=5.0,
            pool=5.0,
            read=180.0,
        )
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Kubernetes reliability engineer. "
                        "Analyze logs and identify root cause, severity, "
                        "and recommended actions."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "max_tokens": 150,
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{LLAMA_URL}/v1/chat/completions",
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


async def stream_llm(prompt: str):
    MAX_TOKENS = 200
    # Create a span to trace the LLM streaming call
    with tracer.start_as_current_span("call_llm") as llm_span:
        # Add LLM-specific attributes for debugging
        llm_span.set_attribute("llm.model", MODEL_NAME)
        llm_span.set_attribute("llm.max_tokens", 200)
        llm_span.set_attribute("llm.temperature", 0.3)
        llm_span.set_attribute("llm.streaming", True)
        llm_span.set_attribute("llm.provider", "llama-cpp")

        logger.info(
            "Calling LLM for analysis",
            extra={
                "extra_fields": {
                    "model": MODEL_NAME,
                    "max_tokens": 200,
                    "temperature": 0.3,
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
            async with client.stream(
                "POST",
                f"{LLAMA_URL}/v1/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "stream": True,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a Kubernetes reliability engineer.\n"
                                "Analyze logs and identify whether action is required.\n"
                                "If logs are informational, clearly say so.\n"
                                "Write plain text, not Markdown."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
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
