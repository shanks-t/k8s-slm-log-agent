"""Models for golden dataset samples and evaluation results."""

from typing import Optional

from pydantic import BaseModel, Field


class GoldenSample(BaseModel):
    """A single sample from the golden dataset with ground truth labels."""

    # Log metadata
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    timestamp_human: str = Field(..., description="Human-readable ISO 8601 timestamp")
    namespace: str = Field(..., description="Kubernetes namespace")
    pod: str = Field(..., description="Pod name")
    container: str = Field(..., description="Container name")
    node: str = Field(..., description="Node name")
    log_line: str = Field(..., description="Raw log content")

    # Detected metadata (from extraction script)
    detected_severity: Optional[str] = Field(None, description="Auto-detected severity")
    signature: Optional[str] = Field(None, description="Normalized log signature")
    signature_hash: Optional[str] = Field(None, description="Hash of signature")

    # Ground truth labels (what the LLM should extract)
    root_cause: str = Field(..., description="Ground truth root cause")
    severity: str = Field(..., description="Ground truth severity (info|warn|error|critical)")
    component: str = Field(..., description="Ground truth component")
    summary: str = Field(..., description="Ground truth summary")
    action_needed: str = Field(..., description="Ground truth action (investigate|monitor|scale|fix_config)")

    # Source tracking
    source: str = Field(..., description="Data source (synthetic|real)")


class SampleEvaluationResult(BaseModel):
    """Evaluation result for a single sample."""

    sample_id: int = Field(..., description="Index in golden dataset")
    timestamp: int = Field(..., description="Sample timestamp")

    # Ground truth
    ground_truth: dict = Field(..., description="Ground truth extraction")

    # Prediction
    prediction: dict = Field(..., description="LLM prediction")

    # Correctness
    correct_fields: list[str] = Field(..., description="List of correctly predicted fields")
    incorrect_fields: list[str] = Field(..., description="List of incorrectly predicted fields")

    # Latency
    latency_ms: float = Field(..., description="Inference latency in milliseconds")


class LogEntry(BaseModel):
    """A log entry retrieved from Loki."""

    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    timestamp_human: str = Field(..., description="Human-readable ISO 8601 timestamp")
    labels: dict[str, str] = Field(..., description="Loki labels (namespace, pod, container, node, etc.)")
    log_line: str = Field(..., description="Raw log content")

    @property
    def namespace(self) -> str:
        """Get namespace from labels."""
        return self.labels.get("namespace", "")

    @property
    def pod(self) -> str:
        """Get pod from labels."""
        return self.labels.get("pod", "")

    @property
    def container(self) -> str:
        """Get container from labels."""
        return self.labels.get("container", "")

    @property
    def node(self) -> str:
        """Get node from labels."""
        return self.labels.get("node", "")
