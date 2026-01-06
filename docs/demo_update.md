## System Overview

### What We've Built

A **production-grade two-node Kubernetes cluster** (v1.35.0) running a complete GitOps-managed observability and AI-powered log analysis platform:

- **GitOps:** Flux CD reconciling from GitHub main branch with automated deployments
- **Logging Pipeline:** Grafana Alloy (DaemonSet) → Loki → Grafana
- **Tracing:** Tempo for distributed tracing with OpenTelemetry
- **Monitoring:** Prometheus + kube-state-metrics + node-exporter for full cluster metrics
- **Gateway & Routing:** Envoy Gateway with Gateway API (HTTPRoute resources)
- **AI/ML Layer:** llama.cpp serving Llama 3.2 3B + FastAPI log analyzer with prompt registry
- **Data Processing:** Golden dataset generation with real + synthetic logs
- **Node Optimization:** Workload placement based on hardware capabilities (labels + taints)

---

## Architecture Components

### Node 1 (Control Plane + UI Layer)

**Hardware:** Intel Core i7-8700 (6 cores, 12 threads), 32GB RAM

**Workloads:**
- Kubernetes v1.35.0 control plane (API server, scheduler, controller-manager, etcd)
- Envoy Gateway data plane (HTTP/HTTPS ingress proxy)
- Grafana (visualization and dashboards)
- Grafana Alloy (log & trace collection agent - DaemonSet)
- Metrics Server (resource metrics API)
- Prometheus Node Exporter (host metrics)
- FastAPI Log Analyzer service (AI-powered log analysis)

**Why Node 1?**
- Lighter workloads keep control plane responsive
- UI services benefit from stable, low-latency environment
- Separation prevents LLM inference from impacting cluster operations
- Label: `hardware=light` for workload scheduling

### Node 2 (Compute + Storage Layer)

**Hardware:** Intel Core i7-12700T (12 cores, 20 threads), 94GB RAM, 2x NVMe drives

**Storage:**
- **Primary NVMe (Sabrent 954GB):** OS and system files
- **Secondary NVMe (Samsung 477GB):** `/mnt/k8s-storage` - dedicated for workloads
  - Loki log chunks and indices (200GB PV)
  - Tempo trace storage (50GB PV)
  - LLM models (20GB PV)
  - Vector database (planned)

**Workloads:**
- Loki StatefulSet (log storage and query engine)
- Tempo StatefulSet (distributed tracing storage)
- llama.cpp Deployment (LLM inference server - Llama 3.2 3B)
- Grafana Alloy DaemonSet (log & trace collection agent)
- Prometheus server (metrics storage and query engine)
- kube-state-metrics (Kubernetes object metrics)
- Prometheus Node Exporter (host metrics)
- Prometheus Pushgateway (batch job metrics)
- Flux controllers (GitOps reconciliation)
- Envoy Gateway controller (Gateway API management)

**Why Node 2?**
- High core count (12 physical cores) excellent for LLM inference
- AVX_VNNI CPU instructions accelerate neural network operations
- Large memory (94GB) supports multiple AI + observability workloads
- Dedicated NVMe eliminates I/O contention between OS and workloads
- Label: `hardware=heavy` + Taint: `heavy=true:NoSchedule` for dedicated workloads
