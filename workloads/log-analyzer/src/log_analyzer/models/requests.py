"""Pydantic models for API requests."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    """Time range for log queries."""

    start: datetime = Field(..., description="Start time (ISO 8601 format)")
    end: datetime = Field(..., description="End time (ISO 8601 format)")


class LogFilters(BaseModel):
    """Filters for log queries."""

    namespace: Optional[str] = Field(None, description="Kubernetes namespace filter")
    pod: Optional[str] = Field(None, description="Pod name filter (supports wildcards)")
    container: Optional[str] = Field(None, description="Container name filter")
    node: Optional[str] = Field(None, description="Node name filter")
    severity: Optional[str] = Field(None, description="Log severity filter (info|warn|error|critical)")
    log_filter: Optional[str] = Field(None, description="Regex pattern to match in log lines")


class AnalyzeRequest(BaseModel):
    """Request to analyze logs."""

    time_range: TimeRange = Field(..., description="Time range for log query")
    filters: LogFilters = Field(default_factory=LogFilters, description="Optional filters")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of logs to retrieve")


class EvaluateRequest(BaseModel):
    """Request to run evaluation on golden dataset."""

    dataset_path: Optional[str] = Field(None, description="Path to golden dataset JSON file")
    sample_limit: Optional[int] = Field(None, ge=1, description="Limit number of samples to evaluate")
