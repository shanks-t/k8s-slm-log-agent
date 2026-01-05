from pathlib import Path

import pytest

from log_analyzer.registry import load_prompt_registry, render_prompt
from log_analyzer.models.registry import RenderedPrompt

# Get path to prompt_templates relative to test file
PROMPTS_DIR = Path(__file__).parent.parent / "prompt_templates"


@pytest.mark.unit
def test_render_prompt_returns_messages_and_hashes():
    registry = load_prompt_registry(PROMPTS_DIR)

    result = render_prompt(
        registry=registry,
        prompt_id="k8s_log_analysis_v1",
        variables={"logs": "ERROR: pod crashed"},
    )

    user_content = result.messages[1]["content"]

    assert result.id == "k8s_log_analysis_v1"
    assert result.template_hash
    assert result.variables_hash
    assert result.rendered_hash
    assert isinstance(result.messages, list)
    assert "ERROR: pod crashed" in user_content
    assert "unknown" in user_content
    assert isinstance(result, RenderedPrompt)
    assert len(result.messages) == 2
    assert result.messages[0]["role"] == "system"
    assert result.messages[1]["role"] == "user"
