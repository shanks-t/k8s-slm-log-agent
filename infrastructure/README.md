# Infrastructure

This directory contains all platform-level infrastructure components for the Kubernetes cluster, deployed using **GitOps** principles via [Flux CD](https://fluxcd.io/).

## Table of Contents

- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Deployment Model](#deployment-model)
- [How It Works](#how-it-works)
- [Working with Grafana Dashboards](#working-with-grafana-dashboards)
- [Adding New Components](#adding-new-components)
- [Troubleshooting](#troubleshooting)

---

## Overview

**GitOps Deployment**: All infrastructure is declaratively defined in YAML and automatically deployed by Flux. When you commit changes to this directory and push to GitHub, Flux detects the changes and applies them to the cluster.

**Key Concepts**:
- **HelmRelease**: Flux resource that manages Helm chart deployments
- **Kustomization**: Flux resource that applies plain Kubernetes manifests
- **HelmRepository**: Defines where to fetch Helm charts from

---

## Directory Structure

```
infrastructure/
├── README.md                    # This file
├── kustomization.yaml          # Root kustomization (aggregates all subdirectories)
│
├── sources/                    # HelmRepository definitions
│   ├── kustomization.yaml
│   ├── prometheus-charts.yaml  # Prometheus community charts
│   ├── grafana-charts.yaml     # Grafana community charts
│   └── ...
│
├── storage/                    # Persistent storage resources
│   ├── kustomization.yaml
│   ├── local-storageclass.yaml # StorageClass for local volumes
│   ├── prometheus-pv.yaml      # PersistentVolume for Prometheus
│   ├── loki-pv.yaml           # PersistentVolume for Loki
│   └── ...
│
├── controllers/                # Cluster controllers
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   └── envoy-gateway-helmrelease.yaml
│
├── gateway/                    # Ingress gateway configuration
│   ├── kustomization.yaml
│   ├── 01-gatewayclass.yaml
│   ├── 03-gateway.yaml
│   └── 05-grafana-httproute.yaml
│
├── logging/                    # Observability: logs, traces, dashboards
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── loki-helmrelease.yaml      # Log aggregation
│   ├── grafana-helmrelease.yaml   # Dashboarding
│   ├── tempo-helmrelease.yaml     # Distributed tracing
│   ├── alloy-helmrelease.yaml     # Log collection agent
│   └── dashboards/                # Grafana dashboard ConfigMaps
│       └── kubernetes-configmap.yaml
│
└── monitoring/                 # Observability: metrics
    ├── kustomization.yaml
    ├── namespace.yaml
    ├── prometheus-helmrelease.yaml    # Metrics collection & storage
    └── metrics-server-helmrelease.yaml
```

---

## Deployment Model

### GitOps Flow

```
┌─────────────┐
│   Git Push  │  1. Developer commits infrastructure changes
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Flux Detects   │  2. Flux source-controller polls GitHub every 1m
│  New Commit     │     (or reconcile immediately with `flux reconcile`)
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ Flux Reconciles  │  3. kustomize-controller applies Kustomizations
│  Kustomizations  │     helm-controller applies HelmReleases
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Kubernetes     │  4. Resources created/updated in cluster
│     Cluster      │
└──────────────────┘
```

### Reconciliation Order

The root `kustomization.yaml` defines the deployment order:

1. **sources/** - HelmRepositories (required before HelmReleases)
2. **storage/** - PersistentVolumes (required before stateful workloads)
3. **controllers/** - Cluster-level controllers
4. **gateway/** - Ingress gateway and routes
5. **logging/** - Log aggregation, dashboards, tracing
6. **monitoring/** - Metrics collection and monitoring

This ordering ensures dependencies are satisfied before dependent resources are created.

---

## How It Works

### HelmRelease Pattern

Most infrastructure components use Helm charts managed by Flux's **HelmRelease** custom resource.

**Example: Prometheus HelmRelease**

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: prometheus
  namespace: monitoring
spec:
  interval: 5m  # Check for chart updates every 5 minutes
  chart:
    spec:
      chart: prometheus
      version: '27.6.0'  # Pin to specific version
      sourceRef:
        kind: HelmRepository
        name: prometheus-community  # References sources/prometheus-charts.yaml
        namespace: flux-system
  values:
    # Helm chart values override (replaces values.yaml)
    server:
      persistentVolume:
        enabled: true
        size: 50Gi
    # ... more configuration
```

**How it works**:
1. Flux `helm-controller` watches HelmRelease resources
2. Fetches chart from referenced HelmRepository
3. Renders chart with provided values
4. Applies resources to cluster
5. Re-reconciles on interval or when HelmRelease changes

**Updating a HelmRelease**:
1. Edit the HelmRelease YAML file
2. Commit and push to GitHub
3. Flux detects change and runs `helm upgrade` automatically
4. (Optional) Force immediate reconcile: `flux reconcile helmrelease prometheus -n monitoring`

### Kustomization Pattern

Each subdirectory has a `kustomization.yaml` that lists resources to deploy.

**Example: logging/kustomization.yaml**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - loki-helmrelease.yaml
  - grafana-helmrelease.yaml
  - tempo-helmrelease.yaml
  - alloy-helmrelease.yaml
  - dashboards/kubernetes-configmap.yaml
```

Flux's `kustomize-controller` applies all resources in the order listed.

---

## Working with Grafana Dashboards

Grafana dashboards are stored as **ConfigMaps** with a special label that allows the Grafana sidecar to auto-discover and load them.

### Understanding the Dashboard Script

The `just dashboard-cm <name>` recipe automates ConfigMap creation from Grafana dashboard exports. Here's what happens under the hood:

**Script flow** (`just-helpers/dashboard-cm.sh`):

1. **Validation**:
   - Checks for dashboard name argument
   - Verifies `tmp/dashboard.json` exists
   - Validates JSON is well-formed using `jq`

2. **ConfigMap Generation**:
   - Creates base ConfigMap: `kubectl create configmap --dry-run=client`
   - Adds required label: `grafana_dashboard: "1"` (via awk)
   - Adds `last-applied-configuration` annotation: `kubectl apply --dry-run=client`
   - Adds header comments with update instructions
   - Outputs to: `infrastructure/logging/dashboards/<name>-configmap.yaml`

3. **Server-Side Validation**:
   - Runs `kubectl apply --dry-run=server` to validate against cluster
   - Checks for API compatibility and schema errors
   - Exits with error if validation fails

4. **Cluster Deployment**:
   - Automatically applies ConfigMap to cluster: `kubectl apply -f <file>`
   - Shows apply output (created/configured/unchanged)
   - **Auto-reload on updates**: If ConfigMap already exists, restarts Grafana to force reload
   - Displays ConfigMap status and sidecar logs after successful deployment
   - Exits with error if apply fails (file still saved for manual inspection)

5. **Output**:
   - Displays dashboard title, UID, and file size
   - Shows ConfigMap status in cluster
   - Provides next steps for verification and committing
   - Cleans up temporary files

**Error handling**:
- Missing arguments → Usage instructions
- Missing `tmp/dashboard.json` → Step-by-step export guide
- Invalid JSON → Clear error message
- Failed validation → Points to output file for debugging
- Uses `set -euo pipefail` for strict bash error handling

**Why we add the `last-applied-configuration` annotation**:

When you use `kubectl apply`, Kubernetes performs a **three-way merge**:
1. **Current state** (what's in the cluster)
2. **Last applied** (stored in `kubectl.kubernetes.io/last-applied-configuration` annotation)
3. **Desired state** (what you're applying now)

Without this annotation, `kubectl apply` can't determine which fields you intentionally removed vs which were set by defaults. The script pre-adds this annotation by running `kubectl apply --dry-run=client`, which eliminates the warning:

```
Warning: resource configmaps/grafana-dashboard-kubernetes is missing the
kubectl.kubernetes.io/last-applied-configuration annotation...
```

This ensures clean, warning-free deployments from the start.

### Dashboard Workflow

#### 1. Create/Edit Dashboard in Grafana UI

1. Navigate to Grafana (typically `http://<your-cluster>/grafana`)
2. Create a new dashboard or edit an existing one
3. Add panels with PromQL queries (Prometheus) or LogQL queries (Loki)
4. Configure variables (e.g., `$namespace`, `$pod`)
5. Test thoroughly until the dashboard works perfectly

**Pro tip**: Use dashboard variables for reusability:
```
$namespace - Kubernetes namespace selector
$pod - Pod name selector
$interval - Time interval for rate() functions
```

#### 2. Export Dashboard JSON

1. Click the **Settings** icon (⚙️) in the top-right
2. Select **JSON Model** from the left sidebar
3. Click **Copy to Clipboard** or manually select all (Cmd+A / Ctrl+A)
4. Save to `tmp/dashboard.json` at the repository root

**Example**:
```bash
# Create tmp directory if needed
mkdir -p tmp

# Paste clipboard content
pbpaste > tmp/dashboard.json  # macOS
# or
xclip -o > tmp/dashboard.json  # Linux

# Verify it's valid JSON
jq empty tmp/dashboard.json && echo "✅ Valid JSON" || echo "❌ Invalid JSON"
```

#### 3. Generate and Deploy ConfigMap with Just Recipe

Run the `dashboard-cm` recipe with a descriptive name:

```bash
just dashboard-cm kubernetes-pods
# Creates AND applies: infrastructure/logging/dashboards/kubernetes-pods-configmap.yaml
```

**What the script does**:
```
✅ Validates tmp/dashboard.json exists and is valid JSON
✅ Creates ConfigMap YAML with grafana_dashboard: "1" label
✅ Adds last-applied-configuration annotation (prevents warnings)
✅ Validates against Kubernetes API (dry-run=server)
✅ Outputs to infrastructure/logging/dashboards/<name>-configmap.yaml
✅ Automatically applies to cluster
✅ Shows dashboard title, UID, and ConfigMap status
```

**Expected output**:
```
Creating ConfigMap 'grafana-dashboard-kubernetes-pods'...
Applying ConfigMap to cluster...
configmap/grafana-dashboard-kubernetes-pods created

✅ ConfigMap created and applied: infrastructure/logging/dashboards/kubernetes-pods-configmap.yaml

Dashboard info:
  Title: Kubernetes / Pods
  UID: k8s-pods-monitoring
  Size: 2847 lines

ConfigMap status:
  NAME                                 DATA   AGE
  grafana-dashboard-kubernetes-pods    1      2s

Next steps:
  1. Wait ~10 seconds for Grafana sidecar to reload
  2. Verify dashboard appears in Grafana UI
  3. Check sidecar logs: kubectl logs -n logging deployment/grafana -c grafana-sc-dashboard
  4. Commit: git add infrastructure/logging/dashboards/kubernetes-pods-configmap.yaml && git commit -m 'feat: add kubernetes-pods dashboard'
```

**If updating an existing dashboard**, you'll see:
```
Applying ConfigMap to cluster...
configmap/grafana-dashboard-kubernetes-pods configured

ConfigMap updated. Restarting Grafana to reload dashboard...
Waiting for Grafana to be ready...
deployment "grafana" successfully rolled out

✅ ConfigMap deployed: infrastructure/logging/dashboards/kubernetes-pods-configmap.yaml

Dashboard info:
  Title: Kubernetes / Pods
  UID: k8s-pods-monitoring
  Size: 2847 lines

ConfigMap status:
  NAME                                 DATA   AGE
  grafana-dashboard-kubernetes-pods    1      5h

Sidecar status (last 3 events):
  2025-12-31T17:17:30.804760+00:00 INFO Writing /tmp/dashboards/Kubernetes/kubernetes-pods-dashboard.json (ascii)
  2025-12-31T17:17:38.519976+00:00 INFO None sent to http://localhost:3000/api/admin/provisioning/dashboards/reload. Response: 200 OK {"message":"Dashboards config reloaded"}

Next steps:
  1. Verify dashboard appears in Grafana UI
  2. Test dashboard functionality (variables, panels, queries)
  3. Commit: git add infrastructure/logging/dashboards/kubernetes-pods-configmap.yaml && git commit -m 'feat: add kubernetes-pods dashboard'
```

#### 4. Verify the Dashboard

The ConfigMap is already applied to the cluster. Now verify Grafana loaded it:

**Check Grafana sidecar discovered it**:
```bash
kubectl logs -n logging deployment/grafana -c grafana-sc-dashboard | grep kubernetes-pods
```

Expected output showing discovery:
```
time="2025-12-30T16:45:23Z" level=info msg="Initializing provider" provider=sidecar.provider
time="2025-12-30T16:45:23Z" level=info msg="Discovered dashboard" file="kubernetes-pods-dashboard.json"
```

**Access in Grafana UI**:
1. Wait ~10 seconds for sidecar to detect and load
2. Navigate to **Dashboards** in Grafana
3. Search for your dashboard title ("Kubernetes / Pods")
4. Verify all panels load correctly
5. Test any dashboard variables ($namespace, $pod, etc.)

**Troubleshooting**: If dashboard doesn't appear:
```bash
# Check if ConfigMap has correct label
kubectl get configmap grafana-dashboard-kubernetes-pods -n logging \
  -o jsonpath='{.metadata.labels.grafana_dashboard}'
# Should output: 1

# Restart Grafana to force reload
kubectl rollout restart deployment/grafana -n logging
```

#### 5. Add to Kustomization (for GitOps)

Edit `infrastructure/logging/kustomization.yaml` and add your new dashboard:

```yaml
resources:
  - namespace.yaml
  - loki-helmrelease.yaml
  - grafana-helmrelease.yaml
  - tempo-helmrelease.yaml
  - alloy-helmrelease.yaml
  - dashboards/kubernetes-configmap.yaml
  - dashboards/kubernetes-pods-configmap.yaml  # ← Add here
```

**Why this step is necessary**: The ConfigMap exists in the cluster from step 4, but won't survive cluster rebuilds or be tracked in Git. Adding to kustomization makes it part of your infrastructure-as-code.

#### 6. Commit to Git

Once validated, commit for permanent deployment:

```bash
git add infrastructure/logging/dashboards/kubernetes-pods-configmap.yaml
git add infrastructure/logging/kustomization.yaml
git commit -m "$(cat <<'EOF'
feat: add Kubernetes pod metrics dashboard

Add comprehensive dashboard for monitoring pod-level metrics:
- CPU and memory usage per pod
- Network I/O rates
- Pod restart counts
- Resource requests vs limits

Data source: Prometheus (cAdvisor and kube-state-metrics)
EOF
)"
git push origin main
```

**Flux reconciliation**: Flux will detect the commit and apply the ConfigMap cluster-wide within ~1 minute.

### Dashboard Organization by Data Source

As you create more dashboards, organize them by **primary data source** for clarity:

**Recommended structure**:
```
infrastructure/logging/dashboards/
├── kustomization.yaml                    # References all subdirectories
│
├── prometheus/                           # Dashboards querying Prometheus
│   ├── kustomization.yaml
│   ├── kubernetes-pods-configmap.yaml    # cAdvisor metrics
│   ├── kubernetes-nodes-configmap.yaml   # Node exporter metrics
│   ├── coredns-configmap.yaml           # CoreDNS metrics
│   └── cluster-capacity-configmap.yaml  # kube-state-metrics
│
├── loki/                                 # Dashboards querying Loki
│   ├── kustomization.yaml
│   ├── application-logs-configmap.yaml  # App log patterns
│   ├── error-rates-configmap.yaml       # Error log analysis
│   └── audit-logs-configmap.yaml        # Kubernetes audit logs
│
├── tempo/                                # Dashboards querying Tempo
│   ├── kustomization.yaml
│   ├── trace-latency-configmap.yaml     # Request latency traces
│   └── service-dependencies-configmap.yaml  # Service mesh
│
└── mixed/                                # Dashboards using multiple sources
    ├── kustomization.yaml
    ├── cluster-overview-configmap.yaml  # Prometheus + Loki + Tempo
    └── slo-dashboard-configmap.yaml     # SLI/SLO tracking
```

#### Setting Up the Organized Structure

**1. Create subdirectories**:
```bash
mkdir -p infrastructure/logging/dashboards/{prometheus,loki,tempo,mixed}
```

**2. Create kustomization for each category**:

```yaml
# infrastructure/logging/dashboards/prometheus/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - kubernetes-pods-configmap.yaml
  - kubernetes-nodes-configmap.yaml
  - coredns-configmap.yaml
```

```yaml
# infrastructure/logging/dashboards/loki/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - application-logs-configmap.yaml
  - error-rates-configmap.yaml
```

```yaml
# infrastructure/logging/dashboards/tempo/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - trace-latency-configmap.yaml
```

```yaml
# infrastructure/logging/dashboards/mixed/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - cluster-overview-configmap.yaml
```

**3. Create parent kustomization**:

```yaml
# infrastructure/logging/dashboards/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - prometheus/
  - loki/
  - tempo/
  - mixed/
```

**4. Update main logging kustomization**:

```yaml
# infrastructure/logging/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - loki-helmrelease.yaml
  - grafana-helmrelease.yaml
  - tempo-helmrelease.yaml
  - alloy-helmrelease.yaml
  - dashboards/  # Now references the dashboards/ directory
```

#### Updated Dashboard Workflow with Categories

**Creating a Prometheus dashboard**:
```bash
# 1. Export from Grafana to tmp/dashboard.json

# 2. Generate and deploy ConfigMap
just dashboard-cm coredns
# ConfigMap is now live in cluster!

# 3. Move to appropriate category
mv infrastructure/logging/dashboards/coredns-configmap.yaml \
   infrastructure/logging/dashboards/prometheus/

# 4. Add to category kustomization
echo "  - coredns-configmap.yaml" >> infrastructure/logging/dashboards/prometheus/kustomization.yaml

# 5. Verify categorization
kubectl apply -k infrastructure/logging/dashboards/prometheus/ --dry-run=server

# 6. Commit for GitOps
git add infrastructure/logging/dashboards/prometheus/
git commit -m "feat: add CoreDNS metrics dashboard"
git push
```

**Note**: The dashboard is immediately available in Grafana after step 2. Steps 3-6 organize it for GitOps and team collaboration.

### Dashboard Naming Best Practices

**Use descriptive names that indicate**:
1. **What component** (kubernetes, coredns, loki, application)
2. **What aspect** (pods, nodes, logs, traces, capacity)

**Good examples**:
- `kubernetes-pods` - Pod-level resource metrics
- `kubernetes-nodes` - Node-level system metrics
- `coredns-performance` - DNS query rates and latency
- `loki-error-analysis` - Application error log patterns
- `cluster-capacity` - Overall resource capacity planning
- `application-logs-search` - General log exploration

**Avoid**:
- Generic names: `dashboard1`, `metrics`, `logs`
- Version numbers: `dashboard-v2` (use Git for versions)
- Dates: `dashboard-2025-01` (use Git history)

### Migration: Flat to Organized Structure

If you've already created dashboards in the flat structure, migrate them:

```bash
# Create new structure
mkdir -p infrastructure/logging/dashboards/{prometheus,loki,tempo,mixed}

# Move existing dashboard
mv infrastructure/logging/dashboards/kubernetes-configmap.yaml \
   infrastructure/logging/dashboards/prometheus/

# Create category kustomizations (as shown above)

# Update references in main kustomization
# Change from listing individual files to referencing directory

# Test
kubectl apply -k infrastructure/logging/dashboards/ --dry-run=server

# Commit migration
git add infrastructure/logging/dashboards/
git commit -m "refactor: organize dashboards by data source"
```

---

## Adding New Components

### Adding a New HelmRelease

**Example: Adding Redis**

1. **Add HelmRepository** (if needed):

```yaml
# infrastructure/sources/redis-charts.yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: bitnami
  namespace: flux-system
spec:
  interval: 1h
  url: https://charts.bitnami.com/bitnami
```

2. **Create subdirectory**:

```bash
mkdir -p infrastructure/redis
```

3. **Create namespace**:

```yaml
# infrastructure/redis/namespace.yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: redis
```

4. **Create HelmRelease**:

```yaml
# infrastructure/redis/redis-helmrelease.yaml
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: redis
  namespace: redis
spec:
  interval: 5m
  chart:
    spec:
      chart: redis
      version: '18.4.0'
      sourceRef:
        kind: HelmRepository
        name: bitnami
        namespace: flux-system
  values:
    auth:
      enabled: true
      password: "changeme"
    master:
      persistence:
        enabled: true
        size: 8Gi
```

5. **Create kustomization**:

```yaml
# infrastructure/redis/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - redis-helmrelease.yaml
```

6. **Add to root kustomization**:

```yaml
# infrastructure/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - sources/
  - storage/
  - controllers/
  - gateway/
  - logging/
  - monitoring/
  - redis/          # ← Add new component
```

7. **Commit and push**:

```bash
git add infrastructure/sources/redis-charts.yaml
git add infrastructure/redis/
git add infrastructure/kustomization.yaml
git commit -m "feat: add Redis for caching"
git push origin main
```

Flux will automatically deploy Redis within 1 minute (or immediately with `flux reconcile kustomization infrastructure`).

---

## Troubleshooting

### Check Flux Status

```bash
# Overall Flux health
flux check

# View all Flux resources
flux get all -A

# View specific HelmRelease
flux get helmrelease prometheus -n monitoring

# View reconciliation logs
flux logs --level=error --since=10m
```

### HelmRelease Failed

```bash
# Get HelmRelease status
kubectl get helmrelease -n monitoring prometheus -o yaml

# Check conditions
kubectl describe helmrelease -n monitoring prometheus

# Force reconciliation
flux reconcile helmrelease prometheus -n monitoring

# Suspend/resume to retry
flux suspend helmrelease prometheus -n monitoring
flux resume helmrelease prometheus -n monitoring
```

### Kustomization Failed

```bash
# Check Kustomization status
flux get kustomizations

# View detailed status
kubectl describe kustomization -n flux-system infrastructure

# Force reconciliation
flux reconcile kustomization infrastructure

# View what would be applied (dry-run)
kubectl kustomize infrastructure/
```

### Dashboard Not Appearing in Grafana

1. **Check ConfigMap exists**:
   ```bash
   kubectl get configmap -n logging -l grafana_dashboard=1
   ```

2. **Verify label is correct**:
   ```bash
   kubectl get configmap grafana-dashboard-kubernetes -n logging -o yaml | grep grafana_dashboard
   ```
   Should show: `grafana_dashboard: "1"`

3. **Check Grafana sidecar logs**:
   ```bash
   kubectl logs -n logging deployment/grafana -c grafana-sc-dashboard
   ```

4. **Force sidecar reload**:
   ```bash
   kubectl rollout restart deployment/grafana -n logging
   ```

5. **Verify dashboard JSON is valid**:
   ```bash
   kubectl get configmap grafana-dashboard-kubernetes -n logging -o json | \
     jq -r '.data["kubernetes-dashboard.json"]' | jq empty
   ```

### View Applied Resources

```bash
# See all resources managed by Flux in infrastructure kustomization
flux tree kustomization infrastructure

# See all Helm releases
helm list -A

# See what Prometheus HelmRelease deployed
kubectl get all -n monitoring -l app.kubernetes.io/instance=prometheus
```

---

## Best Practices

1. **Pin Helm chart versions**: Always specify exact versions (e.g., `version: '27.6.0'`) to prevent unexpected upgrades
2. **Test locally first**: Use `kubectl apply --dry-run=server` before committing
3. **Small commits**: One component per commit for easier rollback
4. **Meaningful commit messages**: Explain what and why, not just what changed
5. **Use Flux reconciliation**: Prefer `flux reconcile` over manual `kubectl apply`
6. **Monitor Flux health**: Regularly check `flux get all` for failed reconciliations
7. **Leverage GitOps**: Let Flux apply changes - avoid manual kubectl edits in production

---

## Additional Resources

- [Flux Documentation](https://fluxcd.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [Kustomize Documentation](https://kustomize.io/)
- [Grafana Dashboard Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards)
