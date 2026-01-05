"""Application configuration using Pydantic Settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Service configuration
    service_name: str = "log-analyzer"
    service_version: str = "0.1.0"
    log_level: str = "INFO"

    model_name: str = "llama-3.2-3b-instruct"

    # Loki configuration
    loki_url: str = "http://loki.logging.svc.cluster.local:3100"
    loki_timeout: int = 10
    loki_max_retries: int = 3

    # LLM configuration
    llm_url: str = "http://llama-cpp.llm.svc.cluster.local:8080"
    llm_model: str = "llama-3.2-3b-instruct"
    llm_timeout: int = 30
    llm_temperature: float = 0.1
    llm_max_tokens: int = 512

    # Retrieval configuration
    default_log_limit: int = 50
    max_log_limit: int = 200

    # Evaluation configuration
    golden_dataset_path: str = "/app/golden_dataset_synthetic.json"
    evaluation_results_dir: str = "/app/results"

    # Observability configuration
    otel_enabled: bool = False
    otel_exporter: str = "console"  # Options: "console", "otlp", "jaeger"
    otel_endpoint: str = "http://localhost:4317"
    deployment_environment: str = "local"

    # Prompt registry configuration
    # K8s default: /app/prompt_templates (ConfigMap mount or baked into image)
    # Local dev: override with LOG_ANALYZER_PROMPTS_DIR=./prompt_templates
    prompts_dir: Path = Path("/app/prompt_templates")
    analyze_prompt_id: str = "k8s_log_analysis_v1"

    model_config = SettingsConfigDict(
        env_prefix="LOG_ANALYZER_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance
settings = Settings()
