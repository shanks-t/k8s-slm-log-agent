# Infrastructure Roadmap: Flux GitOps Migration for K3s Homelab

**Status:** Planning → Implementation Ready
**Last Updated:** 2025-12-27
**Goal:** Migrate existing K3s homelab from imperative management to declarative Flux-based GitOps

---

## Table of Contents

1. [Purpose & End State](#purpose--end-state)
2. [Conceptual Model](#conceptual-model)
3. [Current Cluster Inventory](#current-cluster-inventory)
4. [Migration Plan (10 Steps)](#migration-plan-10-steps)
5. [Repository Structure](#repository-structure)
6. [Step-by-Step Implementation](#step-by-step-implementation)
7. [Validation & Testing](#validation--testing)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Resources](#resources)

---

## Purpose & End State

### Purpose

This roadmap outlines the migration of an existing K3s homelab cluster—currently managed imperatively with `kubectl` and Helm—into a fully declarative, reproducible system managed by Flux.

### End State

A cluster where:

- ✅ **Git is the single source of truth**
- ✅ **Flux continuously reconciles cluster state from Git**
- ✅ **The cluster can be wiped and rebuilt with minimal manual steps**
- ✅ **No inbound internet access required** (pull-based model)
- ✅ **Persistent data loss is acceptable** (observability data is ephemeral)

### Benefits

1. **Disaster Recovery:** Full cluster rebuild in ~15-20 minutes via `flux bootstrap`
2. **Audit Trail:** Every change is a Git commit (who, what, when, why)
3. **Declarative State:** No more "what's actually running?" questions
4. **Reproducibility:** Clone repo → bootstrap → working cluster
5. **Version Control:** Rollback any change with `git revert`
6. **GitOps Best Practices:** Production-grade patterns for homelab learning

---

## Conceptual Model

Flux operates using a **pull-based GitOps model**:

```
┌─────────────────────┐
│   Git Repository    │  ← Desired state (YAML manifests)
│   (GitHub/GitLab)   │     Single source of truth
└──────────┬──────────┘
           │
           │ Flux polls every 1-5 minutes
           │ (cluster initiates connection)
           │
           ▼
┌─────────────────────┐
│   Flux Controllers  │  ← Running in K3s cluster
│   (in flux-system)  │     source-controller
└──────────┬──────────┘     kustomize-controller
           │                helm-controller
           │ Applies changes
           │
           ▼
┌─────────────────────┐
│   K3s Cluster       │  ← Actual state
│   (Node 1 + 2)      │     Converges to Git state
└─────────────────────┘
```

**Key Properties:**

- **No inbound connections:** GitHub never connects to your cluster
- **Drift prevention:** Manual `kubectl` edits get reverted by Flux
- **Self-healing:** If a pod crashes, Flux ensures it comes back matching Git
- **Works anywhere:** Private homelabs, on-prem clusters, air-gapped environments

**Reference:** [Flux Core Concepts](https://fluxcd.io/flux/concepts/)

---

## Current Cluster Inventory

### Namespaces (8 total)

```
default                   # Default namespace (unused)
envoy-gateway-system      # Envoy Gateway ingress controller
kube-node-lease           # K8s internal
kube-public               # K8s internal
kube-system               # K8s control plane + K3s components
llm                       # LLM inference services
log-analyzer              # Log analysis FastAPI service
logging                   # Observability stack (Loki, Grafana, Tempo, Alloy)
```

### Helm-Managed Applications (5 total)

| Release | Namespace | Chart | Version | Notes |
|---------|-----------|-------|---------|-------|
| `eg` | envoy-gateway-system | gateway-helm | v1.4.6 | Ingress controller |
| `alloy` | logging | alloy | 1.4.0 | Log collection (DaemonSet) |
| `grafana` | logging | grafana | 10.2.0 | Dashboarding UI |
| `loki` | logging | loki | 6.21.0 | Log storage and query |
| `tempo` | logging | tempo | 1.24.1 | Distributed tracing |

**Action Required:** Convert to Flux HelmReleases

### YAML-Managed Workloads (2 total)

| Name | Namespace | Type | Image | Notes |
|------|-----------|------|-------|-------|
| `llama-cpp` | llm | Deployment | ghcr.io/ggml-org/llama.cpp:server | LLM inference server |
| `log-analyzer` | log-analyzer | Deployment | docker.io/library/log-analyzer:latest | FastAPI log analysis |

**Action Required:** Export manifests, commit to Git

### Persistent Volumes (4 total)

| PVC | Namespace | Size | Bound To | Data Type |
|-----|-----------|------|----------|-----------|
| `llama-models-pvc` | llm | 20Gi | llama-models-pv | LLM model files |
| `storage-loki-0` | logging | 200Gi | loki-pv | Log chunks and indexes |
| `storage-tempo-0` | logging | 50Gi | PV (dynamic) | Trace data |
| `tempo-pvc` | logging | 50Gi | tempo-pv | Trace data |

**Data Loss Policy:** ✅ Acceptable (models can be re-downloaded, logs/traces are ephemeral)

### Storage Classes

- **local-path** (default): K3s built-in local path provisioner
  - Uses host filesystem: `/var/lib/rancher/k3s/storage/`
  - No replication, no HA
  - Suitable for homelab

### Total Workload Count

- **13 workloads** total (Deployments + StatefulSets + DaemonSets)
- Mix of Helm-managed and YAML-managed

### Missing Infrastructure (To Be Added)

- **Container Registry:** Need local registry for log-analyzer images
  - Will be added during migration as infrastructure component

---

## Migration Plan (10 Steps)

### Overview

| Step | Phase | Estimated Time | Risk Level |
|------|-------|---------------|------------|
| 1. Inventory | Discovery | 1 hour | Low |
| 2. Export State | Backup | 2 hours | Low |
| 3. Clean Manifests | Preparation | 3-4 hours | Medium |
| 4. Define Repository | Setup | 2 hours | Low |
| 5. Convert Helm | Migration | 3-4 hours | Medium |
| 6. Secrets Strategy | Security | 1 hour | Low |
| 7. Bootstrap Flux | Installation | 1 hour | Medium |
| 8. Define Reconciliation | Configuration | 2 hours | Medium |
| 9. Migrate Incrementally | Deployment | 4-6 hours | High |
| 10. Validate Rebuild | Testing | 2-3 hours | High |

**Total Estimated Time:** 20-30 hours (spread over 1-2 weeks)

---

## Repository Structure

### Final Git Repository Layout

```
k8s-slm-log-agent/
├── .gitignore
├── README.md
├── agents.md
├── infra-roadmap.md
│
├── clusters/
│   └── homelab/                          # Cluster-specific entry point
│       ├── flux-system/                  # Flux self-management (auto-generated)
│       │   ├── gotk-components.yaml      # Flux controllers
│       │   ├── gotk-sync.yaml            # Git sync config
│       │   └── kustomization.yaml
│       │
│       ├── infrastructure.yaml           # Root kustomization for infra
│       └── workloads.yaml                # Root kustomization for apps
│
├── infrastructure/                       # Platform services
│   ├── kustomization.yaml                # Infra root
│   │
│   ├── sources/                          # Helm repositories
│   │   ├── kustomization.yaml
│   │   ├── grafana-charts.yaml           # HelmRepository: grafana.github.io
│   │   ├── prometheus-charts.yaml        # HelmRepository: prometheus-community
│   │   └── envoyproxy-charts.yaml        # HelmRepository: gateway.envoyproxy.io
│   │
│   ├── controllers/                      # Cluster controllers
│   │   ├── kustomization.yaml
│   │   └── envoy-gateway/
│   │       ├── namespace.yaml
│   │       └── helmrelease.yaml
│   │
│   ├── logging/                          # Observability stack
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── loki-helmrelease.yaml
│   │   ├── grafana-helmrelease.yaml
│   │   ├── tempo-helmrelease.yaml
│   │   └── alloy-helmrelease.yaml
│   │
│   └── storage/                          # Storage infrastructure
│       ├── kustomization.yaml
│       ├── llama-pv.yaml                 # PersistentVolume for models
│       ├── loki-pv.yaml                  # PersistentVolume for logs
│       └── tempo-pv.yaml                 # PersistentVolume for traces
│
├── workloads/                            # Application workloads
│   ├── kustomization.yaml                # Workloads root
│   │
│   ├── llm/                              # LLM inference
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── llama-pvc.yaml
│   │   ├── llama-deployment.yaml
│   │   └── llama-service.yaml
│   │
│   └── log-analyzer/                     # Log analysis service
│       ├── kustomization.yaml
│       ├── namespace.yaml
│       ├── configmap.yaml
│       ├── deployment.yaml
│       └── service.yaml
│
├── workloads-legacy/                     # Temporary: old manifests
│   └── log-analyzer/
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── README.md
│       └── src/
│
└── scripts/                              # Helper scripts
    ├── export-cluster-state.sh
    ├── clean-manifests.sh
    └── validate-rebuild.sh
```

### Key Design Principles

1. **Separation of Concerns:**
   - `infrastructure/` = platform-level services
   - `workloads/` = application-level services

2. **Explicit Namespaces:**
   - Every resource group declares its namespace
   - No implicit defaults

3. **Kustomize Composition:**
   - Root kustomizations reference subdirectories
   - Allows layering and patching

4. **Flux Entry Points:**
   - `clusters/homelab/infrastructure.yaml`
   - `clusters/homelab/workloads.yaml`
   - These are the only files Flux watches

5. **Self-Documenting:**
   - Directory structure reflects cluster architecture
   - Anyone can understand the system by reading the tree

---

## Step-by-Step Implementation

### Step 1: Inventory the Existing Cluster

**Goal:** Understand current cluster state before making changes.

**Actions:**

```bash
# 1.1 List all namespaces
kubectl get namespaces -o name > inventory/namespaces.txt

# 1.2 List all Helm releases
helm list -A -o yaml > inventory/helm-releases.yaml

# 1.3 List all non-Helm workloads
kubectl get deployments,statefulsets,daemonsets -A -o yaml > inventory/workloads.yaml

# 1.4 List all services
kubectl get services -A -o yaml > inventory/services.yaml

# 1.5 List all persistent volumes and claims
kubectl get pv,pvc -A -o yaml > inventory/storage.yaml

# 1.6 List all CRDs
kubectl get crd -o name > inventory/crds.txt

# 1.7 List all storage classes
kubectl get storageclass -o yaml > inventory/storageclasses.yaml

# 1.8 Export Helm values for each release
helm get values eg -n envoy-gateway-system > inventory/helm-values-envoy-gateway.yaml
helm get values alloy -n logging > inventory/helm-values-alloy.yaml
helm get values grafana -n logging > inventory/helm-values-grafana.yaml
helm get values loki -n logging > inventory/helm-values-loki.yaml
helm get values tempo -n logging > inventory/helm-values-tempo.yaml
```

**Deliverable:**
- `inventory/` directory with complete cluster state snapshot
- Reference documentation for comparison during migration

**Estimated Time:** 1 hour

**Reference:** [Kubernetes kubectl Cheatsheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

---

### Step 2: Export Current Cluster State

**Goal:** Export all resources as YAML for review and refactoring.

**Actions:**

```bash
# 2.1 Create export directory structure
mkdir -p exports/{infrastructure,workloads}/{controllers,logging,llm,log-analyzer}

# 2.2 Export llm namespace resources
kubectl get all,configmap,secret,pvc -n llm -o yaml > exports/workloads/llm/all-resources.yaml

# 2.3 Export log-analyzer namespace resources
kubectl get all,configmap,secret,pvc -n log-analyzer -o yaml > exports/workloads/log-analyzer/all-resources.yaml

# 2.4 Export logging namespace resources (non-Helm managed)
kubectl get configmap,secret,pvc -n logging -o yaml > exports/infrastructure/logging/config-and-storage.yaml

# 2.5 Export envoy-gateway namespace resources (non-Helm managed)
kubectl get configmap,secret -n envoy-gateway-system -o yaml > exports/infrastructure/controllers/envoy-config.yaml

# 2.6 Export PersistentVolumes
kubectl get pv -o yaml > exports/infrastructure/storage/persistent-volumes.yaml

# 2.7 Export StorageClasses
kubectl get storageclass -o yaml > exports/infrastructure/storage/storage-classes.yaml
```

**Deliverable:**
- `exports/` directory with raw YAML exports
- Contains runtime metadata and status fields (will be cleaned in Step 3)

**Estimated Time:** 2 hours

**Reference:** [kubectl get Output Options](https://kubernetes.io/docs/reference/kubectl/cheatsheet/#formatting-output)

---

### Step 3: Normalize and Clean Manifests

**Goal:** Convert exported manifests into clean, declarative desired state.

**Actions:**

**3.1 Remove Generated Fields**

Fields to remove from exported YAML:
- `metadata.creationTimestamp`
- `metadata.generation`
- `metadata.resourceVersion`
- `metadata.uid`
- `metadata.selfLink`
- `metadata.managedFields`
- `metadata.annotations` (except user-defined ones)
- `status` (entire section)

**3.2 Split Resources into Separate Files**

Best practice: One resource type per file

```bash
# Example: Split llm namespace export
# Input: exports/workloads/llm/all-resources.yaml (contains Deployment, Service, PVC, etc.)
# Output: infrastructure/storage/llama-pvc.yaml
#         workloads/llm/llama-deployment.yaml
#         workloads/llm/llama-service.yaml
```

**3.3 Specific Resources to Clean**

**LLaMA Deployment:**
```bash
# Export clean version
kubectl get deployment llama-cpp -n llm -o yaml \
  | yq eval 'del(.metadata.creationTimestamp, .metadata.generation, .metadata.resourceVersion, .metadata.uid, .metadata.managedFields, .status)' - \
  > workloads/llm/llama-deployment.yaml

# Manually review and ensure:
# - Node selector: hardware=heavy
# - Image: ghcr.io/ggml-org/llama.cpp:server (pin version!)
# - Resources: CPU and memory limits
# - Volume mounts correct
```

**Log-Analyzer Deployment:**
```bash
# Export clean version
kubectl get deployment log-analyzer -n log-analyzer -o yaml \
  | yq eval 'del(.metadata.creationTimestamp, .metadata.generation, .metadata.resourceVersion, .metadata.uid, .metadata.managedFields, .status)' - \
  > workloads/log-analyzer/deployment.yaml

# Manually review and ensure:
# - Node selector: hardware=light
# - Image: docker.io/library/log-analyzer:latest (consider versioning)
# - ConfigMap references
# - Health checks
```

**PersistentVolumes:**
```bash
# Export PVs (need manual cleanup)
kubectl get pv llama-models-pv -o yaml \
  | yq eval 'del(.metadata.creationTimestamp, .metadata.resourceVersion, .metadata.uid, .metadata.managedFields, .status)' - \
  > infrastructure/storage/llama-pv.yaml

# Repeat for loki-pv, tempo-pv
```

**3.4 Helm Values Extraction**

For each Helm release, extract custom values (non-default settings):

```bash
# Loki custom values
helm get values loki -n logging > infrastructure/logging/loki-values.yaml

# Review and keep only customizations:
# - persistence settings
# - node selectors
# - resource limits
# - retention policies
```

**3.5 Decision: Managed vs Excluded**

Make explicit decisions for each resource:

| Resource | Decision | Location | Notes |
|----------|----------|----------|-------|
| Envoy Gateway | HelmRelease | infrastructure/controllers/ | Pin version v1.4.6 |
| Loki | HelmRelease | infrastructure/logging/ | Pin version 6.21.0 |
| Grafana | HelmRelease | infrastructure/logging/ | Pin version 10.2.0 |
| Tempo | HelmRelease | infrastructure/logging/ | Pin version 1.24.1 |
| Alloy | HelmRelease | infrastructure/logging/ | Pin version 1.4.0 |
| LLaMA | YAML | workloads/llm/ | Export deployment + service + PVC |
| log-analyzer | YAML | workloads/log-analyzer/ | Export deployment + service + configmap |
| PersistentVolumes | YAML | infrastructure/storage/ | Export llama-pv, loki-pv, tempo-pv |
| Namespaces | YAML | Explicit declaration in each component | |

**Excluded (managed by K3s/Flux):**
- `kube-system` namespace resources (K3s managed)
- `flux-system` namespace (Flux self-managed)
- `kube-public`, `kube-node-lease` (K8s internals)

**Deliverable:**
- Clean, declarative YAML manifests in Git repo structure
- No runtime metadata or controller-generated fields
- Ready for Flux management

**Estimated Time:** 3-4 hours (manual review required)

**Reference:** [Flux Repository Structure Guide](https://fluxcd.io/flux/guides/repository-structure/)

---

### Step 4: Define Repository Structure

**Goal:** Organize Git repository to clearly represent cluster desired state.

**Actions:**

**4.1 Create Directory Structure**

```bash
# Create base structure
mkdir -p clusters/homelab/flux-system
mkdir -p infrastructure/{sources,controllers,logging,storage}
mkdir -p workloads/{llm,log-analyzer}

# Create root kustomization files
touch infrastructure/kustomization.yaml
touch workloads/kustomization.yaml
touch infrastructure/sources/kustomization.yaml
touch infrastructure/controllers/kustomization.yaml
touch infrastructure/logging/kustomization.yaml
touch infrastructure/storage/kustomization.yaml
touch workloads/llm/kustomization.yaml
touch workloads/log-analyzer/kustomization.yaml
```

**4.2 Create Infrastructure Kustomization**

```yaml
# infrastructure/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - sources/
  - storage/
  - logging/
  - controllers/
```

**4.3 Create Workloads Kustomization**

```yaml
# workloads/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - llm/
  - log-analyzer/
```

**4.4 Create Flux Entry Points**

```yaml
# clusters/homelab/infrastructure.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  interval: 10m
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure
  prune: true
  wait: true
```

```yaml
# clusters/homelab/workloads.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: workloads
  namespace: flux-system
spec:
  interval: 5m
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./workloads
  prune: true
  wait: true
  dependsOn:
    - name: infrastructure
```

**4.5 Validate Structure**

```bash
# Check directory tree
tree -L 3 .

# Expected output:
# .
# ├── clusters
# │   └── homelab
# │       ├── infrastructure.yaml
# │       └── workloads.yaml
# ├── infrastructure
# │   ├── controllers
# │   ├── kustomization.yaml
# │   ├── logging
# │   ├── sources
# │   └── storage
# └── workloads
#     ├── kustomization.yaml
#     ├── llm
#     └── log-analyzer
```

**Deliverable:**
- Organized Git repository structure
- Clear separation of infrastructure vs workloads
- Kustomize composition defined
- Flux entry points created

**Estimated Time:** 2 hours

**Reference:** [Flux Repository Structure Guide](https://fluxcd.io/flux/guides/repository-structure/)

---

### Step 5: Convert Helm Installs to Declarative HelmReleases

**Goal:** Replace imperative `helm install` commands with declarative Flux HelmReleases.

**Actions:**

**5.1 Create Helm Repository Sources**

```yaml
# infrastructure/sources/grafana-charts.yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: grafana
  namespace: flux-system
spec:
  interval: 1h
  url: https://grafana.github.io/helm-charts
```

```yaml
# infrastructure/sources/prometheus-charts.yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: prometheus-community
  namespace: flux-system
spec:
  interval: 1h
  url: https://prometheus-community.github.io/helm-charts
```

```yaml
# infrastructure/sources/envoyproxy-charts.yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: envoyproxy
  namespace: flux-system
spec:
  interval: 1h
  url: https://gateway.envoyproxy.io
```

```yaml
# infrastructure/sources/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - grafana-charts.yaml
  - prometheus-charts.yaml
  - envoyproxy-charts.yaml
```

**5.2 Create Loki HelmRelease**

```yaml
# infrastructure/logging/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: logging
```

```yaml
# infrastructure/logging/loki-helmrelease.yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: loki
  namespace: logging
spec:
  interval: 5m
  chart:
    spec:
      chart: loki
      version: '6.21.0'  # Pin to current version
      sourceRef:
        kind: HelmRepository
        name: grafana
        namespace: flux-system
  install:
    createNamespace: false
    remediation:
      retries: 3
  upgrade:
    remediation:
      retries: 3
  values:
    # Paste output from: helm get values loki -n logging
    # Example values (adjust to your actual config):
    loki:
      auth_enabled: false
      commonConfig:
        replication_factor: 1
      storage:
        type: filesystem

    singleBinary:
      replicas: 1
      persistence:
        enabled: true
        storageClass: local-path
        size: 200Gi
      nodeSelector:
        hardware: heavy  # Run on Node 2
      resources:
        requests:
          cpu: 1000m
          memory: 2Gi
        limits:
          cpu: 4000m
          memory: 8Gi

    gateway:
      enabled: false

    monitoring:
      selfMonitoring:
        enabled: false
      lokiCanary:
        enabled: false
```

**5.3 Create Grafana HelmRelease**

```yaml
# infrastructure/logging/grafana-helmrelease.yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: grafana
  namespace: logging
spec:
  interval: 5m
  chart:
    spec:
      chart: grafana
      version: '10.2.0'  # Pin to current version
      sourceRef:
        kind: HelmRepository
        name: grafana
        namespace: flux-system
  values:
    # Paste output from: helm get values grafana -n logging
    # Example values:
    adminPassword: admin  # Change in production!

    persistence:
      enabled: true
      storageClassName: local-path
      size: 10Gi

    nodeSelector:
      hardware: light  # Run on Node 1

    datasources:
      datasources.yaml:
        apiVersion: 1
        datasources:
          - name: Loki
            type: loki
            url: http://loki:3100
            access: proxy
            isDefault: true
          - name: Tempo
            type: tempo
            url: http://tempo:3200
            access: proxy

    service:
      type: ClusterIP
      port: 80
```

**5.4 Create Tempo HelmRelease**

```yaml
# infrastructure/logging/tempo-helmrelease.yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: tempo
  namespace: logging
spec:
  interval: 5m
  chart:
    spec:
      chart: tempo
      version: '1.24.1'  # Pin to current version
      sourceRef:
        kind: HelmRepository
        name: grafana
        namespace: flux-system
  values:
    # Paste output from: helm get values tempo -n logging
    persistence:
      enabled: true
      storageClassName: local-path
      size: 50Gi

    nodeSelector:
      hardware: heavy  # Run on Node 2

    tempo:
      receivers:
        otlp:
          protocols:
            grpc:
              endpoint: 0.0.0.0:4317
            http:
              endpoint: 0.0.0.0:4318
```

**5.5 Create Alloy HelmRelease**

```yaml
# infrastructure/logging/alloy-helmrelease.yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: alloy
  namespace: logging
spec:
  interval: 5m
  chart:
    spec:
      chart: alloy
      version: '1.4.0'  # Pin to current version
      sourceRef:
        kind: HelmRepository
        name: grafana
        namespace: flux-system
  values:
    # Paste output from: helm get values alloy -n logging
    # Alloy runs as DaemonSet on all nodes
    alloy:
      configMap:
        create: true
        content: |
          # Alloy configuration (paste your current config)
```

**5.6 Create Envoy Gateway HelmRelease**

```yaml
# infrastructure/controllers/envoy-gateway-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: envoy-gateway-system
```

```yaml
# infrastructure/controllers/envoy-gateway-helmrelease.yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: eg
  namespace: envoy-gateway-system
spec:
  interval: 5m
  chart:
    spec:
      chart: gateway-helm
      version: 'v1.4.6'  # Pin to current version
      sourceRef:
        kind: HelmRepository
        name: envoyproxy
        namespace: flux-system
  values:
    # Paste output from: helm get values eg -n envoy-gateway-system
    # Default values are usually fine
```

**5.7 Update Kustomizations**

```yaml
# infrastructure/logging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - loki-helmrelease.yaml
  - grafana-helmrelease.yaml
  - tempo-helmrelease.yaml
  - alloy-helmrelease.yaml
```

```yaml
# infrastructure/controllers/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - envoy-gateway-namespace.yaml
  - envoy-gateway-helmrelease.yaml
```

**5.8 Testing (Before Flux)**

```bash
# Validate Kustomize build
kustomize build infrastructure/

# Check for YAML errors
kustomize build infrastructure/ | kubectl apply --dry-run=client -f -
```

**Deliverable:**
- All Helm releases converted to HelmRelease CRDs
- Helm values version-controlled in Git
- Chart versions pinned (no auto-updates until verified)

**Estimated Time:** 3-4 hours (gathering values, testing)

**Reference:** [Flux Helm Controller](https://fluxcd.io/flux/components/helm/)

---

### Step 6: Decide on Secret Management Strategy

**Goal:** Define how secrets will be handled in GitOps (initially simple, room for future encryption).

**Current Assessment:**

Your cluster has minimal secrets:
- Grafana admin password (if customized)
- Potentially registry credentials (if added)
- Potentially API keys for log-analyzer (if added)

**Recommended Approach: Commit Secrets to Private Git Repo (For Now)**

Since:
- ✅ Your repo is private
- ✅ Limited secrets exposure
- ✅ Persistent data loss is acceptable
- ✅ You can rotate secrets easily

You can commit secrets directly to Git initially, with a clear path to SOPS encryption later.

**Actions:**

**6.1 Create Secret Manifests**

```yaml
# infrastructure/logging/grafana-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: grafana-admin
  namespace: logging
type: Opaque
stringData:
  admin-password: "your-password-here"  # Plain text for now
```

**6.2 Update .gitignore (Optional Protection)**

```bash
# .gitignore
# Prevent accidental commit of unencrypted secrets
*-secret.yaml.unencrypted
*.key
*.pem
age.txt
```

**6.3 Document Future SOPS Migration Path**

Create placeholder documentation for when you're ready:

```markdown
# infrastructure/logging/SECRETS.md

## Current State: Plain Text Secrets in Private Repo

Secrets are committed as plain YAML to this private Git repository.

## Future Migration: SOPS Encryption

When ready to encrypt secrets:

1. Install SOPS and age
2. Generate age key
3. Create .sops.yaml config
4. Encrypt existing secrets: `sops -e -i grafana-secret.yaml`
5. Configure Flux decryption provider
6. Test rebuild process

Reference: https://fluxcd.io/flux/guides/mozilla-sops/
```

**6.4 Update HelmRelease to Use Secret**

```yaml
# infrastructure/logging/grafana-helmrelease.yaml
spec:
  values:
    # Remove inline password
    # adminPassword: admin

    # Reference secret instead
    admin:
      existingSecret: grafana-admin
      userKey: admin-user
      passwordKey: admin-password
```

**Deliverable:**
- Secrets committed to private Git repo (acceptable for homelab)
- Clear documentation for future SOPS migration
- No blockers to bootstrapping Flux

**Estimated Time:** 1 hour

**Reference:** [Flux SOPS Guide](https://fluxcd.io/flux/guides/mozilla-sops/) (for future)

---

### Step 7: Bootstrap Flux Into the Cluster

**Goal:** Install Flux controllers and connect them to your Git repository.

**Prerequisites:**

- ✅ Git repository created and pushed (all manifests committed)
- ✅ GitHub personal access token with repo permissions
- ✅ Flux CLI installed: `brew install fluxcd/tap/flux`

**Actions:**

**7.1 Check Prerequisites**

```bash
# Install Flux CLI
brew install fluxcd/tap/flux

# Verify Flux version
flux --version

# Check cluster compatibility
flux check --pre
# Expected output: ✔ Kubernetes version >= 1.26.0
```

**7.2 Set Environment Variables**

```bash
# Set GitHub credentials
export GITHUB_USER=your-github-username
export GITHUB_TOKEN=ghp_your_personal_access_token
export GITHUB_REPO=k8s-slm-log-agent
```

**7.3 Bootstrap Flux**

```bash
# Bootstrap Flux with GitHub
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=$GITHUB_REPO \
  --branch=main \
  --path=clusters/homelab \
  --personal \
  --components-extra=image-reflector-controller,image-automation-controller
```

**What This Does:**

1. ✅ Creates `flux-system` namespace
2. ✅ Installs Flux controllers:
   - source-controller (watches Git)
   - kustomize-controller (applies manifests)
   - helm-controller (manages Helm releases)
   - notification-controller (sends alerts)
   - image-reflector-controller (watches registries)
   - image-automation-controller (auto-updates images)
3. ✅ Creates GitRepository resource pointing to your repo
4. ✅ Creates Kustomization watching `clusters/homelab/`
5. ✅ Commits Flux manifests to Git (`clusters/homelab/flux-system/`)
6. ✅ Starts reconciliation loop

**7.4 Verify Flux Installation**

```bash
# Check Flux components
flux check
# Expected: ✔ All components ready

# Check GitRepository sync
flux get sources git
# Expected: flux-system ready

# Check Kustomizations
flux get kustomizations
# Expected: flux-system ready

# Watch reconciliation (live)
flux logs --follow --level=info
```

**7.5 Verify Git Commits**

```bash
# Flux should have committed to your repo
git pull

# Check flux-system directory
ls -la clusters/homelab/flux-system/
# Expected files:
# - gotk-components.yaml (Flux controllers)
# - gotk-sync.yaml (GitRepository + Kustomization)
# - kustomization.yaml
```

**7.6 Initial Reconciliation**

Flux will now attempt to reconcile your infrastructure and workloads!

```bash
# Watch Flux apply your resources
kubectl get kustomizations -n flux-system -w

# Check HelmRepositories
flux get sources helm

# Check HelmReleases
flux get helmreleases -A

# Check pods in all namespaces
kubectl get pods -A
```

**Expected Behavior:**

- Flux creates namespaces (llm, log-analyzer, logging)
- Flux installs Helm charts (Loki, Grafana, Tempo, Alloy, Envoy Gateway)
- Flux creates deployments (llama-cpp, log-analyzer)
- Resources converge to desired state

**Troubleshooting:**

If Flux fails to reconcile:

```bash
# Check Flux events
flux events --for Kustomization/infrastructure

# Check specific HelmRelease
flux logs --kind=HelmRelease --name=loki --namespace=logging

# Force reconciliation
flux reconcile kustomization infrastructure --with-source
```

**Deliverable:**
- ✅ Flux installed and running in cluster
- ✅ Git repository connected
- ✅ Reconciliation loop active
- ✅ Flux managing cluster state

**Estimated Time:** 1 hour (including troubleshooting)

**Reference:** [Flux Bootstrap Guide](https://fluxcd.io/flux/installation/bootstrap/)

---

### Step 8: Define Reconciliation Boundaries

**Goal:** Configure how Flux reconciles resources and handles drift.

**Actions:**

**8.1 Review Root Kustomizations**

These were created in Step 4 and applied during bootstrap:

```yaml
# clusters/homelab/infrastructure.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  interval: 10m           # Check Git every 10 minutes
  retryInterval: 1m       # Retry failures after 1 minute
  timeout: 5m             # Max time for apply operations
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure  # Watch this Git path
  prune: true             # Delete resources removed from Git
  wait: true              # Wait for resources to be ready
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: loki
      namespace: logging
```

**8.2 Configure Prune Behavior**

**`prune: true`** means:
- If you delete a YAML file from Git, Flux deletes it from the cluster
- **Danger:** Be careful when removing resources!

**Safety Recommendations:**

```yaml
# For critical infrastructure, use prune: false initially
spec:
  prune: false  # Manual cleanup required
```

**8.3 Configure Health Checks**

Health checks ensure dependencies are ready before proceeding:

```yaml
# clusters/homelab/workloads.yaml
spec:
  dependsOn:
    - name: infrastructure  # Wait for infra before deploying workloads
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: log-analyzer
      namespace: log-analyzer
```

**8.4 Configure Reconciliation Intervals**

Balance between responsiveness and cluster load:

| Resource Type | Recommended Interval | Reasoning |
|--------------|---------------------|-----------|
| Infrastructure | 10m | Infrequent changes |
| Workloads | 5m | More frequent updates |
| Helm Repos | 1h | Charts change rarely |
| Git Source | 1m | Fast feedback for development |

**8.5 Configure Retry Behavior**

```yaml
spec:
  retryInterval: 1m  # Retry after failure
  timeout: 5m        # Max time before declaring failure
```

**8.6 Test Drift Prevention**

Flux should revert manual changes:

```bash
# Make manual change
kubectl edit deployment log-analyzer -n log-analyzer
# Change replicas: 1 → 2

# Wait for reconciliation (up to 5 minutes)
# Flux should revert to replicas: 1

# Force immediate reconciliation
flux reconcile kustomization workloads
```

**Deliverable:**
- Reconciliation intervals configured
- Health checks defined for critical resources
- Prune behavior understood and tested
- Drift prevention validated

**Estimated Time:** 2 hours (including testing)

**Reference:** [Flux Kustomize Controller](https://fluxcd.io/flux/components/kustomize/)

---

### Step 9: Migrate Incrementally

**Goal:** Safely migrate resources from imperative to Flux management in stages.

**Strategy: Blue-Green Migration**

Migrate in phases, validating each before proceeding.

**Phase 1: Infrastructure Foundation (Sources + Storage)**

**9.1.1 Verify Helm Repositories**

```bash
# Flux should have created HelmRepositories
flux get sources helm
# Expected: grafana, prometheus-community, envoyproxy - all ready

# If not ready, debug:
flux logs --kind=HelmRepository --name=grafana
```

**9.1.2 Apply Storage Resources**

```bash
# Storage should be applied by Flux
kubectl get pv
# Expected: llama-models-pv, loki-pv, tempo-pv

kubectl get pvc -A
# Expected: llama-models-pvc (llm), storage-loki-0 (logging), tempo-pvc (logging)
```

**9.1.3 Validation**

```bash
# Check Flux reconciliation
flux get kustomizations
# infrastructure should be "Applied"
```

**Phase 2: Logging Infrastructure (Helm Releases)**

**9.2.1 Verify Loki HelmRelease**

```bash
# Check HelmRelease status
flux get helmrelease loki -n logging

# Check Loki pods
kubectl get pods -n logging -l app.kubernetes.io/name=loki

# If issues:
flux logs --kind=HelmRelease --name=loki --namespace=logging
```

**9.2.2 Compare Old vs New**

```bash
# Old Helm release (if still present)
helm list -n logging

# New Flux-managed release
kubectl get helmrelease -n logging

# If both exist, uninstall old one:
helm uninstall loki -n logging  # Only after Flux version is working!
```

**9.2.3 Repeat for Other Logging Components**

```bash
# Grafana
flux get helmrelease grafana -n logging
kubectl get pods -n logging -l app.kubernetes.io/name=grafana

# Tempo
flux get helmrelease tempo -n logging
kubectl get pods -n logging -l app.kubernetes.io/name=tempo

# Alloy
flux get helmrelease alloy -n logging
kubectl get pods -n logging -l app.kubernetes.io/name=alloy
```

**9.2.4 Clean Up Old Helm Releases**

Only after Flux versions are confirmed working:

```bash
# List old releases
helm list -A

# Uninstall (Flux takes over)
helm uninstall loki -n logging
helm uninstall grafana -n logging
helm uninstall tempo -n logging
helm uninstall alloy -n logging
```

**Phase 3: Controllers (Envoy Gateway)**

**9.3.1 Verify Envoy Gateway HelmRelease**

```bash
flux get helmrelease eg -n envoy-gateway-system
kubectl get pods -n envoy-gateway-system
```

**9.3.2 Clean Up Old Helm Release**

```bash
helm uninstall eg -n envoy-gateway-system
```

**Phase 4: Workloads (LLaMA + log-analyzer)**

**9.4.1 Verify LLaMA Deployment**

```bash
# Check Flux applied it
kubectl get deployment llama-cpp -n llm

# Check pod status
kubectl get pods -n llm

# Compare to original
kubectl get deployment llama-cpp -n llm -o yaml > /tmp/flux-llama.yaml
# Compare with exports/workloads/llm/all-resources.yaml
```

**9.4.2 Verify log-analyzer Deployment**

```bash
kubectl get deployment log-analyzer -n log-analyzer
kubectl get pods -n log-analyzer

# Test endpoint
kubectl port-forward -n log-analyzer svc/log-analyzer 8000:8000 &
curl http://localhost:8000/health
```

**9.4.3 No Cleanup Needed**

Since these were YAML-managed (not Helm), Flux takes over immediately.

**Phase 5: Final Validation**

**9.5.1 Check All Resources**

```bash
# Verify Flux managing everything
flux get kustomizations

# Check all HelmReleases
flux get helmreleases -A

# Check all pods
kubectl get pods -A

# Check all PVCs
kubectl get pvc -A
```

**9.5.2 Test Application Functionality**

```bash
# Test Grafana
kubectl port-forward -n logging svc/grafana 3000:80
# Open http://localhost:3000

# Test log-analyzer
kubectl port-forward -n log-analyzer svc/log-analyzer 8000:8000
curl http://localhost:8000/v1/analyze/stream

# Test LLaMA
kubectl port-forward -n llm svc/llama-cpp 8080:8080
curl http://localhost:8080/v1/models
```

**9.5.3 Document Any Manual Steps**

If anything required manual intervention, document it:

```markdown
# MIGRATION_NOTES.md

## Manual Steps Required

1. PersistentVolumes had to be manually created before bootstrap
   - Reason: HostPath volumes need node-specific configuration
   - Solution: Applied PV manifests before Flux bootstrap

2. Grafana admin password reset
   - Reason: Secret not migrated correctly
   - Solution: `kubectl create secret ...`
```

**Deliverable:**
- All resources migrated to Flux management
- Old Helm releases uninstalled
- All services functional
- Full cluster managed by Git

**Estimated Time:** 4-6 hours (testing, validation, troubleshooting)

**Reference:** [Flux Migration Guide](https://fluxcd.io/flux/guides/multi-tenancy/)

---

### Step 10: Validate Rebuild Process

**Goal:** Prove that Git is the single source of truth by rebuilding the cluster from scratch.

**WARNING:** This is destructive! Only proceed when you're confident everything is in Git.

**Actions:**

**10.1 Pre-Rebuild Checklist**

Before destroying the cluster, verify:

```bash
# ✅ All manifests committed to Git
git status
# Should be clean

# ✅ All changes pushed to GitHub
git log origin/main..HEAD
# Should be empty

# ✅ Critical data backed up (if needed)
# Models can be re-downloaded
# Logs/traces are ephemeral (acceptable loss)

# ✅ Document current working state
kubectl get all -A > pre-rebuild-state.yaml
kubectl get pv,pvc -A >> pre-rebuild-state.yaml
helm list -A >> pre-rebuild-state.yaml
```

**10.2 Destroy the Cluster**

```bash
# SSH to each node
ssh node1
sudo /usr/local/bin/k3s-uninstall.sh  # or k3s-agent-uninstall.sh

ssh node2
sudo /usr/local/bin/k3s-agent-uninstall.sh
```

**10.3 Reinstall K3s**

```bash
# On Node 1 (control plane)
ssh node1
curl -sfL https://get.k3s.io | sh -s - server \
  --disable traefik \
  --node-label hardware=light

# Get K3s token
sudo cat /var/lib/rancher/k3s/server/node-token

# On Node 2 (worker)
ssh node2
curl -sfL https://get.k3s.io | K3S_URL=https://node1:6443 \
  K3S_TOKEN=<token-from-node1> \
  sh -s - agent \
  --node-label hardware=heavy
```

**10.4 Apply Node Taints**

```bash
# From local machine (with kubectl configured)
kubectl taint nodes node2 heavy=true:NoSchedule
```

**10.5 Create PersistentVolumes (If Needed)**

Some resources may need manual pre-creation:

```bash
# If using hostPath PVs, create directories on nodes
ssh node2 "sudo mkdir -p /mnt/k8s-storage/models /mnt/k8s-storage/loki /mnt/k8s-storage/tempo"

# Apply PV manifests (if not managed by Flux)
kubectl apply -f infrastructure/storage/
```

**10.6 Bootstrap Flux**

```bash
# Set credentials
export GITHUB_USER=your-github-username
export GITHUB_TOKEN=ghp_your_personal_access_token
export GITHUB_REPO=k8s-slm-log-agent

# Bootstrap
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=$GITHUB_REPO \
  --branch=main \
  --path=clusters/homelab \
  --personal \
  --components-extra=image-reflector-controller,image-automation-controller
```

**10.7 Watch Flux Reconcile**

```bash
# Watch Flux apply resources
flux logs --follow --level=info

# In another terminal, watch resources appear
watch -n 2 'kubectl get pods -A'

# Check Kustomizations
flux get kustomizations

# Check HelmReleases
flux get helmreleases -A
```

**10.8 Validate All Services**

```bash
# Wait for all pods to be ready (may take 5-15 minutes)
kubectl wait --for=condition=ready pod --all -A --timeout=600s

# Check specific services
kubectl get pods -n logging
kubectl get pods -n llm
kubectl get pods -n log-analyzer
kubectl get pods -n envoy-gateway-system

# Test functionality
kubectl port-forward -n logging svc/grafana 3000:80
kubectl port-forward -n log-analyzer svc/log-analyzer 8000:8000
kubectl port-forward -n llm svc/llama-cpp 8080:8080
```

**10.9 Compare Pre/Post States**

```bash
# Export post-rebuild state
kubectl get all -A > post-rebuild-state.yaml
kubectl get pv,pvc -A >> post-rebuild-state.yaml

# Compare
diff pre-rebuild-state.yaml post-rebuild-state.yaml
# Should be identical (except resource IDs, timestamps)
```

**10.10 Document Rebuild Time**

```bash
# Note total time from cluster destruction to fully functional
# Target: < 20 minutes

# Example timeline:
# - K3s install: 5 minutes
# - Flux bootstrap: 2 minutes
# - Infrastructure reconciliation: 8 minutes
# - Workload reconciliation: 3 minutes
# - Health checks: 2 minutes
# Total: 20 minutes
```

**Success Criteria:**

- ✅ Cluster rebuilt from Git alone (no manual kubectl apply)
- ✅ All namespaces created
- ✅ All Helm releases deployed
- ✅ All workloads running
- ✅ All services functional
- ✅ Rebuild time < 20 minutes
- ✅ No manual intervention required (except K3s install + Flux bootstrap)

**Deliverable:**
- Proven disaster recovery capability
- Git validated as single source of truth
- Documented rebuild process
- Confidence in GitOps workflow

**Estimated Time:** 2-3 hours (including rebuild and validation)

**Reference:** [Flux Bootstrap Cheatsheet](https://fluxcd.io/flux/cheatsheets/bootstrap/)

---

## Validation & Testing

### Continuous Validation Checklist

After migration, regularly validate GitOps workflow:

**Daily:**
- [ ] `flux get sources git` - Git sync healthy
- [ ] `flux get kustomizations` - All kustomizations applied
- [ ] `kubectl get pods -A` - All pods running

**Weekly:**
- [ ] Test drift prevention: manual edit → Flux reverts
- [ ] Review Flux logs: `flux logs --level=error`
- [ ] Check for pending Git commits: `git status`

**Monthly:**
- [ ] Test disaster recovery: rebuild from Git
- [ ] Review HelmRelease versions: any updates needed?
- [ ] Audit secrets: rotate if needed

### Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| **Helm chart conflicts** | HelmRelease stuck in "Pending" | Uninstall old Helm release: `helm uninstall <name>` |
| **Resource ownership** | "resource already exists" error | Delete existing resource, let Flux recreate |
| **PVC binding** | PVC stuck in "Pending" | Check PV exists, verify storageClass, check node labels |
| **Image pull errors** | Pod stuck in "ImagePullBackOff" | Verify image name, check registry access |
| **Reconciliation failures** | Kustomization shows "Failed" | `flux logs --kind=Kustomization --name=<name>` |
| **Git sync issues** | GitRepository not updating | Check GitHub token, verify repo access |

---

## Troubleshooting Guide

### Debugging Flux Resources

```bash
# Check overall Flux health
flux check

# View Flux events
flux events

# Check specific resource
flux get kustomizations infrastructure
flux logs --kind=Kustomization --name=infrastructure

# Check HelmRelease
flux get helmreleases -A
flux logs --kind=HelmRelease --name=loki --namespace=logging

# Force reconciliation
flux reconcile kustomization infrastructure --with-source
flux reconcile helmrelease loki -n logging
```

### Debugging Kubernetes Resources

```bash
# Check pod status
kubectl get pods -A
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace>

# Check events
kubectl get events -A --sort-by='.lastTimestamp'

# Check resource ownership
kubectl get deployment log-analyzer -n log-analyzer -o yaml | grep -A 5 ownerReferences
```

### Emergency Rollback

If Flux breaks something:

```bash
# Option 1: Revert Git commit
git revert <bad-commit-hash>
git push
# Flux will reconcile to previous state

# Option 2: Suspend reconciliation
flux suspend kustomization infrastructure
# Make manual fixes
flux resume kustomization infrastructure

# Option 3: Disable Flux entirely
flux suspend kustomization flux-system
# Cluster is now static, make manual changes
```

---

## Resources

### Official Documentation

- **Flux Core Concepts:** https://fluxcd.io/flux/concepts/
- **Flux Bootstrap Guide:** https://fluxcd.io/flux/installation/bootstrap/
- **Flux Repository Structure:** https://fluxcd.io/flux/guides/repository-structure/
- **Flux Helm Controller:** https://fluxcd.io/flux/components/helm/
- **Flux Kustomize Controller:** https://fluxcd.io/flux/components/kustomize/
- **Flux SOPS Guide:** https://fluxcd.io/flux/guides/mozilla-sops/ (future)
- **Kubernetes kubectl Overview:** https://kubernetes.io/docs/reference/kubectl/overview/
- **Kubernetes kubectl Cheatsheet:** https://kubernetes.io/docs/reference/kubectl/cheatsheet/

### Community Examples

- [K3s Homelab with Flux GitOps](https://aviitala.com/posts/flux-homelab/)
- [From Zero to GitOps: K3s on Raspberry Pi with Flux](https://dev.to/shankar_t/from-zero-to-gitops-building-a-k3s-homelab-on-a-raspberry-pi-with-flux-sops-55b7)
- [Production Homelab with K3s and FluxCD](https://github.com/HYP3R00T/homelab)
- [ahgraber/homelab-gitops-k3s](https://github.com/ahgraber/homelab-gitops-k3s)
- [Implementing GitOps in Kubernetes Homelab](https://balisong.dev/blog/implementing-gitops-with-flux-in-kubernetes/)

### Tools

- **Flux CLI:** `brew install fluxcd/tap/flux`
- **yq (YAML processor):** `brew install yq`
- **kustomize:** `brew install kustomize`

---

## Summary: Migration Phases

### Phase 1: Planning & Preparation (Days 1-3)
- ✅ Inventory cluster
- ✅ Export resources
- ✅ Clean manifests
- ✅ Define repo structure
- ✅ Convert Helm to HelmReleases

### Phase 2: Flux Bootstrap (Day 4)
- ✅ Install Flux CLI
- ✅ Bootstrap Flux
- ✅ Verify Git sync
- ✅ Watch initial reconciliation

### Phase 3: Incremental Migration (Days 5-7)
- ✅ Migrate infrastructure (Helm releases)
- ✅ Migrate workloads (YAML deployments)
- ✅ Clean up old resources
- ✅ Validate functionality

### Phase 4: Validation & Testing (Day 8-10)
- ✅ Test drift prevention
- ✅ Rebuild cluster from scratch
- ✅ Document any manual steps
- ✅ Create runbooks

### Phase 5: Ongoing Operations
- ✅ Monitor Flux reconciliation
- ✅ Update resources via Git
- ✅ Regular disaster recovery tests
- ✅ Eventually: add SOPS encryption

---

## End State Verification

Your cluster is successfully migrated when:

- ✅ **Git is source of truth:** All resources defined in Git
- ✅ **Flux reconciles continuously:** `flux get kustomizations` shows all "Applied"
- ✅ **No manual kubectl needed:** Changes made via Git commits
- ✅ **Drift is prevented:** Manual edits get reverted by Flux
- ✅ **Disaster recovery works:** Cluster rebuilt in < 20 minutes
- ✅ **Audit trail exists:** Git log shows all changes
- ✅ **Secrets managed:** Strategy defined (plain text → future SOPS)
- ✅ **Documentation complete:** Runbooks for common operations

---

## Next Steps

After successful migration:

1. **Add monitoring:** Flux metrics to Grafana
2. **Set up notifications:** Flux alerts to Slack/Discord
3. **Implement SOPS:** Encrypt secrets in Git
4. **Add image automation:** Auto-update container images
5. **Multi-environment:** Add dev/staging clusters
6. **Renovate integration:** Automated dependency updates
7. **Backup Git repo:** Ensure GitHub backup strategy

---

**Status:** Ready for Implementation
**Risk Level:** Medium (can rollback to manual management anytime)
**Time Investment:** 20-30 hours over 1-2 weeks
**Long-term Value:** High - production-grade GitOps for homelab

This migration transforms your homelab from "manually managed cluster" to "declarative, reproducible infrastructure as code."
