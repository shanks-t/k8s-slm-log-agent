# Claude Code Preferences

## Learning Mode

**User is actively learning:**
1. **How to build AI agents** (LLM-powered log analysis, RAG systems)
2. **Kubernetes administration** in preparation for the **Certified Kubernetes Administrator (CKA)** exam

### Learning Approach
- **Default approach**: Coach and guide, don't just write code
- **Explain concepts**: Help user understand what to build and why
- **Ask questions**: Help user think through design decisions
- **Provide hints**: Point to documentation, patterns, and best practices
- **Write code only when**: User explicitly requests it ("write the code", "implement this for me")

### CKA Exam Preparation Focus
When working with Kubernetes commands and concepts, **relate them to CKA exam domains**:

**CKA Exam Domains (v1.35):**
1. **Cluster Architecture, Installation & Configuration (25%)**
   - Control plane components, kubeadm, RBAC, Kubernetes upgrades
2. **Workloads & Scheduling (15%)**
   - Deployments, ConfigMaps, Secrets, scaling, node selectors, taints/tolerations
3. **Services & Networking (20%)**
   - Services, Ingress, NetworkPolicies, CNI plugins, DNS
4. **Storage (10%)**
   - PersistentVolumes, PersistentVolumeClaims, StorageClasses, volume types
5. **Troubleshooting (30%)**
   - Cluster and application failures, logs, monitoring, debugging

**For each Kubernetes operation:**
- **Identify which CKA domain** it relates to
- **Explain the exam-relevant aspects** (what you'd need to know/do on the exam)
- **Provide exam-style context** (time pressure, kubectl efficiency, imperative vs declarative)
- **Highlight common exam scenarios** this prepares you for

### CKA Exam Skills to Practice
- **kubectl imperative commands** (faster than writing YAML)
- **kubectl explain** for API documentation during exam
- **JSONPath queries** for extracting specific data
- **Troubleshooting patterns** (logs, events, describe, exec)
- **YAML generation shortcuts** (`kubectl create --dry-run=client -o yaml`)
- **Time management** (17 questions in 2 hours = ~7 minutes per question)

## Communication Style

- **No emojis** unless explicitly requested
- **Be direct and concise**
- **Focus on technical accuracy**
- **Prefer explanations over implementations**
- **Always explain commands**: When providing kubectl, helm, ssh, or any terminal commands, explain what each command does and why it's needed

## When to Write Code

Only write complete implementations when user says:
- "Write the code"
- "Implement this"
- "Show me the implementation"
- "Just do it for me"

Otherwise: explain, guide, ask questions, provide pseudocode or structure.

## Development Environment

This repository uses **uv** (modern Python package manager) for dependency management:

- **Running Python scripts**: Use `uv run python <script.py>` instead of `python3`
- **Dependencies**: Defined in `pyproject.toml` at repository root
- **Evaluation scripts**: Located in `evals/` directory, use `uv run python` for execution
- **Installing dependencies**: Run `uv sync` to install/update all dependencies

Example:
```bash
# Run evaluation extraction script
cd evals
uv run python extract_golden_dataset.py

# Install/update all dependencies
uv sync
```

# Homelab Log Intelligence Platform — Project Goals & Architecture

This document describes the high-level goals, architectural principles, and learning approach for building a Kubernetes-based log intelligence system.

## Project Goals

Build a realistic, production-inspired observability + LLM pipeline that demonstrates:

- **AI Engineering:** LLM-powered log analysis with structured extraction
- **MLOps Practices:** Reproducible evaluation, experiment tracking, quality metrics
- **Kubernetes Administration:** Multi-node cluster management, workload scheduling, CNI networking
- **Production Patterns:** OpenTelemetry tracing, GitOps deployment, separation of concerns

The system supports:
- Structured log ingestion and analysis
- LLM-based root cause extraction and triage
- OpenTelemetry instrumentation for distributed tracing
- Evaluation framework with golden dataset
- Multi-node workload distribution optimized for performance

---

## Architectural Principles

### 1. Hardware-Aware Workload Placement

The two-node cluster uses hardware characteristics to optimize workload placement:

**Node 1 (Control Plane + UX):**
- Kubernetes control plane components
- User-facing services (Grafana, API Gateway)
- Lightweight application services (FastAPI log analyzer)
- Stateless routing and query services

**Node 2 (Compute + Storage):**
- LLM inference (llama.cpp with 3B-8B models)
- Data-intensive services (Loki log storage)
- Persistent storage backed by dedicated NVMe
- Future: Vector database for semantic search

**Why this matters:**
- Isolates heavy compute from control plane (stability)
- Optimizes I/O for data-heavy workloads (performance)
- Reflects production patterns of role-based node scheduling

**Implementation Details:** See `docs/node-specs.md` for hardware specifications

### 2. Separation of Concerns

**Production vs. Evaluation:**
- Production API serves real traffic (optimized for latency, stability)
- Evaluation harness measures quality offline (no latency constraints, tests multiple configs)
- Shared core library ensures production and eval use identical analysis logic

**Why this matters:**
- Prevents eval experiments from affecting production performance
- Enables rapid experimentation without deployment risk
- Industry-standard pattern (OpenAI, Anthropic, Google all do this)

**Implementation Details:** See `evals.md` for evaluation framework architecture

### 3. Observability First

Every component is instrumented with OpenTelemetry:
- **Traces:** Distributed tracing across Loki queries and LLM calls
- **Logs:** Structured JSON with automatic trace context injection
- **Metrics:** (Future) Prometheus metrics for quality and performance

**Why this matters:**
- Enables debugging production issues (trace individual requests)
- Provides data for optimization (which step is slow?)
- Demonstrates production-grade practices

**Implementation Details:** See `workloads/log-analyzer/README.md`

---

## System Components

### Observability Stack

**Purpose:** Collect, store, and visualize logs and traces from the entire cluster

**Key Components:**
- **Grafana Alloy**: Log collection (DaemonSet on all nodes)
- **Loki**: Log storage and querying (Node 2)
- **Tempo**: Distributed tracing backend (Node 2)
- **Grafana**: Visualization and exploration (Node 1)

**Why this stack:**
- Industry-standard tools (transferable skills)
- Lightweight enough for homelab
- Strong integration (trace-to-logs correlation)
- Open source (no vendor lock-in)

**Implementation Details:** See `infrastructure/o11y/` and `platform/o11y/`

### LLM Inference Layer

**Purpose:** Provide language model inference for log analysis

**Key Components:**
- **llama.cpp**: CPU-optimized inference server (Node 2)
- **Models**: Llama 3.2 3B (baseline), with support for 1B and 7B variants
- **API**: OpenAI-compatible endpoints for easy integration

**Why llama.cpp:**
- CPU-only inference (no GPU required)
- Quantized models (smaller, faster)
- Production-ready (used at scale)
- OpenAI-compatible API (familiar interface)

**Implementation Details:** See `workloads/llm/`

### Log Analysis Service

**Purpose:** Analyze logs using LLM to extract root causes, severity, and recommendations

**Key Components:**
- **FastAPI Service**: REST API with streaming support (Node 1)
- **Core Analyzer**: Shared library used by production and evaluation
- **OpenTelemetry**: Distributed tracing and structured logging

**Capabilities:**
- Structured extraction (root cause, severity, component)
- Streaming analysis (real-time feedback)
- JSON API (programmatic access)
- Trace context propagation

**Implementation Details:** See `workloads/log-analyzer/README.md`

### Evaluation Framework

**Purpose:** Measure and improve LLM quality through reproducible experiments

**Key Components:**
- **Golden Dataset**: 150 labeled samples from real cluster logs
- **Experiment Runner**: Offline harness for testing configurations
- **Metrics & Visualization**: Accuracy tracking in Grafana

**Why evaluation matters:**
- Prevents quality regressions
- Enables data-driven decisions (model selection, prompt tuning)
- Demonstrates MLOps best practices

**Implementation Details:** See `evals.md` for comprehensive roadmap

### Gateway & Ingress

**Purpose:** Route external traffic to services with proper HTTP routing

**Key Components:**
- **Envoy Gateway**: Modern Kubernetes Gateway API implementation
- **HTTPRoute**: Path-based routing to backend services

**Why Envoy Gateway:**
- Gateway API (future of Kubernetes ingress)
- Powerful routing capabilities
- Production-grade (used at scale)

**Implementation Details:** See `infrastructure/gateway/README.md`

---

## Current State & Component Status

### Infrastructure (Cluster Foundation)
- ✅ **Kubernetes v1.35** - Installed via kubeadm on both nodes
- ✅ **Cilium CNI** - Container networking with eBPF
- ✅ **Flux CD** - GitOps for continuous deployment
- ✅ **Node Configuration** - Labels, taints, and workload scheduling
- ✅ **Storage** - Dedicated NVMe on Node 2 for persistent volumes

**Relevant Documentation:**
- `docs/node-specs.md` - Hardware specifications
- `infrastructure/` - Core Kubernetes infrastructure manifests

### Observability Stack
- ✅ **Loki** - Log storage operational on Node 2
- ✅ **Tempo** - Distributed tracing operational
- ✅ **Grafana Alloy** - Log collection from all nodes
- ✅ **Grafana** - Dashboards and exploration UI
- ✅ **Trace-to-Logs Correlation** - Bidirectional linking working

### LLM & Analysis Services
- ✅ **llama.cpp** - Serving Llama 3.2 3B on Node 2
- ✅ **Log Analyzer API** - FastAPI service with streaming support
- ✅ **OpenTelemetry Integration** - Distributed tracing operational
- ⏸️ **Evaluation Framework** - Dataset created, harness in progress
- ⏸️ **Multi-Model Support** - Single model (3B), can add 1B/7B variants

**Relevant Documentation:**
- `workloads/llm/README.md` - LLM deployment details
- `workloads/log-analyzer/README.md` - Log analyzer service docs
- `evals.md` - Evaluation framework roadmap

### Gateway & Routing
- ✅ **Envoy Gateway** - Installed and operational
- ✅ **Test HTTPRoute** - Basic routing validated
- ⏸️ **Production Routes** - Can expose Grafana and log-analyzer via Gateway

**Relevant Documentation:**
- `infrastructure/gateway/README.md` - Gateway configuration

---

## Learning Outcomes

This project provides hands-on experience with:

### AI Engineering
- LLM prompt engineering for domain-specific tasks
- Structured output extraction from unstructured text
- Evaluation framework design (golden datasets, metrics)
- Experiment tracking and model selection
- MLOps patterns (reproducibility, versioning, quality monitoring)

### Kubernetes Administration (CKA Exam Preparation)
- **Cluster Installation:** kubeadm init, worker node joining, CNI setup
- **Workload Scheduling:** Node selectors, taints/tolerations, pod placement
- **Networking:** CNI troubleshooting, service discovery, Gateway API
- **Storage:** PersistentVolumes, PersistentVolumeClaims, storage classes
- **Troubleshooting:** Log analysis, debugging failed pods, DNS issues

### Production Patterns
- **Observability:** OpenTelemetry distributed tracing, structured logging
- **GitOps:** Flux CD for declarative deployments
- **Separation of Concerns:** Production API vs. evaluation harness
- **Configuration Management:** ConfigMaps, environment variables, versioning
- **Resource Management:** CPU/memory limits, node affinity

---

## Summary

This homelab demonstrates a production-inspired log intelligence system that:

- **Analyzes Kubernetes logs** using small language models (3B parameters)
- **Provides structured insights** (root cause, severity, recommendations)
- **Instruments everything** with OpenTelemetry for observability
- **Measures quality** through reproducible evaluation
- **Runs efficiently** on consumer hardware (no GPU required)

The architecture balances:
- **Learning:** Covers AI engineering, Kubernetes, and MLOps
- **Realism:** Uses production patterns and industry-standard tools
- **Practicality:** Fits on a two-node homelab cluster

**Next Steps:**
- Complete evaluation framework (Phase 1-2 in `evals.md`)
- Experiment with model variants and prompt templates
- Expose services via Envoy Gateway
- Build Grafana dashboards for evaluation metrics

**For Implementation Details:**
- Component-specific docs in respective README files
- Evaluation roadmap in `evals.md`
- CKA exam preparation tips throughout this document

