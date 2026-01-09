# LLM Evaluation & Prompt Optimization Framework

**Complete roadmap for measuring, improving, and tracking LLM-powered log analysis quality.**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Golden Dataset (Phase 1 - COMPLETE)](#phase-1-golden-dataset-complete)
4. [Shared Analyzer Module (Phase 2)](#phase-2-shared-analyzer-module)
5. [Evaluation Harness (Phase 3)](#phase-3-evaluation-harness)
6. [Prompt Optimization (Phase 4)](#phase-4-prompt-optimization)
7. [Grafana Visualization (Phase 5)](#phase-5-grafana-visualization)
8. [Complete Workflows](#complete-workflows)
9. [Time Estimates](#time-estimates)
10. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

This document unifies two complementary systems:

1. **Evaluation Harness** - Measures quality of ANY prompt/model/config against golden dataset
2. **Prompt Optimizer** - Searches for better prompts using systematic variation

Both systems share:
- Golden dataset (115 labeled samples, 100% real cluster logs)
- Metrics module (unified accuracy/quality measures)
- Grafana dashboards (single view of all experiments and optimizations)

**Key Innovation:** Separate optimization environment (M2 MacBook with GPU) from production environment (K8s cluster with CPU). This enables:
- ⚡ Fast iteration: 1 minute per experiment (vs 42 minutes in cluster)
- 🎯 Systematic improvement: Data-driven prompt selection
- 📊 Continuous monitoring: Track quality over time in Grafana
- 🏠 Zero cluster impact: Optimize locally, deploy via GitOps

---

## Architecture Overview

### System Components

```
┌────────────────────────────────────────────────────────────────┐
│                   UNIFIED EVALUATION SYSTEM                    │
└────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   DATASETS   │    │ SHARED ANALYZER  │    │   METRICS    │
│              │    │                  │    │              │
│ golden-v1    │◀──▶│ analyzer.py      │◀──▶│ metrics.py   │
│ - train (60) │    │ prompts.py       │    │              │
│ - val (55)   │    │ models.py        │    │ • Accuracy   │
└──────────────┘    └──────────────────┘    │ • Quality    │
                             │               │ • Latency    │
                             │               └──────┬───────┘
                             │                      │
        ┌────────────────────┴──────────┐           │
        │                               │           │
        ▼                               ▼           │
┌──────────────────┐          ┌──────────────────┐  │
│ EVAL HARNESS     │          │ PROMPT OPTIMIZER │  │
│                  │          │                  │  │
│ • Run exps       │          │ • Generate       │  │
│ • Full dataset   │          │   candidates     │  │
│ • Detailed       │          │ • Test on val    │  │
│   metrics        │          │ • Select best    │  │
│                  │          │ • Output YAML    │  │
└────────┬─────────┘          └────────┬─────────┘  │
         │                             │            │
         └──────────┬──────────────────┘            │
                    │                               │
                    ▼                               │
         ┌────────────────────┐                     │
         │  RESULT STORAGE    │◀────────────────────┘
         │                    │
         │ experiments/runs/  │
         │ optimization/runs/ │
         │ dashboards/*.json  │
         └──────────┬─────────┘
                    │
                    ▼
         ┌────────────────────┐
         │ GRAFANA DASHBOARDS │
         │                    │
         │ • Leaderboard      │
         │ • Trends           │
         │ • Categories       │
         └────────────────────┘
```

### Design Principles

1. **Separation of Concerns**
   - Production API (log-analyzer): Optimized for latency, stable config
   - Evaluation System (evals/): Measures quality offline, tests variations

2. **Shared Core Logic**
   - Single `LogAnalyzer` class used by production, evaluation, and optimization
   - Ensures what you measure = what you deploy

3. **Local Optimization, Remote Deployment**
   - Optimize on M2 MacBook (fast GPU inference)
   - Deploy to K8s cluster (CPU inference) via GitOps
   - No optimization overhead in production

4. **Git-Reviewable Artifacts**
   - Prompts are YAML files, not opaque binaries
   - Experiment results are JSON/JSONL
   - Everything versioned and reviewable

---

## Phase 1: Golden Dataset (COMPLETE) ✅

### Status

**COMPLETE** - 115 labeled samples ready for evaluation

### Dataset Structure

```json
{
  "timestamp": 1766954816856.0,
  "namespace": "log-analyzer",
  "pod": "log-analyzer-7669d66676-gvm8p",
  "container": "log-analyzer",
  "node": "node-1",
  "log_line": "...",
  "detected_severity": "ERROR",
  "signature_hash": "562e4ddb",
  "source": "real",
  "root_cause": "tempo_unavailable",
  "severity": "warn",
  "component": "opentelemetry_exporter",
  "summary": "OpenTelemetry exporter cannot reach Tempo service",
  "action_needed": "monitor"
}
```

### Dataset Statistics

- **Total samples:** 115 (100% real cluster logs)
- **Severity distribution:**
  - ERROR: 79 (69%)
  - WARN: 28 (24%)
  - INFO: 5 (4%)
  - CRITICAL: 3 (3%)
- **Namespace coverage:**
  - log-analyzer: 30 (26%)
  - kube-system: 20 (17%)
  - envoy-gateway-system: 20 (17%)
  - flux-system: 19 (17%)
  - llm: 18 (16%)
  - logging: 8 (7%)
- **Failure categories:** 21 unique categories

### Train/Validation Split

For prompt optimization, we split the dataset:

```bash
# Create train/validation split (60/55)
cd evals
uv run python scripts/split_dataset.py golden-v1.json

# Output:
# - golden-v1-train.json (60 samples) - For few-shot examples
# - golden-v1-validation.json (55 samples) - For optimization search
```

**Rationale for 60/55 split:**
- **Training (60 samples):** Used to extract few-shot examples during optimization
- **Validation (55 samples):** Used to measure candidate prompts during search
- **Full (115 samples):** Used for final experiments and production validation

### Location

```
evals/
├── golden-v1.json              # Full dataset (115 samples)
├── golden-v1-train.json        # Training split (60 samples)
└── golden-v1-validation.json   # Validation split (55 samples)
```

---

## Phase 2: Shared Analyzer Module

### Goal

Extract core log analysis logic into a reusable module shared by:
1. Production API (`main.py`)
2. Evaluation harness (`run_experiment.py`)
3. Prompt optimizer (`run_optimization.py`)

This ensures **what you measure = what you deploy**.

### Directory Structure

```
workloads/log-analyzer/src/log_analyzer/
├── main.py                      # FastAPI application (uses core/)
├── core/                        # NEW - Shared logic
│   ├── __init__.py
│   ├── analyzer.py              # LogAnalyzer class
│   ├── prompts.py               # Prompt template management
│   └── models.py                # Data models
└── evaluation/                  # NEW - Evaluation-specific
    ├── __init__.py
    ├── metrics.py               # Quality metrics
    └── utils.py                 # Eval helpers
```

### Core Analyzer API

```python
# workloads/log-analyzer/src/log_analyzer/core/analyzer.py

from dataclasses import dataclass
from typing import List, Dict, Any
import httpx
from opentelemetry import trace

@dataclass
class LLMConfig:
    """LLM inference configuration."""
    temperature: float = 0.3
    max_tokens: int = 200
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

@dataclass
class LogEntry:
    """Normalized log entry."""
    timestamp: str
    namespace: str
    pod: str
    container: str
    node: str
    message: str

@dataclass
class Analysis:
    """Structured analysis result."""
    root_cause: str
    severity: str
    component: str
    summary: str
    action_needed: str
    raw_response: str  # For debugging

class LogAnalyzer:
    """
    Core log analysis logic.

    Shared by:
    - Production API (main.py)
    - Evaluation harness (run_experiment.py)
    - Prompt optimizer (run_optimization.py)
    """

    def __init__(
        self,
        llm_url: str,
        model_name: str,
        prompt_template: str,
        config: LLMConfig,
        tracer: trace.Tracer = None
    ):
        self.llm_url = llm_url
        self.model_name = model_name
        self.prompt_template = prompt_template
        self.config = config
        self.tracer = tracer

    def build_prompt(
        self,
        logs: List[LogEntry],
        namespace: str = "unknown",
        time_range: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Build LLM prompt from logs using configured template.

        Returns messages array for OpenAI-compatible API.
        """
        # Load template (from registry or inline)
        # Render with Jinja2
        # Return {"messages": [...]}
        pass

    async def call_llm(self, messages: List[Dict]) -> str:
        """
        Call LLM API with messages.

        Returns raw LLM response text.
        """
        span = self.tracer.start_span("call_llm") if self.tracer else None

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                        "top_p": self.config.top_p,
                    }
                )
                resp.raise_for_status()
                data = resp.json()

                if span:
                    span.set_attribute("llm.tokens_prompt", data["usage"]["prompt_tokens"])
                    span.set_attribute("llm.tokens_completion", data["usage"]["completion_tokens"])

                return data["choices"][0]["message"]["content"]
        finally:
            if span:
                span.end()

    def parse_response(self, llm_response: str) -> Analysis:
        """
        Parse LLM response into structured Analysis object.

        Handles various output formats gracefully.
        """
        # Extract fields using regex or simple parsing
        # Return Analysis dataclass
        pass

    async def analyze(
        self,
        logs: List[LogEntry],
        namespace: str = "unknown",
        time_range: str = "unknown"
    ) -> Analysis:
        """
        Main analysis entrypoint.

        This is the ONLY method called by production/eval/optimizer.
        """
        span = self.tracer.start_span("analyze") if self.tracer else None

        try:
            messages = self.build_prompt(logs, namespace, time_range)
            response = await self.call_llm(messages["messages"])
            analysis = self.parse_response(response)
            return analysis
        finally:
            if span:
                span.end()
```

### Metrics Module

```python
# workloads/log-analyzer/evaluation/metrics.py

from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class MetricResult:
    """Result of evaluating a single prediction."""
    # Core accuracy (used by optimizer)
    root_cause_exact_match: float  # 0.0 or 1.0
    severity_exact_match: float
    action_exact_match: float

    # Quality metrics (used by harness)
    component_f1: float  # 0.0 to 1.0
    summary_rouge_l: float  # 0.0 to 1.0

    # Aggregate score (primary optimization target)
    overall: float

def exact_match(expected: str, predicted: str) -> float:
    """Binary exact match: 1.0 if match, 0.0 otherwise."""
    return 1.0 if expected.strip().lower() == predicted.strip().lower() else 0.0

def semantic_similarity(expected: str, predicted: str) -> float:
    """
    Jaccard similarity between tokenized strings.

    Simple but effective for log analysis.
    Can upgrade to embeddings later if needed.
    """
    exp_tokens = set(expected.lower().split())
    pred_tokens = set(predicted.lower().split())

    if not exp_tokens and not pred_tokens:
        return 1.0
    if not exp_tokens or not pred_tokens:
        return 0.0

    intersection = len(exp_tokens & pred_tokens)
    union = len(exp_tokens | pred_tokens)

    return intersection / union if union > 0 else 0.0

def component_f1_score(expected: str, predicted: str) -> float:
    """
    F1 score for component detection.

    Handles partial matches (e.g., "kubelet" vs "kube-system/kubelet").
    """
    # Simple implementation: token-based similarity
    return semantic_similarity(expected, predicted)

def rouge_score(expected: str, predicted: str) -> float:
    """
    ROUGE-L score for summary quality.

    Measures longest common subsequence between summaries.
    """
    # Simple approximation: use semantic similarity
    # Can upgrade to real ROUGE library later
    return semantic_similarity(expected, predicted)

def evaluate_prediction(
    expected: Dict[str, Any],
    predicted: Dict[str, Any]
) -> MetricResult:
    """
    Unified metrics used by BOTH evaluation harness AND optimizer.

    Priority ranking (from user):
    1. Root cause accuracy (40%)
    2. Action accuracy (25%)
    3. Severity accuracy (20%)
    4. Summary quality (10%)
    5. Component F1 (5%)

    Args:
        expected: Ground truth from golden dataset
        predicted: LLM's analysis output

    Returns:
        MetricResult with all metrics computed
    """
    # Core accuracy (binary)
    root_cause_match = exact_match(
        expected.get("root_cause", ""),
        predicted.get("root_cause", "")
    )
    severity_match = exact_match(
        expected.get("severity", ""),
        predicted.get("severity", "")
    )
    action_match = exact_match(
        expected.get("action_needed", ""),
        predicted.get("action_needed", "")
    )

    # Quality metrics (continuous)
    component_f1 = component_f1_score(
        expected.get("component", ""),
        predicted.get("component", "")
    )
    summary_rouge = rouge_score(
        expected.get("summary", ""),
        predicted.get("summary", "")
    )

    # Weighted overall score
    overall = (
        root_cause_match * 0.40 +
        action_match * 0.25 +
        severity_match * 0.20 +
        summary_rouge * 0.10 +
        component_f1 * 0.05
    )

    return MetricResult(
        root_cause_exact_match=root_cause_match,
        severity_exact_match=severity_match,
        action_exact_match=action_match,
        component_f1=component_f1,
        summary_rouge_l=summary_rouge,
        overall=overall
    )
```

### Success Criteria

- [ ] `LogAnalyzer` class created in `core/analyzer.py`
- [ ] Metrics module created in `evaluation/metrics.py`
- [ ] Production `main.py` uses shared analyzer
- [ ] All tests pass
- [ ] No behavior changes in production API

**Time estimate:** 1-2 days

---

## Phase 3: Evaluation Harness

### Goal

Build a system to run reproducible experiments that measure LLM quality against the golden dataset.

### Directory Structure

```
evals/
├── datasets/
│   ├── golden-v1.json              # Full dataset
│   ├── golden-v1-train.json        # Training split
│   └── golden-v1-validation.json   # Validation split
│
├── experiments/
│   ├── configs/                    # Experiment configurations
│   │   ├── baseline-v1.yaml
│   │   ├── optimized-v2.yaml
│   │   ├── llama-1b-fast.yaml
│   │   └── high-temp.yaml
│   │
│   ├── runs/                       # Experiment results (gitignored)
│   │   ├── 20250109-143000-baseline-v1/
│   │   │   ├── config.json         # Frozen config snapshot
│   │   │   ├── results.jsonl       # Per-sample results
│   │   │   ├── metrics.json        # Aggregated metrics
│   │   │   └── summary.md          # Human-readable report
│   │   └── ...
│   │
│   └── leaderboard.json            # Cross-experiment comparison
│
└── scripts/
    ├── run_experiment.py           # Run single experiment
    ├── compare_experiments.py      # Compare two experiments
    └── update_leaderboard.py       # Aggregate results
```

### Experiment Configuration

```yaml
# evals/experiments/configs/baseline-v1.yaml

experiment_id: "baseline-v1"
description: "Baseline with current prompt v1"

dataset:
  path: "evals/golden-v1.json"  # Full dataset for experiments

model:
  endpoint: "http://localhost:8080"  # M2 MacBook llama-server
  name: "llama-3.2-3b-instruct"

llm_config:
  temperature: 0.3
  max_tokens: 200
  top_p: 0.95

prompt:
  id: "k8s_log_analysis_v1"
  path: "workloads/log-analyzer/prompt_templates/k8s_log_analysis_v1.yaml"

execution:
  concurrency: 4  # Parallel requests (M2 can handle this)
```

### Justfile Integration

```makefile
# justfile (add to root)

# Run an experiment
experiment config_name:
    #!/usr/bin/env bash
    set -euo pipefail
    cd workloads/log-analyzer
    uv run python ../../evals/scripts/run_experiment.py \
        ../../evals/experiments/configs/{{config_name}}.yaml

# Compare two experiments
compare exp1 exp2:
    uv run python evals/scripts/compare_experiments.py {{exp1}} {{exp2}}

# Update leaderboard
leaderboard:
    uv run python evals/scripts/update_leaderboard.py
```

### Success Criteria

- [ ] Experiment runner script works
- [ ] Can run full experiment in ~1 minute (M2, 4x parallelization)
- [ ] Results saved in structured format
- [ ] Summary report generated
- [ ] Justfile commands working

**Time estimate:** 2-3 days

---

## Phase 4: Prompt Optimization

### Goal

Systematically search for better prompts using the validation dataset.

### How It Works

```
1. Define Search Space
   ├─ Instruction variants (3 options)
   ├─ Few-shot strategies (4 options)
   ├─ Reasoning approaches (3 options)
   └─ Output formats (3 options)
   Total: 3×4×3×3 = 108 combinations

2. Sample Candidates (10 random)

3. Evaluate Each Candidate
   ├─ Test on validation set (55 samples)
   ├─ Compute overall score
   └─ Time: 55 × 2s = 110s per candidate

4. Select Winner
   ├─ Rank by overall score
   ├─ Export best as k8s_log_analysis_v2.yaml
   └─ Save all results

5. Validate Winner
   ├─ Run full experiment (115 samples)
   └─ Compare with baseline
```

### Search Space Definition

See `dspy.md` Part 5 for complete search space implementation.

### Justfile Integration

```makefile
# justfile (add)

# Run prompt optimization on M2 MacBook
optimize-prompts:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "🚀 Starting prompt optimization..."
    echo ""
    echo "Prerequisites:"
    echo "  ✓ llama.cpp server running on localhost:8080"
    echo "  ✓ Validation dataset: evals/golden-v1-validation.json"
    echo ""
    read -p "Press Enter to continue (Ctrl+C to cancel)..."
    cd workloads/log-analyzer
    uv run python evaluation/optimize.py

# Complete workflow
optimize-and-validate:
    just optimize-prompts
    just experiment optimized-v2
    just compare baseline-v1 optimized-v2
```

### Success Criteria

- [ ] Optimizer generates candidates from search space
- [ ] Evaluates 10 candidates in ~5 minutes (M2, 4x parallelization)
- [ ] Exports winner as YAML
- [ ] Can iterate weekly without cluster impact

**Time estimate:** 2-3 days

---

## Phase 5: Grafana Visualization

### Goal

Single dashboard showing all experiments and optimization runs with trend analysis.

### Dashboard Layout

**Panel 1: Experiment Leaderboard (Table)**
- All experiments ranked by overall score
- Shows: experiment_id, prompt, score, latency, date

**Panel 2: Score Over Time (Time Series)**
- Track prompt performance across versions
- Compare multiple experiments

**Panel 3: Category Accuracy (Heatmap)**
- Per-category breakdown
- Identify weak spots

### Data Flow

```
Experiments → leaderboard.json → Grafana JSON API → Dashboard
```

### Justfile Integration

```makefile
# Update Grafana dashboards
leaderboard:
    uv run python evals/scripts/update_leaderboard.py
```

### Success Criteria

- [ ] Leaderboard JSON generated and served
- [ ] Grafana dashboard shows all experiments
- [ ] Can compare prompts visually
- [ ] Trend analysis over time

**Time estimate:** 1-2 days

---

## Complete Workflows

### Workflow 1: Establish Baseline

```bash
# One-time M2 setup (30 min)
cd ~/workspace/llama.cpp
LLAMA_METAL=1 make -j
./llama-server -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf -ngl 99 -np 4 --port 8080

# Measure current performance (1 min)
cd ~/workspace/k8s-slm-log-agent
just experiment baseline-v1

# View results
cat evals/experiments/runs/latest/summary.md

# Update Grafana
just leaderboard
```

**Time: 1 minute** (after setup)

---

### Workflow 2: Optimize Prompts

```bash
# Run optimization (5 min)
just optimize-prompts

# Validate winner (1 min)
just experiment optimized-v2

# Compare
just compare baseline-v1 optimized-v2

# Deploy if improved
git add workloads/log-analyzer/prompt_templates/k8s_log_analysis_v2.yaml
git commit -m "feat: optimize prompt v2 (+5.8% accuracy)"
git push origin main
```

**Time: ~7 minutes**

---

## Time Estimates

### Hardware Performance

| Hardware | Inference Speed | Concurrency | Throughput |
|----------|----------------|-------------|------------|
| **Cluster (CPU-only)** | 22s per request | 1 | 2.7 samples/min |
| **M2 Sequential** | 2s per request | 1 | 30 samples/min |
| **M2 Parallel (4x)** | 2s per request | 4 | 115 samples/min ⚡ |

### Operation Times

| Operation | Dataset Size | Time (M2, 4x) | Notes |
|-----------|--------------|---------------|-------|
| **Single Experiment** | 115 samples | **~1 minute** | Full evaluation |
| **Validation Run** | 55 samples | **~30 seconds** | Optimization subset |
| **Prompt Optimization** | 550 calls | **~5 minutes** | 10 candidates |
| **Compare Experiments** | N/A | **<5 seconds** | Post-processing |
| **Update Dashboards** | N/A | **<5 seconds** | JSON generation |

### Cost Analysis (vs Cluster)

| Approach | Full Experiment | Optimization |
|----------|----------------|--------------|
| **Cluster Only** | 42 min ❌ | 3.4 hours ❌ |
| **M2 Sequential** | 4 min | 20 min |
| **M2 Parallel (4x)** | **1 min** ✅ | **5 min** ✅ |

**Key Insight:** M2 parallel execution is **42x faster** than cluster.

---

## Implementation Roadmap

### Phase 1: Golden Dataset ✅ COMPLETE

**Status:** COMPLETE
**Deliverable:** 115 labeled samples ready

---

### Phase 2: Shared Analyzer Module (1-2 days)

**Goal:** Extract core logic into reusable module

**Tasks:**
- [ ] Create `core/analyzer.py` with `LogAnalyzer` class
- [ ] Create `evaluation/metrics.py` with unified metrics
- [ ] Refactor `main.py` to use shared analyzer
- [ ] Write unit tests
- [ ] Verify production API unchanged

---

### Phase 3: Evaluation Harness (2-3 days)

**Goal:** Run reproducible experiments

**Tasks:**
- [ ] Implement `run_experiment.py`
- [ ] Add experiment configs
- [ ] Add justfile recipes
- [ ] Test on M2 MacBook (~1 min runtime)
- [ ] Generate summary reports

---

### Phase 4: Prompt Optimization (2-3 days)

**Goal:** Systematic prompt search

**Tasks:**
- [ ] Define search space (108 combinations)
- [ ] Implement candidate generator
- [ ] Implement `optimize.py`
- [ ] Split dataset (60/55)
- [ ] Test optimization (~5 min runtime)
- [ ] Export winner as YAML

---

### Phase 5: Grafana Visualization (1-2 days)

**Goal:** Track quality over time

**Tasks:**
- [ ] Implement `update_leaderboard.py`
- [ ] Generate JSON for Grafana
- [ ] Create Grafana dashboard
- [ ] Add API endpoints
- [ ] Test full workflow

---

### Total Timeline

**Sequential:** 7-11 days
**MVP (Phases 2-3 only):** 3-5 days

---

## Quick Start

```bash
# 1. One-time M2 setup (30 min)
cd ~/workspace
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
LLAMA_METAL=1 make -j
mkdir models && cd models
wget https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf

# 2. Start local LLM server
cd ~/workspace/llama.cpp
./llama-server -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf -ngl 99 -np 4 --port 8080

# 3. Establish baseline (1 min)
cd ~/workspace/k8s-slm-log-agent
just experiment baseline-v1

# 4. Optimize prompts (5 min)
just optimize-prompts

# 5. Validate winner (1 min)
just experiment optimized-v2

# 6. Compare
just compare baseline-v1 optimized-v2

# 7. Update Grafana
just leaderboard

# 8. Deploy
git commit -m "feat: optimize prompt (+X% accuracy)"
git push origin main
```

**Total time: ~7 minutes** (after one-time setup)
