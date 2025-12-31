# Homelab LLM Observability & Evaluation Platform

A **production-inspired Kubernetes homelab platform** for serving and evaluating **LLM-powered log analysis workflows**, with first-class observability, reproducible experiments, and rigorous offline evaluation.

This project is a **research testbed** for modern **MLOps, platform engineering, and LLM observability**, built entirely with **open-source tools** and designed to mirror real production trade-offs under constrained resources.

---

## Why This Project Exists

Most LLM demos stop at *“it works.”*  
Production systems need answers to harder questions:

- Which prompt produced this output?
- Did a model change silently degrade quality?
- Can I reproduce this result two weeks from now? 
- How do I observe LLM behavior using the same primitives as the rest of my stack?

This project explores those questions by:

- Treating **prompts, datasets, and configs as versioned artifacts**
- Running **offline, reproducible evaluations** on real cluster logs
- Using **OpenTelemetry** as the backbone for LLM observability
- Integrating **LLM inference directly into a Kubernetes control-plane context**

It also doubles as hands-on preparation for **CKA-level Kubernetes knowledge** and a practical exploration of state of the art infrastructure management 

---

## What This Demonstrates (for Employers)

- **End-to-end MLOps thinking**: ingestion → inference → evaluation → observability  
- **Strong platform instincts**: separation of control-plane vs workload nodes, storage isolation, GitOps  
- **Evaluation rigor**: golden datasets, A/B testing, ROUGE + human review  
- **Observability maturity**: trace–log–metric correlation for LLM workloads  
- **Judgment under constraints**: small models (llama.cpp), CPU-only inference, homelab realism  

---

## System Architecture (High Level)

### Request Flow

1. **FastAPI Log Analyzer**
   - Queries Loki for structured logs  
   - Routes requests to the appropriate prompt + model configuration  

2. **llama.cpp Inference Server**
   - Runs small LLMs locally (1B–7B)  

3. **OpenTelemetry Instrumentation**
   - Traces prompt selection, rendering, and inference  

4. **Observability Stack**
   - Logs → Loki  
   - Traces → Tempo  
   - Metrics → Prometheus  
   - Visualization → Grafana  

5. **Offline Evaluation Harness**
   - Runs experiments against a frozen golden dataset  
   - Publishes results back into Grafana dashboards  

---

## Core Components

### Kubernetes & GitOps

- **Kubernetes** (2-node homelab cluster)
- **Flux** for GitOps-based reconciliation
- Explicit **workload placement strategy**:
  - Control plane + UX on **Node 1**
  - LLM inference, Loki, and evaluation jobs on **Node 2**

### LLM Serving

- **llama.cpp** behind an HTTP API
- Multiple quantizations tested (Q4, Q8)
- Model choice driven by **accuracy vs latency trade-offs**, not vibes

### Observability (OTel-First)

- **OpenTelemetry** for tracing LLM requests
- **Tempo** for trace storage
- **Loki** for structured logs
- **Prometheus** for metrics
- **Grafana** as the unified UI

> No LLM-specific SaaS required — everything flows through standard telemetry primitives.

---

## LLM Evaluation Framework (Key Differentiator)

### Golden Dataset

- **100% real logs** from my own cluster
- Manually reviewed and labeled
- Covers:
  - `kube-system`
  - Logging stack
  - LLM inference failures
  - GitOps reconciliation issues
- Frozen and versioned (`golden-v1`, `golden-v2`, …)

Think of this as **unit tests for LLM behavior**.

### Evaluation Methodology

Each experiment is fully reproducible and defined by:

- Dataset version
- Model + quantization
- Prompt template + version
- Sampling parameters (temperature, max tokens)

**Metrics include:**

- Root cause exact match
- Severity classification accuracy
- Component detection (F1)
- ROUGE for summary quality
- Latency (avg / p95)
- Token usage

**Results are:**

- Saved per-run with frozen configs
- Compared via A/B testing
- Visualized directly in Grafana

---

## Prompt Engineering as a First-Class Artifact

Prompts are treated like **code**:

- Versioned
- Hashed
- Reviewed in Git
- Attributed in OpenTelemetry traces

Each request can be traced back to:

- Prompt ID
- Prompt version
- Rendered prompt hash
- Model configuration

This allows answering:

> *“Which prompt caused this output?”*  

…without storing raw prompt text in telemetry.

---

## Development & Experimentation Workflow

- Local development via **`just`**
- **Git worktrees** for parallel agent / feature work
- Offline evaluations run locally or as **Kubernetes CronJobs**
- **Flux** reconciles infrastructure + application state

This enables **fast iteration without sacrificing reproducibility**.

---

## Roadmap (Condensed)

### Short Term
- Complete offline evaluation harness
- Finalize prompt registry + intent-based routing

### Medium Term
- Full trace–log–metric correlation for LLM requests
- Grafana dashboards for:
  - Accuracy drift
  - Prompt comparisons
  - Model trade-offs

### Long Term
- Deep Kubernetes administration mastery
- Explore *“infra as data”* using CRDs + custom controllers
- Treat cluster state itself as LLM input

---

## Why This Is Built on OpenTelemetry (Not LLM SaaS)

LLM-specific observability platforms add value — but:

**OTel already provides:**
- Distributed traces
- Correlated logs + metrics
- Vendor-neutral instrumentation

This project demonstrates that you can achieve **80–90% of the value** using open standards — **without locking into a proprietary control plane**.

The remaining gap (prompt UIs, human feedback loops) is intentionally explored as a **design problem**, not outsourced.

---

## Status

This project is **actively evolving**.  
Design decisions are documented intentionally — including trade-offs and TODOs — to reflect **real production thinking**, not a polished demo.
