# Prompt Optimization: Hybrid Approach for CPU-Based Homelab

## Executive Summary

This document outlines a **hybrid approach** to prompt optimization that:
- Maintains our Unix philosophy (simple pipelines, Git-reviewable artifacts)
- Leverages concepts from DSpy without adopting the full framework
- **Runs optimization locally on M2 MacBook** (35 min vs 6 hours in cluster)
- Uses Metal-accelerated GPU inference for fast iteration
- Deploys optimized prompts to CPU-only cluster via GitOps
- Integrates with existing OTel observability stack

**Goal:** Systematically improve prompt quality using our 500+ labeled log examples, without sacrificing simplicity or adding heavy dependencies.

**Key Innovation:** Separate optimization environment (local M2 with GPU) from production environment (K8s cluster with CPU). This gives us 7-22x faster optimization while keeping production lean.

---

## Part 1: What is Prompt Optimization?

### The Problem

Traditional prompt engineering is **manual iteration**:

```
1. Write a prompt
2. Test on a few examples
3. Notice failures
4. Tweak wording
5. Repeat
```

This approach has fundamental issues:
- **Not systematic**: Changes based on anecdotes, not metrics
- **Not reproducible**: No record of what was tried
- **Not scalable**: Doesn't leverage large evaluation datasets
- **Not measurable**: "This seems better" is not a metric

### The Solution: Data-Driven Optimization

**Prompt optimization** treats prompts as **programs with tunable parameters**:

```python
# Instead of manually writing this:
prompt = "Analyze these Kubernetes logs and tell me if action is needed..."

# We define what we want to optimize:
prompt = optimize(
    task_description="Analyze K8s logs for issues",
    training_examples=golden_dataset,  # 500+ labeled examples
    metric=evaluate_accuracy,           # Automated quality measurement
    search_space=[
        "instruction_phrasing",         # Different ways to phrase the task
        "few_shot_examples",            # Which examples to include
        "output_structure",             # Format constraints
        "reasoning_strategy",           # Chain-of-thought, direct answer, etc.
    ]
)
```

The optimizer **searches** this space systematically, measures quality on held-out validation data, and returns the best configuration.

### Key Insight

Prompt optimization is **hyperparameter tuning for natural language**:

| Traditional ML          | Prompt Optimization        |
|------------------------|---------------------------|
| Learning rate          | Instruction phrasing      |
| Batch size             | Number of examples        |
| Architecture           | Reasoning strategy        |
| Grid search            | Discrete prompt search    |
| Validation accuracy    | Eval metric (F1, accuracy)|

---

## Part 2: How DSpy Enables Optimization

### DSpy's Core Components

#### 1. Signatures: Task Specification

DSpy separates **what** you want from **how** to prompt for it:

```python
class LogAnalysis(dspy.Signature):
    """Analyze Kubernetes logs and determine if action is required."""

    logs: str = dspy.InputField(desc="K8s log entries with timestamps")
    namespace: str = dspy.InputField(desc="K8s namespace")

    root_cause: str = dspy.OutputField(desc="Root cause or 'none'")
    severity: str = dspy.OutputField(desc="Severity: info|warning|error|critical")
    action_required: str = dspy.OutputField(desc="yes|no")
```

DSpy **auto-generates** the actual prompt from this specification. The optimizer can then **rewrite** the prompt while maintaining the signature contract.

#### 2. Modules: Reasoning Strategies

Different ways to invoke the LLM:

```python
# Direct prediction
basic = dspy.Predict(LogAnalysis)

# Chain-of-thought reasoning
cot = dspy.ChainOfThought(LogAnalysis)  # Adds "Let's think step by step..."

# Multi-attempt with self-consistency
ensemble = dspy.MultiChainComparison(LogAnalysis)
```

These are **interchangeable** — optimizer picks the best one.

#### 3. Optimizers: Automated Search

**MIPROv2** (DSpy's main optimizer):

```python
optimizer = dspy.MIPROv2(
    metric=evaluate_diagnosis,
    num_candidates=10,
    init_temperature=1.0
)

optimized_program = optimizer.compile(
    student=dspy.ChainOfThought(LogAnalysis),
    trainset=training_examples[:400],
    valset=training_examples[400:]
)
```

**What it does:**
1. **Bootstrapping**: Run your program on training examples, collect successful traces
2. **Instruction proposal**: Generate variations of instructions using grounded examples
3. **Discrete search**: Try different combinations (instructions × few-shot examples × strategies)
4. **Evaluation**: Measure each candidate on validation set
5. **Selection**: Return best-performing configuration

**Cost:** For 10 candidates × 400 training examples = **4000+ LLM calls**

### DSpy's Value Proposition

- **Systematic**: All candidates evaluated identically
- **Reproducible**: Optimization runs are logged and cacheable
- **Scalable**: Automatically leverages your full golden dataset
- **Measurable**: Returns confidence scores and validation metrics

---

## Part 3: Why Full DSpy Doesn't Fit Our Homelab

### Constraint Analysis

| Requirement | DSpy Assumption | Our Reality | Impact |
|------------|----------------|-------------|---------|
| **Inference speed** | <1s per request (GPUs) | 22s per request (CPU) | 4000 calls = 24+ hours |
| **Dependencies** | 40+ packages, ~200MB | 11 packages, minimal | Conflicts with Unix philosophy |
| **Observability** | lm.history (in-memory) | OTel → Tempo (persistent) | Need custom bridge |
| **Artifact format** | JSON blobs (opaque) | YAML files (Git-reviewable) | Breaks GitOps workflow |
| **Optimization frequency** | Frequent recompilation | Infrequent (too slow) | Can't iterate quickly |

### The Real Problem

DSpy optimizes for **researcher productivity** (Stanford NLP's use case):
- Rapid experimentation with cloud GPUs
- Jupyter notebook workflows
- Academic paper deadlines

We optimize for **production homelab simplicity**:
- Transparent, inspectable code
- Git-based versioning
- Minimal runtime dependencies
- Works on consumer hardware

---

## Part 4: Lightweight Optimizer Design

### Philosophy

Build the **minimal viable optimizer** that:
1. ✅ Runs on CPU-only hardware (optimize budget, not speed)
2. ✅ Produces Git-reviewable YAML artifacts
3. ✅ Integrates with existing OTel observability
4. ✅ Requires <200 lines of code
5. ✅ No new runtime dependencies (optimization is dev-time only)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Optimization Pipeline (dev-time, runs locally)              │
│                                                             │
│  1. Load golden dataset (500+ examples)                     │
│  2. Define search space (prompt variations)                 │
│  3. Evaluate each candidate on validation set               │
│  4. Rank by metric (F1, accuracy, etc.)                     │
│  5. Export best prompt as YAML                              │
│                                                             │
│  Output: prompt_templates/k8s_log_analysis_v2.yaml          │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Production Pipeline (runtime, deployed in K8s)              │
│                                                             │
│  FastAPI → Loki → normalize → render_prompt() → llama.cpp  │
│                                                             │
│  (No changes to runtime code)                               │
└─────────────────────────────────────────────────────────────┘
```

**Key insight:** Optimization is **compile-time**, not **run-time**. We run the optimizer once on a laptop, generate an optimized YAML file, commit it to Git, and deploy via Flux.

---

## Part 5: Implementation Plan

### Phase 1: Evaluation Framework (1-2 days)

**Goal:** Establish ground truth metrics

#### 1.1 Data Format

```python
# workloads/log-analyzer/evaluation/golden_dataset.jsonl
{"logs": "...", "namespace": "llm", "expected": {"root_cause": "OOM", "severity": "critical", ...}}
{"logs": "...", "namespace": "logging", "expected": {"root_cause": "none", "severity": "info", ...}}
```

#### 1.2 Metrics Module

```python
# workloads/log-analyzer/evaluation/metrics.py

from typing import Dict, Any

def exact_match(expected: str, predicted: str) -> float:
    """Binary: 1.0 if exact match, 0.0 otherwise."""
    return 1.0 if expected.strip().lower() == predicted.strip().lower() else 0.0

def semantic_similarity(expected: str, predicted: str) -> float:
    """
    Simple token-based similarity (upgrade to embeddings later if needed).
    Uses Jaccard similarity: intersection / union of word tokens.
    """
    exp_tokens = set(expected.lower().split())
    pred_tokens = set(predicted.lower().split())

    intersection = len(exp_tokens & pred_tokens)
    union = len(exp_tokens | pred_tokens)

    return intersection / union if union > 0 else 0.0

def evaluate_diagnosis(expected: Dict[str, Any], predicted: Dict[str, Any]) -> Dict[str, float]:
    """
    Composite metric for log analysis quality.

    Returns dict with per-field scores and overall score.
    """
    scores = {
        "severity": exact_match(expected["severity"], predicted["severity"]),
        "action_required": exact_match(expected["action_required"], predicted["action_required"]),
        "root_cause": semantic_similarity(expected["root_cause"], predicted["root_cause"]),
    }

    # Weighted average: severity and action are critical, root cause is best-effort
    scores["overall"] = (
        scores["severity"] * 0.4 +
        scores["action_required"] * 0.4 +
        scores["root_cause"] * 0.2
    )

    return scores
```

#### 1.3 Baseline Evaluation

```bash
# Measure current prompt performance
just eval-baseline

# Expected output:
# Baseline Performance (k8s_log_analysis_v1):
#   Severity accuracy: 0.87
#   Action accuracy: 0.92
#   Root cause similarity: 0.68
#   Overall score: 0.83
```

**Deliverable:** Know our starting point with statistical confidence.

---

### Phase 2: Prompt Variation Generator (2-3 days)

**Goal:** Create controlled variations of prompts to search

#### 2.1 Search Space Definition

```python
# workloads/log-analyzer/evaluation/search_space.py

INSTRUCTION_VARIANTS = {
    "tone": [
        "You are a senior Kubernetes Site Reliability Engineer.",
        "You are an expert at diagnosing Kubernetes operational issues.",
        "You are a systems engineer analyzing production logs.",
    ],
    "constraints": [
        "Follow these rules strictly:\n- Do NOT invent facts not present in the logs",
        "Important guidelines:\n- Base conclusions only on log evidence",
        "Critical requirements:\n- Only use information explicitly in the logs",
    ],
    "output_structure": [
        "Root cause:\nSeverity:\nAction required:\nRecommended steps:",
        "1. Root cause:\n2. Severity level:\n3. Action needed:\n4. Next steps:",
        "**Root Cause:** ...\n**Severity:** ...\n**Action Required:** ...\n**Steps:** ...",
    ],
}

FEW_SHOT_STRATEGIES = [
    "none",           # Zero-shot
    "positive_only",  # Show 3 examples of issues found
    "mixed",          # Show 2 issues + 1 benign case
    "hard_negatives", # Show cases where benign logs look suspicious
]

REASONING_STRATEGIES = [
    "direct",         # "Analyze these logs..."
    "cot",            # "Let's analyze these logs step by step..."
    "structured_cot", # "First, identify error patterns. Second, assess severity. Third..."
]
```

#### 2.2 Template Generator

```python
# workloads/log-analyzer/evaluation/generator.py

import itertools
import yaml
from pathlib import Path
from typing import Iterator, Dict, Any

def generate_prompt_candidates() -> Iterator[Dict[str, Any]]:
    """
    Generate all combinations in search space.

    Yields prompt configurations as dicts (ready to serialize to YAML).
    """
    for (tone, constraints, output, few_shot, reasoning) in itertools.product(
        INSTRUCTION_VARIANTS["tone"],
        INSTRUCTION_VARIANTS["constraints"],
        INSTRUCTION_VARIANTS["output_structure"],
        FEW_SHOT_STRATEGIES,
        REASONING_STRATEGIES,
    ):
        system_prompt = f"{tone}\n\n{constraints}\n\nOutput format:\n{output}"

        if reasoning == "cot":
            system_prompt += "\n\nAnalyze the logs step-by-step before providing your conclusion."
        elif reasoning == "structured_cot":
            system_prompt += "\n\nFollow this analysis process:\n1. Identify error patterns\n2. Assess severity\n3. Determine if action is needed\n4. Formulate recommendations"

        # Build user prompt with few-shot examples if needed
        user_prompt = build_user_prompt(few_shot_strategy=few_shot)

        yield {
            "id": f"k8s_log_analysis_candidate_{hash(system_prompt) % 10000}",
            "description": f"Candidate: {reasoning} reasoning, {few_shot} examples",
            "system": system_prompt,
            "user": user_prompt,
            "model_defaults": {"temperature": 0.3, "max_tokens": 200},
            "inputs": {
                "required": ["logs"],
                "optional": {"namespace": "unknown", "time_range": "unknown"}
            },
            "_meta": {
                "tone": tone[:30],
                "few_shot": few_shot,
                "reasoning": reasoning,
            }
        }

def build_user_prompt(few_shot_strategy: str) -> str:
    """Construct user prompt with optional few-shot examples."""
    base = "Context:\n- Namespace: {{ namespace }}\n- Time window: {{ time_range }}\n\nLogs:\n---\n{{ logs }}\n---"

    if few_shot_strategy == "none":
        return base

    # Load curated few-shot examples from golden dataset
    examples = load_few_shot_examples(strategy=few_shot_strategy)
    examples_text = "\n\n".join([
        f"Example {i+1}:\nLogs: {ex['logs']}\nAnalysis: {ex['analysis']}"
        for i, ex in enumerate(examples)
    ])

    return f"Here are some examples:\n\n{examples_text}\n\nNow analyze these logs:\n\n{base}"
```

**Search space size:**
- 3 tones × 3 constraints × 3 output formats × 4 few-shot × 3 reasoning = **324 candidates**

At 22s per eval × 50 validation examples = **18 minutes per candidate** → **4 days total**

**Optimization:** Parallelize across multiple nodes or use a smaller validation set (10 examples = ~4 hours total).

---

### Phase 3: Optimizer Implementation (2-3 days)

**Goal:** Run evaluation, rank candidates, export winner

#### 3.1 Main Optimizer Script

```python
# workloads/log-analyzer/evaluation/optimize.py

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any
import yaml

from log_analyzer.config import settings
from log_analyzer.llm import call_llm
from log_analyzer.registry import render_prompt
from evaluation.metrics import evaluate_diagnosis
from evaluation.generator import generate_prompt_candidates

async def evaluate_candidate(
    prompt_config: Dict[str, Any],
    validation_set: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluate a single prompt candidate on validation set.

    Returns: {
        "prompt_id": "...",
        "scores": {"overall": 0.85, "severity": 0.90, ...},
        "config": {...}
    }
    """
    # Temporarily load this candidate as a PromptTemplate
    from log_analyzer.models.registry import PromptTemplate
    from log_analyzer.registry import sha256_json

    template = PromptTemplate(
        id=prompt_config["id"],
        description=prompt_config["description"],
        template_hash=sha256_json({"system": prompt_config["system"], "user": prompt_config["user"]}),
        system_template=prompt_config["system"],
        user_template=prompt_config["user"],
        required_inputs=prompt_config["inputs"]["required"],
        optional_inputs=prompt_config["inputs"]["optional"],
        llm_config=prompt_config["model_defaults"],
    )

    total_scores = {"overall": 0.0, "severity": 0.0, "action_required": 0.0, "root_cause": 0.0}

    # Evaluate on each validation example
    for example in validation_set:
        # Render prompt with example inputs
        rendered = render_prompt(
            registry={template.id: template},
            prompt_id=template.id,
            variables={
                "logs": example["logs"],
                "namespace": example.get("namespace", "unknown"),
                "time_range": example.get("time_range", "unknown"),
            }
        )

        # Get LLM prediction
        prediction = await call_llm(rendered)

        # Parse prediction (simple heuristic for now)
        parsed_prediction = parse_llm_output(prediction)

        # Score this prediction
        scores = evaluate_diagnosis(example["expected"], parsed_prediction)

        # Accumulate scores
        for key in total_scores:
            total_scores[key] += scores[key]

    # Average scores
    n = len(validation_set)
    avg_scores = {k: v / n for k, v in total_scores.items()}

    return {
        "prompt_id": prompt_config["id"],
        "scores": avg_scores,
        "config": prompt_config,
    }

def parse_llm_output(text: str) -> Dict[str, str]:
    """
    Extract structured fields from LLM's plain-text response.

    TODO: Make this more robust (regex or simple parser).
    """
    lines = text.strip().split("\n")
    result = {
        "root_cause": "unknown",
        "severity": "unknown",
        "action_required": "unknown",
    }

    for line in lines:
        lower = line.lower()
        if "root cause:" in lower:
            result["root_cause"] = line.split(":", 1)[1].strip()
        elif "severity:" in lower:
            result["severity"] = line.split(":", 1)[1].strip()
        elif "action required:" in lower:
            result["action_required"] = line.split(":", 1)[1].strip()

    return result

async def run_optimization(
    validation_set: List[Dict[str, Any]],
    max_candidates: int = 10,
    output_dir: Path = Path("./optimization_results"),
):
    """
    Main optimization loop.

    1. Generate candidates
    2. Evaluate each on validation set
    3. Rank by overall score
    4. Export top candidate as YAML
    """
    output_dir.mkdir(exist_ok=True)

    print("Generating prompt candidates...")
    candidates = list(generate_prompt_candidates())

    # Optional: Sample a subset if search space is too large
    if len(candidates) > max_candidates:
        import random
        candidates = random.sample(candidates, max_candidates)

    print(f"Evaluating {len(candidates)} candidates on {len(validation_set)} examples...")
    print(f"Estimated time: {len(candidates) * len(validation_set) * 22 / 3600:.1f} hours")

    results = []
    for i, candidate in enumerate(candidates):
        print(f"[{i+1}/{len(candidates)}] Evaluating {candidate['id']}...")
        result = await evaluate_candidate(candidate, validation_set)
        results.append(result)

        # Save intermediate results (in case of crash)
        with open(output_dir / "intermediate_results.jsonl", "a") as f:
            f.write(json.dumps(result) + "\n")

    # Rank candidates by overall score
    results.sort(key=lambda x: x["scores"]["overall"], reverse=True)

    # Export full results
    with open(output_dir / "all_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Export best candidate as YAML
    best = results[0]
    print(f"\nBest candidate: {best['prompt_id']}")
    print(f"Overall score: {best['scores']['overall']:.3f}")
    print(f"Scores: {best['scores']}")

    # Generate next version number
    next_version = "v2"  # TODO: Auto-increment based on existing files
    best_config = best["config"]
    best_config["id"] = f"k8s_log_analysis_{next_version}"

    output_path = Path("./prompt_templates") / f"k8s_log_analysis_{next_version}.yaml"
    with open(output_path, "w") as f:
        yaml.dump(best_config, f, default_flow_style=False, sort_keys=False)

    print(f"\nOptimized prompt saved to: {output_path}")
    print("Review the file, then commit to Git and deploy via Flux.")

    return results

if __name__ == "__main__":
    # Load validation set
    validation_examples = []
    with open("evaluation/golden_dataset.jsonl") as f:
        all_examples = [json.loads(line) for line in f]

    # Use 20% of data for validation (rest for few-shot examples if needed)
    validation_examples = all_examples[400:]  # Last 100 examples

    # Run optimization
    asyncio.run(run_optimization(validation_examples, max_candidates=10))
```

#### 3.2 Usage

```bash
# From workloads/log-analyzer/
cd /Users/treyshanks/workspace/k8s-slm-log-agent/workloads/log-analyzer

# Run optimizer (will take ~4 hours for 10 candidates × 100 validation examples)
uv run python -m evaluation.optimize

# Output:
# Generating prompt candidates...
# Evaluating 10 candidates on 100 examples...
# Estimated time: 6.1 hours
# [1/10] Evaluating k8s_log_analysis_candidate_1234...
# ...
# Best candidate: k8s_log_analysis_candidate_5678
# Overall score: 0.891
# Scores: {'overall': 0.891, 'severity': 0.94, 'action_required': 0.96, 'root_cause': 0.75}
#
# Optimized prompt saved to: prompt_templates/k8s_log_analysis_v2.yaml
```

#### 3.3 Review and Deploy

```bash
# Review the optimized prompt
cat prompt_templates/k8s_log_analysis_v2.yaml

# Compare with baseline
git diff prompt_templates/k8s_log_analysis_v1.yaml prompt_templates/k8s_log_analysis_v2.yaml

# If satisfied, commit and deploy
git add prompt_templates/k8s_log_analysis_v2.yaml
git commit -m "feat: add optimized prompt v2 (overall score: 0.891 → +6.1% vs baseline)"

# Update config to use v2
# config.py: ANALYZE_PROMPT_ID = "k8s_log_analysis_v2"

# Deploy via Flux GitOps
git push origin main
# Flux will automatically reconcile and restart pods with new prompt
```

---

### Phase 4: Integration with OTel (1 day)

**Goal:** Track optimization runs in Tempo for debugging

```python
# Add tracing to optimizer
from log_analyzer.observability import get_tracer
tracer = get_tracer(__name__)

async def evaluate_candidate(prompt_config, validation_set):
    with tracer.start_as_current_span("evaluate_candidate") as span:
        span.set_attribute("prompt.id", prompt_config["id"])
        span.set_attribute("prompt.reasoning_strategy", prompt_config["_meta"]["reasoning"])
        span.set_attribute("validation_set_size", len(validation_set))

        # ... existing evaluation logic ...

        span.set_attribute("eval.overall_score", avg_scores["overall"])
        span.set_attribute("eval.severity_score", avg_scores["severity"])
```

**Benefit:** View optimization runs in Grafana, debug failures, compare candidates visually.

---

## Part 6: Local M2 MacBook Optimization Workflow

### The Problem with Cluster-Based Optimization

Running optimization **in the cluster** has a major bottleneck:
- Cluster inference: **22s per request** (CPU-only llama.cpp)
- 10 candidates × 100 validation examples = **1000 LLM calls**
- Total time: **1000 × 22s = 6.1 hours**

This is slow, consumes cluster resources, and blocks other workloads.

### The M2 MacBook Advantage

Your M2 MacBook has significant advantages for optimization:

| Hardware | Inference Speed | Speedup |
|----------|----------------|---------|
| **Cluster (CPU)** | 22s per request | 1x baseline |
| **M2 (Metal GPU)** | ~1-3s per request | **7-22x faster** |
| **M2 (Neural Engine)** | ~0.5-1s per request | **22-44x faster** |

**Impact on optimization time:**
- Cluster: 6.1 hours
- M2 MacBook: **17-30 minutes** 🚀

### Architecture: Local Optimization, Remote Deployment

```
┌──────────────────────────────────────────────────────────┐
│ Developer's M2 MacBook (optimization time)               │
│                                                          │
│  1. Run llama.cpp locally with Metal acceleration       │
│  2. Execute optimizer against local LLM endpoint        │
│  3. Generate optimized_v2.yaml in 20 minutes            │
│  4. Review and commit to Git                            │
│                                                          │
│  Output: prompt_templates/k8s_log_analysis_v2.yaml      │
└─────────────────────┬────────────────────────────────────┘
                      │ git push
                      ▼
┌──────────────────────────────────────────────────────────┐
│ GitHub Repository (version control)                      │
│  ✓ New prompt committed with eval scores in message     │
│  ✓ Reviewable diff: v1 → v2 changes                     │
└─────────────────────┬────────────────────────────────────┘
                      │ Flux CD sync
                      ▼
┌──────────────────────────────────────────────────────────┐
│ K8s Cluster (production runtime)                         │
│                                                          │
│  ✓ Flux applies new ConfigMap with v2 prompt           │
│  ✓ Pods restart with optimized prompt                   │
│  ✓ No optimization overhead in production               │
└──────────────────────────────────────────────────────────┘
```

**Key insight:** Optimization is a **local dev task**, like running tests or building Docker images. It doesn't belong in the cluster.

### Setup: llama.cpp on M2 MacBook

#### Step 1: Install llama.cpp with Metal Support

```bash
# Clone llama.cpp
cd ~/workspace
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Build with Metal (M2 GPU acceleration)
make clean
LLAMA_METAL=1 make -j

# Verify Metal support
./llama-cli --version
# Should show: LLAMA_METAL=1
```

#### Step 2: Download Model

```bash
# Create models directory
mkdir -p ~/workspace/llama.cpp/models

# Download same model as cluster (Llama 3.2 3B)
cd ~/workspace/llama.cpp/models

# Option A: Use huggingface-cli
huggingface-cli download \
  bartowski/Llama-3.2-3B-Instruct-GGUF \
  Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  --local-dir .

# Option B: Direct download
wget https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf
```

#### Step 3: Start Local Server

```bash
# Terminal 1: Start llama.cpp server with Metal
cd ~/workspace/llama.cpp

./llama-server \
  -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf \
  -c 4096 \
  -ngl 99 \
  --port 8080 \
  --host 127.0.0.1

# -ngl 99: offload all layers to GPU (Metal)
# -c 4096: context window size
# --port 8080: OpenAI-compatible API endpoint

# Expected output:
# llama_new_context_with_model: Metal backend enabled
# llama_model_load: using Metal backend
# Server listening on http://127.0.0.1:8080
```

#### Step 4: Verify Metal Acceleration

```bash
# Terminal 2: Test inference speed
time curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.2-3b",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 50
  }'

# Expected: 1-3 seconds (vs 22s on cluster)
```

### Integration: Point Optimizer at Local Endpoint

Update the optimizer to use local LLM:

```python
# workloads/log-analyzer/evaluation/optimize.py

import os

# Override LLM endpoint for local optimization
LOCAL_LLM_URL = "http://localhost:8080"

async def run_optimization(
    validation_set: List[Dict[str, Any]],
    max_candidates: int = 10,
    use_local_llm: bool = True,  # NEW FLAG
):
    # Temporarily override settings for optimization
    if use_local_llm:
        original_llm_url = settings.llm_url
        settings.llm_url = LOCAL_LLM_URL
        print(f"Using local LLM: {LOCAL_LLM_URL}")
        print("⚡ Metal-accelerated inference enabled")

    try:
        # ... existing optimization logic ...

        # Update time estimate with faster inference
        inference_time = 2.0 if use_local_llm else 22.0  # seconds
        estimated_hours = len(candidates) * len(validation_set) * inference_time / 3600
        print(f"Estimated time: {estimated_hours:.1f} hours")

        results = []
        for i, candidate in enumerate(candidates):
            result = await evaluate_candidate(candidate, validation_set)
            results.append(result)

        # ... rest of optimization ...

    finally:
        # Restore original settings
        if use_local_llm:
            settings.llm_url = original_llm_url
```

### Justfile Integration

Add optimization as a release step:

```makefile
# justfile (add to root)

# Run prompt optimization locally with M2 acceleration
optimize-prompts:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "🚀 Starting prompt optimization on M2 MacBook..."
    echo ""
    echo "Prerequisites:"
    echo "  1. llama.cpp server running on localhost:8080"
    echo "  2. Golden dataset ready: workloads/log-analyzer/evaluation/golden_dataset.jsonl"
    echo ""
    read -p "Press Enter to continue (Ctrl+C to cancel)..."

    cd workloads/log-analyzer
    uv run python -m evaluation.optimize --use-local-llm

    echo ""
    echo "✅ Optimization complete!"
    echo "📄 Review: prompt_templates/k8s_log_analysis_v2.yaml"
    echo "📊 Results: optimization_results/all_results.json"
    echo ""
    echo "Next steps:"
    echo "  1. Review the optimized prompt"
    echo "  2. Update config.py to use v2"
    echo "  3. Commit and push to deploy via Flux"

# Release workflow with optimization
release-with-optimization:
    just optimize-prompts
    just test-prompts
    just release
```

### Complete Workflow

```bash
# Step 1: Start local LLM server (Terminal 1)
cd ~/workspace/llama.cpp
./llama-server -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf -ngl 99 --port 8080

# Step 2: Run optimization (Terminal 2)
cd ~/workspace/k8s-slm-log-agent
just optimize-prompts

# Output:
# 🚀 Starting prompt optimization on M2 MacBook...
# Using local LLM: http://localhost:8080
# ⚡ Metal-accelerated inference enabled
# Evaluating 10 candidates on 100 examples...
# Estimated time: 0.6 hours (35 minutes)
# [1/10] Evaluating candidate_1234... ✓ (2.1s avg)
# [2/10] Evaluating candidate_5678... ✓ (1.8s avg)
# ...
# Best candidate: k8s_log_analysis_candidate_5678
# Overall score: 0.891 (+6.1% vs baseline)
#
# ✅ Optimization complete! (34 minutes)

# Step 3: Review optimized prompt
cat workloads/log-analyzer/prompt_templates/k8s_log_analysis_v2.yaml
git diff prompt_templates/k8s_log_analysis_v1.yaml prompt_templates/k8s_log_analysis_v2.yaml

# Step 4: Update config to use v2
# Edit workloads/log-analyzer/src/log_analyzer/config.py
# Change: ANALYZE_PROMPT_ID = "k8s_log_analysis_v2"

# Step 5: Commit and deploy
git add .
git commit -m "feat: optimize prompt to v2 (score: 0.833→0.891, +6.1%)"
git push origin main

# Flux automatically deploys to cluster in ~30 seconds
```

### Cost-Benefit Analysis

| Approach | Time | Cluster Impact | Quality |
|----------|------|----------------|---------|
| **Manual tuning** | Days of iteration | Low (testing only) | Subjective |
| **Cluster optimization** | 6.1 hours | High (blocks resources) | Systematic |
| **M2 local optimization** | **35 minutes** | **None** | **Systematic** |

**Winner:** M2 local optimization gives us systematic quality with minimal time investment and zero cluster impact.

### Advanced: Use Different Model for Optimization

You can even use a **better/faster model** for optimization than what runs in production:

```bash
# Download a larger model for optimization (more accurate)
cd ~/workspace/llama.cpp/models
wget https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf

# Start server with larger model
./llama-server -m models/Qwen2.5-7B-Instruct-Q4_K_M.gguf -ngl 99 --port 8080

# Run optimization with more capable model
just optimize-prompts

# Result: Better optimization quality, optimized prompt still works with 3B model in cluster
```

This is similar to using GPT-4 to optimize prompts for GPT-3.5 deployment.

### Why This Is Better Than DSpy

DSpy assumes you're optimizing **in the same environment** as deployment. But separation of concerns is better:

- **Optimization environment**: M2 MacBook, fast inference, full compute
- **Production environment**: K8s cluster, CPU inference, minimal resources

This approach:
- ✅ Leverages local hardware advantages
- ✅ Doesn't consume cluster resources
- ✅ Fits naturally into dev workflow
- ✅ Works with existing Git/Flux GitOps
- ✅ Can use better models for optimization

---

## Part 7: Advanced Extensions (Future)

### 6.1 Multi-Objective Optimization

Currently we optimize for **accuracy**. We might also care about:

```python
def multi_objective_score(expected, predicted, llm_metadata):
    accuracy = evaluate_diagnosis(expected, predicted)["overall"]
    latency_penalty = min(llm_metadata["tokens_total"] / 500, 1.0)  # Penalize long outputs

    # Pareto optimization: 80% accuracy, 20% efficiency
    return 0.8 * accuracy + 0.2 * (1 - latency_penalty)
```

### 6.2 Active Learning

Instead of evaluating all 324 candidates:

```python
# 1. Evaluate a random sample (10 candidates)
# 2. Use a cheap surrogate model to predict which candidates are promising
# 3. Evaluate only top-K predictions
# 4. Repeat until convergence

# Reduces 324 evaluations → ~50 evaluations (6x speedup)
```

### 6.3 Continuous Optimization

Set up a cron job:

```yaml
# kubernetes CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: prompt-optimizer
  namespace: log-analyzer
spec:
  schedule: "0 2 * * 0"  # Weekly, Sunday at 2am
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: optimizer
            image: log-analyzer:latest
            command: ["python", "-m", "evaluation.optimize"]
            env:
            - name: LOG_ANALYZER_LLM_URL
              value: "http://llama-cpp.llm.svc.cluster.local:8080"
```

Every week, the optimizer runs on the latest golden dataset and proposes a new prompt version if significant improvement is found.

---

## Part 7: Success Metrics

### How We'll Know This Works

**Baseline (current state):**
- Manual prompt iterations: ~1 per week
- Evaluation: informal ("seems better")
- Quality measurement: none

**After Phase 1 (Evaluation Framework):**
- ✅ Quantitative baseline: "v1 achieves 0.83 overall score"
- ✅ Reproducible metrics: same score every run
- ✅ Statistical confidence: tested on 100+ examples

**After Phase 2-3 (Lightweight Optimizer):**
- ✅ Systematic search: 10-324 candidates evaluated
- ✅ Git-reviewable: optimized prompts committed as YAML
- ✅ Measurable improvement: "v2 achieves 0.89 overall score (+7% vs baseline)"

**Long-term benefits:**
- 📈 Continuous improvement: re-run optimizer as dataset grows
- 📊 A/B testing: compare model versions objectively
- 📖 Explainability: "v2 improved because it added structured chain-of-thought"

---

## Part 8: Comparison with Full DSpy

| Aspect | Full DSpy | Our Lightweight Optimizer |
|--------|-----------|--------------------------|
| **Lines of code** | Framework (10k+ LOC) | ~200 LOC |
| **Dependencies** | 40+ packages | 0 new (uses existing) |
| **Optimization time** | 4000 calls × 22s = 24h | 1000 calls × 22s = 6h |
| **Output format** | JSON blob (opaque) | YAML file (Git-reviewable) |
| **Runtime overhead** | In-process optimization | No runtime overhead |
| **Observability** | lm.history (new system) | OTel spans (existing) |
| **Learning curve** | Read DSpy docs, learn abstractions | Read 200 lines of Python |
| **Flexibility** | Constrained by framework | Full control over search |
| **State of art optimizers** | ❌ (MIPROv2, BootstrapFewShot) | ✅ (grid search, random) |

**Trade:** We give up DSpy's sophisticated optimizers in exchange for simplicity, control, and homelab-appropriate constraints.

---

## Part 9: Implementation Timeline

| Phase | Effort | Deliverable |
|-------|--------|-------------|
| **Phase 0: M2 Setup** | 30 minutes | llama.cpp running locally with Metal |
| **Phase 1: Eval Framework** | 1-2 days | `evaluation/metrics.py`, baseline scores |
| **Phase 2: Candidate Generator** | 2-3 days | `evaluation/generator.py`, 324 candidates |
| **Phase 3: Optimizer** | 2-3 days | `evaluation/optimize.py`, optimized v2 prompt |
| **Phase 4: OTel Integration** | 1 day | Tempo traces for optimization runs (optional) |
| **Total** | **6-9 days** | Systematic prompt optimization pipeline |

**Optimization run time:** 35 minutes on M2 MacBook (vs 6 hours in cluster)

---

## Part 10: Next Steps

### Immediate Actions

1. **Set up M2 MacBook for optimization** (30 minutes):
   ```bash
   # Clone and build llama.cpp with Metal
   cd ~/workspace
   git clone https://github.com/ggerganov/llama.cpp
   cd llama.cpp
   LLAMA_METAL=1 make -j

   # Download model
   mkdir -p models
   cd models
   wget https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf

   # Test local server
   cd ..
   ./llama-server -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf -ngl 99 --port 8080
   ```

2. **Create golden dataset structure**:
   ```bash
   mkdir -p workloads/log-analyzer/evaluation
   touch workloads/log-analyzer/evaluation/golden_dataset.jsonl
   ```

3. **Export your 500+ labeled examples** to JSONL format

4. **Implement `metrics.py`** (Phase 1) and measure baseline

5. **Review this document** with questions:
   - Is 6-9 days of effort worth systematic optimization?
   - Should we start with a smaller search space (fewer candidates)?
   - Do we need active learning, or is grid search sufficient?

### Decision Points

**GO decision:** Proceed with lightweight optimizer if:
- ✅ We have 100+ high-quality labeled examples ready
- ✅ We can tolerate **35-minute optimization runs** on M2 MacBook
- ✅ We want systematic improvement over manual tuning

**NO-GO decision:** Stay with manual prompting if:
- ❌ Golden dataset is not ready (<50 examples)
- ❌ Current prompts already achieve >95% accuracy
- ❌ We don't have time for 6-9 day implementation

**Note:** With M2 local optimization, the barrier is **much lower**. You can iterate weekly without consuming cluster resources.

---

## Conclusion

This hybrid approach gives us:
- 🎯 **Systematic optimization** (DSpy's core value)
- 🏠 **Homelab-appropriate** (no framework lock-in, Git-based workflow)
- ⚡ **M2-accelerated** (35 minutes vs 6 hours, leverages local hardware)
- 🔍 **Transparent** (200 LOC, Git-reviewable artifacts)
- 📊 **Measurable** (quantitative metrics, not vibes)
- 🚀 **Production-ready** (optimization in dev, deployment in cluster)

We learn from DSpy's concepts without adopting its constraints.

**Philosophy alignment:** This is still a Unix tool—it reads JSONL, writes YAML, composes with existing tools, and does one thing well: find better prompts.

**Key innovation:** Separating optimization environment (M2 MacBook with GPU) from production environment (K8s cluster with CPU) gives us the best of both worlds—fast iteration during development, minimal resources in production.
