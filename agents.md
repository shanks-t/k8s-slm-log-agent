# Claude Code Preferences

## Learning Mode

**User is actively learning how to build AI agents.**

- **Default approach**: Coach and guide, don't just write code
- **Explain concepts**: Help user understand what to build and why
- **Ask questions**: Help user think through design decisions
- **Provide hints**: Point to documentation, patterns, and best practices
- **Write code only when**: User explicitly requests it ("write the code", "implement this for me")

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

# Homelab Log Intelligence Platform — Architecture & Implementation Guide

This document summarizes the recommended architecture for running a Kubernetes-based log intelligence system in a two-node homelab, and provides a phased roadmap for implementation.

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
- RAG retrieval components  
- Evaluation / batch jobs  

### **Run control-plane & UX services on Node 1**
- Kubernetes control plane (API server, controller manager, scheduler)  
- Ingress controller / API gateway  
- Grafana dashboards  
- Log analyzer API (FastAPI)  
- OTel Collector (agent + gateway mode)  
- grafana alloy / Fluent Bit  
- Any stateless routing/query services  

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

### **Metrics & Traces**
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
  - Explore traces (Tempo)
  - Analyze metrics (Prometheus)

---

# 4. LLM-Powered Log Intelligence Layer

This system provides structured extraction, triage, and summarization of logs using small language models.

### **Components on Node 2**
- llama.cpp deployments (3B + 7B variants)  
- Vector DB (Chroma/LanceDB/Qdrant)  
- Embedding workers (CPU-optimized)  

### **Components on Node 1**
- Log analyzer API (FastAPI)
  - Routes queries to Loki  
  - Chunks logs  
  - Embeds → vector search → retrieval  
  - Calls LLM inference → structured extraction  
  - Emits OTel spans/metrics  
- Ingress routing for public/internal access
- Dashboards for insights

### **Extraction Tasks Supported**
- Structured extraction (root cause, component, error signatures)
- Summaries over time windows
- Triage ranking of errors
- “What changed?” comparisons between time windows
- Pattern detection for app + infra logs

---

# 5. Evaluation & Drift Detection

To ensure the log intelligence system remains correct over time:

### **Golden Dataset**
- Curated set of:
  - Kubernetes infra logs  
  - Application logs  
  - Common failure signatures  
- Each with:
  - Ground-truth structured JSON extraction  
  - Optional natural-language summary

### **Evaluation Job (CronJob on Node 2)**
- Replay golden samples through the pipeline
- Compute metrics:
  - Extraction accuracy  
  - Root-cause accuracy  
  - Severity classification accuracy  
  - Summary adequacy scores  
- Emit OpenTelemetry metrics for:
  - Drift detection  
  - Regression tracking  
  - Pipeline latency  

### **Visualization**
- Grafana dashboards for:
  - Eval accuracy over time  
  - RAG retrieval hit rate  
  - LLM inference latency  
  - Chunking efficiency metrics  

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


---

# 7. Implementation Roadmap (Phased Steps)

Below is a clean, incremental roadmap for implementing the full system.

---

## **Phase 1 — Cluster Restructuring** ✅ COMPLETE
1. ✅ Move the Kubernetes control plane from Node 2 → Node 1
2. ✅ Confirm node labels:
   - Node 1 → `hardware=light`
   - Node 2 → `hardware=heavy`
3. ✅ Apply node taints:
   - Node 2: `heavy=true:NoSchedule`
4. ✅ Configure node selectors for heavy services to run only on Node 2
5. ✅ Install and configure Envoy Gateway
   - Disabled Traefik
   - Deployed Envoy Gateway on Node 1
   - LoadBalancer service via K3s servicelb
   - Validated with test HTTPRoute  

---

## **Phase 2 — Logging Infrastructure** ✅ COMPLETE
1. ✅ Mount and configure Samsung NVMe on Node 2 at `/mnt/k8s-storage`
2. ✅ Deploy Loki on Node 2 with persistent storage on Samsung NVMe
3. ✅ Deploy Grafana Alloy DaemonSet on both nodes (replaces deprecated Promtail)
4. ✅ Install Grafana on Node 1 (via Helm)
5. ✅ Configure Grafana data source for Loki
6. ✅ Create HTTPRoute to expose Grafana via Envoy Gateway at http://10.0.0.102/grafana
7. ✅ Fix cross-node networking (opened UDP port 8472 for VXLAN)
8. ✅ Validate: View container logs in Grafana

**Technology Decisions:**
- **Grafana Alloy instead of Promtail:** Promtail is deprecated (EOL March 2026). Alloy is the replacement and offers unified log/metrics/trace collection, better performance, and active development. This also simplifies Phase 4 by eliminating the need for separate OpenTelemetry Collector deployment.
- **OpenTelemetry integration:** Deferred to Phase 4 when FastAPI service is instrumented. Alloy will handle OTel trace collection when needed.  

---

## **Phase 3 — LLM Serving Layer + Evaluation Setup**
**Revised approach:** Build evaluation infrastructure BEFORE full deployment to measure performance with real data.

1. ✅ Extract 200 sample logs from Loki → Create golden dataset
   - Mix of Kubernetes infra logs and application logs
   - Label with ground truth: root cause, severity, component, summary, action needed
   - **Status:** Complete - hybrid approach implemented
     - Enhanced extraction script with noise filtering, severity detection, and stratified sampling
     - 30+ synthetic log templates covering diverse K8s failure scenarios
     - Scripts: `extract_golden_dataset.py`, `synthesize_logs.py`, `combine_datasets.py`, `dataset_analysis.py`
     - Target: 150 logs (70% real, 30% synthetic) with 25% INFO, 25% WARN, 40% ERROR, 10% CRITICAL

2. ✅ Deploy llama.cpp on Node 2 (Llama 3.2 3B model)
   - **Status:** Complete and tested
   - **Model:** Llama 3.2 3B Instruct Q4_K_M (1.87 GB)
   - **Performance:** 19.75 tokens/sec (CPU-only with AVX_VNNI)
   - **Namespace:** `llm`
   - **Resources:** 10 CPU cores, 6-10 GB memory
   - **Storage:** `/mnt/k8s-storage/models` via local PersistentVolume on Node 2
   - **API:** OpenAI-compatible endpoint at `llama-cpp.llm.svc.cluster.local:8080`
   - **Manifests:** `k8s/llama-cpp/`
   - **Tested:** Chat completions working correctly with proper Kubernetes troubleshooting responses

3. Deploy Chroma vector DB on Node 2 with persistent storage
4. Deploy embedding model (BGE-small-en-v1.5) on Node 2
5. Build evaluation framework:
   - Extraction accuracy metrics
   - Embedding quality (retrieval precision/recall)
   - RAG relevance scoring
   - LLM output quality vs ground truth
   - End-to-end latency measurements
6. Run baseline evaluation with golden dataset
7. Iterate on prompts/configs based on metrics

**Rationale:** Understanding model limitations early allows data-driven iteration before building full RAG pipeline in Phase 4.

**Technology Decisions:**
- **Llama 3.2 3B Q4_K_M:** Good balance of quality vs speed for CPU inference (vs 1B or 7B variants)
- **llama.cpp:** CPU-optimized with AVX_VNNI support for Intel 12th gen (i7-12700T)
- **BGE-small-en-v1.5:** Better retrieval quality than E5-small (33M params)
- **Dedicated `llm` namespace:** Clean separation of ML workloads from infrastructure  

---

## **Phase 4 — Log Retrieval + RAG Pipeline**
1. Build FastAPI log analyzer service on Node 1  
2. Implement:
   - Loki querying  
   - Log chunking (300–800 tokens)  
   - Embedding generation  
   - Vector search for RAG  
3. Add OpenTelemetry spans for:
   - Retrieval  
   - Embedding  
   - Vector search  
   - LLM inference  
   - Post-processing  
4. Expose via Ingress  

---

## **Phase 5 — LLM Extraction + Summarization**
1. Implement structured extraction prompts (infra + app log variants)  
2. Implement summarization and triage prompts  
3. Store extracted JSON results in PostgreSQL/DuckDB  
4. Build Grafana dashboards to visualize outputs  

---

## **Phase 6 — Evaluation + Drift Detection**
1. Build golden dataset for infra/app logs  
2. Implement evaluation job (CronJob on Node 2)  
3. Compute:
   - Accuracy  
   - Root cause identification  
   - Severity correctness  
4. Emit OTel metrics to Prometheus  
5. Build evaluation dashboards + alerts  

---

## **Phase 7 — (Optional) Migrate to Full Kubernetes**
1. Replace K3s with kubeadm or “Kubernetes the Hard Way”  
2. Migrate workloads using the same Helm charts/manifests  
3. Validate:
   - Scheduling  
   - Affinity rules  
   - Control-plane separation  
   - Production-like behavior  

---

# 8. Summary

This design gives you:

- A scalable, CPU-optimized LLM logging pipeline  
- A realistic multi-node Kubernetes architecture  
- Full observability using OpenTelemetry  
- Production-style evaluation and drift detection  
- Hands-on experience in LLM serving, RAG, log analytics, and K8s infrastructure  

    This Markdown file can be used directly by you or an LLM assistant to guide implementation, automate provisioning, or refactor components as your homelab evolves.
