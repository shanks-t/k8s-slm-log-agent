# Cluster State Exports

This directory contains raw YAML exports of all cluster resources for the Flux migration.

**Date:** 2025-12-27
**Purpose:** Step 2 of Flux GitOps migration - export current cluster state
**Next Step:** Clean and normalize these manifests (Step 3)

## Directory Structure

```
exports/
├── infrastructure/          # Platform-level resources
│   ├── controllers/         # Envoy Gateway config
│   ├── logging/             # Logging stack config/storage
│   └── storage/             # PVs and StorageClasses
└── workloads/               # Application workloads
    ├── llm/                 # llama-cpp resources
    └── log-analyzer/        # log-analyzer resources
```

## Export Contents

### Infrastructure

**Controllers (Envoy Gateway):**
- `controllers/envoy-config.yaml` - ConfigMaps and Secrets

**Logging:**
- `logging/config-and-storage.yaml` - ConfigMaps, Secrets, and PVCs for Loki/Grafana/Tempo/Alloy

**Storage:**
- `storage/persistent-volumes.yaml` - All PVs (llama-models-pv, loki-pv, tempo-pv)
- `storage/storage-classes.yaml` - K3S local-path StorageClass

### Workloads

**LLM (llama-cpp):**
- `llm/all-resources.yaml` - Deployment, Service, PVC, ConfigMaps, Secrets

**Log Analyzer:**
- `log-analyzer/all-resources.yaml` - Deployment, Service, ConfigMap, Secrets

## Important Notes

### Runtime Metadata (To Be Cleaned in Step 3)

These exported files contain runtime metadata that should NOT be in declarative manifests:
- `metadata.creationTimestamp`
- `metadata.resourceVersion`
- `metadata.uid`
- `metadata.managedFields`
- `status` sections

### Helm-Managed Resources

The following are managed by Helm and will be converted to HelmReleases (not cleaned from exports):
- Loki
- Grafana
- Tempo
- Alloy
- Envoy Gateway

Helm values are already exported in `inventory/helm-values-*.yaml`.

### K3S-Specific Resources

**StorageClass:**
- `local-path` (default) - K3S built-in provisioner
- Will be used as-is in Flux manifests (no replacement needed)

**PersistentVolumes:**
- Manual creation required (use hostPath on Node 2)
- Paths: `/mnt/k8s-storage/{models,loki,tempo}`

## Next Steps (Step 3)

1. Split `all-resources.yaml` files into individual resource files
2. Remove runtime metadata (creationTimestamp, resourceVersion, etc.)
3. Remove status sections
4. Organize into final Flux directory structure:
   - `infrastructure/storage/` - PVs
   - `workloads/llm/` - llama-cpp manifests
   - `workloads/log-analyzer/` - log-analyzer manifests
5. Create kustomization.yaml files for each directory

## Reference

See [infra-roadmap.md](../infra-roadmap.md) Step 2 and Step 3 for detailed instructions.
