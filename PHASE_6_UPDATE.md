# Phase 6 Update - Replace in K3S_TO_K8S_MIGRATION_PLAN.md

Replace Phase 6 section with this:

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

**CKA Domain 2 - Workloads & Scheduling (15%)**

Recreate node labels/taints from K3S cluster:

```bash
# Label node-1 as lightweight hardware
kubectl label node node-1 hardware=light

# Label node-2 as heavy hardware
kubectl label node node-2 hardware=heavy

# Taint node-2 for heavy workloads only
kubectl taint node node-2 heavy=true:NoSchedule
```
