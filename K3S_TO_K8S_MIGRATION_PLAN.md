# K3S to Full Kubernetes Migration Plan

**Date:** 2025-12-28 (Updated: 2025-12-29)
**Reason:** K3S kube-router NetworkPolicy incompatibility blocking Flux CD
**Estimated Time:** 2-3 hours
**Risk Level:** Medium (no critical data loss risk)
**Status:** ✅ **COMPLETED** (2025-12-29)
**Purpose:** Production Kubernetes cluster + CKA exam preparation

---

## Migration Outcome Summary

**Final Cluster State:**
- ✅ Kubernetes v1.35.0 (upgraded from v1.31)
- ✅ 2 nodes (node-1 control-plane, node-2 worker)
- ✅ Flannel CNI (vxlan, UDP 8472)
- ✅ Same network CIDRs as K3S (Pod: 10.42.0.0/16, Service: 10.43.0.0/16)
- ✅ Node labels and taints applied
- ✅ Ready for Flux CD bootstrap

**CKA Exam Skills Practiced:**
- Domain 1 (25%): Cluster installation with kubeadm, multi-version upgrade
- Domain 2 (15%): Node labeling, taints/tolerations
- Domain 3 (20%): CNI installation and troubleshooting
- Domain 5 (30%): Node NotReady troubleshooting, CNI debugging, shell command issues

---

## Lessons Learned (CKA Exam Insights)

### 1. Kubernetes Version Upgrades Must Be Incremental
**Issue:** Attempted to skip from v1.31 → v1.35 directly
**Error:** `kubeadm only supports deploying clusters with control plane version >= 1.34.0`
**Solution:** Fresh install with v1.35.0 instead of 4-step upgrade (1.31→1.32→1.33→1.34→1.35)
**CKA Lesson:** On exam, Kubernetes upgrades must be done one minor version at a time

### 2. SSH Command Shell Glob Expansion Gotcha
**Issue:** `ssh node1 'sudo rm -rf /etc/cni/net.d/*'` didn't delete files
**Root Cause:** `*` glob expanded on local machine (no such directory), not on remote node
**Solution:** Either escape glob (`\*`), or SSH in directly and run command
**CKA Lesson:** On exam, when remote commands fail, SSH into node and run directly (safer, faster)

### 3. Node "Ready" Doesn't Mean "Functional"
**Issue:** Node showed Ready but CoreDNS stuck in ContainerCreating for 30+ minutes
**Root Cause:** CNI config file existed but no CNI pods running (half-installed CNI)
**Troubleshooting Pattern:**
```bash
kubectl get nodes              # Ready
kubectl get pods -A            # CoreDNS ContainerCreating
ls /etc/cni/net.d/            # Config exists
kubectl get pods -n kube-system | grep flannel  # No CNI pods!
```
**CKA Lesson:** Always verify CNI pods running, not just node status

### 4. kubeadm reset Doesn't Clean Everything
**Files NOT removed by `kubeadm reset`:**
- `/etc/cni/net.d/*` (CNI configs)
- `/opt/cni/bin/*` (CNI binaries)
- Some iptables rules
**CKA Lesson:** Manual cleanup required after reset for clean reinstall

### 5. Flannel vs Cilium for CKA Exam
**Decision:** Use Flannel initially, upgrade to Cilium later as learning exercise
**Rationale:**
- Flannel is simpler and more common on CKA exam
- Cilium upgrade later teaches CNI replacement (another CKA skill)
- Exam typically uses Flannel, Calico, or Weave
**CKA Lesson:** Practice with exam-standard tools first, then explore alternatives

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
  --pod-network-cidr=10.244.0.0/16 \
  --service-cidr=10.96.0.0/12 \
  --apiserver-advertise-address=10.0.0.102 \
  --node-name=node-1'
```

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

**CKA Domain 3 - Services & Networking (20%)**

**CNI Choice:** Flannel (CKA exam standard, simple, widely used)

**Why Flannel:**
- Most common CNI on CKA exam (along with Calico)
- Simple overlay network (VXLAN)
- No external dependencies
- Easy to troubleshoot
- Can upgrade to Cilium later as learning exercise

**CKA Exam Note:** Exam will specify which CNI to install. Common options:
- Flannel: `kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml`
- Calico: `kubectl apply -f https://docs.projectcalico.org/manifests/calico.yaml`
- Weave: `kubectl apply -f https://github.com/weaveworks/weave/releases/download/v2.8.1/weave-daemonset-k8s.yaml`

#### 4.1 Verify CNI Directory is Clean

```bash
# CKA Troubleshooting Tip: Always check before installing CNI
ssh node1 'ls /etc/cni/net.d/'
# Should be empty (or just .kubernetes-cni-keep)

# If files exist from previous attempts:
ssh node1
sudo rm -rf /etc/cni/net.d/*
exit

# CKA Lesson: SSH glob expansion gotcha!
# Don't use: ssh node1 'sudo rm /etc/cni/net.d/*'  (glob expands locally)
# Use: SSH in directly and run command (safer on exam)
```
#### Had to cleanup old cilium and flannel kernel level network interface objects
- 'sudo bash -s' so everything executes as root on the remote host
```sh
ssh node1 'sudo bash -s' <<'EOF'
set -euo pipefail

# --- Remove leftover Cilium interfaces (ignore if absent) ---
ip link delete cilium_net 2>/dev/null || true
ip link delete cilium_host 2>/dev/null || true
ip link delete cilium_vxlan 2>/dev/null || true

# --- Remove leftover Flannel/CNI interfaces (ignore if absent) ---
ip link delete flannel.1 2>/dev/null || true
ip link delete cni0 2>/dev/null || true

# --- Clear CNI config + state ---
rm -rf /etc/cni/net.d/*
rm -rf /var/lib/cni/*

# --- Ensure required kernel modules ---
modprobe br_netfilter || true

# --- Sysctls for Kubernetes networking ---
cat >/etc/sysctl.d/k8s.conf <<'SYSCTL'
net.bridge.bridge-nf-call-iptables=1
net.bridge.bridge-nf-call-ip6tables=1
net.ipv4.ip_forward=1
SYSCTL

sysctl --system

# --- Restart services ---
systemctl restart containerd || true
systemctl restart kubelet

echo "Done. Current links:"
ip -br link | sed 's/^/  /'
EOF

```

#### 4.2 Install Flannel CNI

```bash
# CKA exam-style approach (kubectl only, no external CLIs)
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

**What this creates:**
- Namespace: `kube-flannel`
- ServiceAccount: `flannel`
- ClusterRole/ClusterRoleBinding: RBAC for flannel
- ConfigMap: `kube-flannel-cfg` (network config)
- DaemonSet: `kube-flannel-ds` (runs on all nodes)

**CKA Exam Knowledge: How CNI Works**
1. **CNI config file** created in `/etc/cni/net.d/` (tells kubelet which CNI to use)
2. **CNI DaemonSet pods** run on every node (allocate IPs, create routes)
3. **Kubelet** calls CNI plugin when creating/deleting pods
4. **Pods** get IP addresses from CNI IPAM (IP Address Management)

#### 4.3 Watch Flannel Deployment

```bash
# CKA Troubleshooting Pattern: Watch pods deploy
kubectl get pods -n kube-flannel -w

# Expected sequence:
# kube-flannel-ds-xxxxx   0/1   Init:0/2            (installing CNI binaries)
# kube-flannel-ds-xxxxx   0/1   Init:1/2            (installing CNI config)
# kube-flannel-ds-xxxxx   0/1   PodInitializing     (starting main container)
# kube-flannel-ds-xxxxx   1/1   Running             (CNI operational)
```

#### 4.4 Verify CNI Installation (CKA Troubleshooting Checklist)

```bash
# 1. Check Flannel pods running
kubectl get pods -n kube-flannel
# Should see: kube-flannel-ds-xxxxx   1/1   Running

# 2. Check CNI config created
ssh node1 'ls /etc/cni/net.d/'
# Should see: 10-flannel.conflist

# 3. Check CoreDNS now running (proves networking works)
kubectl get pods -n kube-system -l k8s-app=kube-dns
# Should see: coredns-xxx   1/1   Running (not Pending/ContainerCreating)

# 4. Check node status
kubectl get nodes
# Expected: node-1   Ready   control-plane

# 5. Test pod networking (CKA exam verification)
kubectl run test-dns --image=busybox:1.28 --rm -it --restart=Never -- nslookup kubernetes.default
# Should resolve to 10.43.0.1 (service CIDR)
```

**CKA Troubleshooting: If CoreDNS Still Pending**

```bash
# Check CNI pod logs
kubectl logs -n kube-flannel kube-flannel-ds-xxxxx

# Check kubelet logs on node
ssh node1 'sudo journalctl -u kubelet -n 50 | grep -i cni'

# Check for CNI config
ssh node1 'cat /etc/cni/net.d/10-flannel.conflist'

# Common issues:
# - Flannel pod CrashLooping → Check pod logs
# - No CNI config file → DaemonSet pod didn't run init containers
# - Node still NotReady → Give it 30 seconds, CNI takes time to initialize
#  When pods won't start (ContainerCreating):

#   1. ✓ Check CNI pods running: kubectl get pods -n kube-flannel
#   2. ✓ Check subnet file: cat /run/flannel/subnet.env
#   3. ✗ Check CNI config: ls /etc/cni/net.d/  ← YOU FOUND THE ISSUE HERE!
#   4. Check kubelet logs: journalctl -u kubelet | grep cni
#   5. Restart CNI pods if needed

#   Memorize this order for the exam!

#   ---
#   Run This Now:

#   # Restart Flannel pod to recreate CNI config
#   kubectl delete pod -n kube-flannel kube-flannel-ds-v4qrr

#   # Watch it restart
#   kubectl get pods -n kube-flannel -w
#   # (Ctrl+C after it shows Running)

#   # Immediately check if CNI config was created
#   ssh node1 'ls -la /etc/cni/net.d/'

#   # If config exists, watch CoreDNS start
#   kubectl get pods -n kube-system -w
```

---

### Phase 5: Join Worker Node (15 minutes)

#### 5.1 Get Join Command

```bash
ssh node1 'sudo kubeadm token create --print-join-command'
# Copy the output
```
or
```sh
JOIN_CMD=$(ssh node1 'sudo -n kubeadm token create --print-join-command')
TOKEN=$(sed -n 's/.*--token \([^ ]*\).*/\1/p' <<<"$JOIN_CMD")
HASH=$(sed -n 's/.*--discovery-token-ca-cert-hash \([^ ]*\).*/\1/p' <<<"$JOIN_CMD")
```

#### 5.2 Join node-2

```bash
# Paste the join command from above
ssh node2 'sudo kubeadm join 10.0.0.102:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash> \
  --node-name=node-2'
```
or
```sh
ssh node2 "sudo kubeadm join 10.0.0.102:6443 \
  --token $TOKEN \
  --discovery-token-ca-cert-hash $HASH \
  --node-name=node-2"
```


#### 5.3 Verify Both Nodes Ready

```bash
kubectl get nodes
# Expected:
# node-1   Ready    control-plane   Xm   v1.31.x
# node-2   Ready    <none>          Xm   v1.31.x
```

---

### Phase 6: Storage Provisioning (SKIPPED - Flux Will Handle)

**CKA Domain 4 - Storage (10%)**

**Decision:** Skip manual storage provisioner installation. Flux GitOps will create PersistentVolumes from `infrastructure/storage/`.

**Rationale:**
- PV manifests already exist in Flux repo (`infrastructure/storage/`)
- Flux will create them during Phase 9 (infrastructure reconciliation)
- Avoids duplicate resource management (imperative vs declarative)
- Follows GitOps best practice: single source of truth

**What Flux Will Create:**

```yaml
# From infrastructure/storage/kustomization.yaml:
resources:
  - llama-pv.yaml    # 20GB for LLM models on Node 2
  - loki-pv.yaml     # 200GB for Loki log storage on Node 2
  - tempo-pv.yaml    # 50GB for Tempo trace storage on Node 2
```

**PV Configuration (Example: llama-pv.yaml):**
- **storageClassName:** `local-storage` (no provisioner, static binding)
- **path:** `/mnt/k8s-storage/models` (existing directory on node-2)
- **nodeAffinity:** Tied to node-2 (where Samsung NVMe is mounted)
- **reclaimPolicy:** Retain (data safe even if PVC deleted)
- **accessMode:** ReadOnlyMany (multiple LLM pods can share)

**CKA Exam Knowledge: Static vs Dynamic Provisioning**

| Static (Our Approach) | Dynamic |
|----------------------|---------|
| Admin creates PV manually | StorageClass + Provisioner create PV automatically |
| PVC binds to existing PV | PVC triggers PV creation |
| Good for: Local storage, NFS | Good for: Cloud storage (AWS EBS, GCE PD) |
| **No provisioner needed** | Requires storage provisioner |

**CKA Exam Scenario:** "Create a PV for local storage on node-2 at /data"
- Answer: Create PV with `local:` volume type + nodeAffinity
- **No StorageClass or provisioner needed for local volumes!**

**Verification After Flux Bootstrap (Phase 9):**

```bash
# Check PVs created by Flux
kubectl get pv
# Expected:
# NAME              CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      STORAGECLASS
# llama-models-pv   20Gi       ROX            Retain           Available   local-storage
# loki-pv           200Gi      RWO            Retain           Available   local-storage
# tempo-pv          50Gi       RWO            Retain           Available   local-storage

# Verify PVs point to correct paths on node-2
kubectl describe pv llama-models-pv | grep -A 5 "Source:"
# Expected:
#   Source:
#     Type:  LocalVolume
#     Path:  /mnt/k8s-storage/models

# Check node affinity
kubectl get pv llama-models-pv -o jsonpath='{.spec.nodeAffinity}'
# Should include: node-2
```

**Why This Approach Works:**
1. Data already exists in `/mnt/k8s-storage/` from K3S cluster
2. Flux creates PVs that point to existing data
3. HelmReleases (Loki, Tempo) create PVCs that bind to these PVs
4. Workloads mount existing data seamlessly (zero data migration!)

**CKA Exam Tip:** On the exam, you might be asked to create PVs manually using `kubectl create -f pv.yaml`. Our Flux approach is GitOps-style (declarative), but the underlying concept is the same: PV → PVC binding based on storageClassName + capacity matching.

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
# Should pass with Kubernetes 1.35.0 >=1.32.0-0
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
