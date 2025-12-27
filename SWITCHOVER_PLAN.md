# Flux Switchover Plan: Detailed Step-by-Step Guide

**Goal:** Safely migrate from imperative management (Helm/kubectl) to Flux GitOps WITHOUT breaking the running cluster

**Key Strategy:** Install Flux with reconciliation SUSPENDED, then hand over resources one at a time

---

## The Answer to Your Question

**"Can we install Flux and setup our Flux repo without the control loop interfering with current resources?"**

**YES!** Here's exactly how:

---

## Phase 1: Install Flux WITHOUT Reconciling (SAFE)

### What We'll Do

1. **Add `suspend: true` to Flux entry points** (in Git)
2. **Bootstrap Flux** (installs controllers + CRDs)
3. **Flux creates Kustomization resources** (but they're suspended)
4. **Your existing resources are UNTOUCHED** (Flux control loop is OFF for our resources)

### How Flux Suspended Mode Works

```
┌─────────────────────────────────────────────────┐
│  Flux Controllers (RUNNING)                     │
│  - source-controller (watches Git)              │
│  - kustomize-controller (applies manifests)     │
│  - helm-controller (manages Helm releases)      │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  GitRepository (ACTIVE)                         │
│  - Pulls from github.com/.../k8s-slm-log-agent  │
│  - Branch: agent/flux                           │
│  - Interval: 1m                                 │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  Kustomization: infrastructure (SUSPENDED ⏸)    │
│  - Path: ./infrastructure                       │
│  - Status: Suspended, not reconciling           │
│  - Your Helm releases: UNTOUCHED                │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  Kustomization: workloads (SUSPENDED ⏸)         │
│  - Path: ./workloads                            │
│  - Status: Suspended, not reconciling           │
│  - Your deployments: UNTOUCHED                  │
└─────────────────────────────────────────────────┘
```

**Key Point:** Flux is installed and running, but the `infrastructure` and `workloads` Kustomizations are suspended, so Flux doesn't touch your existing resources.

---

## Detailed Steps

### Step 1: Prepare Git Repository (5 minutes)

**Add suspend flags to prevent immediate reconciliation:**

**Edit: `clusters/homelab/infrastructure.yaml`**
```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  suspend: true  # ← ADD THIS LINE
  interval: 10m
  retryInterval: 1m
  timeout: 5m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure
  prune: true
  wait: true
  healthChecks:
    - apiVersion: helm.toolkit.fluxcd.io/v2beta1
      kind: HelmRelease
      name: loki
      namespace: logging
    - apiVersion: helm.toolkit.fluxcd.io/v2beta1
      kind: HelmRelease
      name: eg
      namespace: envoy-gateway-system
```

**Edit: `clusters/homelab/workloads.yaml`**
```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: workloads
  namespace: flux-system
spec:
  suspend: true  # ← ADD THIS LINE
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
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: llama-cpp
      namespace: llm
    - apiVersion: apps/v1
      kind: Deployment
      name: log-analyzer
      namespace: log-analyzer
```

**Commit and push:**
```bash
git add clusters/homelab/
git commit -m "feat(flux): add suspend flags for safe bootstrap"
git push
```

**What this does:** When Flux bootstraps, it will create these Kustomizations but they won't reconcile (control loop is OFF).

---

### Step 2: Bootstrap Flux (10 minutes)

**Prerequisites:**
- SSH'd into node1 (where kubectl works)
- GitHub token set: `export GITHUB_TOKEN=ghp_your_token`
- Branch pushed to GitHub

**Run bootstrap command:**
```bash
# On node1
export GITHUB_USER=your-github-username
export GITHUB_TOKEN=ghp_your_token
export GITHUB_REPO=k8s-slm-log-agent

flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=$GITHUB_REPO \
  --branch=agent/flux \
  --path=clusters/homelab \
  --personal \
  --components-extra=image-reflector-controller,image-automation-controller
```

**What happens:**
1. Flux installs its controllers in `flux-system` namespace
2. Flux installs CRDs (HelmRelease, Kustomization, etc.)
3. Flux creates GitRepository watching your repo
4. Flux creates `infrastructure` and `workloads` Kustomizations (SUSPENDED)
5. Flux commits its own manifests to Git (`clusters/homelab/flux-system/`)
6. **Your existing resources: COMPLETELY UNTOUCHED**

**Expected output:**
```
► connecting to github.com
✔ repository "https://github.com/your-user/k8s-slm-log-agent" created
► cloning branch "agent/flux" from Git repository "https://github.com/your-user/k8s-slm-log-agent.git"
✔ cloned repository
► generating component manifests
✔ generated component manifests
✔ component manifests are up to date
► installing components in "flux-system" namespace
✔ installed components
✔ reconciled components
► determining if source secret "flux-system/flux-system" exists
► generating source secret
✔ public key: ecdsa-sha2-nistp384 AAAAE2VjZHN...
✔ configured deploy key "flux-system-main-flux-system-./clusters/homelab" for "https://github.com/your-user/k8s-slm-log-agent"
► applying source secret "flux-system/flux-system"
✔ reconciled source secret
► generating sync manifests
✔ generated sync manifests
✔ sync manifests are up to date
► applying sync manifests
✔ reconciled sync configuration
◎ waiting for Kustomization "flux-system/flux-system" to be reconciled
✔ Kustomization reconciled successfully
► confirming components are healthy
✔ helm-controller: deployment ready
✔ kustomize-controller: deployment ready
✔ notification-controller: deployment ready
✔ source-controller: deployment ready
✔ all components are healthy
```

**Downtime:** **ZERO** (Flux installed but not reconciling your resources)

---

### Step 3: Verify Suspended State (2 minutes)

**Check Flux is installed but suspended:**
```bash
# Verify Flux controllers running
kubectl get pods -n flux-system
# Expected: 4-6 pods all Running

# Check Kustomizations
flux get kustomizations
# Expected output:
# NAME            REVISION        SUSPENDED  READY
# flux-system     agent/flux@sha  False      True
# infrastructure  agent/flux@sha  True       Unknown  ← SUSPENDED!
# workloads       agent/flux@sha  True       Unknown  ← SUSPENDED!
```

**Check your existing resources UNTOUCHED:**
```bash
# Helm releases still there
helm list -A
# Should show: eg, loki, grafana, tempo, alloy

# Deployments still running
kubectl get deployments -A
# Should show: llama-cpp, log-analyzer, etc.

# All pods healthy
kubectl get pods -A
# All should be Running (no restarts, no changes)
```

**Success criteria:**
- ✅ Flux controllers running
- ✅ infrastructure/workloads Kustomizations showing SUSPENDED
- ✅ Existing Helm releases unchanged
- ✅ Existing pods unchanged

---

### Step 4: Test Reconciliation Preview (5 minutes)

**Now we can preview what Flux WOULD do (without actually doing it):**

```bash
# Preview infrastructure changes
flux diff kustomization infrastructure --path ./infrastructure

# Preview workloads changes
flux diff kustomization workloads --path ./workloads
```

**What to look for:**

**Expected (GOOD):**
```
► HelmRepository/grafana created
► HelmRepository/envoyproxy created
► PersistentVolume/llama-models-pv created
► HelmRelease/loki created
...
```

**Unexpected (BAD - investigate before proceeding):**
```
✗ Deployment/llama-cpp deleted  ← DANGER!
✗ Service/loki modified         ← Review carefully
```

**Important:** `flux diff` shows what WOULD happen. Nothing is applied yet.

---

## Phase 2: Hand Over Resources (Incremental Migration)

**Now that Flux is installed in suspended mode, we can hand over resources one at a time.**

### Strategy: Component-by-Component Migration

**For each component:**
1. Create targeted test Kustomization (or resume specific path)
2. Watch Flux reconcile
3. Verify Flux ADOPTED existing resources (not recreated)
4. Uninstall old Helm release
5. Verify Flux still manages it

---

### Example: Migrate Envoy Gateway (First Component)

**Why first?** Lowest risk, standalone controller, easy to rollback.

**Step 1: Create test Kustomization (temporary)**

```bash
# On node1
cat > /tmp/test-envoy-gateway.yaml << EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: test-envoy-gateway
  namespace: flux-system
spec:
  interval: 1m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./infrastructure/controllers
  prune: false  # Don't delete anything (safety)
  wait: true
EOF

kubectl apply -f /tmp/test-envoy-gateway.yaml
```

**What this does:** Creates a temporary Kustomization that only reconciles `infrastructure/controllers/` (Envoy Gateway).

**Step 2: Watch Flux reconcile**

```bash
# Terminal 1: Watch Kustomization
flux get kustomizations test-envoy-gateway --watch

# Terminal 2: Watch HelmRelease
flux get helmrelease eg -n envoy-gateway-system --watch

# Terminal 3: Watch pods
kubectl get pods -n envoy-gateway-system --watch
```

**Expected behavior:**
1. Flux creates HelmRepository (envoyproxy)
2. Flux creates HelmRelease (eg)
3. HelmRelease controller sees existing Helm-managed resources
4. HelmRelease ADOPTS existing resources (no pod restarts)
5. Pods keep running (no disruption)

**Step 3: Verify adoption (not recreation)**

```bash
# Check pod ages (should be OLD, not freshly created)
kubectl get pods -n envoy-gateway-system -o wide

# Check restart counts (should be 0)
kubectl get pods -n envoy-gateway-system -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}'

# Check Envoy Gateway still serving traffic
curl -I http://10.0.0.102/grafana  # Should return 200 OK
```

**Success criteria:**
- ✅ HelmRelease shows READY True
- ✅ Pods still running (same pod ages as before)
- ✅ No restarts (restart count = 0 or minimal)
- ✅ Service still accessible

**Step 4: Uninstall old Helm release**

**ONLY after verifying Flux adoption successful:**

```bash
# This removes Helm's ownership, Flux takes over
helm uninstall eg -n envoy-gateway-system

# Verify Flux still owns it
flux get helmrelease eg -n envoy-gateway-system
# Should show: READY True

# Verify pods still running
kubectl get pods -n envoy-gateway-system
# Should show: same pods, still Running
```

**Step 5: Clean up test Kustomization**

```bash
# Remove temporary test Kustomization
kubectl delete kustomization test-envoy-gateway -n flux-system

# Envoy Gateway now managed by suspended infrastructure Kustomization
# (We'll resume it later once all components migrated)
```

**Downtime:** 10-30 seconds (HelmRelease adoption time)

---

### Repeat for Each Component

**Migration order (lowest risk → highest risk):**

1. ✅ **Envoy Gateway** (just completed above)
2. **Alloy** (DaemonSet, logs) - 30s downtime
3. **Tempo** (tracing) - 30s downtime
4. **Grafana** (UI) - 30s downtime
5. **llama-cpp** (LLM) - 1min downtime
6. **log-analyzer** (API) - 1min downtime
7. **Loki** (log storage, HIGHEST RISK) - 2-3min downtime

**For each component, follow same 5-step process above.**

---

## Phase 3: Resume Full Reconciliation

**After all components successfully migrated:**

### Resume Infrastructure Kustomization

```bash
# Edit clusters/homelab/infrastructure.yaml
# Remove line: suspend: true

git add clusters/homelab/infrastructure.yaml
git commit -m "feat(flux): resume infrastructure reconciliation"
git push

# Flux will pick up change and resume reconciliation
flux reconcile kustomization flux-system

# Verify
flux get kustomizations
# infrastructure should show SUSPENDED False, READY True
```

### Resume Workloads Kustomization

```bash
# Edit clusters/homelab/workloads.yaml
# Remove line: suspend: true

git add clusters/homelab/workloads.yaml
git commit -m "feat(flux): resume workloads reconciliation"
git push

flux reconcile kustomization flux-system

# Verify
flux get kustomizations
# workloads should show SUSPENDED False, READY True
```

**Now Flux is fully managing your cluster!**

---

## Verification Checklist

**After full migration:**

- [ ] `flux get all` shows all resources
- [ ] `flux get kustomizations` shows infrastructure/workloads READY (not suspended)
- [ ] `helm list -A` returns EMPTY (all migrated to Flux)
- [ ] `kubectl get pods -A` shows all pods Running
- [ ] Grafana UI accessible (http://10.0.0.102/grafana)
- [ ] LLM inference working (test llama-cpp API)
- [ ] Log analysis working (test log-analyzer API)
- [ ] Logs flowing to Loki (check Grafana Explore)
- [ ] Traces flowing to Tempo (check Grafana Explore)

---

## Rollback Procedures

### Rollback Single Component

If a component migration fails:

```bash
# 1. Suspend Flux
flux suspend kustomization infrastructure

# 2. Delete Flux HelmRelease
kubectl delete helmrelease <component> -n <namespace>

# 3. Reinstall with Helm
helm install <component> <chart-repo>/<chart> \
  -n <namespace> \
  -f inventory/helm-values-<component>.yaml

# 4. Resume Flux (it will ignore this component now)
flux resume kustomization infrastructure
```

### Rollback Entire Flux Migration

If Flux catastrophically fails:

```bash
# 1. Uninstall Flux
flux uninstall --silent

# 2. Reinstall all Helm releases
cd inventory/
helm install loki grafana/loki -n logging -f helm-values-loki.yaml
helm install grafana grafana/grafana -n logging -f helm-values-grafana.yaml
helm install tempo grafana/tempo -n logging -f helm-values-tempo.yaml
helm install alloy grafana/alloy -n logging -f helm-values-alloy.yaml
helm install eg envoyproxy/gateway-helm -n envoy-gateway-system

# 3. Reapply workloads
kubectl apply -f ../workloads/llama-cpp/k8s/
kubectl apply -f ../workloads/log-analyzer/k8s/

# 4. Verify
kubectl get pods -A
```

**Recovery time:** 10-15 minutes

---

## Summary

**Yes, you can install Flux without it interfering with current resources!**

**How:**
1. Add `suspend: true` to Flux entry points (Git commit)
2. Bootstrap Flux (installs controllers + CRDs, but suspended)
3. Test with `flux diff` (preview changes, no apply)
4. Migrate incrementally (one component at a time)
5. Resume full reconciliation (remove suspend flags)

**Total time:** 2-3 days (careful, tested migration)
**Total downtime:** 5-7 minutes (staggered across components)
**Rollback capability:** At every step

**Next step:** Complete prerequisites (push branch, fix cluster access), then proceed with Phase 1.
