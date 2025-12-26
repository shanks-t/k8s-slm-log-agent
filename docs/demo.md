# Homelab Log Intelligence Platform - System Demo

**A Production-Grade Kubernetes Observability + AI Platform**

This document provides a guided tour of the homelab infrastructure, demonstrating a complete log intelligence system built on Kubernetes with integrated LLM capabilities.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Interactive Demo](#interactive-demo)
4. [Design Rationale](#design-rationale)
5. [Performance Metrics](#performance-metrics)

---

## System Overview

### What We've Built

A **two-node Kubernetes cluster** running a complete observability and AI-powered log analysis platform:

- **Logging Pipeline:** Grafana Alloy → Loki → Grafana
- **Gateway & Routing:** Envoy Gateway with HTTPRoute configuration
- **AI/ML Layer:** llama.cpp serving Llama 3.2 3B for log analysis
- **Data Processing:** Golden dataset generation with real + synthetic logs
- **Node Optimization:** Workload placement based on hardware capabilities

### Infrastructure At a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer                            │
│                      (K3s ServiceLB)                            │
│                         10.0.0.102                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Envoy Gateway                             │
│                   (envoy-gateway-system)                        │
│                  HTTP/HTTPS Routing Layer                       │
└──────────────┬──────────────────────────────────┬───────────────┘
               │                                  │
               ▼                                  ▼
    ┌──────────────────┐              ┌──────────────────┐
    │     Grafana      │              │   llama.cpp      │
    │  (Dashboards)    │              │  (AI Analysis)   │
    │  Node 1          │              │  Node 2          │
    │  /grafana        │              │  llm namespace   │
    └────────┬─────────┘              └──────────────────┘
             │
             ▼
    ┌──────────────────┐
    │       Loki       │
    │  (Log Storage)   │
    │     Node 2       │
    │  logging ns      │
    └────────┬─────────┘
             ▲
             │
    ┌────────┴─────────┐
    │  Grafana Alloy   │
    │  (Log Collector) │
    │  Both Nodes      │
    │  DaemonSet       │
    └──────────────────┘
```

---

## Architecture Components

### Node 1 (Control Plane + UI Layer)

**Hardware:** Intel Core i7-8700 (6 cores, 12 threads), 32GB RAM

**Workloads:**
- Kubernetes control plane (API server, scheduler, controller-manager)
- Envoy Gateway (HTTP/HTTPS ingress)
- Grafana (visualization and dashboards)
- Grafana Alloy (log collection agent)

**Why Node 1?**
- Lighter workloads keep control plane responsive
- UI services benefit from stable, low-latency environment
- Separation prevents LLM inference from impacting cluster operations

### Node 2 (Compute + Storage Layer)

**Hardware:** Intel Core i7-12700T (12 cores, 20 threads), 94GB RAM, 2x NVMe drives

**Storage:**
- **Primary NVMe (Sabrent 954GB):** OS and system files
- **Secondary NVMe (Samsung 477GB):** `/mnt/k8s-storage` - dedicated for workloads
  - Loki log chunks and indices
  - LLM models
  - Vector database (planned)

**Workloads:**
- Loki (log storage and query engine)
- llama.cpp (LLM inference server)
- Grafana Alloy (log collection agent)
- Future: Chroma vector DB, embedding models

**Why Node 2?**
- High core count (12 physical cores) excellent for LLM inference
- AVX_VNNI CPU instructions accelerate neural network operations
- Large memory (94GB) supports multiple AI workloads
- Dedicated NVMe eliminates I/O contention between OS and workloads

---

## Interactive Demo

### 1. Cluster Overview

#### Check Node Status and Labels

```bash
# View nodes with labels
kubectl get nodes --show-labels

# Expected output:
# node-1   Ready    control-plane,master   hardware=light
# node-2   Ready    <none>                 hardware=heavy
```

**What to observe:**
- Node 1 has `control-plane` and `master` roles
- Node 2 has `hardware=heavy` label (for workload targeting)

#### View Node Resources

```bash
# Detailed node information
kubectl describe node node-1
kubectl describe node node-2

# Quick resource view
kubectl top nodes
```

**Key metrics:**
- Node 1: Lower CPU usage (control plane + UI)
- Node 2: Higher CPU usage (LLM + Loki)

#### Check Taints and Tolerations

```bash
# Node 2 should have heavy taint to prevent general workloads
kubectl get node node-2 -o json | jq '.spec.taints'
```

**Expected:**
```json
[
  {
    "effect": "NoSchedule",
    "key": "heavy",
    "value": "true"
  }
]
```

**Why?** Ensures only LLM and storage workloads (with matching tolerations) run on Node 2.

---

### 2. Envoy Gateway Deep Dive

**Purpose:** Modern, production-grade API gateway for HTTP/HTTPS routing with advanced features like traffic splitting, header manipulation, and TLS termination.

#### Check Envoy Gateway Status

```bash
# Envoy Gateway deployment
kubectl get deployment -n envoy-gateway-system

# Gateway classes available
kubectl get gatewayclass

# Active gateways
kubectl get gateway -A
```

#### View Envoy Configuration

```bash
# Envoy pods (data plane)
kubectl get pods -n envoy-gateway-system

# Check logs
kubectl logs -n envoy-gateway-system -l gateway.envoyproxy.io/owning-gateway-name=eg --tail=50
```

#### Test HTTPRoute for Grafana

```bash
# View HTTPRoute configuration
kubectl get httproute -A
kubectl describe httproute grafana-route -n default

# Access Grafana via gateway
curl -I http://10.0.0.102/grafana
```

**Expected:** 302 redirect to login page

#### Why Envoy Gateway?

**Advantages over Traefik/Nginx:**
- **Gateway API:** Kubernetes-native, role-oriented configuration
- **Extensibility:** WebAssembly filters, ext_authz, rate limiting
- **Performance:** Envoy's battle-tested proxy (used by Istio, Ambassador)
- **Advanced routing:** Header-based routing, traffic mirroring, retries
- **Observability:** Rich metrics, tracing integration

**Key Features We Use:**
- **HTTPRoute:** Path-based routing (`/grafana` → Grafana service)
- **LoadBalancer:** K3s servicelb exposes gateway on node IP
- **Namespace routing:** Cross-namespace service access

---

### 3. Logging Stack (Grafana Alloy → Loki → Grafana)

**Architecture:** Modern replacement for deprecated Promtail → unified collection agent.

#### Check Grafana Alloy DaemonSet

```bash
# Alloy running on all nodes
kubectl get daemonset -n logging

# Pods (should be 2 - one per node)
kubectl get pods -n logging -l app.kubernetes.io/name=alloy

# Check logs from Node 2's collector
kubectl logs -n logging -l app.kubernetes.io/name=alloy --tail=20 | grep "component started"
```

**What Alloy does:**
- Discovers pods via Kubernetes API
- Tails container logs from `/var/log/pods`
- Labels logs with namespace, pod, container metadata
- Ships to Loki with batching and compression

#### Inspect Loki Deployment

```bash
# Loki pods on Node 2
kubectl get pods -n logging -l app.kubernetes.io/name=loki -o wide

# Check node placement
kubectl get pod -n logging -l app.kubernetes.io/name=loki -o jsonpath='{.items[0].spec.nodeName}'

# Loki storage (PVC on Node 2's NVMe)
kubectl get pvc -n logging
```

#### Query Loki

```bash
# Port-forward Loki
kubectl port-forward -n logging svc/loki 3100:3100

# Query all logs (last 1 hour)
curl -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode "query={namespace=\"logging\"}" \
  --data-urlencode "start=$(date -u -v-1H +%s)000000000" \
  --data-urlencode "end=$(date -u +%s)000000000" | jq '.data.result[0].values[0:3]'

# Query error logs
curl -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={job=~".+"} |~ "(?i)error"' \
  --data-urlencode "limit=10" | jq '.data.result | length'
```

#### Access Grafana UI

```bash
# Open Grafana (via Envoy Gateway)
# Browser: http://10.0.0.102/grafana
# Default credentials: admin/admin (first login prompts for password change)
```

**Demo flow in Grafana:**
1. Go to **Explore**
2. Select **Loki** data source
3. Try LogQL queries:
   ```
   {namespace="logging"}
   {namespace="llm"} |= "llama"
   {job=~".+"} |~ "(?i)(error|warn)"
   ```
4. View log volume over time
5. Filter by namespace, pod, severity

#### Why This Stack?

**Grafana Alloy vs Promtail:**
- **Unified agent:** Logs, metrics, traces in one component
- **Better performance:** Native compression, smarter batching
- **Future-proof:** Active development (Promtail EOL March 2026)
- **Flexibility:** OpenTelemetry support built-in

**Loki Design:**
- **Cost-effective:** Index only metadata (not full log content)
- **Kubernetes-native:** Automatic label extraction from K8s
- **Fast queries:** Time-series based, not full-text search
- **Scalable:** Horizontal scaling via microservices mode (future)

---

### 4. LLM Inference Server (llama.cpp)

**Purpose:** CPU-optimized LLM serving for log analysis, extraction, and troubleshooting recommendations.

#### Check llama.cpp Deployment

```bash
# Pod status in llm namespace
kubectl get pods -n llm

# Verify Node 2 placement
kubectl get pod -n llm -l app=llama-cpp -o wide

# Resource usage
kubectl top pod -n llm
```

**Expected CPU:** 10-14 cores actively used during inference

#### Inspect Configuration

```bash
# Deployment configuration
kubectl get deployment llama-cpp -n llm -o yaml | grep -A 5 "args:"

# PersistentVolume (model storage)
kubectl get pv | grep llama

# Check volume mounted correctly
kubectl exec -n llm -l app=llama-cpp -- ls -lh /models/
```

**Expected:** `llama-3.2-3b-instruct-q4_k_m.gguf` (~1.9GB)

#### Test LLM Inference

**Health check:**
```bash
kubectl run test-curl -n llm --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/health
```

**Model info:**
```bash
kubectl run test-curl -n llm --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/v1/models | jq
```

**Chat completion (Kubernetes troubleshooting):**
```bash
kubectl run test-curl -n llm --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a Kubernetes expert. Be concise."},
      {"role": "user", "content": "What causes ImagePullBackOff errors?"}
    ],
    "max_tokens": 150,
    "temperature": 0.5
  }' | jq -r '.choices[0].message.content'
```

**Performance test:**
```bash
# Note the tokens/sec in the response
kubectl run test-curl -n llm --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Explain Kubernetes pod lifecycle phases."}
    ],
    "max_tokens": 200
  }' | jq '.timings.predicted_per_second'
```

**Expected:** ~18-20 tokens/sec

#### View LLM Logs

```bash
# Model loading and startup
kubectl logs -n llm -l app=llama-cpp --tail=100 | grep -E "(model|llama server listening)"

# Real-time inference logs
kubectl logs -n llm -l app=llama-cpp -f
```

#### Why llama.cpp?

**Technology Choice:**
- **CPU-optimized:** No GPU required, uses AVX_VNNI instructions
- **Quantized models:** Q4_K_M format reduces memory (1.9GB vs 6GB for full precision)
- **OpenAI-compatible API:** Drop-in replacement for OpenAI client libraries
- **Fast inference:** 19.75 tok/s on Node 2's i7-12700T (competitive with cloud GPUs for small models)
- **Production-ready:** Metrics endpoint, health checks, concurrent request handling

**Model Choice (Llama 3.2 3B):**
- **Size:** 3 billion parameters - good balance of capability vs speed
- **Quality:** Meta's Instruct-tuned variant - strong instruction following
- **Specialization:** General reasoning suitable for log analysis
- **Performance:** 150-token response in ~7-8 seconds (excellent UX)

**Deployment Design:**
- **Dedicated namespace:** Clean isolation from infrastructure
- **Resource limits:** 10-14 CPU cores, 6-10GB memory (tuned to benchmarks)
- **Local storage:** Model on Node 2's NVMe (fast loading, no network dependency)
- **Tolerations:** Ensures scheduling only on Node 2's high-performance hardware

---

### 5. Golden Dataset Pipeline

**Purpose:** Generate high-quality, diverse log samples for evaluating LLM extraction accuracy.

#### Dataset Scripts Location

```bash
ls -lh scripts/
```

**Files:**
- `extract_golden_dataset.py` - Extract real logs from Loki
- `synthesize_logs.py` - Generate synthetic logs from templates
- `combine_datasets.py` - Merge real + synthetic with target distribution
- `dataset_analysis.py` - Quality analysis and reporting
- `log_templates.json` - 30+ K8s failure scenario templates

#### Run Dataset Extraction (Demo)

```bash
# Requires Loki port-forward
kubectl port-forward -n logging svc/loki 3100:3100

# Extract real logs (in another terminal)
cd /path/to/k8s-log-agent
uv run python scripts/extract_golden_dataset.py
```

**What it does:**
1. Queries Loki with 15 targeted LogQL filters (errors, warnings, failures)
2. Filters out noise (CoreDNS warnings, routine Envoy logs)
3. Detects severity (INFO/WARN/ERROR/CRITICAL)
4. Deduplicates by error signature
5. Stratified sampling to meet target distribution
6. Outputs: `golden_dataset_real.json`

#### Generate Synthetic Logs

```bash
uv run python scripts/synthesize_logs.py
```

**What it does:**
- Loads 30+ templates (CrashLoopBackOff, OOMKilled, ImagePullBackOff, etc.)
- Randomizes values (IPs, pod names, timestamps, namespaces)
- Pre-fills ground truth labels from templates
- Outputs: `golden_dataset_synthetic.json`

#### Combine Datasets

```bash
uv run python scripts/combine_datasets.py
```

**Target distribution:**
- 25% INFO (37 logs)
- 25% WARN (38 logs)
- 40% ERROR (60 logs)
- 10% CRITICAL (15 logs)
- **Total:** 150 logs

#### Analyze Dataset Quality

```bash
uv run python scripts/dataset_analysis.py
```

**Reports:**
- Severity distribution vs targets
- Failure category coverage
- Namespace/component diversity
- Labeling completeness
- Sample previews

#### Why This Approach?

**Hybrid Strategy:**
- **Real logs:** Capture actual production patterns, edge cases, multi-line errors
- **Synthetic logs:** Fill gaps in rare failures (OOMKilled, RBAC denials, cert errors)
- **Balanced distribution:** Prevents model bias toward common log types

**Quality Techniques:**
- **Noise filtering:** Removes 60-70% of low-value logs (success messages, routine warnings)
- **Intelligent deduplication:** Groups similar errors by signature, keeps 1-2 examples
- **Stratified sampling:** Ensures representative distribution across severity levels

**Use Cases:**
- Evaluate LLM extraction accuracy (root cause, severity, component identification)
- Benchmark RAG retrieval quality (can the system find relevant logs?)
- Test prompt variations (which system prompt produces best results?)
- Detect model drift (performance degradation over time)

---

## Design Rationale

### Two-Node Architecture

**Why not single-node?**
- **Workload isolation:** LLM inference is CPU-intensive; separating from control plane prevents starvation
- **Storage optimization:** Node 2's dual NVMe setup dedicates fast storage to I/O workloads (Loki, vector DB)
- **Realistic topology:** Mirrors production multi-node clusters (better learning experience)
- **Horizontal scaling:** Architecture supports adding more nodes in the future

**Why not three+ nodes?**
- **Cost/power:** Homelab constraints favor efficient resource usage
- **Sufficient capacity:** 32GB + 94GB RAM, 18 + 20 CPU threads handles current workload
- **K3s benefits:** Lightweight distribution works well at small scale

### Namespace Design

```
default          - General K8s resources, HTTPRoutes
envoy-gateway-system - Gateway control plane + data plane
logging          - Loki, Grafana, Alloy
llm              - llama.cpp, future: Chroma, embeddings
kube-system      - Kubernetes core components
```

**Rationale:**
- **Isolation:** Failure in one namespace doesn't cascade
- **RBAC:** Fine-grained access control per namespace
- **Resource quotas:** Can limit CPU/memory per namespace (future)
- **Organization:** Clear separation of concerns (infra vs ML vs observability)

### Storage Strategy

**Node 1:** No persistent workloads (ephemeral control plane)

**Node 2:**
- **OS drive (Sabrent NVMe):** System files, K8s binaries, temporary data
- **/mnt/k8s-storage (Samsung NVMe):** Persistent workload data
  - Loki chunks and indices
  - LLM models (1.9GB Llama 3.2 3B)
  - Future: Vector database, embeddings cache

**Why separate drives?**
- **I/O isolation:** Loki writes don't contend with OS reads
- **Performance:** Dedicated NVMe for workloads improves query latency
- **Data safety:** Can wipe/rebuild OS without losing workload data
- **Clear paths:** `/mnt/k8s-storage/models`, `/mnt/k8s-storage/loki` (easy backups)

### Technology Choices

| Component | Choice | Alternative Considered | Rationale |
|-----------|--------|------------------------|-----------|
| **Gateway** | Envoy Gateway | Traefik, Nginx Ingress | Gateway API standard, advanced features, production-proven Envoy proxy |
| **Log collection** | Grafana Alloy | Promtail, Fluent Bit | Unified agent (logs+metrics+traces), Promtail EOL, better performance |
| **Log storage** | Loki | Elasticsearch, ClickHouse | K8s-native labels, cost-effective, simpler ops, Grafana integration |
| **LLM runtime** | llama.cpp | Ollama, vLLM, TGI | CPU-optimized, quantization support, minimal dependencies, OpenAI API |
| **Model** | Llama 3.2 3B Q4_K_M | Llama 3.2 1B, Qwen 2.5, Phi-3 | Balance of quality vs speed, Meta's strong instruction tuning |
| **Vector DB** | Chroma (planned) | Qdrant, Weaviate, Milvus | Simplicity, Python-native, good embeddings support |
| **Embeddings** | BGE-small (planned) | E5-small, MiniLM | Better retrieval quality, same performance tier |

---

## Performance Metrics

### LLM Inference (llama.cpp)

**Benchmark Results (Node 2):**
- **Model:** Llama 3.2 3B Instruct Q4_K_M
- **Prompt processing:** 94.58 tok/s (512 tokens)
- **Text generation:** 19.75 tok/s (128 tokens)
- **Real-world latency:**
  - 100 token response: ~5 seconds
  - 200 token response: ~10 seconds
  - 300 token log analysis: ~15 seconds

**CPU Optimization:**
- **Instructions used:** AVX2, AVX_VNNI, FMA, BMI2
- **Threads:** 14 (tuned for i7-12700T's P-cores)
- **Parallel requests:** 2 concurrent
- **Memory:** ~2.5GB (model + KV cache + buffers)

### Logging Pipeline

**Alloy Collection:**
- **Targets:** ~20-30 pods across 2 nodes
- **Throughput:** ~1000-5000 log lines/min (varies by activity)
- **Overhead:** ~50-100MB memory per DaemonSet pod
- **Batching:** 1MB batches, 10s flush interval

**Loki Storage:**
- **Index:** Label-based (namespace, pod, container, node)
- **Compression:** ~10:1 ratio (varies by log content)
- **Query latency:** <500ms for 1-hour range (hot cache)
- **Retention:** 30 days (configurable)

**Grafana Queries:**
- **LogQL processing:** Real-time filtering, aggregation
- **Dashboard refresh:** 5-30s intervals
- **Explore latency:** <1s for simple queries, <5s for complex aggregations

### Network

**Cross-node traffic:**
- **Alloy → Loki:** ~1-5 Mbps (compressed log shipping)
- **Grafana → Loki:** Burst ~10-50 Mbps during queries
- **Client → Envoy → Services:** <1 Mbps (UI access)

**Intra-node (Node 2):**
- **Loki → NVMe:** ~50-200 MB/s writes (chunk flush)
- **llama.cpp → NVMe:** 1.9GB model load in ~2-3 seconds

---

## Demo Script (5-Minute Walkthrough)

**For showcasing the system to others:**

### 1. Cluster Overview (30 seconds)

```bash
kubectl get nodes -o wide
kubectl get pods --all-namespaces -o wide | head -20
```

**Talk track:** "Two-node cluster. Node 1 runs control plane + UI. Node 2 runs compute-heavy workloads (Loki, LLM). Notice pod distribution aligns with node capabilities."

### 2. Gateway Routing (1 minute)

```bash
# Show HTTPRoute
kubectl get httproute -A
kubectl describe httproute grafana-route -n default

# Access Grafana
echo "Open browser: http://10.0.0.102/grafana"
```

**Talk track:** "Envoy Gateway routes traffic. HTTPRoute sends `/grafana` to Grafana service. Gateway API is the future of K8s ingress."

### 3. Logging Stack (1.5 minutes)

```bash
# Show components
kubectl get all -n logging

# Query Loki
kubectl port-forward -n logging svc/loki 3100:3100 &
curl -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="llm"} |= "llama"' | jq '.data.result[0].values[0:3]'
```

**In Grafana:**
- Navigate to Explore → Loki
- Query: `{namespace="llm"}` → Show real-time LLM logs
- Query: `{job=~".+"} |~ "(?i)error"` → Filter errors cluster-wide

**Talk track:** "Alloy collects logs from all pods. Loki stores with label indices. Grafana provides query UI. This is production-grade observability."

### 4. LLM Inference (2 minutes)

```bash
# Show deployment
kubectl get pod -n llm -o wide
kubectl top pod -n llm

# Test inference
kubectl run test-curl -n llm --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a Kubernetes expert."},
      {"role": "user", "content": "Explain why a pod might be in CrashLoopBackOff."}
    ],
    "max_tokens": 150
  }' | jq -r '.choices[0].message.content'
```

**Talk track:** "Running Llama 3.2 3B on CPU. 19 tokens/sec with AVX_VNNI optimization. OpenAI-compatible API. This will power log analysis and troubleshooting recommendations. Watch the CPU spike to ~12 cores during inference."

### 5. Golden Dataset (30 seconds)

```bash
ls -lh scripts/
cat scripts/log_templates.json | jq '.templates[0:3]'
```

**Talk track:** "Hybrid approach: extract real logs from Loki, generate synthetic logs for rare failures. 150 labeled samples for evaluating LLM accuracy. This is how we'll measure extraction quality and iterate on prompts."

---

## Next Steps

**Completed (Phase 1-3):**
- ✅ Two-node K3s cluster with workload placement
- ✅ Envoy Gateway with HTTPRoute routing
- ✅ Grafana + Loki + Alloy logging stack
- ✅ llama.cpp LLM inference server
- ✅ Golden dataset generation pipeline

**In Progress (Phase 3):**
- 🔄 Chroma vector database deployment
- 🔄 BGE-small embedding model deployment
- 🔄 Evaluation framework (test LLM against golden dataset)

**Upcoming (Phase 4-5):**
- FastAPI log analyzer service
- RAG pipeline (retrieval-augmented generation)
- Structured extraction prompts
- End-to-end log triage and summarization
- Grafana dashboards for LLM insights

**Future Enhancements:**
- OpenTelemetry traces integration
- Drift detection (monitor LLM accuracy over time)
- Alert integration (route critical logs to LLM for auto-triage)
- Multi-model support (switch between 1B/3B/7B based on complexity)

---

## Useful Commands Reference

### Cluster Management

```bash
# Node status
kubectl get nodes -o wide
kubectl describe node <node-name>
kubectl top nodes

# All resources
kubectl get all --all-namespaces
kubectl get pods --all-namespaces -o wide

# Events
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | tail -20
```

### Debugging

```bash
# Pod logs
kubectl logs -n <namespace> <pod-name> --tail=100 -f

# Pod shell
kubectl exec -n <namespace> <pod-name> -it -- /bin/sh

# Describe resource
kubectl describe pod -n <namespace> <pod-name>

# Resource usage
kubectl top pod -n <namespace>
```

### Port Forwarding

```bash
# Loki
kubectl port-forward -n logging svc/loki 3100:3100

# Grafana
kubectl port-forward -n default svc/grafana 3000:3000

# llama.cpp
kubectl port-forward -n llm svc/llama-cpp 8080:8080
```

### Quick Tests

```bash
# Create test pod
kubectl run test-curl -n <namespace> --rm -it --image=curlimages/curl -- sh

# One-shot curl
kubectl run test-curl -n <namespace> --rm -it --image=curlimages/curl -- \
  curl -v http://<service>:<port>/path
```

---

**Document maintained by:** Trey Shanks
**Last updated:** December 2025
**Project:** k8s-log-agent
**Status:** Phase 3 in progress
