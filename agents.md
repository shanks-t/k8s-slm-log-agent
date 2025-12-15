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

## **Phase 3 — Foundation: LLM Serving + Golden Dataset**
**Status:** ✅ COMPLETE

This phase establishes the foundation for evaluation-driven development.

1. ✅ Extract golden dataset from Loki
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

**Technology Decisions:**
- **Llama 3.2 3B Q4_K_M:** Good balance of quality vs speed for CPU inference (vs 1B or 7B variants)
- **llama.cpp:** CPU-optimized with AVX_VNNI support for Intel 12th gen (i7-12700T)
- **Dedicated `llm` namespace:** Clean separation of ML workloads from infrastructure

---

## **Phase 3A — Baseline: Time-Based Retrieval**
**Goal:** Establish baseline extraction accuracy using simple time-ordered log retrieval (no vector DB).

1. Deploy FastAPI log analyzer service on Node 1
   - Namespace: `log-analyzer`
   - Node selector: `hardware=light`
   - Resources: 2 CPU cores, 2GB memory
   - Expose via Envoy Gateway HTTPRoute

2. Implement simple retrieval pipeline:
   - Query Loki using LogQL for time-range filtered logs
   - Example: `{namespace="logging"} | json | severity="error" [1h]`
   - Return top N logs ordered by timestamp (most recent first)
   - No embedding, no semantic search

3. Implement structured extraction:
   - Send retrieved logs to llama.cpp
   - Prompt engineering for extraction:
     - Root cause identification
     - Severity classification
     - Component detection
     - Summary generation
     - Action recommendation
   - Parse LLM JSON output

4. Build evaluation framework:
   - Run golden dataset (150 samples) through baseline pipeline
   - Compute metrics:
     - **Extraction accuracy:** Field-level F1 scores (root_cause, severity, component)
     - **Root cause accuracy:** Exact match vs ground truth
     - **Severity classification:** Confusion matrix (INFO/WARN/ERROR/CRITICAL)
     - **End-to-end latency:** Time from query → result
   - Store results in JSON/CSV for comparison

5. Add basic observability:
   - OpenTelemetry spans for:
     - Loki query duration
     - LLM inference latency
     - Total request latency
   - Log extraction results for debugging

**Success Criteria:**
- Baseline extraction accuracy measured on golden dataset
- Documented failure modes (what kinds of logs does time-based retrieval miss?)
- Latency measurements (p50, p95, p99)

**Rationale:**
- Establishes ground truth for comparison
- Answers: "Do we even need semantic search?"
- Simple architecture = faster iteration on prompts
- Many use cases work fine with time-based retrieval

**Learning Outcomes:**
- LLM prompt engineering for structured extraction
- Kubernetes service architecture (FastAPI ↔ Loki ↔ LLM)
- Evaluation framework design
- Understanding when simple approaches suffice

---

## **Phase 3B — Hybrid Retrieval: Add Vector DB**
**Goal:** Add semantic search and measure improvement over baseline.

1. Deploy Chroma vector DB on Node 2:
   - Persistent storage on Samsung NVMe (`/mnt/k8s-storage/chroma`)
   - Node selector: `hardware=heavy`
   - Resources: 4 CPU cores, 4GB memory
   - Client library in FastAPI service

2. Deploy embedding model on Node 2:
   - Model: BGE-small-en-v1.5 (384 dimensions, 33M params)
   - Deployment: CPU-optimized inference server
   - API: gRPC or HTTP endpoint
   - Resources: 2 CPU cores, 2GB memory
   - Alternative: Sentence-Transformers library directly in FastAPI

3. Implement log embedding pipeline:
   - Batch job: Embed historical logs from Loki
     - Time range: Last 7 days (matches Loki retention)
     - Target: 10K-50K log chunks
   - Chunking strategy:
     - Option A: 300-800 tokens per chunk (as originally planned)
     - Option B: One embedding per log line with metadata
   - Store in Chroma with metadata:
     - timestamp, namespace, pod, container, node, severity
     - Allows hybrid filtering (vector search + metadata filters)

4. Implement hybrid retrieval strategy:
   ```python
   def retrieve_context(query: str, time_range: TimeRange, namespace: str = None):
       # Step 1: Structured pre-filter via Loki
       loki_results = query_loki(
           labels={"namespace": namespace} if namespace else {},
           time_range=time_range,
           limit=1000  # Broad time-based filter
       )

       # Step 2: Semantic search within filtered results
       query_embedding = embed_model.encode(query)
       relevant_chunks = chroma.query(
           query_embeddings=[query_embedding],
           where={
               "timestamp": {"$gte": time_range.start, "$lte": time_range.end},
               "namespace": namespace
           },
           n_results=20  # Top-K semantic matches
       )

       # Step 3: Re-rank or merge (optional)
       # Combine time-relevance + semantic-relevance scores

       return relevant_chunks
   ```

5. Update FastAPI service:
   - Add `/v2/analyze` endpoint with hybrid retrieval
   - Keep `/v1/analyze` endpoint with baseline retrieval
   - A/B comparison mode for evaluation

6. Evaluate hybrid retrieval vs baseline:
   - Run same golden dataset through hybrid pipeline
   - Compute delta metrics:
     - **Retrieval precision:** % of retrieved chunks that are relevant
     - **Retrieval recall:** % of relevant chunks that were retrieved
     - **Extraction accuracy improvement:** F1 delta vs baseline
     - **Latency overhead:** Embedding + vector search time
   - Analyze failure modes:
     - When does semantic search help? (e.g., paraphrased errors)
     - When does it hurt? (e.g., time-critical recent errors)

7. Build agentic retrieval router (optional):
   - Decision logic to choose strategy:
     - Specific pod query → Structured (baseline)
     - Semantic query ("why is it slow?") → Hybrid
     - Time-bounded alert → Structured
     - Root cause analysis → Hybrid
   - Measure router accuracy on golden dataset queries

**Success Criteria:**
- Hybrid retrieval shows measurable improvement on specific query types
- Documented when to use which strategy
- Latency overhead is acceptable (<500ms added for embedding + search)

**Rationale:**
- Data-driven decision: Only keep vector DB if it improves accuracy
- Hybrid approach combines strengths of both methods
- Prepares for agentic retrieval patterns in later phases

**Learning Outcomes:**
- Vector database operations (embedding, indexing, querying)
- Retrieval evaluation (precision/recall vs end-task accuracy)
- Context engineering (chunking, metadata preservation)
- Hybrid system design (when to use which tool)

**Technology Decisions:**
- **Chroma:** Simple Python API, good for learning, built-in metadata filtering
- **BGE-small-en-v1.5:** Better retrieval quality than E5-small, still CPU-friendly
- **Hybrid filtering:** Vector search + metadata filters avoid embedding entire corpus

---

## **Phase 4 — Production Features**
Build production-ready features on top of the retrieval system.

1. Implement advanced extraction prompts:
   - Infra log variants (K8s events, resource issues, network errors)
   - App log variants (application errors, business logic failures)
   - Multi-log correlation (cascade failure detection)

2. Add summarization and triage:
   - Time-window summaries ("What happened in the last hour?")
   - Incident triage ranking (severity + impact scoring)
   - "What changed?" drift detection between time windows
   - Pattern detection for recurring issues

3. Store extraction results:
   - PostgreSQL or DuckDB for structured storage
   - Schema: timestamp, query, retrieved_logs, extraction_result, metadata
   - Enables historical analysis and trend detection

4. Build Grafana dashboards:
   - Extraction accuracy over time
   - Top errors by component/namespace
   - LLM inference latency trends
   - RAG retrieval hit rate

5. Add full OpenTelemetry instrumentation:
   - Distributed tracing across all services
   - Custom metrics: extraction_accuracy, retrieval_precision, llm_tokens_per_sec
   - Export to Prometheus + Tempo

6. Expose via Ingress with authentication:
   - Public endpoint: `/api/v2/analyze`
   - Rate limiting and API key authentication
   - Request logging for monitoring

---

## **Phase 5 — Evaluation + Drift Detection**
Continuous evaluation and monitoring of the log intelligence system.

1. Expand golden dataset:
   - Add real incident logs as they occur
   - Community-sourced K8s failure scenarios
   - Target: 500+ samples with diverse failure modes

2. Implement evaluation CronJob (runs on Node 2):
   - Daily/weekly evaluation runs
   - Replay golden samples through current pipeline
   - Compare results vs ground truth
   - Detect accuracy drift over time

3. Compute comprehensive metrics:
   - Extraction accuracy (precision, recall, F1 per field)
   - Root cause identification accuracy
   - Severity classification confusion matrix
   - Summary quality scores (ROUGE, BERTScore)
   - Retrieval quality (MRR, NDCG)

4. Emit OTel metrics to Prometheus:
   - `log_extraction_accuracy{field="root_cause"}` gauge
   - `log_retrieval_precision` gauge
   - `llm_inference_latency_seconds` histogram
   - `eval_run_timestamp` counter

5. Build evaluation dashboards + alerts:
   - Accuracy trend over time (detect drift)
   - Per-component/namespace accuracy breakdown
   - Alerting: accuracy drops below threshold
   - Comparison: baseline vs hybrid performance

---

## **Phase 6 — (Optional) Advanced Topics**
Explore advanced LLM and retrieval patterns.

1. Multi-agent orchestration:
   - Specialist agents for different log types (infra vs app)
   - Routing agent that delegates to specialists
   - Consensus mechanisms for high-confidence extraction

2. Active learning loop:
   - Flag low-confidence extractions for human review
   - User feedback → add to golden dataset
   - Retrain/re-prompt based on failures

3. Fine-tuning experiments:
   - Fine-tune Llama 3.2 3B on K8s log extraction task
   - Compare vs prompt engineering approach
   - Measure accuracy vs inference latency trade-off

4. Advanced retrieval:
   - HyDE (Hypothetical Document Embeddings)
   - Re-ranker model (cross-encoder) after initial retrieval
   - Graph-based retrieval (log entries as nodes, correlations as edges)

---

## **Phase 7 — (Optional) Migrate to Full Kubernetes**
Replace K3s with production-grade Kubernetes.

1. Replace K3s with kubeadm or "Kubernetes the Hard Way"
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
