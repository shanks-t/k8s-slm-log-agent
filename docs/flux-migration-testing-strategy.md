# Flux Migration: Testing & Safe Transition Strategy

**Date:** 2025-12-27
**Purpose:** Validate Flux configuration and minimize downtime during migration
**Cluster State:** Live K3S cluster with active development

---

## Problem Statement

**Challenge:** We need to migrate a **live, working cluster** from imperative management (Helm/kubectl) to declarative Flux GitOps **without breaking active development workflows**.

**Constraints:**
- ✅ Cluster is actively used for development
- ✅ Downtime must be minimal (< 5 minutes per component)
- ✅ Must be able to rollback if Flux migration fails
- ✅ Cannot test Flux reconciliation until Flux is installed
- ✅ Helm and Flux cannot both manage the same resource simultaneously

---

## Testing Strategy: Three Phases

### Phase 1: Pre-Bootstrap Validation (NOW)
**Goal:** Validate everything we can WITHOUT installing Flux

### Phase 2: Flux Bootstrap in "Suspended Mode" (SAFE)
**Goal:** Install Flux but keep it suspended (not reconciling)

### Phase 3: Incremental Migration (CONTROLLED)
**Goal:** Hand over resources one at a time, test each

---

## Phase 1: Pre-Bootstrap Validation

### 1.1 Kustomize Build Validation

**What it tests:** YAML syntax, resource composition, kustomize structure

```bash
# Validate infrastructure builds
kubectl kustomize infrastructure/

# Validate workloads build
kubectl kustomize workloads/

# Validate Flux entry points
kubectl kustomize clusters/homelab/
```

**Expected:** No errors, clean YAML output

**Status:** ✅ Already done (Steps 4-5)

---

### 1.2 Server-Side Dry-Run

**What it tests:** Kubernetes API validation, schema validation, admission webhooks

```bash
# Test infrastructure (without applying)
kubectl kustomize infrastructure/ | kubectl apply --dry-run=server -f -

# Test workloads (without applying)
kubectl kustomize workloads/ | kubectl apply --dry-run=server -f -
```

**Expected:** Resources validated by API server, no errors

**What this catches:**
- Invalid field names
- Missing required fields
- Type mismatches
- Admission webhook rejections

**What this DOESN'T catch:**
- Runtime issues (pod crashes, image pull failures)
- Resource conflicts with existing resources
- PVC binding failures
- Node affinity mismatches

---

### 1.3 Resource Conflict Detection

**What it tests:** Check if resources already exist in cluster

```bash
# Check for namespace conflicts
kubectl get namespace llm logging log-analyzer envoy-gateway-system

# Check for deployment conflicts
kubectl get deployment llama-cpp -n llm
kubectl get deployment log-analyzer -n log-analyzer
kubectl get statefulset loki -n logging

# Check for service conflicts
kubectl get service llama-cpp -n llm
kubectl get service log-analyzer -n log-analyzer
kubectl get service loki grafana tempo -n logging

# Check for PV conflicts
kubectl get pv llama-models-pv loki-pv tempo-pv
```

**Expected:** All resources exist (since they're running)

**Action:** Document these for migration (Flux will adopt them)

---

### 1.4 Flux Prerequisites Check

**What it tests:** Flux installation requirements

```bash
# Install Flux CLI (if not already installed)
brew install fluxcd/tap/flux

# Check Flux prerequisites
flux check --pre

# Expected output:
# ✔ Kubernetes version >= 1.26.0
# ✔ kubectl version >= 1.26.0
```

**What this verifies:**
- Kubernetes version compatible
- kubectl configured correctly
- Cluster reachable

---

### 1.5 HelmRelease Validation

**What it tests:** HelmRelease CRD syntax (Flux-specific)

```bash
# Flux has a validator for HelmRelease resources
# But it requires Flux to be installed...

# Alternative: Use kubectl to validate CRD structure
kubectl kustomize infrastructure/logging/ | grep -A 100 "kind: HelmRelease"
```

**Manual checks:**
- Chart name matches Helm repo
- Chart version exists in repo
- SourceRef points to valid HelmRepository
- Namespace matches HelmRelease namespace

---

### 1.6 Chart Version Availability Check

**What it tests:** Chart versions exist in upstream repos

```bash
# Add Helm repos locally
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add envoyproxy https://gateway.envoyproxy.io
helm repo update

# Check if chart versions exist
helm search repo grafana/loki --version 6.21.0
helm search repo grafana/grafana --version 10.2.0
helm search repo grafana/tempo --version 1.24.1
helm search repo grafana/alloy --version 1.4.0
helm search repo envoyproxy/gateway-helm --version v1.4.6
```

**Expected:** All chart versions found

**If not found:** Update HelmRelease to use available version

---

### 1.7 Git Repository Pre-Flight

**What it tests:** Git repo is accessible and has all commits

```bash
# Verify all changes committed
git status
# Expected: nothing to commit, working tree clean

# Verify branch exists remotely
git push --dry-run

# Verify GitHub repo accessible
curl -s https://api.github.com/repos/$GITHUB_USER/k8s-slm-log-agent | jq .name
```

**Expected:** Clean working tree, remote accessible

---

### 1.8 Create Migration Checklist

**What it does:** Document current state and migration order

```bash
# Create migration state snapshot
cat > MIGRATION_STATE.md << EOF
# Migration State Snapshot

**Date:** $(date)
**Branch:** $(git branch --show-current)
**Commit:** $(git rev-parse HEAD)

## Current Cluster State

### Helm Releases (Imperative)
- loki (6.21.0) - logging namespace
- grafana (10.2.0) - logging namespace
- tempo (1.24.1) - logging namespace
- alloy (1.4.0) - logging namespace
- eg (v1.4.6) - envoy-gateway-system namespace

### YAML Workloads (Imperative)
- llama-cpp - llm namespace
- log-analyzer - log-analyzer namespace

### Migration Order
1. Bootstrap Flux (suspended)
2. Migrate storage (PVs) - no conflicts
3. Migrate Envoy Gateway (low risk)
4. Migrate Loki (medium risk, logging downtime)
5. Migrate Grafana (low risk, dashboard downtime)
6. Migrate Tempo (low risk, tracing downtime)
7. Migrate Alloy (low risk, log collection gap)
8. Migrate llama-cpp (low risk, LLM downtime)
9. Migrate log-analyzer (low risk, API downtime)

### Rollback Plan
- Keep Helm values in inventory/ for re-installation
- Can suspend Flux and revert to Helm if needed
- PVs are Retain policy (data safe)
EOF
```

---

## Phase 2: Flux Bootstrap in "Suspended Mode"

**Goal:** Install Flux controllers WITHOUT reconciling our resources

### Why This is Safe

Flux bootstrap installs:
1. Flux controllers (flux-system namespace)
2. GitRepository resource (watches your repo)
3. Kustomization resources (apply manifests)

We can **suspend** the infrastructure/workloads Kustomizations so Flux doesn't touch existing resources.

---

### 2.1 Modify Entry Points for Suspended Mode

**Before bootstrapping, update Flux entry points:**

```bash
# Edit clusters/homelab/infrastructure.yaml
# Add: spec.suspend: true
```

```yaml
# clusters/homelab/infrastructure.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: infrastructure
  namespace: flux-system
spec:
  suspend: true  # ← ADD THIS LINE
  interval: 10m
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
  suspend: true  # ← ADD THIS LINE
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./workloads
  prune: true
  wait: true
  dependsOn:
    - name: infrastructure
```

**Commit these changes:**
```bash
git add clusters/homelab/
git commit -m "feat(flux): add suspend flags for safe bootstrap"
git push
```

---

### 2.2 Bootstrap Flux (Suspended)

**Now bootstrap Flux:**

```bash
# Set GitHub credentials
export GITHUB_USER=your-github-username
export GITHUB_TOKEN=ghp_your_personal_access_token
export GITHUB_REPO=k8s-slm-log-agent

# Bootstrap Flux
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=$GITHUB_REPO \
  --branch=agent/flux \
  --path=clusters/homelab \
  --personal \
  --components-extra=image-reflector-controller,image-automation-controller
```

**What happens:**
- ✅ Flux controllers installed in `flux-system` namespace
- ✅ GitRepository resource created (watches your repo)
- ✅ infrastructure/workloads Kustomizations created BUT SUSPENDED
- ✅ Your existing resources UNTOUCHED

**Verify Flux is suspended:**
```bash
flux get kustomizations
# Expected:
# NAME            READY   SUSPENDED
# flux-system     True    False
# infrastructure  False   True     ← Suspended!
# workloads       False   True     ← Suspended!
```

**Downtime:** ZERO (Flux is installed but not reconciling)

---

### 2.3 Test Flux Without Applying

**Now that Flux is installed, we can test reconciliation in dry-run mode:**

```bash
# Diff infrastructure (shows what Flux WOULD apply)
flux diff kustomization infrastructure --path ./infrastructure

# Diff workloads
flux diff kustomization workloads --path ./workloads
```

**What this shows:**
- Resources that would be created
- Resources that would be modified
- Resources that would be deleted

**Look for:**
- ❌ Unexpected deletions (DANGER!)
- ⚠️  Resource modifications (review carefully)
- ✅ New resources only (safe)

---

## Phase 3: Incremental Migration

**Goal:** Hand over resources one at a time

### Migration Strategy: Blue-Green Handover

**Approach:** For each component:
1. Let Flux create HelmRelease
2. HelmRelease adopts existing Helm-managed resources
3. Uninstall old Helm release
4. Flux now owns the resource

**Why this works:** Helm and Flux HelmRelease create the same underlying resources (Deployments, Services, etc.). Kubernetes doesn't care who created them.

---

### 3.1 Migration Order (Lowest Risk First)

**Order by risk level:**

| Component | Risk | Reason | Downtime |
|-----------|------|--------|----------|
| **1. Storage (PVs)** | Low | No running pods depend on PV creation | 0s |
| **2. Envoy Gateway** | Low | Standalone controller, easy rollback | 10s |
| **3. Alloy** | Low | DaemonSet, gradual rollout | 30s |
| **4. Tempo** | Low | Tracing, non-critical, can lose recent traces | 30s |
| **5. Grafana** | Low | UI only, no data loss | 30s |
| **6. llama-cpp** | Medium | Workload, but no persistent state | 1min |
| **7. log-analyzer** | Medium | Workload, but no persistent state | 1min |
| **8. Loki** | **HIGH** | Log storage, uses PV, critical | 2-3min |

**Total estimated downtime:** 5-7 minutes (staggered across components)

---

### 3.2 Migration Template (Per Component)

**For each component, follow this template:**

#### Pre-Migration Checklist
```bash
# 1. Verify Helm release exists
helm list -A | grep <component>

# 2. Export current manifests (backup)
helm get manifest <release> -n <namespace> > backup-<component>.yaml

# 3. Export current values (backup)
helm get values <release> -n <namespace> > backup-<component>-values.yaml

# 4. Verify pods are running
kubectl get pods -n <namespace> -l app=<component>
```

#### Migration Steps
```bash
# 1. Resume ONLY this component in Flux
# (Keep infrastructure/workloads suspended, use targeted Kustomization)

# 2. Watch Flux reconcile
flux logs --kind=HelmRelease --name=<component> --namespace=<namespace> --follow

# 3. Check if Flux created HelmRelease
kubectl get helmrelease <component> -n <namespace>

# 4. Wait for HelmRelease to be ready
kubectl wait --for=condition=ready helmrelease/<component> -n <namespace> --timeout=5m

# 5. Verify pods still running (Flux should adopt, not recreate)
kubectl get pods -n <namespace> -l app=<component>

# 6. Check for pod restarts (should be 0 or minimal)
kubectl get pods -n <namespace> -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}'

# 7. If successful: Uninstall old Helm release
helm uninstall <component> -n <namespace>

# 8. Verify Flux still manages it
flux get helmrelease <component> -n <namespace>
```

#### Rollback (if migration fails)
```bash
# 1. Suspend Flux Kustomization
flux suspend kustomization infrastructure

# 2. Delete Flux HelmRelease
kubectl delete helmrelease <component> -n <namespace>

# 3. Re-install with Helm
helm install <component> <chart-repo>/<chart> -n <namespace> -f backup-<component>-values.yaml

# 4. Verify restoration
kubectl get pods -n <namespace>
```

---

### 3.3 Detailed Migration: Example (Envoy Gateway)

Let's walk through migrating Envoy Gateway as an example:

**Step 1: Pre-flight checks**
```bash
# Current state
helm list -n envoy-gateway-system
# NAME  NAMESPACE               REVISION  STATUS    CHART
# eg    envoy-gateway-system    1         deployed  gateway-helm-v1.4.6

# Backup
helm get manifest eg -n envoy-gateway-system > backup-envoy-gateway.yaml
helm get values eg -n envoy-gateway-system > backup-envoy-gateway-values.yaml

# Verify running
kubectl get pods -n envoy-gateway-system
```

**Step 2: Create targeted Kustomization (temporary)**

Instead of resuming ALL of infrastructure, create a targeted Kustomization just for Envoy Gateway:

```yaml
# /tmp/test-envoy-gateway.yaml
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
  prune: false  # Don't delete anything
  wait: true
```

Apply it:
```bash
kubectl apply -f /tmp/test-envoy-gateway.yaml
```

**Step 3: Watch Flux reconcile**
```bash
# Watch Flux logs
flux logs --kind=Kustomization --name=test-envoy-gateway --follow

# In another terminal, watch HelmRelease
flux get helmrelease eg -n envoy-gateway-system --watch
```

**Step 4: Verify adoption (not recreation)**
```bash
# Check if pods restarted
kubectl get pods -n envoy-gateway-system -o wide

# Check pod ages (should be OLD, not freshly created)
kubectl get pods -n envoy-gateway-system -o jsonpath='{.items[*].metadata.creationTimestamp}'

# Check restart count (should be 0)
kubectl get pods -n envoy-gateway-system -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}'
```

**Step 5: If successful, uninstall Helm release**
```bash
# This tells Helm to stop managing the resources
# Flux is now in charge
helm uninstall eg -n envoy-gateway-system

# Verify Flux still owns it
flux get helmrelease eg -n envoy-gateway-system
# Should show: READY True

# Pods should still be running
kubectl get pods -n envoy-gateway-system
```

**Step 6: Clean up temporary Kustomization**
```bash
kubectl delete kustomization test-envoy-gateway -n flux-system
```

**Step 7: Add to permanent infrastructure Kustomization**

Now that we know it works, we can resume the full infrastructure Kustomization later.

---

### 3.4 Special Case: Loki (High Risk)

**Why high risk:**
- Uses PersistentVolume
- Critical for logging
- Longest migration time

**Extra precautions:**

```bash
# 1. Before migration, ensure PV exists
kubectl get pv loki-pv
kubectl get pvc storage-loki-0 -n logging

# 2. Check PV is Retain policy
kubectl get pv loki-pv -o jsonpath='{.spec.persistentVolumeReclaimPolicy}'
# Expected: Retain

# 3. Backup current Loki data (optional)
ssh node2 'sudo tar -czf /tmp/loki-backup.tar.gz /mnt/k8s-storage/loki'

# 4. During migration, watch for PVC rebinding
kubectl get pvc storage-loki-0 -n logging --watch

# 5. If PVC goes to "Pending", investigate immediately
kubectl describe pvc storage-loki-0 -n logging
```

**Expected behavior:**
- Flux HelmRelease creates new StatefulSet spec
- StatefulSet controller sees existing PVC
- PVC rebinds to new pod (if pod recreated)
- Data preserved

**Worst case:**
- PVC fails to bind
- New Loki pod stuck in Pending
- Old Loki pod still running (graceful degradation)
- Rollback: `helm install loki ...`

---

## Phase 4: Full Migration Validation

**After all components migrated:**

### 4.1 Resume Full Infrastructure Kustomization

```bash
# Edit clusters/homelab/infrastructure.yaml
# Remove: spec.suspend: true

git add clusters/homelab/infrastructure.yaml
git commit -m "feat(flux): resume infrastructure reconciliation"
git push

# Verify Flux picks up change
flux reconcile kustomization flux-system
flux get kustomizations
# Expected: infrastructure READY True (not suspended)
```

### 4.2 Resume Workloads Kustomization

```bash
# Edit clusters/homelab/workloads.yaml
# Remove: spec.suspend: true

git add clusters/homelab/workloads.yaml
git commit -m "feat(flux): resume workloads reconciliation"
git push

flux reconcile kustomization flux-system
flux get kustomizations
# Expected: workloads READY True (not suspended)
```

### 4.3 Full Cluster Validation

```bash
# Check all Flux resources
flux get all

# Check all pods
kubectl get pods -A

# Check HelmReleases
flux get helmreleases -A

# Verify no old Helm releases
helm list -A
# Expected: empty (all migrated to Flux)
```

---

## Testing Checklist Summary

### Pre-Bootstrap (Do NOW)
- [ ] `kubectl kustomize infrastructure/` (builds clean)
- [ ] `kubectl kustomize workloads/` (builds clean)
- [ ] `kubectl apply --dry-run=server -f -` (server validates)
- [ ] `flux check --pre` (prerequisites met)
- [ ] Helm chart versions exist in repos
- [ ] Git working tree clean and pushed
- [ ] Migration order documented

### During Bootstrap (Suspended Mode)
- [ ] Add `suspend: true` to infrastructure.yaml
- [ ] Add `suspend: true` to workloads.yaml
- [ ] Commit and push
- [ ] Run `flux bootstrap github ...`
- [ ] Verify `flux get kustomizations` shows suspended
- [ ] Test `flux diff` on suspended Kustomizations

### During Migration (Per Component)
- [ ] Backup Helm manifests and values
- [ ] Create targeted Kustomization (or resume specific path)
- [ ] Watch Flux logs during reconciliation
- [ ] Verify pods NOT restarted (adoption, not recreation)
- [ ] Uninstall old Helm release
- [ ] Verify Flux owns resource

### Post-Migration (Full Validation)
- [ ] Resume infrastructure Kustomization
- [ ] Resume workloads Kustomization
- [ ] `helm list -A` returns empty
- [ ] `flux get helmreleases -A` shows all components
- [ ] All pods running and healthy
- [ ] Services accessible
- [ ] Test core functionality (Grafana UI, LLM inference, log analysis)

---

## Rollback Procedures

### Rollback Flux Entirely

If Flux migration catastrophically fails:

```bash
# 1. Suspend all Flux reconciliation
flux suspend kustomization infrastructure
flux suspend kustomization workloads

# 2. Uninstall Flux
flux uninstall --silent

# 3. Re-install everything with Helm
cd inventory/
for release in loki grafana tempo alloy; do
  helm install $release grafana/$release -n logging -f helm-values-$release.yaml
done
helm install eg envoyproxy/gateway-helm -n envoy-gateway-system

# 4. Re-apply YAML workloads
kubectl apply -f ../workloads/llama-cpp/k8s/
kubectl apply -f ../workloads/log-analyzer/k8s/
```

**Estimated recovery time:** 10-15 minutes

---

## Risk Mitigation Summary

| Risk | Mitigation |
|------|------------|
| **Flux breaks cluster** | Bootstrap in suspended mode first |
| **Resource conflicts** | Server-side dry-run before applying |
| **Data loss** | PVs use Retain policy, backup Loki data |
| **Downtime** | Migrate incrementally, test each component |
| **Can't rollback** | Keep Helm values, document rollback procedure |
| **Unknown Flux behavior** | Test with `flux diff` in suspended mode |

---

## Next Steps

**Immediate (before bootstrap):**
1. Run Pre-Bootstrap Validation (Section 1)
2. Create MIGRATION_STATE.md snapshot
3. Add `suspend: true` to Flux entry points
4. Commit and push

**Day 1 (low risk):**
5. Bootstrap Flux in suspended mode
6. Test `flux diff` on suspended Kustomizations
7. Migrate storage (PVs) - zero downtime

**Day 2 (gradual migration):**
8. Migrate Envoy Gateway (test migration process)
9. Migrate Alloy, Tempo, Grafana (low risk)
10. Validate observability stack working

**Day 3 (workloads + Loki):**
11. Migrate llama-cpp, log-analyzer
12. Migrate Loki (highest risk, do last)
13. Resume full infrastructure/workloads
14. Full cluster validation

**Total estimated time:** 2-3 days with testing
**Total downtime:** 5-7 minutes (staggered)

---

## Conclusion

**Can we test everything before applying?**
- ✅ YAML syntax: Yes (`kubectl kustomize`)
- ✅ API schema: Yes (`kubectl apply --dry-run=server`)
- ✅ Chart versions: Yes (`helm search repo`)
- ✅ Flux structure: Yes (`flux diff` after suspended bootstrap)
- ❌ Runtime behavior: No (requires actual reconciliation)

**Recommendation:**
1. Do all pre-bootstrap validation NOW
2. Bootstrap Flux in suspended mode (safe, reversible)
3. Test with `flux diff` (see what WOULD happen)
4. Migrate incrementally, one component at a time
5. Keep old Helm releases as rollback option

This approach minimizes risk and gives you multiple "escape hatches" if something goes wrong.
