# Homelab Log Intelligence Platform

A Kubernetes-based log intelligence system that combines small language models with retrieval-augmented generation (RAG) to analyze, extract, and summarize logs from a two-node homelab cluster.

## Overview

This project implements a production-inspired observability pipeline that ingests logs from Kubernetes infrastructure and applications, uses vector embeddings for semantic search, and leverages local LLM inference (llama.cpp) to perform structured extraction, triage, and summarization of log data.

**Key Components:**
- Log collection and storage (Grafana Alloy, Loki)
- LLM serving layer (llama.cpp with Llama 3.2 3B)
- FastAPI log analyzer service
- Vector database for RAG retrieval
- OpenTelemetry instrumentation
- Evaluation framework with golden dataset


## Using git work trees for multi-agent workflows

Call giit worktree add -b <new-wt-branch> <path-to-working-dr> (must be outside of current .git repo) <branch-to-create-worktree-from>. e.g.
```sh
git worktree add -b agent/flux ../a-k8s-slm-log-agent-wt main
```
List worktrees:
```sh
git worktree list
```
e.g. I created a worktree to migrate my project to flux while continuing development on the agent Fastapi service
```sh
git worktree list
/Users/treyshanks/workspace/k8s-slm-log-agent       de51178 [main]
/Users/treyshanks/workspace/k8s-slm-log-agent-wt-a  de51178 [agent/flux]
```
Then cd into worktree and give your agent instructions! e.g.
```sh
cd ../../k8s-slm-log-agent-wt-a
git status
```
When you are ready to push your changes from worktree to a remote branch:
```sh
cd <worktree>
git add .
git commit -m "Agent changes"
git push -u origin agent/flux
```

## Local Development

This project uses [`just`](https://just.systems/) as a command runner for development workflows. Just is a modern alternative to Make, designed specifically for running project-specific commands. It provides a clean, ergonomic syntax and works consistently across platforms.

### Why Just?

- **Task runner, not a build system**: Unlike Make, `just` is designed for running commands, not tracking dependencies
- **No tab vs space confusion**: Uses any whitespace for indentation
- **Better error messages**: Clear, helpful output when things go wrong
- **Cross-platform**: Works on Linux, macOS, and Windows
- **Recipe parameters**: Support for default values and parameterized commands

**Learn more:** [Just Programmer's Manual](https://just.systems/man/en/) | [Recipe Parameters](https://just.systems/man/en/recipe-parameters.html)

### Available Commands

All commands should be run from the repository root:

```bash
just --list
Available recipes:
    build                                              # Output: ghcr.io/${GITHUB_USER}/log-analyzer:latest and :${GIT_SHA}
    default                                            # Default recipe runs dev
    deploy                                             # Workflow: Updates deployment.yaml → git commit → git push → flux reconcile
    dev                                                # Stop with: Ctrl+C or 'just stop'
    dev-k8s                                            # Note: For one-off tests, use 'just test-k8s-local' (auto-cleanup)
    evaluate namespace="log-analyzer" duration="1h"    # just evaluate kube-system 1h       # Evaluate last 1 hour
    push                                               # Requires: 'just build' to have been run first
    release                                            # Example: just release
    stop                                               # Safe to run even if nothing is running.
    stop-k8s                                           # Safe to run even if nothing is running.
    test                                               # Dependencies are mocked (Loki, LLaMA).
    test-all                                           # Requires: 'just dev' running in another terminal
    test-int                                           # Tests use real Loki, LLaMA services via port-forward.
    test-k8s namespace="log-analyzer" duration="1h"    # just test-k8s namespace=llm duration=24h
    test-k8s-local namespace="log-analyzer" duration="1h" # just test-k8s-local namespace=llm duration=24h
    test-stream namespace="kube-system" duration="24h" # just test-stream kube-system 24h  # Last 24 hours of kube-system
```

## Architecture & Implementation Guide

This section summarizes the architecture for running a Kubernetes-based log intelligence system in a two-node homelab, and provides a phased roadmap for implementation.

The goal is to build a realistic, production-inspired observability + LLM pipeline that supports:

- Structured log ingestion (infra + application)
- RAG-powered log retrieval
- LLM-based extraction, triage, and summarization
- OpenTelemetry instrumentation
- Evaluation + drift detection with a golden dataset
- Efficient multi-node workload distribution (Node 1 vs Node 2)

---

# 1. [Cluster Hardware Summary](./reference/node-specs.md)
---

# 2. Storage Strategy

### **Node 2 Dedicated K8s Storage**

Node 2 has two NVMe drives with different purposes:

**Primary NVMe (Sabrent 953.9GB):**
- Operating system and base system files
- Mounted at `/`

**Secondary NVMe (Samsung MZVPV512 476.9GB):**
- Dedicated Kubernetes workload storage
- Mounted at `/mnt/k8s-storage`
- Purpose: High-I/O workloads requiring fast storage
- Used for:
  - Loki log storage and chunks
  - Vector database (embeddings, indices)
  - Any persistent volumes for heavy compute workloads

**Rationale:**
- Separates OS I/O from workload I/O (prevents resource contention)
- Samsung NVMe dedicated to most I/O-intensive services (Loki, Vector DB)
- Clean separation makes data management and backup strategies simpler
- Can wipe/rebuild OS without affecting persistent workload data

**Configuration:**
```bash
# Format and mount (one-time setup)
mkfs.ext4 /dev/nvme1n1
mkdir -p /mnt/k8s-storage
mount /dev/nvme1n1 /mnt/k8s-storage

# Add to /etc/fstab for automatic mounting
echo '/dev/nvme1n1 /mnt/k8s-storage ext4 defaults 0 2' >> /etc/fstab
```

---

# 3. Workload Distribution Strategy

To maximize performance and reflect production-grade design patterns:

### **Run heavy compute and storage on Node 2**
- LLM servers (3B–8B)  
- Vector DB + embeddings  
- Loki for log storage  
- Evaluation / batch jobs  

### **Run control-plane & UX services on Node 1**
- Kubernetes control plane (API server, controller manager, scheduler)  
- Ingress controller / API gateway  
- Grafana dashboards  
- Log analyzer API (FastAPI)  
- TODO: OTel Collector (agent + gateway mode)  
- grafana alloy

### **Rationale**
- Node 2’s memory bandwidth + NVMe drastically improves LLM and vector DB performance.
- Node 1’s lighter workload keeps UI + control plane responsive.
- Isolation ensures LLM inference cannot starve the Kubernetes control plane.

---

# 3. Logging + Observability Stack Overview

### **Log Collection**
- grafana alloy (DaemonSet on both nodes)
- Ship host, container, and application logs
- Application logs should be structured JSON for clean extraction

### **Log Storage & Query**
- Loki (running on Node 2)
  - Persistent volume on NVMe
  - High ingest and query performance

### **Metrics & Traces** TODO:
- OpenTelemetry Collector:
  - **Agent mode** on both nodes for log collection
  - **Gateway mode** on Node 1 as central trace+metric router
- Export:
  - Traces → Tempo/Jaeger
  - Metrics → Prometheus
  - Logs → Loki

### **Dashboards**
- Grafana on Node 1
  - Explore logs (Loki)
  - TODO: Explore traces (Tempo)
  - TODO: Analyze metrics (Prometheus)

---

# 4. LLM-Powered Log Intelligence Layer

This system provides structured extraction, triage, and summarization of logs using small language models.

### **Components on Node 2**
- llama.cpp deployments (3B + 7B variants)  
- TODO: Vector DB (Chroma/LanceDB/Qdrant)  
- TODO: Embedding workers (CPU-optimized)  

### **Components on Node 1**
- Log analyzer API (FastAPI)
  - Routes queries to Loki  
  - Calls LLM inference → structured extraction  
  - TODO: Emits OTel spans/metrics  
- Ingress routing for public/internal access
- Dashboards for insights

### **Extraction Tasks Supported** TODO:
- Structured extraction (root cause, component, error signatures)
- Summaries over time windows
- Triage ranking of errors
- “What changed?” comparisons between time windows
- Pattern detection for app + infra logs

---

# 5. Evaluation & Drift Detection TODO:

Current [evals plan](./evals.md)

---

# 6. Node Placement Diagram

- Node 1 (Lightweight)
    - K8S Control Plane
    - Grafana
    - FastAPI Log Analyzer
    - OpenTelemetry Collector (Gateway)
    - Promtail
    - Ingress Controller
    - API Gateway / Routing
    - Misc. management services

-  Node 2 (High Performance)
    - Llama.cpp Model Servers
    - Vector Database (Chroma/Lance/Qdrant)
    - Embedding Workers
    - Loki (storage + query frontends)
    - Evaluation CronJobs
    - Retrieval components
    - Heavy compute workloads