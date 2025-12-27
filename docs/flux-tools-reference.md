# Flux GitOps Tools Reference

**Purpose:** Explain all tools and commands used during the Flux migration
**Audience:** Future reference for understanding the GitOps workflow

---

## Core Tools

### 1. Flux CLI (`flux`)

**What it is:** Command-line tool for managing Flux in Kubernetes clusters

**Installation:**
```bash
brew install fluxcd/tap/flux
```

**Key Commands:**

| Command | Purpose | Example |
|---------|---------|---------|
| `flux check` | Verify Flux controllers are healthy | `flux check` |
| `flux bootstrap` | Install Flux into cluster and connect to Git | `flux bootstrap github --owner=...` |
| `flux get sources git` | Show Git repositories Flux is watching | `flux get sources git` |
| `flux get kustomizations` | Show Kustomizations and their status | `flux get kustomizations` |
| `flux get helmreleases -A` | Show Helm releases managed by Flux | `flux get helmreleases -A` |
| `flux reconcile` | Force immediate reconciliation (instead of waiting for interval) | `flux reconcile kustomization infrastructure` |
| `flux logs` | View logs from Flux controllers | `flux logs --follow --level=info` |
| `flux events` | Show recent Flux events | `flux events --for Kustomization/infrastructure` |
| `flux suspend` | Temporarily stop reconciliation | `flux suspend kustomization infrastructure` |
| `flux resume` | Resume reconciliation | `flux resume kustomization infrastructure` |

**What Flux Does:**
- **Pull-based GitOps:** Flux runs in your cluster and pulls from Git (not push-based)
- **Continuous reconciliation:** Every X minutes, Flux checks Git and applies changes
- **Drift detection:** If you manually edit resources, Flux reverts them to match Git
- **Self-healing:** If a pod crashes, Flux ensures it comes back matching Git state

**Flux Architecture:**
```
Git Repository (GitHub)
        ↓
  [source-controller]  ← Watches Git for changes
        ↓
  [kustomize-controller]  ← Applies Kustomize manifests
  [helm-controller]       ← Manages Helm releases
        ↓
  Kubernetes Cluster
```

---

### 2. Kustomize (`kubectl kustomize`)

**What it is:** Tool for customizing Kubernetes YAML files without templating

**Why Flux Uses It:** Kustomize is **declarative** - you compose resources by reference, not by editing templates

**Installation:** Built into `kubectl` (no separate install needed)

**Key Commands:**

| Command | Purpose | Example |
|---------|---------|---------|
| `kubectl kustomize <dir>` | Build final YAML from kustomization.yaml | `kubectl kustomize infrastructure/` |
| `kubectl apply -k <dir>` | Build and apply in one step | `kubectl apply -k workloads/llm/` |
| `kubectl kustomize --dry-run` | Validate without applying | `kubectl kustomize infrastructure/ --dry-run=client` |

**How Kustomize Works:**

**kustomization.yaml:**
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
```

**What `kubectl kustomize` does:**
1. Reads `kustomization.yaml`
2. Loads all referenced resource files
3. Combines them into a single YAML stream
4. Outputs to stdout (or applies to cluster if using `-k`)

**Example:**
```bash
# Build and preview YAML
kubectl kustomize workloads/llm/

# Build and apply to cluster
kubectl apply -k workloads/llm/
```

**Kustomize vs Helm:**
- **Kustomize:** Declarative composition, no templating, built into kubectl
- **Helm:** Templating engine (Go templates), package manager, requires Helm CLI

**Flux uses both:**
- Kustomize for plain YAML resources
- Helm for chart-based applications (via HelmRelease CRD)

---

### 3. Helm

**What it is:** Package manager for Kubernetes

**Why Flux Uses It:** Manage complex applications (Loki, Grafana, etc.) with reusable charts

**Key Commands:**

| Command | Purpose | Example |
|---------|---------|---------|
| `helm list -A` | List installed Helm releases | `helm list -A` |
| `helm get values <release> -n <ns>` | Export current values | `helm get values loki -n logging` |
| `helm get manifest <release> -n <ns>` | Show deployed manifests | `helm get manifest loki -n logging` |
| `helm uninstall <release> -n <ns>` | Remove Helm release | `helm uninstall loki -n logging` |
| `helm repo list` | List Helm repositories | `helm repo list` |

**Imperative vs Flux Helm:**

**Imperative (Old Way):**
```bash
helm install loki grafana/loki -n logging --values loki-values.yaml
```

**Declarative Flux Way:**
```yaml
apiVersion: helm.toolkit.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: loki
  namespace: logging
spec:
  chart:
    spec:
      chart: loki
      sourceRef:
        kind: HelmRepository
        name: grafana
  values:
    # ... values here ...
```

Flux applies the HelmRelease, then Flux's `helm-controller` installs/updates the chart.

---

### 4. kubectl

**What it is:** Kubernetes command-line tool

**Key Commands (GitOps Context):**

| Command | Purpose | Example |
|---------|---------|---------|
| `kubectl get pods -A` | List all pods | `kubectl get pods -A` |
| `kubectl get kustomizations -n flux-system` | Show Flux Kustomizations | `kubectl get kustomizations -n flux-system` |
| `kubectl get helmreleases -A` | Show Flux HelmReleases | `kubectl get helmreleases -A` |
| `kubectl describe <resource>` | Get detailed info | `kubectl describe pod loki-0 -n logging` |
| `kubectl logs <pod> -n <ns>` | View pod logs | `kubectl logs loki-0 -n logging` |
| `kubectl apply -k <dir>` | Apply Kustomize directory | `kubectl apply -k workloads/llm/` |
| `kubectl wait --for=condition=ready pod --all -A --timeout=600s` | Wait for all pods to be ready | During rebuild validation |

---

## Flux Workflow

### How Flux Manages Your Cluster

**1. Bootstrap (One-Time Setup):**
```bash
flux bootstrap github \
  --owner=your-github-username \
  --repository=k8s-slm-log-agent \
  --branch=main \
  --path=clusters/homelab \
  --personal
```

**What this does:**
- Installs Flux controllers in `flux-system` namespace
- Creates GitRepository resource pointing to your repo
- Creates Kustomization watching `clusters/homelab/`
- Commits Flux manifests to Git (`clusters/homelab/flux-system/`)
- Starts reconciliation loop

**2. Reconciliation Loop (Continuous):**
```
Every 1-10 minutes (configurable):
  1. Flux checks Git for changes (source-controller)
  2. If changes detected, pulls new manifests
  3. Applies manifests to cluster (kustomize-controller, helm-controller)
  4. Verifies resources are healthy
  5. Repeats
```

**3. Making Changes:**
```bash
# Old way (imperative):
kubectl apply -f deployment.yaml

# Flux way (declarative):
git add deployment.yaml
git commit -m "Update deployment"
git push
# Flux automatically applies in <interval> minutes

# Force immediate reconciliation:
flux reconcile kustomization workloads
```

---

## Directory Structure Explained

### Flux Repository Layout

```
k8s-slm-log-agent/
├── clusters/homelab/              # Cluster-specific entry point
│   ├── infrastructure.yaml        # Root Kustomization for infra
│   └── workloads.yaml             # Root Kustomization for apps
│
├── infrastructure/                # Platform-level resources
│   ├── kustomization.yaml         # Root (references subdirs)
│   ├── sources/                   # HelmRepositories
│   ├── controllers/               # Envoy Gateway HelmRelease
│   ├── logging/                   # Loki, Grafana HelmReleases
│   └── storage/                   # PersistentVolumes
│
└── workloads/                     # Application workloads
    ├── kustomization.yaml         # Root (references subdirs)
    ├── llm/                       # LLaMA.cpp manifests
    └── log-analyzer/              # FastAPI service manifests
```

**How It Works:**

1. **Flux watches:** `clusters/homelab/`
2. **Finds:** `infrastructure.yaml` and `workloads.yaml`
3. **Creates:** Kustomizations pointing to `./infrastructure` and `./workloads`
4. **Reads:** `infrastructure/kustomization.yaml` and `workloads/kustomization.yaml`
5. **Applies:** All referenced resources recursively

**Key Principle:** Git directory structure = Kubernetes resource organization

---

## Validation Commands

### Before Bootstrap

**Check Flux prerequisites:**
```bash
flux check --pre
```

**Expected output:**
```
✔ Kubernetes version >= 1.26.0
✔ kubectl version >= 1.26.0
```

**Validate Kustomize structure:**
```bash
kubectl kustomize infrastructure/
kubectl kustomize workloads/
```

**Expected:** YAML output with no errors

**Dry-run apply:**
```bash
kubectl apply -k infrastructure/ --dry-run=client
kubectl apply -k workloads/ --dry-run=client
```

**Expected:** Resources validated, no errors

---

### After Bootstrap

**Check Flux controllers:**
```bash
flux check
```

**Expected output:**
```
✔ source-controller: deployment ready
✔ kustomize-controller: deployment ready
✔ helm-controller: deployment ready
✔ notification-controller: deployment ready
```

**Check Git sync:**
```bash
flux get sources git
```

**Expected:**
```
NAME        REVISION        READY   MESSAGE
flux-system main@sha1:abc... True    stored artifact
```

**Check Kustomizations:**
```bash
flux get kustomizations
```

**Expected:**
```
NAME            REVISION        READY   MESSAGE
flux-system     main@sha1:...   True    Applied revision: main@sha1:...
infrastructure  main@sha1:...   True    Applied revision: main@sha1:...
workloads       main@sha1:...   True    Applied revision: main@sha1:...
```

**Check HelmReleases:**
```bash
flux get helmreleases -A
```

**Expected:**
```
NAMESPACE              NAME      REVISION  READY
envoy-gateway-system   eg        v1.4.6    True
logging                loki      6.21.0    True
logging                grafana   10.2.0    True
logging                tempo     1.24.1    True
logging                alloy     1.4.0     True
```

---

## Troubleshooting Commands

### Flux Issues

**View Flux logs:**
```bash
flux logs --follow --level=error
```

**Check specific Kustomization:**
```bash
flux get kustomization infrastructure
flux logs --kind=Kustomization --name=infrastructure
```

**Check specific HelmRelease:**
```bash
flux get helmrelease loki -n logging
flux logs --kind=HelmRelease --name=loki --namespace=logging
```

**Force reconciliation:**
```bash
flux reconcile kustomization infrastructure --with-source
```

**Suspend/resume (for debugging):**
```bash
flux suspend kustomization infrastructure
# Make manual changes...
flux resume kustomization infrastructure
```

---

### Kubernetes Issues

**Check pod status:**
```bash
kubectl get pods -A
kubectl describe pod loki-0 -n logging
kubectl logs loki-0 -n logging
```

**Check events:**
```bash
kubectl get events -A --sort-by='.lastTimestamp' | tail -20
```

**Check resource ownership:**
```bash
kubectl get deployment llama-cpp -n llm -o yaml | grep -A 5 ownerReferences
```

---

## GitOps Principles

### Single Source of Truth

**Rule:** Git is authoritative. Cluster state is derived from Git.

**Example:**
```bash
# ❌ Wrong (manual change):
kubectl edit deployment llama-cpp -n llm

# ✅ Right (Git change):
vim workloads/llm/llama-deployment.yaml
git add workloads/llm/llama-deployment.yaml
git commit -m "Update llama-cpp resources"
git push
flux reconcile kustomization workloads
```

**What happens if you manually edit:**
1. Change is applied immediately
2. Flux detects drift on next reconciliation
3. Flux reverts to Git state
4. Manual change is lost

---

### Declarative Configuration

**Imperative (Old Way):**
```bash
kubectl create namespace llm
kubectl create -f deployment.yaml
kubectl expose deployment llama-cpp --port=8080
```

**Declarative (Flux Way):**
```yaml
# All in Git:
workloads/llm/namespace.yaml
workloads/llm/llama-deployment.yaml
workloads/llm/llama-service.yaml
```

**Benefits:**
- **Reproducible:** Clone repo → bootstrap → working cluster
- **Auditable:** Every change is a Git commit
- **Rollback:** `git revert` to undo changes
- **Review:** Pull requests for cluster changes

---

## Flux-Specific CRDs

### GitRepository

**Purpose:** Defines a Git repository to watch

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-system
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/user/repo
  ref:
    branch: main
```

**What it does:** Flux clones the repo every `interval` and stores it as an artifact

---

### Kustomization (Flux)

**Purpose:** Defines how to apply Kustomize manifests from Git

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure
  prune: true
  wait: true
```

**What it does:** Runs `kubectl apply -k ./infrastructure` every 10 minutes

---

### HelmRepository

**Purpose:** Defines a Helm chart repository

```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: HelmRepository
metadata:
  name: grafana
  namespace: flux-system
spec:
  interval: 1h
  url: https://grafana.github.io/helm-charts
```

**What it does:** Flux indexes the Helm repository every hour

---

### HelmRelease

**Purpose:** Defines a Helm chart to install/upgrade

```yaml
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
      version: '6.21.0'
      sourceRef:
        kind: HelmRepository
        name: grafana
        namespace: flux-system
  values:
    # ... values ...
```

**What it does:** Flux installs/upgrades the chart every 5 minutes if values change

---

## Common Patterns

### Pattern 1: Deploy New Workload

```bash
# 1. Create manifests
mkdir workloads/new-app
cat > workloads/new-app/kustomization.yaml << EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
EOF

# 2. Add to root kustomization
vim workloads/kustomization.yaml
# Add: - new-app/

# 3. Commit and push
git add workloads/new-app/
git commit -m "Add new-app workload"
git push

# 4. Watch Flux deploy
flux reconcile kustomization workloads
kubectl get pods -n new-app -w
```

---

### Pattern 2: Update Helm Chart Values

```bash
# 1. Edit HelmRelease
vim infrastructure/logging/loki-helmrelease.yaml
# Update spec.values

# 2. Commit and push
git add infrastructure/logging/loki-helmrelease.yaml
git commit -m "Update Loki retention policy"
git push

# 3. Watch Flux upgrade
flux reconcile helmrelease loki -n logging
kubectl rollout status statefulset loki -n logging
```

---

### Pattern 3: Disaster Recovery

```bash
# 1. Wipe cluster
ssh node1 'sudo /usr/local/bin/k3s-uninstall.sh'
ssh node2 'sudo /usr/local/bin/k3s-agent-uninstall.sh'

# 2. Reinstall K3S
ssh node1 'curl -sfL https://get.k3s.io | sh -s - server --disable traefik'

# 3. Bootstrap Flux
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=k8s-slm-log-agent \
  --branch=main \
  --path=clusters/homelab

# 4. Watch everything come back
flux get kustomizations -w
```

**Result:** Cluster rebuilt in ~15-20 minutes from Git alone

---

## Summary

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **flux** | Manage Flux controllers and GitOps workflow | Bootstrapping, checking status, debugging |
| **kubectl kustomize** | Build Kustomize manifests | Validating structure before committing |
| **helm** | Export values from existing releases | During migration (Step 1-5) |
| **kubectl** | Interact with Kubernetes API | Debugging pods, checking resource status |
| **git** | Version control for cluster state | Every change to cluster configuration |

**Golden Rule:** Everything goes through Git. Manual kubectl changes get reverted by Flux.

---

**Last Updated:** 2025-12-27
**Related:** [infra-roadmap.md](../infra-roadmap.md), [FLUX_MIGRATION_PROGRESS.md](../FLUX_MIGRATION_PROGRESS.md)
