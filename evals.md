# LLM Evaluation Framework for Log Analysis

This document provides a comprehensive roadmap for building a reproducible evaluation framework to measure and improve the quality of LLM-powered log analysis.

## Overview

The evaluation framework enables:

- **Scientific experimentation** on LLM configurations (models, parameters, prompts)
- **Data-driven model selection** based on accuracy vs. latency trade-offs
- **Reproducible results** with versioned datasets, configs, and code
- **Regression detection** to catch quality degradation over time
- **Visualization** of experiment results in Grafana

---

## Architecture

### Design Principles

**1. Separation of Concerns**
```
Production API (log-analyzer)     Evaluation Harness (evals/)
└─ Serves real user traffic        └─ Measures quality offline
   └─ Optimized for latency           └─ No latency constraints
   └─ Stable configuration            └─ Tests multiple configs
   └─ Health checks, SLAs             └─ Emits quality metrics
```

**2. Shared Core Logic**
```
workloads/log-analyzer/src/log_analyzer/core/
└─ analyzer.py      # Shared by production API and eval scripts
└─ prompts.py       # Prompt templates (versioned)
└─ metrics.py       # Evaluation metrics
└─ models.py        # Data models
```

**3. Execution Models**

| Execution Mode | When to Use | Trade-offs |
|----------------|-------------|------------|
| **Local MacBook** | Development, rapid iteration | ✅ Fast feedback, easy debugging<br>❌ Requires port-forwarding |
| **K8s CronJob** | Nightly regression testing | ✅ Automated, close to data<br>❌ Slower iteration cycle |

---

## Directory Structure

```
evals/
├── datasets/                        # Golden datasets (frozen test sets)
│   ├── golden-v1/                   # Version 1 (150 samples)
│   │   ├── metadata.json            # Dataset statistics
│   │   ├── samples.json             # All samples in one file
│   │   └── samples/                 # Individual sample files (optional)
│   │       ├── 001-oom-kill.json
│   │       ├── 002-image-pull.json
│   │       └── ...
│   └── golden-v2/                   # Future versions
│
├── experiments/
│   ├── configs/                     # Experiment configurations
│   │   ├── llama3.2-3b-baseline.yaml
│   │   ├── llama3.2-3b-temp0.1.yaml
│   │   ├── llama3.2-1b-fast.yaml
│   │   └── ...
│   ├── runs/                        # Experiment results (gitignored)
│   │   ├── 20251230-120000-llama3.2-3b-baseline/
│   │   │   ├── config.json          # Frozen experiment snapshot
│   │   │   ├── results.jsonl        # Per-sample results
│   │   │   ├── metrics.json         # Aggregated metrics
│   │   │   └── summary.md           # Human-readable report
│   │   └── ...
│   └── leaderboard.json             # Cross-experiment comparison
│
├── scripts/
│   ├── extract_golden_dataset.py    # ✅ Extract real logs from Loki
│   ├── synthesize_logs.py           # ✅ Generate synthetic logs
│   ├── combine_datasets.py          # ✅ Merge real + synthetic
│   ├── dataset_analysis.py          # ✅ Analyze dataset quality
│   ├── run_experiment.py            # NEW - Run single experiment
│   ├── compare_experiments.py       # NEW - Compare two runs
│   ├── export_metrics.py            # NEW - Export to Prometheus/JSON
│   └── update_leaderboard.py        # NEW - Aggregate results
│
└── README.md                        # Quick start guide
```

---

## Golden Dataset

### Purpose

A **golden dataset** is a frozen, labeled test set used to measure LLM quality consistently across experiments. Think of it as "unit tests for LLM accuracy."

**Critical**: The dataset must contain **realistic samples from your actual cluster** to be valid. Synthetic logs are useful for filling gaps, but the majority should be real.

### Requirements

- **Size**: 100-200 samples (target: 150)
- **Realism**: 70%+ real logs from your cluster
- **Diversity**: Cover different namespaces, failure modes, severities
- **Quality**: Manually labeled ground truth for each sample
- **Versioning**: Immutable once created (golden-v1, golden-v2, etc.)
- **Balance**: Representative distribution across categories and severities

### Target Namespace Coverage

Your cluster has these key namespaces to sample from:

| Namespace | Log Type | Priority | Target Samples |
|-----------|----------|----------|----------------|
| **kube-system** | Infrastructure errors (kubelet, kube-proxy, etc.) | HIGH | 30-40 |
| **logging** | Observability stack (Loki, Tempo, Alloy) | HIGH | 20-30 |
| **llm** | LLM inference errors (llama-cpp) | HIGH | 15-20 |
| **log-analyzer** | Application logs (FastAPI, analysis errors) | HIGH | 15-20 |
| **envoy-gateway-system** | Gateway/routing errors | MEDIUM | 10-15 |
| **flux-system** | GitOps reconciliation | MEDIUM | 10-15 |
| **kube-flannel** | CNI networking | LOW | 5-10 |

**Why this distribution?**
- **kube-system**: Most common source of production issues
- **logging**: Critical for observability, errors here affect everything
- **llm + log-analyzer**: Your application logs, most relevant for your use case
- **envoy/flux**: Important but less frequent errors
- **kube-flannel**: Usually stable, sample for completeness

### Sample Structure

Each sample in the golden dataset has this structure:

```json
{
  "id": "001",
  "category": "pod_lifecycle",
  "severity": "error",
  "namespace": "kube-system",
  "logs": [
    {
      "timestamp": "2025-12-30T10:15:23Z",
      "namespace": "kube-system",
      "pod": "kubelet-node-2",
      "container": "kubelet",
      "node": "node-2",
      "message": "Failed to pull image \"registry.k8s.io/pause:3.9\": rpc error: code = Unknown desc = failed to pull and unpack image"
    },
    {
      "timestamp": "2025-12-30T10:15:20Z",
      "namespace": "kube-system",
      "pod": "kubelet-node-2",
      "container": "kubelet",
      "node": "node-2",
      "message": "Back-off pulling image \"registry.k8s.io/pause:3.9\""
    }
  ],
  "ground_truth": {
    "root_cause": "image_pull_failed",
    "severity": "error",
    "component": "kubelet",
    "summary": "Failed to pull container image from registry, possibly due to network issues or invalid image reference",
    "action_needed": "investigate_network"
  },
  "source": "real",
  "extraction_metadata": {
    "extracted_at": "2025-12-30T12:00:00Z",
    "query": "{namespace=\"kube-system\"} |~ \"(?i)(pull|image).*failed\"",
    "loki_labels": {
      "namespace": "kube-system",
      "pod": "kubelet-node-2",
      "container": "kubelet"
    }
  }
}
```

### Creating the Dataset

#### Step 1: Extract Real Logs from Your Cluster

Port-forward to Loki:
```bash
kubectl port-forward -n logging svc/loki 3100:3100
```

Run the extraction script with targeted queries for your namespaces:

```bash
cd evals
uv run python extract_golden_dataset.py
```

The script (`extract_golden_dataset.py`) queries Loki with these high-value patterns across your namespaces:

**Infrastructure Errors (kube-system)**:
- Pod lifecycle: `{namespace="kube-system"} |~ "(?i)(backoff|crashloop|oomkilled|evicted)"`
- Image problems: `{namespace="kube-system"} |~ "(?i)(imagepull|errimage|failed to pull)"`
- Kubelet errors: `{namespace="kube-system",container="kubelet"} |~ "(?i)error"`
- DNS failures: `{namespace="kube-system"} |~ "(?i)(no such host|dns.*timeout)"`

**Observability Stack (logging)**:
- Loki errors: `{namespace="logging",pod=~"loki-.*"} |~ "(?i)(error|failed|panic)"`
- Tempo errors: `{namespace="logging",pod=~"tempo-.*"} |~ "(?i)(error|failed)"`
- Alloy errors: `{namespace="logging",pod=~"alloy-.*"} |~ "(?i)(error|failed)"`

**Application Logs (llm, log-analyzer)**:
- LLM inference errors: `{namespace="llm"} |~ "(?i)(error|failed|timeout|context.*exceeded)"`
- Log analyzer errors: `{namespace="log-analyzer"} |~ "(?i)(error|exception|failed)"`

**Gateway & GitOps (envoy-gateway-system, flux-system)**:
- Envoy errors: `{namespace="envoy-gateway-system"} |~ "(?i)(upstream|connection|error)"`
- Flux reconciliation: `{namespace="flux-system"} |~ "(?i)(failed|error|reconciliation)"`

**Networking (kube-flannel)**:
- CNI errors: `{namespace="kube-flannel"} |~ "(?i)(error|failed)"`

**What the script does**:
1. Queries Loki with targeted LogQL for each namespace
2. Filters out noise (successful health checks, routine logs)
3. Detects severity levels automatically
4. Deduplicates by error signature
5. Performs stratified sampling to get balanced distribution
6. Saves to `golden_dataset_real.json`

**Expected output**:
- 70-100 real logs from your cluster
- Automatic severity detection
- Balanced across namespaces
- Rich contextual information

#### Step 2: Generate Synthetic Logs (Fill Gaps)

Generate synthetic logs for failure modes not present in your real logs:

```bash
uv run python synthesize_logs.py
```

This creates `golden_dataset_synthetic.json` with:
- 30-50 synthetic samples
- Pre-labeled ground truth
- Coverage for rare failure scenarios (e.g., certificate expiration, RBAC denials)

#### Step 3: Combine Real + Synthetic

Merge to create final balanced dataset:

```bash
uv run python combine_datasets.py
```

Creates `golden_dataset_unlabeled.json` with:
- 150 total samples
- 70% real, 30% synthetic
- Target distribution: 25% INFO, 25% WARN, 40% ERROR, 10% CRITICAL

#### Step 4: Analyze Quality

Review the dataset quality:

```bash
uv run python dataset_analysis.py
```

Outputs:
- Severity distribution
- Namespace coverage
- Category breakdown
- Labeling completeness
- Quality recommendations

#### Step 5: Manual Review & Labeling

**Critical step**: Manually review and label real logs.

```bash
# Open the unlabeled dataset
cat golden_dataset_unlabeled.json | jq '.' | less

# For each real log (source: "real"), fill in ground_truth:
# - root_cause: Error category (e.g., "image_pull_failed", "dns_timeout")
# - severity: "info" | "warn" | "error" | "critical"
# - component: Affected component (e.g., "kubelet", "loki/ingester")
# - summary: 1-2 sentence description
# - action_needed: "investigate" | "fix_config" | "scale" | "monitor" | "ignore"

# Save labeled version
# (Edit in VS Code or your preferred editor)
```

**Labeling guidelines**:
- **root_cause**: Use consistent categories (see Categories section below)
- **severity**: Match Kubernetes severity conventions
  - INFO: Informational, no action needed
  - WARN: Potential issue, monitor
  - ERROR: Problem affecting functionality, needs investigation
  - CRITICAL: Service outage, immediate action
- **component**: Format as `namespace/container` or just component name
- **summary**: Describe WHAT happened (not just repeating the error)
- **action_needed**: What should an SRE do?

#### Step 6: Create Versioned Dataset

```bash
# Create golden-v1 directory
mkdir -p datasets/golden-v1

# Copy labeled dataset
cp golden_dataset_labeled.json datasets/golden-v1/samples.json

# Create metadata
cat > datasets/golden-v1/metadata.json <<EOF
{
  "version": "golden-v1",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "description": "Initial golden dataset from homelab cluster",
  "sample_count": 150,
  "severity_distribution": {
    "INFO": 37,
    "WARN": 38,
    "ERROR": 60,
    "CRITICAL": 15
  },
  "namespace_distribution": {
    "kube-system": 35,
    "logging": 25,
    "llm": 18,
    "log-analyzer": 17,
    "envoy-gateway-system": 12,
    "flux-system": 12,
    "kube-flannel": 8
  },
  "categories": [
    "pod_lifecycle",
    "image_pull",
    "network",
    "dns",
    "storage",
    "config",
    "infrastructure",
    "llm_inference",
    "observability"
  ],
  "real_vs_synthetic": {
    "real": 105,
    "synthetic": 45
  }
}
EOF
```

### Failure Categories

Standardize root_cause labels across samples:

**Pod Lifecycle**:
- `container_oom_killed`
- `crashloop_backoff`
- `pod_evicted`
- `container_exit_nonzero`

**Image Issues**:
- `image_pull_failed`
- `image_pull_backoff`
- `image_not_found`
- `registry_unreachable`

**Network**:
- `connection_refused`
- `connection_timeout`
- `network_unreachable`
- `service_no_endpoints`

**DNS**:
- `dns_resolution_failed`
- `dns_timeout`
- `nxdomain`

**Storage**:
- `pvc_mount_failed`
- `pvc_pending`
- `disk_pressure`
- `volume_not_found`

**Configuration**:
- `configmap_not_found`
- `secret_not_found`
- `invalid_yaml`
- `rbac_permission_denied`

**LLM Inference**:
- `llm_context_exceeded`
- `llm_timeout`
- `llm_model_load_failed`
- `llm_oom`

**Observability**:
- `loki_ingester_failed`
- `tempo_ingestion_error`
- `alloy_scrape_failed`
- `metrics_export_failed`

---

## Experiment Configuration

Each experiment is defined by a YAML configuration file:

```yaml
# evals/experiments/configs/llama3.2-3b-baseline.yaml
experiment_id: "llama3.2-3b-baseline"
description: "Baseline configuration with llama 3.2 3B model"

dataset:
  version: "golden-v1"

model:
  endpoint: "http://localhost:8080"  # Port-forward to K8s
  name: "llama-3.2-3b-instruct"

llm_config:
  temperature: 0.3
  max_tokens: 200
  top_p: 0.95
  frequency_penalty: 0.0
  presence_penalty: 0.0

prompt:
  template: "root_cause_v1"
  system_prompt: |
    You are a Kubernetes reliability engineer.
    Analyze logs and identify root cause, severity, and recommended actions.

    Output format:
    Root Cause: <category>
    Severity: <info|warn|error|critical>
    Component: <namespace/container>
    Summary: <1-2 sentence description>
    Action: <investigate|fix_config|scale|monitor|ignore>
```

### Experiment Variants

Create multiple configurations to test:

**Model Variants:**
```yaml
# llama3.2-3b-q4.yaml (current, faster)
model:
  name: "llama-3.2-3b-instruct"
  file: "llama-3.2-3b-instruct-q4_k_m.gguf"

# llama3.2-3b-q8.yaml (slower, more accurate?)
model:
  name: "llama-3.2-3b-instruct-q8"
  file: "llama-3.2-3b-instruct-q8_0.gguf"

# llama3.2-1b-q4.yaml (faster, less accurate?)
model:
  name: "llama-3.2-1b-instruct"
  file: "llama-3.2-1b-instruct-q4_k_m.gguf"
```

**Temperature Variants:**
```yaml
# High precision (deterministic)
llm_config:
  temperature: 0.1

# Balanced
llm_config:
  temperature: 0.3

# Creative (more variation)
llm_config:
  temperature: 0.5
```

**Prompt Variants:**
```yaml
# Structured output
prompt:
  template: "structured_v1"

# Chain-of-thought reasoning
prompt:
  template: "cot_v1"

# Few-shot examples
prompt:
  template: "fewshot_v1"
```

---

## Running Experiments

### Setup

```bash
# 1. Ensure golden dataset exists
ls -la evals/datasets/golden-v1/samples.json

# 2. Start port-forwards to K8s services
just dev
# This starts:
# - Loki port-forward (not needed for evals, but useful)
# - llama-cpp port-forward (needed)
# - Tempo port-forward (optional, for tracing)

# 3. Verify services are accessible
curl http://localhost:8080/health  # llama-cpp
```

### Run Single Experiment

```bash
# Run experiment with config file
cd /Users/treyshanks/workspace/k8s-slm-log-agent
just experiment llama3.2-3b-baseline

# This executes:
# uv run python evals/scripts/run_experiment.py \
#   evals/experiments/configs/llama3.2-3b-baseline.yaml
```

### What Happens During Experiment

```
1. Load experiment config
2. Load golden dataset (golden-v1)
3. Initialize LogAnalyzer with config
4. For each sample in dataset:
   a. Run analysis using shared LogAnalyzer
   b. Compare result with ground_truth
   c. Compute metrics (accuracy, latency, tokens)
   d. Save individual result
5. Aggregate metrics across all samples
6. Save results to experiments/runs/<timestamp>-<exp-id>/
7. Update leaderboard.json
8. Print summary
```

### Experiment Output

```
experiments/runs/20251230-120000-llama3.2-3b-baseline/
├── config.json          # Frozen experiment configuration
│   {
│     "experiment_id": "llama3.2-3b-baseline",
│     "run_timestamp": "2025-12-30T12:00:00Z",
│     "dataset_version": "golden-v1",
│     "model": {...},
│     "llm_config": {...},
│     "git_commit": "72ee353"
│   }
│
├── results.jsonl        # Per-sample results (JSONL for streaming)
│   {"sample_id":"001","predicted_root_cause":"container_oom_killed",...}
│   {"sample_id":"002","predicted_root_cause":"image_pull_failed",...}
│   ...
│
├── metrics.json         # Aggregated metrics
│   {
│     "accuracy": {
│       "root_cause_exact_match": 0.82,
│       "severity_classification": 0.94,
│       "component_detection": 0.88
│     },
│     "performance": {
│       "avg_latency_ms": 1850,
│       "p95_latency_ms": 2400,
│       "total_tokens": 125000
│     },
│     "per_category": {...}
│   }
│
└── summary.md           # Human-readable report
    # Experiment Summary

    **Experiment ID:** llama3.2-3b-baseline
    **Dataset:** golden-v1 (150 samples)
    **Model:** llama-3.2-3b-instruct

    ## Results
    - Root Cause Accuracy: 82%
    - Severity Accuracy: 94%
    - Average Latency: 1850ms

    ## Top Failures
    1. Network errors: 50% accuracy (20/40 samples)
    2. DNS failures: 65% accuracy (13/20 samples)
    ...
```

---

## Evaluation Metrics

### Accuracy Metrics

**1. Root Cause Exact Match**
```python
correct = predicted_root_cause == ground_truth_root_cause
accuracy = correct_count / total_samples
```

**2. Severity Classification**
```python
# Confusion matrix: INFO, WARN, ERROR, CRITICAL
from sklearn.metrics import classification_report

report = classification_report(
    y_true=[s.ground_truth.severity for s in samples],
    y_pred=[s.predicted.severity for s in samples]
)
```

**3. Component Detection (F1 Score)**
```python
# Partial credit for component name similarity
from sklearn.metrics import f1_score

f1 = f1_score(
    y_true=[s.ground_truth.component for s in samples],
    y_pred=[s.predicted.component for s in samples],
    average='weighted'
)
```

**4. Summary Quality (ROUGE Score)**
```python
# Measure overlap between predicted and ground truth summaries
from rouge_score import rouge_scorer

scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'])
scores = scorer.score(ground_truth_summary, predicted_summary)
```

### Quality Metrics

**1. Hallucination Rate**
```python
# Did LLM mention logs that don't exist?
hallucination_rate = samples_with_hallucinations / total_samples
```

**2. Missed Log Rate**
```python
# Did LLM ignore important logs from input?
missed_rate = samples_with_missed_logs / total_samples
```

### Performance Metrics

**1. Latency**
```python
avg_latency_ms = sum(latencies) / len(latencies)
p95_latency_ms = np.percentile(latencies, 95)
p99_latency_ms = np.percentile(latencies, 99)
```

**2. Token Usage**
```python
total_tokens = sum(sample.tokens_used for sample in samples)
avg_tokens_per_sample = total_tokens / len(samples)
cost_usd = total_tokens * COST_PER_TOKEN
```

### Per-Category Metrics

Break down accuracy by failure category:

```python
categories = ["pod_lifecycle", "image_pull", "network", "dns", "storage", "config", "llm_inference"]

for category in categories:
    category_samples = [s for s in samples if s.category == category]
    category_accuracy = compute_accuracy(category_samples)
    print(f"{category}: {category_accuracy:.1%}")
```

---

## Shared Library Pattern

### Core Analyzer Module

```python
# workloads/log-analyzer/src/log_analyzer/core/analyzer.py
"""
Shared analysis logic used by both production API and evaluation scripts.
"""

from dataclasses import dataclass
from typing import List
import httpx

@dataclass
class LLMConfig:
    temperature: float = 0.3
    max_tokens: int = 200
    top_p: float = 0.95

class LogAnalyzer:
    """
    Core log analysis logic.

    Shared by:
    - Production API (main.py)
    - Evaluation scripts (run_experiment.py)
    - Unit tests (test_analyzer.py)
    """

    def __init__(self, llm_url: str, model_name: str, config: LLMConfig):
        self.llm_url = llm_url
        self.model_name = model_name
        self.config = config

    def build_prompt(self, logs: List[LogEntry]) -> str:
        """Build LLM prompt from logs."""
        # Shared prompt building logic
        pass

    async def call_llm(self, prompt: str) -> str:
        """Call LLM API."""
        # Shared LLM calling logic
        pass

    def parse_response(self, llm_response: str) -> Analysis:
        """Parse LLM response into structured output."""
        # Shared parsing logic
        pass

    async def analyze(self, logs: List[LogEntry]) -> Analysis:
        """Main analysis entrypoint."""
        prompt = self.build_prompt(logs)
        response = await self.call_llm(prompt)
        return self.parse_response(response)
```

### Usage in Production

```python
# workloads/log-analyzer/src/log_analyzer/main.py
from log_analyzer.core.analyzer import LogAnalyzer, LLMConfig

# Initialize once at startup
analyzer = LogAnalyzer(
    llm_url=LLAMA_URL,
    model_name=MODEL_NAME,
    config=LLMConfig(temperature=0.3)
)

@app.post("/v1/analyze")
async def analyze_logs(request: AnalyzeRequest):
    logs = await query_loki(request.filters)
    analysis = await analyzer.analyze(logs)
    return {"analysis": analysis.summary, ...}
```

### Usage in Evaluation

```python
# evals/scripts/run_experiment.py
import sys
from pathlib import Path

# Add log-analyzer to Python path
sys.path.append(str(Path(__file__).parent.parent.parent / "workloads" / "log-analyzer" / "src"))

from log_analyzer.core.analyzer import LogAnalyzer, LLMConfig

async def run_experiment(config: Dict):
    # Initialize analyzer with experiment config
    analyzer = LogAnalyzer(
        llm_url=config["model"]["endpoint"],
        model_name=config["model"]["name"],
        config=LLMConfig(**config["llm_config"])
    )

    # Load golden dataset
    dataset = load_golden_dataset(config["dataset"]["version"])

    # Run evaluation
    for sample in dataset:
        analysis = await analyzer.analyze(sample["logs"])

        # Compare with ground truth
        is_correct = analysis.root_cause == sample["ground_truth"]["root_cause"]

        # Save result
        save_result(sample["id"], analysis, is_correct)
```

---

## Visualization in Grafana

### Setup

1. **Install Grafana Infinity Plugin**
```bash
# On Grafana pod or via Helm values
kubectl exec -it -n logging deployment/grafana -- \
  grafana-cli plugins install yesoreyeram-infinity-datasource

# Restart Grafana
kubectl rollout restart -n logging deployment/grafana
```

2. **Configure Infinity Datasource**
- Navigate to Grafana → Configuration → Data Sources
- Add new "Infinity" datasource
- Configure to read JSON files from eval results

### Dashboard: Experiment Leaderboard

**Panel: Table**
```json
{
  "datasource": "Infinity",
  "type": "table",
  "targets": [
    {
      "type": "json",
      "source": "url",
      "url": "http://localhost:8000/api/evals/leaderboard",
      "format": "table",
      "columns": [
        {"selector": "experiment_id", "text": "Experiment", "type": "string"},
        {"selector": "model_name", "text": "Model", "type": "string"},
        {"selector": "accuracy", "text": "Accuracy", "type": "number"},
        {"selector": "avg_latency_ms", "text": "Latency (ms)", "type": "number"},
        {"selector": "cost_usd", "text": "Cost ($)", "type": "number"}
      ]
    }
  ]
}
```

### Dashboard: Accuracy Over Time

**Panel: Time Series**
```
Query: Read from experiments/leaderboard.json
X-axis: run_timestamp
Y-axis: accuracy
Group by: experiment_id
```

### Dashboard: Accuracy by Category

**Panel: Bar Chart**
```
Query: Read from latest experiment run metrics.json
X-axis: category (pod_lifecycle, image_pull, network, etc.)
Y-axis: accuracy
```

### Serving Leaderboard via API (Optional)

```python
# workloads/log-analyzer/src/log_analyzer/main.py

@app.get("/api/evals/leaderboard")
async def get_leaderboard():
    """Serve leaderboard for Grafana Infinity datasource."""
    leaderboard_path = Path(__file__).parent.parent.parent.parent / "evals" / "experiments" / "leaderboard.json"

    with open(leaderboard_path) as f:
        return json.load(f)
```

---

## Roadmap

### Phase 1: Dataset Finalization ✅ COMPLETE

**Goal**: Production-ready golden dataset with ground truth labels from real cluster logs

**Tasks**:
- [x] Start Loki port-forward: `kubectl port-forward -n logging svc/loki 3100:3100`
- [x] Run extraction workflow with severity filters and extended time windows:
  ```bash
  cd evals
  uv run python extract_by_namespace_and_severity.py
  ```
- [x] Extract additional logs from previous evaluation runs:
  ```bash
  uv run python extract_from_previous_evals.py
  ```
- [x] Merge and rebalance datasets with namespace priorities:
  ```bash
  uv run python merge_and_rebalance.py
  ```
- [x] **Complete**: Automated + manual labeling of all logs
  - Created 30 hand-labeled samples (`sample_labeled.json`)
  - Created comprehensive labeling guide (`LABELING_GUIDE.md`)
  - Automated labeling of remaining 85 logs using pattern matching (`label_all_logs.py`)
  - Final dataset: `golden_dataset.json` (100% labeled)
- [x] Analyze quality: `uv run python dataset_analysis.py golden_dataset.json`
- [x] Create versioned dataset:
  ```bash
  cp golden_dataset.json golden-v1.json
  ```

**Deliverable**: `evals/golden-v1.json` ✅ (115 fully labeled samples, 100% real)

**Results Achieved**:
- ✅ 115 total samples (100% real cluster logs, 0% synthetic)
- ✅ Severity distribution:
  - ERROR: 79 (69%) - actionable failures
  - WARN: 28 (24%) - transient issues
  - INFO: 5 (4%) - informational
  - CRITICAL: 3 (3%) - manual intervention needed
- ✅ Namespace coverage (prioritized log-analyzer + llm):
  - log-analyzer: 30 (26%)
  - kube-system: 20 (17%)
  - envoy-gateway-system: 20 (17%)
  - flux-system: 19 (17%)
  - llm: 18 (16%)
  - logging: 8 (7%)
- ✅ 100% of samples have complete ground_truth labels
- ✅ 21 unique failure categories:
  - Top: apiserver_not_ready (14), empty_query_result (11), context_size_exceeded (10), metrics_server_missing (9), exception_stacktrace (8)
- ✅ Action distribution reveals real cluster issues:
  - investigate: 43 (37%) - real errors requiring attention
  - none: 29 (25%) - expected/transient
  - increase_context_size: 10 (9%) - identified config issue
  - wait_for_apiserver: 14 (12%) - startup transients

**Key Insights**:
- Used LogQL severity filters (`|~ "(?i)(error|warn|critical)"`) to exclude INFO noise
- Extended lookback windows (7-14 days) to capture rare failures
- Discovered actionable issues: LLM context size too small (10 errors), Flux Helm failures (9 errors)
- Pattern-based labeling enabled systematic classification across 21 failure types

---

### Phase 2: Offline Evaluation Harness (Week 3-4)

**Goal**: Run reproducible experiments against golden dataset

**Tasks**:
- [ ] Create shared `LogAnalyzer` library:
  ```bash
  mkdir -p workloads/log-analyzer/src/log_analyzer/core
  touch workloads/log-analyzer/src/log_analyzer/core/analyzer.py
  touch workloads/log-analyzer/src/log_analyzer/core/metrics.py
  touch workloads/log-analyzer/src/log_analyzer/core/prompts.py
  ```
- [ ] Extract core logic from `main.py` into `analyzer.py`
- [ ] Write `evals/scripts/run_experiment.py`:
  - Load experiment config from YAML
  - Initialize LogAnalyzer with config
  - Run analysis on each golden sample
  - Compute accuracy, latency, F1 metrics
  - Save results to `experiments/runs/<timestamp>-<exp-id>/`
- [ ] Create experiment config schema:
  ```yaml
  # evals/experiments/configs/llama3.2-3b-baseline.yaml
  ```
- [ ] Create 3 baseline configs:
  - `llama3.2-3b-baseline.yaml` (temp: 0.3)
  - `llama3.2-3b-temp0.1.yaml` (high precision)
  - `llama3.2-3b-temp0.5.yaml` (creative)
- [ ] Add justfile recipes:
  ```bash
  # Add to justfile
  experiment config_name:
      uv run python evals/scripts/run_experiment.py evals/experiments/configs/{{config_name}}.yaml

  compare run_id_1 run_id_2:
      uv run python evals/scripts/compare_experiments.py {{run_id_1}} {{run_id_2}}
  ```
- [ ] Write unit tests for shared LogAnalyzer

**Deliverable**: Can run reproducible experiments from command line

**Success Criteria**:
- `just experiment llama3.2-3b-baseline` runs full evaluation
- Results saved with frozen config and git commit
- Metrics computed: root_cause accuracy, severity accuracy, latency, tokens
- Results are reproducible (same config → same results)
- Experiments complete in <10 minutes for 150 samples

---

### Phase 3: Visualization & Metrics (Week 5)

**Goal**: Track experiment results over time in Grafana

**Tasks**:
- [ ] Install Grafana Infinity plugin:
  ```bash
  kubectl exec -it -n logging deployment/grafana -- \
    grafana-cli plugins install yesoreyeram-infinity-datasource
  kubectl rollout restart -n logging deployment/grafana
  ```
- [ ] Create `evals/scripts/update_leaderboard.py`:
  - Scan `experiments/runs/` directory
  - Aggregate metrics from all runs
  - Write to `experiments/leaderboard.json`
- [ ] Add leaderboard justfile recipe:
  ```bash
  leaderboard:
      uv run python evals/scripts/update_leaderboard.py
  ```
- [ ] Create Grafana dashboards:
  - **Experiment Leaderboard** (table view)
  - **Accuracy Over Time** (time series)
  - **Accuracy by Category** (bar chart)
  - **Latency Distribution** (histogram)
- [ ] Optional: Serve leaderboard via API endpoint
  ```python
  @app.get("/api/evals/leaderboard")
  async def get_leaderboard(): ...
  ```

**Deliverable**: Grafana dashboards showing experiment trends

**Success Criteria**:
- Can view leaderboard of all experiments in Grafana
- Can see accuracy trends over time (detect regressions)
- Can drill down to per-category performance
- Can identify best-performing config at a glance

---

### Phase 4: Multi-Model Support (Week 6-7)

**Goal**: A/B test different models and quantizations

**Tasks**:
- [ ] Download additional models to Node 2:
  ```bash
  ssh node2
  cd /mnt/k8s-storage/models

  # 1B model (faster, less accurate?)
  wget https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf

  # 3B Q8 quantization (slower, more accurate?)
  wget https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q8_0.gguf
  ```
- [ ] Create additional llama-cpp deployments:
  - Copy `workloads/llm/llama-deployment.yaml` → `llama-deployment-1b.yaml`
  - Update model path, resource limits
  - Create corresponding service: `llama-service-1b.yaml`
  - Repeat for Q8 variant
- [ ] Deploy new models:
  ```bash
  kubectl apply -f workloads/llm/llama-deployment-1b.yaml
  kubectl apply -f workloads/llm/llama-deployment-3b-q8.yaml
  ```
- [ ] Create experiment configs for each model:
  - `llama3.2-1b-q4-baseline.yaml`
  - `llama3.2-3b-q8-baseline.yaml`
- [ ] Run experiments on all models:
  ```bash
  just experiment llama3.2-3b-q4-baseline
  just experiment llama3.2-1b-q4-baseline
  just experiment llama3.2-3b-q8-baseline
  ```
- [ ] Update leaderboard and compare in Grafana

**Deliverable**: Data-driven model selection (accuracy vs. speed trade-off)

**Success Criteria**:
- Can run same experiment on 3+ different models
- Clear winner for accuracy (even if slower)
- Clear winner for speed (even if less accurate)
- Documented trade-offs with specific numbers:
  - Model A: 92% accuracy, 2.1s latency
  - Model B: 85% accuracy, 1.0s latency
  - Model C: 78% accuracy, 0.6s latency
- Production decision: Choose Model A (accuracy) or Model B (balanced)

---

### Phase 5: Prompt Engineering (Week 8+)

**Goal**: Iterate on prompts using experiment framework

**Tasks**:
- [ ] Create prompt template library:
  ```bash
  mkdir -p workloads/log-analyzer/src/log_analyzer/prompts
  touch workloads/log-analyzer/src/log_analyzer/prompts/root_cause_v1.txt
  touch workloads/log-analyzer/src/log_analyzer/prompts/root_cause_v2.txt
  touch workloads/log-analyzer/src/log_analyzer/prompts/structured_output_v1.txt
  touch workloads/log-analyzer/src/log_analyzer/prompts/chain_of_thought_v1.txt
  ```
- [ ] Write baseline prompts (v1)
- [ ] Run baseline experiment
- [ ] Analyze failure modes:
  ```bash
  # Find samples where LLM failed
  cat experiments/runs/latest/results.jsonl | \
    jq 'select(.is_correct == false) | {sample_id, predicted, actual, category}'
  ```
- [ ] Create targeted prompt improvements (v2):
  - Add few-shot examples for problematic categories
  - Clarify output format
  - Add chain-of-thought for complex errors
- [ ] A/B test prompt variations:
  ```bash
  just experiment prompt-v1-baseline
  just experiment prompt-v2-fewshot
  just experiment prompt-v2-cot
  ```
- [ ] Track prompt performance over time in Grafana
- [ ] Document best prompts for each failure category

**Deliverable**: Best-performing prompts for each task type

**Success Criteria**:
- 5+ prompt variants tested
- Clear winner for root cause extraction
- Documented when to use which prompt (e.g., few-shot for network errors, CoT for cascade failures)
- Baseline → optimized accuracy improvement of 10%+ (e.g., 75% → 85%)
- Production uses best-performing prompt

**Optional: DSPy Integration**
- [ ] If accuracy plateaus <85%, experiment with DSPy
- [ ] Install DSPy: `uv add dspy-ai`
- [ ] Convert golden dataset to DSPy format
- [ ] Define LogAnalysis signature
- [ ] Run BootstrapFewShot optimizer
- [ ] Compare DSPy-optimized vs. manually-crafted prompts

---

### Phase 6: Automation (Future)

**Goal**: Continuous quality monitoring

**Tasks**:
- [ ] Create K8s CronJob for nightly experiments
- [ ] Set up alerting when accuracy drops below threshold
- [ ] Automate leaderboard updates
- [ ] Build evaluation into CI/CD pipeline
- [ ] Create regression test suite

**Deliverable**: Hands-off quality monitoring

---

## Best Practices

### Experiment Hygiene

**1. Always version everything**
- Dataset: `golden-v1`, `golden-v2`
- Prompts: `root_cause_v1`, `root_cause_v2`
- Configs: Include git commit in results

**2. Run experiments in isolation**
- One experiment at a time
- Clean state between runs
- No concurrent modifications to shared state

**3. Document intent**
- Add `description` field to experiment configs
- Explain why you're running the experiment
- Note expected outcome vs. actual

**4. Fail fast**
- Validate config before running full experiment
- Start with 10-sample subset for new configs
- Check for obvious errors before 150-sample run

### Debugging Failed Experiments

```bash
# Check experiment logs
cat experiments/runs/<run-id>/summary.md

# View per-sample failures
jq 'select(.is_correct == false)' experiments/runs/<run-id>/results.jsonl

# Find common failure patterns
jq -r 'select(.is_correct == false) | .category' \
  experiments/runs/<run-id>/results.jsonl | sort | uniq -c | sort -rn
```

### Dataset Maintenance

**When to create golden-v2:**
- Found systematic labeling errors in v1
- Want to add new failure categories
- Dataset doesn't represent current production logs
- Expanding from 150 to 300 samples

**How to version:**
```bash
# Create new version
cp -r evals/datasets/golden-v1 evals/datasets/golden-v2

# Document changes
cat > evals/datasets/golden-v2/CHANGELOG.md <<EOF
# Changes from golden-v1

- Added 50 new samples for DNS failures
- Fixed labeling errors in samples 023, 045, 078
- Updated severity for network timeouts (warn → error)
EOF

# Update metadata
# Edit golden-v2/metadata.json
```

---

## Troubleshooting

### Experiment script hangs

**Symptom**: `run_experiment.py` hangs on first sample

**Causes**:
- Port-forward died (check `just dev`)
- LLM server not responding (check `curl http://localhost:8080/health`)
- Prompt too long, exceeds context window

**Solution**:
```bash
# Check port-forwards
lsof -i :8080  # Should show kubectl port-forward

# Restart if needed
just stop
just dev

# Check LLM health
curl http://localhost:8080/health
curl http://localhost:8080/v1/models
```

### Metrics don't match manual testing

**Symptom**: Experiment shows 80% accuracy, but manual testing seems better

**Causes**:
- Different prompt than production
- Different temperature/sampling
- Different log preprocessing

**Solution**:
```bash
# Run experiment with production config
just experiment production-mirror

# Compare configs
diff \
  workloads/log-analyzer/k8s/01-configmap.yaml \
  evals/experiments/configs/production-mirror.yaml
```

### Grafana dashboard shows no data

**Symptom**: Infinity datasource configured, but panels show "No data"

**Causes**:
- JSON file path incorrect
- JSON format not compatible
- Datasource permissions

**Solution**:
```bash
# Test leaderboard file directly
cat evals/experiments/leaderboard.json | jq .

# Serve via HTTP for easier debugging
cd evals/experiments
python3 -m http.server 8001

# Configure Infinity datasource:
# URL: http://localhost:8001/leaderboard.json
```

---

## References

### Related Documentation

- **Production API**: `workloads/log-analyzer/README.md` - Deployment and API docs
- **Golden Dataset**: `evals/README.md` - Dataset generation workflow
- **Infrastructure**: `infrastructure/gateway/README.md` - Envoy Gateway setup
- **Project Goals**: `agents.md` - High-level project architecture

### External Resources

- [DSPy Documentation](https://dspy-docs.vercel.app/) - Prompt optimization framework
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html) - Experiment tracking
- [Grafana Infinity Plugin](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) - JSON datasource
- [ROUGE Score](https://pypi.org/project/rouge-score/) - Summary quality metrics

---

## Quick Start

```bash
# 1. Create golden dataset from your cluster
cd evals

# Start Loki port-forward
kubectl port-forward -n logging svc/loki 3100:3100 &

# Extract real logs from all namespaces
uv run python extract_golden_dataset.py

# Generate synthetic logs for gaps
uv run python synthesize_logs.py

# Combine into final dataset
uv run python combine_datasets.py

# Manually label real logs
# Edit golden_dataset_unlabeled.json → golden_dataset_labeled.json

# 2. Set up dataset directory
mkdir -p datasets/golden-v1
cp golden_dataset_labeled.json datasets/golden-v1/samples.json

# 3. Start K8s port-forwards
just dev

# 4. Run baseline experiment
just experiment llama3.2-3b-baseline

# 5. View results
cat experiments/runs/*/summary.md

# 6. Update leaderboard
uv run python evals/scripts/update_leaderboard.py

# 7. View in Grafana
open http://localhost:3000/dashboards
```
