import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined

from log_analyzer.models.prompts import (
    PromptTemplate,
    PromptMetadata,
    RenderedPrompt,
)
from log_analyzer.config import settings
from log_analyzer.observability.logging import get_logger

logger = get_logger(__name__)


def sha256_text(content: str) -> str:
    return hashlib.sha256(
        content.replace("\r\n", "\n").strip().encode("utf-8")
    ).hexdigest()


def sha256_json(data: Any) -> str:
    """
    Compute a stable SHA256 hash of any JSON-serializable value.
    """
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_prompt_file(path: Path) -> PromptTemplate:
    """Load and validate a single prompt template file."""
    raw = yaml.safe_load(path.read_text())

    if raw["id"] != path.stem:
        logger.error(
            "Prompt ID mismatch",
            extra={
                "extra_fields": {
                    "file": path.name,
                    "expected_id": path.stem,
                    "actual_id": raw["id"],
                }
            },
        )
        raise ValueError(f"ID mismatch in {path.name}")

    combined = raw["system"] + raw["user"]

    template_hash = sha256_text(combined)

    llm_config = raw["model_defaults"]

    logger.debug(
        "Loaded prompt template",
        extra={
            "extra_fields": {
                "prompt_id": raw["id"],
                "template_hash": template_hash[:8],  # First 8 chars for readability
                "file": path.name,
            }
        },
    )

    return PromptTemplate(
        id=raw["id"],
        description=raw["description"],
        template_hash=template_hash,
        system_template=raw["system"],
        user_template=raw["user"],
        required_inputs=raw["inputs"]["required"],
        optional_inputs=raw["inputs"]["optional"],
        llm_config=llm_config,
    )


def load_prompt_registry(prompts_dir: Path) -> dict[str, PromptTemplate]:
    """Load all prompt templates from directory and build registry."""
    logger.info(
        "Loading prompt registry",
        extra={"extra_fields": {"prompts_dir": str(prompts_dir)}},
    )

    registry: dict[str, PromptTemplate] = {}

    for path in prompts_dir.glob("*.yaml"):
        template = load_prompt_file(path)
        registry[template.id] = template

    prompt_ids = list(registry.keys())
    logger.info(
        "Prompt registry loaded successfully",
        extra={
            "extra_fields": {
                "prompt_count": len(registry),
                "prompt_ids": prompt_ids,
            }
        },
    )

    return registry


def render_prompt(
    registry: dict[str, PromptTemplate], prompt_id: str, variables: dict[str, str]
) -> RenderedPrompt:
    """Render a prompt template with given variables and compute hashes."""
    logger.debug(
        "Rendering prompt",
        extra={
            "extra_fields": {
                "prompt_id": prompt_id,
                "variable_count": len(variables),
            }
        },
    )

    if prompt_id not in registry:
        logger.error(
            "Prompt not found in registry",
            extra={
                "extra_fields": {
                    "prompt_id": prompt_id,
                    "available_prompts": list(registry.keys()),
                }
            },
        )
        raise KeyError(f"Prompt '{prompt_id}' not found in registry")

    template = registry[prompt_id]

    # template.required_inptues is a list of variable nanmes that must be provided
    # variables.keys is the set of user-provided var names
    # the set difference finds inputs that were not passed
    # sets are fast, avoids loops, order does not matter
    missing = set(template.required_inputs) - variables.keys()
    if missing:
        logger.error(
            "Missing required prompt inputs",
            extra={
                "extra_fields": {
                    "prompt_id": prompt_id,
                    "missing_inputs": list(missing),
                    "required_inputs": template.required_inputs,
                    "provided_inputs": list(variables.keys()),
                }
            },
        )
        raise ValueError(f"Missing required inputs: {missing}")

    # when two dicts are merged this way python hands duplicate keys by overriding
    # the values from first dict with vals from second dict
    merged_vars = {**template.optional_inputs, **variables}

    # jinja raises error if template contains items not in merged_vars
    # by default jijna uses less strict Undefined class which allows ops on undefined values (e.g. printing as empty string)
    # and results in silent failures
    # Strict raises exception immediately if any part of template is missing
    jinja_env = Environment(undefined=StrictUndefined)

    # render each template separately to keep system distinct from user instructions
    # keeps aligned with OpenAI style completions
    rendered_system = jinja_env.from_string(template.system_template).render(
        merged_vars
    )
    rendered_user = jinja_env.from_string(template.user_template).render(merged_vars)

    # construct chat messages array
    messages = [
        {"role": "system", "content": rendered_system},
        {"role": "user", "content": rendered_user},
    ]

    variables_hash = sha256_json(merged_vars)
    rendered_hash = sha256_json(messages)

    logger.info(
        "Prompt rendered successfully",
        extra={
            "extra_fields": {
                "prompt_id": prompt_id,
                "template_hash": template.template_hash[:8],
                "variables_hash": variables_hash[:8],
                "rendered_hash": rendered_hash[:8],
            }
        },
    )

    return RenderedPrompt(
        id=template.id,
        template_hash=template.template_hash,
        rendered_hash=rendered_hash,
        variables_hash=variables_hash,
        messages=messages,
        llm_config=template.llm_config,
    )


def list_prompt_metadata(
    registry: dict[str, PromptTemplate],
) -> list[PromptMetadata]:
    now = datetime.utcnow()

    return [
        PromptMetadata(
            id=p.id,
            content_hash=p.template_hash,
            description=p.description,
            loaded_at=now,
        )
        for p in registry.values()
    ]
