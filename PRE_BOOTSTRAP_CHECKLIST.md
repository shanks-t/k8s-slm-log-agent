# Pre-Bootstrap Checklist

**Purpose:** Actionable steps to prepare for safe Flux bootstrap
**Status:** Ready to execute
**Estimated Time:** 30 minutes

---

## Current Status

✅ **Steps 1-5 Complete:**
- Cluster inventory exported
- Flux directory structure created
- 5 HelmReleases converted
- All kustomization files validated

⏳ **Remaining Before Bootstrap:**
- Pre-flight validation
- Suspend flags for safe bootstrap
- Migration state snapshot

---

## Checklist: Complete Before Bootstrap

### 1. Validation (5 minutes)

- [x] **Kustomize builds successfully**
  ```bash
  kubectl kustomize infrastructure/  # ✅ Passed
  kubectl kustomize workloads/       # ✅ Passed
  ```

- [ ] **Chart versions exist in Helm repos**
  ```bash
  helm repo add grafana https://grafana.github.io/helm-charts
  helm repo add envoyproxy https://gateway.envoyproxy.io
  helm repo update

  # Verify chart versions
  helm search repo grafana/loki --version 6.21.0
  helm search repo grafana/grafana --version 10.2.0
  helm search repo grafana/tempo --version 1.24.1
  helm search repo grafana/alloy --version 1.4.0
  helm search repo envoyproxy/gateway-helm --version v1.4.6
  ```

- [ ] **Git working tree clean**
  ```bash
  git status  # Should be: nothing to commit, working tree clean
  ```

- [ ] **All changes pushed to GitHub**
  ```bash
  git push --dry-run  # Should have nothing to push
  ```

- [ ] **Cluster accessible**
  ```bash
  kubectl get nodes  # Should show node1, node2
  kubectl get pods -A | wc -l  # Should show running pods
  ```

---

### 2. Add Suspend Flags (5 minutes)

**Why:** Bootstrap Flux without touching existing resources

**Edit:** `clusters/homelab/infrastructure.yaml`

```yaml
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

**Edit:** `clusters/homelab/workloads.yaml`

```yaml
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

**Commit:**
```bash
git add clusters/homelab/
git commit -m "feat(flux): add suspend flags for safe bootstrap"
git push
```

- [ ] Suspend flags added to infrastructure.yaml
- [ ] Suspend flags added to workloads.yaml
- [ ] Changes committed and pushed

---

### 3. Create Migration State Snapshot (10 minutes)

**Purpose:** Document current state for rollback reference

**Create:** `MIGRATION_STATE.md`

```bash
cat > MIGRATION_STATE.md << EOF
# Migration State Snapshot

**Date:** $(date)
**Branch:** $(git branch --show-current)
**Commit:** $(git rev-parse HEAD)
**Cluster:** K3S homelab (node1 + node2)

---

## Current Cluster State (Pre-Migration)

### Namespaces (8)
- default
- kube-system, kube-public, kube-node-lease (K8s internals)
- envoy-gateway-system (Envoy Gateway)
- logging (Loki, Grafana, Tempo, Alloy)
- llm (llama-cpp)
- log-analyzer (FastAPI service)

### Helm Releases (5) - TO BE MIGRATED
\`\`\`
NAMESPACE              NAME      CHART             VERSION   STATUS
envoy-gateway-system   eg        gateway-helm      v1.4.6    deployed
logging                alloy     alloy             1.4.0     deployed
logging                grafana   grafana           10.2.0    deployed
logging                loki      loki              6.21.0    deployed
logging                tempo     tempo             1.24.1    deployed
\`\`\`

### YAML Workloads (2) - TO BE MIGRATED
- llama-cpp (Deployment + Service + PVC) - llm namespace
- log-analyzer (Deployment + Service + ConfigMap) - log-analyzer namespace

### PersistentVolumes (4)
- llama-models-pv (20Gi, Node 2, /mnt/k8s-storage/models)
- loki-pv (200Gi, Node 2, /mnt/k8s-storage/loki)
- tempo-pv (50Gi, Node 2, /mnt/k8s-storage/tempo)
- pvc-* (50Gi, dynamic, K3S local-path)

---

## Migration Order (Lowest Risk → Highest Risk)

1. **Storage (PVs)** - Risk: LOW, Downtime: 0s
   - Already exist, Flux will adopt them
   - No conflicts expected

2. **Envoy Gateway** - Risk: LOW, Downtime: 10s
   - Standalone controller
   - Easy rollback

3. **Alloy** - Risk: LOW, Downtime: 30s
   - DaemonSet, gradual rollout
   - Log collection gap acceptable

4. **Tempo** - Risk: LOW, Downtime: 30s
   - Tracing, non-critical
   - Can lose recent traces

5. **Grafana** - Risk: LOW, Downtime: 30s
   - UI only, no data loss
   - Dashboards in Git

6. **llama-cpp** - Risk: MEDIUM, Downtime: 1min
   - Workload, no persistent state
   - LLM inference unavailable during migration

7. **log-analyzer** - Risk: MEDIUM, Downtime: 1min
   - Workload, no persistent state
   - API unavailable during migration

8. **Loki** - Risk: HIGH, Downtime: 2-3min
   - Log storage with PV
   - Critical component
   - Potential PVC rebinding issues

**Total Estimated Downtime:** 5-7 minutes (staggered)

---

## Rollback Plan

### If Single Component Fails
1. Suspend Flux: \`flux suspend kustomization infrastructure\`
2. Delete Flux HelmRelease: \`kubectl delete helmrelease <name> -n <namespace>\`
3. Reinstall with Helm: \`helm install <name> <chart> -n <namespace> -f inventory/helm-values-<name>.yaml\`

### If Flux Entirely Fails
1. Uninstall Flux: \`flux uninstall --silent\`
2. Reinstall all Helm releases from \`inventory/\` directory
3. Reapply YAML workloads from \`workloads/*/k8s/\` directories

**Backup Files:**
- \`inventory/helm-releases.yaml\` - List of all releases
- \`inventory/helm-values-*.yaml\` - Helm values for each release
- \`workloads/llama-cpp/k8s/\` - llama-cpp manifests
- \`workloads/log-analyzer/k8s/\` - log-analyzer manifests

---

## Success Criteria

- [x] Flux controllers running in flux-system namespace
- [ ] All HelmReleases show READY True
- [ ] All pods running and healthy
- [ ] Services accessible (Grafana UI, LLM inference, log analysis)
- [ ] No old Helm releases: \`helm list -A\` returns empty
- [ ] Flux managing all resources: \`flux get all\`

---

## Notes

- K3S-specific features: local-path storage, ServiceLB
- Node labels: node1=hardware:light, node2=hardware:heavy
- Node taints: node2=heavy:NoSchedule
- PV reclaim policy: Retain (data safe)
- Grafana admin password: admin (TODO: move to Secret)
EOF
```

**Commit:**
```bash
git add MIGRATION_STATE.md
git commit -m "docs(flux): create migration state snapshot"
git push
```

- [ ] MIGRATION_STATE.md created
- [ ] Committed and pushed

---

### 4. Install Flux CLI (5 minutes)

**If not already installed:**

```bash
# macOS
brew install fluxcd/tap/flux

# Verify installation
flux --version

# Check prerequisites
flux check --pre
# Expected: ✔ Kubernetes version >= 1.26.0
```

- [ ] Flux CLI installed
- [ ] `flux check --pre` passes

---

### 5. Set GitHub Credentials (5 minutes)

**Create GitHub Personal Access Token:**
1. Go to: https://github.com/settings/tokens/new
2. Set name: "Flux GitOps - k8s-slm-log-agent"
3. Expiration: 90 days (or longer)
4. Scopes: Select `repo` (full control of private repositories)
5. Click "Generate token"
6. Copy token (you won't see it again!)

**Set environment variables:**
```bash
export GITHUB_USER=your-github-username
export GITHUB_TOKEN=ghp_your_personal_access_token_here
export GITHUB_REPO=k8s-slm-log-agent

# Verify
echo $GITHUB_USER
echo $GITHUB_REPO
echo ${GITHUB_TOKEN:0:10}...  # Show first 10 chars only
```

**Store securely (optional):**
```bash
# Add to ~/.zshrc or ~/.bashrc for persistence
echo "export GITHUB_USER=your-username" >> ~/.zshrc
echo "export GITHUB_TOKEN=ghp_your_token" >> ~/.zshrc
echo "export GITHUB_REPO=k8s-slm-log-agent" >> ~/.zshrc
```

- [ ] GitHub token created
- [ ] Environment variables set
- [ ] Token verified

---

## Ready to Bootstrap?

**When all checkboxes are complete, you're ready to bootstrap Flux!**

**Next command:**
```bash
flux bootstrap github \
  --owner=$GITHUB_USER \
  --repository=$GITHUB_REPO \
  --branch=agent/flux \
  --path=clusters/homelab \
  --personal \
  --components-extra=image-reflector-controller,image-automation-controller
```

**Expected result:**
- Flux controllers installed in flux-system namespace
- infrastructure/workloads Kustomizations created (SUSPENDED)
- Your existing resources UNTOUCHED
- Zero downtime

**After bootstrap:**
1. Verify suspension: `flux get kustomizations` (infrastructure/workloads should show SUSPENDED True)
2. Test reconciliation: `flux diff kustomization infrastructure --path ./infrastructure`
3. Proceed with incremental migration (see: docs/flux-migration-testing-strategy.md)

---

**Questions before proceeding?** Refer to:
- [flux-migration-testing-strategy.md](docs/flux-migration-testing-strategy.md) - Detailed migration plan
- [flux-tools-reference.md](docs/flux-tools-reference.md) - Flux command reference
- [infra-roadmap.md](infra-roadmap.md) - Original migration roadmap
