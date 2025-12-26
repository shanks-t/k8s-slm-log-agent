"""Pydantic models for API responses."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """Structured extraction from LLM."""

    root_cause: str = Field(..., description="Root cause classification")
    severity: str = Field(..., description="Severity level (info|warn|error|critical)")
    component: str = Field(..., description="Component that generated the log")
    summary: str = Field(..., description="One-sentence summary")
    action_needed: str = Field(..., description="Recommended action (investigate|monitor|scale|fix_config)")


class AnalyzeMetadata(BaseModel):
    """Metadata about the analysis operation."""

    loki_query_ms: float = Field(..., description="Loki query duration in milliseconds")
    llm_inference_ms: float = Field(..., description="LLM inference duration in milliseconds")
    total_latency_ms: float = Field(..., description="Total end-to-end latency")


class AnalyzeResponse(BaseModel):
    """Response from log analysis."""

    query_id: str = Field(..., description="Unique identifier for this query")
    retrieved_logs: int = Field(..., description="Number of logs retrieved from Loki")
    extraction: ExtractionResult = Field(..., description="Structured extraction result")
    metadata: AnalyzeMetadata = Field(..., description="Performance metadata")


class EvaluationMetrics(BaseModel):
    """Aggregate metrics from evaluation run."""

    root_cause_accuracy: float = Field(..., description="Root cause exact match accuracy")
    severity_accuracy: float = Field(..., description="Severity classification accuracy")
    component_accuracy: float = Field(..., description="Component identification accuracy")
    action_accuracy: float = Field(..., description="Action recommendation accuracy")
    overall_f1: float = Field(..., description="Macro-averaged F1 score across all fields")


class LatencyStats(BaseModel):
    """Latency statistics."""

    mean_ms: float = Field(..., description="Mean latency")
    median_ms: float = Field(..., description="Median latency")
    p50_ms: float = Field(..., description="50th percentile")
    p95_ms: float = Field(..., description="95th percentile")
    p99_ms: float = Field(..., description="99th percentile")
    max_ms: float = Field(..., description="Maximum latency")


class EvaluateResponse(BaseModel):
    """Response from evaluation run."""

    evaluation_id: str = Field(..., description="Unique identifier for this evaluation")
    total_samples: int = Field(..., description="Total samples in dataset")
    evaluated_samples: int = Field(..., description="Number of samples actually evaluated")
    metrics: EvaluationMetrics = Field(..., description="Aggregate accuracy metrics")
    latency: LatencyStats = Field(..., description="Latency statistics")
    confusion_matrix: Optional[Dict[str, Any]] = Field(None, description="Confusion matrices for classification")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status (healthy|degraded|unhealthy)")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    dependencies: Optional[Dict[str, str]] = Field(None, description="Status of external dependencies")
