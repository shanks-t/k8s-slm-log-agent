# K3S to Full Kubernetes Migration Plan

**Date:** 2025-12-28
**Reason:** K3S kube-router NetworkPolicy incompatibility blocking Flux CD
**Estimated Time:** 2-3 hours
**Risk Level:** Medium (no critical data loss risk)

---

## Context

**Problem:** K3S embedded kube-router creates iptables NetworkPolicy enforcement rules that cannot be disabled and block pod-to-service communication on port 80, preventing Flux CD from functioning.

**Solution:** Migrate to full Kubernetes which uses standard kube-proxy without K3S-specific kube-router quirks.

**Existing Documentation:**
- Current state already captured in `inventory/` (14 files)
- Manifests already exported to `exports/` (3,274 lines YAML)
- Helm values already saved for all 5 releases
- Flux GitOps structure already prepared in Git

---

## Pre-Migration Status

### Current Cluster State (from FLUX_MIGRATION_PROGRESS.md)

**K3S Version:** v1.33.6+k3s1
**Nodes:** 2 (node-1 control-plane, node-2 worker)

**Helm Releases (5):**
- `loki` (6.21.0) - logging namespace
- `grafana` (10.2.0) - logging namespace
- `tempo` (1.24.1) - logging namespace
- `alloy` (1.4.0) - logging namespace
- `eg` (v1.4.6) - envoy-gateway-system namespace

**Workloads (2):**
- `llama-cpp` - llm namespace (20d uptime)
- `log-analyzer` - log-analyzer namespace (hours old)

**Storage:**
- Node 2 NVMe: `/mnt/k8s-storage` (Samsung 476GB)
- 3 PersistentVolumes: llama-models-pv, loki-pv, tempo-pv
- Local-path provisioner (K3S built-in)

**Networking:**
- CNI: Flannel (vxlan)
- Service CIDR: 10.43.0.0/16
- Pod CIDR: 10.42.0.0/16
- Envoy Gateway for ingress (Traefik disabled)

**Flux Status:**
- Branch: `agent/flux`
- Suspended: infrastructure.yaml and workloads.yaml have `suspend: true`
- Bootstrap attempted but blocked by port 80 issue

---

## Migration Phases

### Phase 1: Uninstall K3S (10 minutes)

#### 1.1 Stop K3S Services

```bash
# On node-1 (control plane)
ssh node1 'sudo systemctl stop k3s'

# On node-2 (worker)
ssh node2 'sudo systemctl stop k3s-agent'
```

#### 1.2 Uninstall K3S

```bash
# On node-1
ssh node1 'sudo /usr/local/bin/k3s-uninstall.sh'

# On node-2
ssh node2 'sudo /usr/local/bin/k3s-agent-uninstall.sh'
```

#### 1.3 Clean Up Remnants

```bash
# On both nodes - remove leftover configs and data
ssh node1 'sudo rm -rf /etc/rancher /var/lib/rancher ~/.kube'
ssh node2 'sudo rm -rf /etc/rancher /var/lib/rancher'

# Clean up iptables (K3S leaves rules behind)
ssh node1 'sudo iptables -F && sudo iptables -t nat -F && sudo iptables -t mangle -F'
ssh node2 'sudo iptables -F && sudo iptables -t nat -F && sudo iptables -t mangle -F'
```

#### 1.4 Preserve Storage

```bash
# Verify Node 2 storage is intact (DO NOT DELETE)
ssh node2 'ls -lh /mnt/k8s-storage/'
# Should show: loki/, tempo/, models/
```

**Expected Result:** K3S completely removed, storage preserved.

---

### Phase 2: Install Kubernetes Prerequisites (20 minutes)

#### 2.1 Install Container Runtime (containerd)

```bash
# On both nodes
for node in node1 node2; do
  ssh $node 'bash -s' << 'SCRIPT'
    # Install containerd
    sudo apt-get update
    sudo apt-get install -y containerd

    # Configure containerd
    sudo mkdir -p /etc/containerd
    containerd config default | sudo tee /etc/containerd/config.toml

    # Enable systemd cgroup driver (required for K8s)
    sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

    # Restart containerd
    sudo systemctl restart containerd
    sudo systemctl enable containerd
SCRIPT
done
```

#### 2.2 Install Kubernetes Packages

```bash
# On both nodes - install kubeadm, kubelet, kubectl
for node in node1 node2; do
  ssh $node 'bash -s' << 'SCRIPT'
    # Add Kubernetes apt repository
    sudo apt-get update
    sudo apt-get install -y apt-transport-https ca-certificates curl gpg

    curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key | \
      sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' | \
      sudo tee /etc/apt/sources.list.d/kubernetes.list

    # Install Kubernetes components
    sudo apt-get update
    sudo apt-get install -y kubelet kubeadm kubectl
    sudo apt-mark hold kubelet kubeadm kubectl

    # Enable kubelet
    sudo systemctl enable kubelet
SCRIPT
done
```

#### 2.3 Disable Swap (Kubernetes requirement)

```bash
# On both nodes
for node in node1 node2; do
  ssh $node 'sudo swapoff -a && sudo sed -i "/ swap / s/^/#/" /etc/fstab'
done
```

#### 2.4 Enable Kernel Modules

```bash
# On both nodes
for node in node1 node2; do
  ssh $node 'bash -s' << 'SCRIPT'
    # Load br_netfilter module
    sudo modprobe br_netfilter
    echo "br_netfilter" | sudo tee /etc/modules-load.d/k8s.conf

    # Enable IP forwarding
    cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
    sudo sysctl --system
SCRIPT
done
```

**Expected Result:** Both nodes ready for Kubernetes installation.

---

### Phase 3: Initialize Kubernetes Cluster (30 minutes)

#### 3.1 Initialize Control Plane (node-1)

```bash
ssh node1 'sudo kubeadm init \
  --pod-network-cidr=10.42.0.0/16 \
  --service-cidr=10.43.0.0/16 \
  --apiserver-advertise-address=10.0.0.102 \
  --node-name=node-1'
```

**Note:** Using same CIDRs as K3S to avoid IP conflicts.

#### 3.2 Configure kubectl Access

```bash
# On node-1
ssh node1 'mkdir -p ~/.kube && \
  sudo cp /etc/kubernetes/admin.conf ~/.kube/config && \
  sudo chown $(id -u):$(id -g) ~/.kube/config'

# Copy kubeconfig to local machine
scp node1:~/.kube/config ~/.kube/config
```

#### 3.3 Verify Control Plane

```bash
kubectl get nodes
# Expected: node-1 NotReady (no CNI yet)

kubectl get pods -A
# Expected: coredns pending (no CNI yet)
```

---

### Phase 4: Install CNI Plugin (15 minutes)

**Choice:** Cilium (recommended - no NetworkPolicy quirks, better observability)

#### 4.1 Install Cilium CLI

```bash
# On local machine
CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt)
CLI_ARCH=amd64
curl -L --fail --remote-name-all https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-darwin-${CLI_ARCH}.tar.gz{,.sha256sum}
shasum -a 256 -c cilium-darwin-${CLI_ARCH}.tar.gz.sha256sum
sudo tar xzvfC cilium-darwin-${CLI_ARCH}.tar.gz /usr/local/bin
rm cilium-darwin-${CLI_ARCH}.tar.gz{,.sha256sum}
```

#### 4.2 Install Cilium to Cluster

```bash
cilium install --version 1.16.5
```

#### 4.3 Verify Cilium

```bash
cilium status --wait

kubectl get pods -n kube-system -l k8s-app=cilium
# Expected: cilium-xxx Running
```

#### 4.4 Verify Node Status

```bash
kubectl get nodes
# Expected: node-1 Ready
```

---

### Phase 5: Join Worker Node (15 minutes)

#### 5.1 Get Join Command

```bash
ssh node1 'sudo kubeadm token create --print-join-command'
# Copy the output
```

#### 5.2 Join node-2

```bash
# Paste the join command from above
ssh node2 'sudo kubeadm join 10.0.0.102:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash> \
  --node-name=node-2'
```

#### 5.3 Verify Both Nodes Ready

```bash
kubectl get nodes
# Expected:
# node-1   Ready    control-plane   Xm   v1.31.x
# node-2   Ready    <none>          Xm   v1.31.x
```

---

### Phase 6: Install Storage Provisioner (10 minutes)

**Option A: Rancher local-path-provisioner (same as K3S)**

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml

# Set as default StorageClass
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

**Option B: Use existing /mnt/k8s-storage with manual PVs**

We'll create PVs pointing to existing directories (for Loki, Tempo, LLM models).

---

### Phase 7: Label and Taint Nodes (5 minutes)

Recreate node labels/taints from K3S cluster:

```bash
# Label node-1 as lightweight hardware
kubectl label node node-1 hardware=light

# Label node-2 as heavy hardware
kubectl label node node-2 hardware=heavy

# Taint node-2 for heavy workloads only
kubectl taint node node-2 heavy=true:NoSchedule
```

---

### Phase 8: Bootstrap Flux CD (10 minutes)

#### 8.1 Verify Flux Prerequisites

```bash
flux check --pre
# Should pass with Kubernetes 1.31
```

#### 8.2 Bootstrap Flux

```bash
# Set GitHub credentials
export GITHUB_USER=<your-github-username>
export GITHUB_TOKEN=<your-github-token>
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

#### 8.3 Verify Flux Installation

```bash
kubectl get pods -n flux-system
# Expected: All 6 Flux controllers Running

flux get all -A
# Expected: GitRepository and Kustomizations (suspended)
```

#### 8.4 TEST PORT 80 (CRITICAL)

```bash
kubectl run test-port80-k8s --image=curlimages/curl --rm -i --restart=Never -- \
  curl -v http://source-controller.flux-system.svc.cluster.local/

# Expected: SUCCESS (200 OK or 404, but NOT connection refused)
```

**If port 80 works:** Migration successful! ✅

---

### Phase 9: Restore Workloads via Flux (30 minutes)

#### 9.1 Create PersistentVolumes for Existing Data

Since we have data in `/mnt/k8s-storage/`, create PVs pointing to existing directories:

```bash
# Apply PV manifests from infrastructure/storage/
kubectl apply -f infrastructure/storage/
```

#### 9.2 Resume Flux Infrastructure Reconciliation

```bash
# Edit clusters/homelab/infrastructure.yaml - remove suspend: true
# Commit and push

git add clusters/homelab/infrastructure.yaml
git commit -m "feat(flux): resume infrastructure reconciliation on K8s"
git push
```

#### 9.3 Monitor Flux Reconciliation

```bash
flux reconcile kustomization flux-system --with-source

# Watch reconciliation
flux logs --follow --level=info

# Check HelmReleases
flux get helmreleases -A
```

#### 9.4 Resume Flux Workloads Reconciliation

```bash
# Edit clusters/homelab/workloads.yaml - remove suspend: true
# Commit and push

git add clusters/homelab/workloads.yaml
git commit -m "feat(flux): resume workloads reconciliation on K8s"
git push

flux reconcile kustomization flux-system --with-source
```

---

### Phase 10: Validation (20 minutes)

#### 10.1 Verify All Pods Running

```bash
kubectl get pods -A
# Expected: All pods Running or Completed
```

#### 10.2 Verify Helm Releases

```bash
flux get helmreleases -A
# Expected: All 5 releases Ready
```

#### 10.3 Verify Workloads

```bash
kubectl get deploy,sts,ds -A
# Expected:
# - llama-cpp deployment Running
# - log-analyzer deployment Running
# - loki StatefulSet Running
# - tempo StatefulSet Running
# - grafana deployment Running
# - alloy DaemonSet Running (2/2)
```

#### 10.4 Verify PersistentVolumes

```bash
kubectl get pv,pvc -A
# Expected: All PVs Bound
```

#### 10.5 Test Services

```bash
# Test Grafana via Envoy Gateway
curl http://10.0.0.102/grafana/

# Test LLM inference
kubectl run test-llm --image=curlimages/curl --rm -i --restart=Never -- \
  curl http://llama-cpp.llm.svc.cluster.local:8080/health

# Test log analyzer
kubectl run test-logs --image=curlimages/curl --rm -i --restart=Never -- \
  curl http://log-analyzer.log-analyzer.svc.cluster.local:8000/health
```

#### 10.6 Verify Flux Drift Detection

```bash
# Make manual change to a deployment
kubectl scale deployment grafana -n logging --replicas=2

# Wait 1 minute, check if Flux reverted it
kubectl get deployment grafana -n logging
# Expected: Replicas back to 1 (Flux reverted)
```

---

## Rollback Plan (If Migration Fails)

If Kubernetes installation fails catastrophically:

```bash
# 1. Uninstall Kubernetes
ssh node1 'sudo kubeadm reset -f && sudo apt-get purge -y kubeadm kubelet kubectl'
ssh node2 'sudo kubeadm reset -f && sudo apt-get purge -y kubeadm kubelet kubectl'

# 2. Reinstall K3S
ssh node1 'curl -sfL https://get.k3s.io | sh -s - --disable traefik --write-kubeconfig-mode 644 --node-label hardware=light'

# Get K3S token
ssh node1 'sudo cat /var/lib/rancher/k3s/server/node-token'

# 3. Join node-2
ssh node2 'curl -sfL https://get.k3s.io | K3S_URL=https://node1:6443 K3S_TOKEN=<token> sh -s - --node-label hardware=heavy'

# 4. Reinstall workloads using Helm (values in inventory/)
cd inventory/
helm install loki grafana/loki -n logging -f helm-values-loki.yaml
helm install grafana grafana/grafana -n logging -f helm-values-grafana.yaml
# ... etc
```

---

## Success Criteria

- ✅ Both nodes show Ready status
- ✅ All 6 Flux controllers Running
- ✅ **Port 80 pod-to-service connectivity works**
- ✅ All 5 HelmReleases reconciled
- ✅ All workloads (llama-cpp, log-analyzer) Running
- ✅ Grafana accessible via Envoy Gateway
- ✅ LLM inference working
- ✅ Log analyzer API responding
- ✅ Flux drift detection working (manual changes reverted)

---

## Known Differences: K8s vs K3S

| Feature | K3S | Full K8s | Impact |
|---------|-----|----------|--------|
| **Storage** | Built-in local-path | Need to install local-path-provisioner | One extra step |
| **LoadBalancer** | Built-in ServiceLB | Need MetalLB or cloud provider | Need to install MetalLB |
| **Ingress** | Built-in Traefik (disabled) | None | Envoy Gateway works on both |
| **NetworkPolicy** | kube-router (buggy) | Standard kube-proxy | **FIXES PORT 80 ISSUE** |
| **Binary size** | Single binary | Multiple components | Doesn't affect us |
| **Memory usage** | Lower | Higher | Node-1 has 32GB, fine |

---

## Post-Migration Tasks

### Optional Enhancements

1. **Install MetalLB for LoadBalancer services**
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml
   ```

2. **Enable Kubernetes Dashboard**
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
   ```

3. **Install Prometheus Operator (for better metrics)**
   ```bash
   helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring
   ```

### Documentation Updates

1. Update `FLUX_MIGRATION_PROGRESS.md` with migration completion
2. Create `K3S_TO_K8S_MIGRATION_RESULTS.md` documenting:
   - Actual time taken
   - Issues encountered
   - Port 80 fix verification
   - Lessons learned

3. Update `agents.md` to mark Phase 7 complete

---

## Estimated Timeline

| Phase | Task | Time | Cumulative |
|-------|------|------|------------|
| 1 | Uninstall K3S | 10 min | 10 min |
| 2 | Install prerequisites | 20 min | 30 min |
| 3 | Initialize control plane | 30 min | 1h |
| 4 | Install Cilium CNI | 15 min | 1h 15m |
| 5 | Join worker node | 15 min | 1h 30m |
| 6 | Install storage | 10 min | 1h 40m |
| 7 | Label/taint nodes | 5 min | 1h 45m |
| 8 | Bootstrap Flux | 10 min | 1h 55m |
| 9 | Restore workloads | 30 min | 2h 25m |
| 10 | Validation | 20 min | **2h 45m** |

**Total: ~3 hours**

---

## References

- [Kubernetes kubeadm installation](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/)
- [Cilium installation](https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/)
- [Flux CD installation](https://fluxcd.io/flux/installation/)
- [Rancher local-path-provisioner](https://github.com/rancher/local-path-provisioner)

---

**Last Updated:** 2025-12-28
**Status:** Ready to execute
**Next Step:** Begin Phase 1 - Uninstall K3S
