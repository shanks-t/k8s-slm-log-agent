# Observability Infrastructure

This directory contains the observability stack configuration: logs, traces, and metrics.

## Architecture

**Loki (on Node 2)**
- Monolithic deployment mode (single pod, all components)
- Stores logs on Samsung NVMe at `/mnt/k8s-storage/loki`
- 200GB persistent storage
- 7-day retention policy

**Tempo (on Node 2)**
- Monolithic deployment mode for distributed tracing
- Stores traces on Samsung NVMe at `/mnt/k8s-storage/tempo`
- 50GB persistent storage
- 7-day (168h) retention policy
- OTLP receivers on ports 4317 (gRPC) and 4318 (HTTP)

**Grafana Alloy (DaemonSet on both nodes)**
- Scrapes container logs from both nodes
- Ships logs to Loki
- Automatically discovers pods and adds labels
- Replaces deprecated Promtail (active development, OTel support)
- Ready for future OTel trace collection if needed

**Grafana (on Node 1)**
- Web UI for exploring logs, traces, and metrics
- Pre-configured datasources: Loki, Tempo
- Trace-to-logs correlation enabled (bidirectional)
- Accessible via Envoy Gateway at http://10.0.0.102/grafana

## Files Overview

- **00-namespace.yaml** - Creates `logging` namespace
- **01-loki-storage.yaml** - PersistentVolume + PersistentVolumeClaim for Loki
- **02-loki-values.yaml** - Helm values for Loki deployment
- **03-alloy-values.yaml** - Helm values for Grafana Alloy DaemonSet
- **04-grafana-values.yaml** - Helm values for Grafana with Loki and Tempo datasources
- **05-grafana-httproute.yaml** - Envoy Gateway HTTPRoute for Grafana access
- **06-tempo-storage.yaml** - PersistentVolume + PersistentVolumeClaim for Tempo
- **07-tempo-values.yaml** - Helm values for Tempo deployment

## Deployment Steps

### 1. Create namespace
```bash
kubectl apply -f k8s/logging/00-namespace.yaml
```

### 2. Prepare storage directory on Node 2
```bash
ssh node2 "sudo mkdir -p /mnt/k8s-storage/loki"
ssh node2 "sudo chown -R 10001:10001 /mnt/k8s-storage/loki"
```

**Why UID 10001?** Loki container runs as non-root user with UID 10001.

### 3. Create PersistentVolume and PersistentVolumeClaim
```bash
kubectl apply -f k8s/logging/01-loki-storage.yaml
```

Verify PV and PVC:
```bash
kubectl get pv loki-pv
kubectl get pvc -n logging loki-pvc
```

Expected: PVC status should be `Bound` to PV.

### 4. Install Loki via Helm
```bash
# Add Grafana Helm repo (if not already added)
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Loki
helm install loki grafana/loki \
  --namespace logging \
  --values k8s/logging/02-loki-values.yaml \
  --version 6.21.0
```

**Version note:** Using 6.x chart which deploys Loki 3.x (latest stable).

### 5. Verify Loki deployment
```bash
# Check pod is running on Node 2
kubectl get pods -n logging -o wide

# Check logs for any errors
kubectl logs -n logging -l app.kubernetes.io/name=loki --tail=50

# Port-forward to test Loki API
kubectl port-forward -n logging svc/loki 3100:3100
```

Then test: `curl http://localhost:3100/ready` (should return "ready")

### 6. Verify storage is being used
```bash
ssh node2 "du -sh /mnt/k8s-storage/loki"
```

You should see directories created: `chunks/`, `index/`, etc.

### 7. Deploy Grafana Alloy DaemonSet

**Add Grafana Helm repo (if not already added):**
```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

**Install Alloy:**
```bash
helm install alloy grafana/alloy \
  --namespace logging \
  --values k8s/logging/03-alloy-values.yaml
```

**What this does:**
- Deploys Alloy as a DaemonSet (one pod per node)
- Configures log discovery for pods on each node
- Sends logs to Loki at `http://loki.logging.svc.cluster.local:3100`
- Adds labels: namespace, pod, container, node, cluster

### 8. Verify Alloy deployment

```bash
# Check Alloy pods - should see one per node
kubectl get pods -n logging -l app.kubernetes.io/name=alloy -o wide
```

**Expected:**
- 2 pods total (one on `node-1`, one on `node-2`)
- Both should be `Running` with `1/1` ready

**Check Alloy logs:**
```bash
kubectl logs -n logging -l app.kubernetes.io/name=alloy --tail=50
```

**What to look for:**
- "configuration loaded successfully" message
- No errors about connecting to Loki
- Discovery messages showing pods being found

**Test log collection:**

Wait a minute for Alloy to discover pods and send logs, then query Loki:

```bash
# Port-forward to Loki
kubectl port-forward -n logging svc/loki 3100:3100
```

In another terminal:
```bash
# Query for logs (replace with actual namespace/pod)
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="logging"}' | jq .
```

**Expected:** JSON response with log entries from the logging namespace

## Troubleshooting

**PVC stays in Pending:**
- Check PV exists: `kubectl get pv loki-pv`
- Check PV/PVC storage class matches: `local-storage`
- Check nodeAffinity in PV matches Node 2's hostname

**Pod stuck in Pending:**
- Check node selector: Pod should target `hardware=heavy`
- Check toleration: Pod needs toleration for `heavy=true:NoSchedule`
- Check PVC is Bound: `kubectl get pvc -n logging`

**Pod CrashLoopBackOff:**
- Check logs: `kubectl logs -n logging <pod-name>`
- Common issue: Permission denied on `/var/loki`
  - Fix: `ssh node2 "sudo chown -R 10001:10001 /mnt/k8s-storage/loki"`

**Pod running but /ready fails:**
- Check Loki config for syntax errors
- Check storage is writable
- View detailed logs: `kubectl logs -n logging -l app.kubernetes.io/name=loki -f`

**Alloy running but no logs in Loki / Grafana shows empty results:**

This is usually a **cross-node networking issue**. Symptoms:
- Loki API works (`curl http://localhost:3100/ready` returns "ready")
- Loki queries return empty results
- Alloy logs show "context deadline exceeded" errors when trying to push to Loki
- Pods on node-1 cannot reach pods on node-2

**Root cause:** K3s uses Flannel CNI with VXLAN backend, which requires **UDP port 8472** to be open between nodes for the overlay network tunnel.

**Diagnosis:**
```bash
# Test cross-node pod connectivity
kubectl run test-ping --rm -i --restart=Never --image=busybox:latest -- ping -c 3 <loki-pod-ip>

# If ping fails, check if VXLAN port is blocked
ssh node1 "sudo iptables -L INPUT -v -n | grep 8472"
ssh node2 "sudo iptables -L INPUT -v -n | grep 8472"
```

**Fix:** Open UDP port 8472 between nodes
```bash
# Add iptables rules on both nodes
ssh node1 "sudo iptables -I INPUT -s 10.0.0.103 -p udp --dport 8472 -j ACCEPT"
ssh node2 "sudo iptables -I INPUT -s 10.0.0.102 -p udp --dport 8472 -j ACCEPT"

# Restart K3s to rebuild VXLAN tunnel
ssh node1 "sudo systemctl restart k3s"
ssh node2 "sudo systemctl restart k3s-agent"

# Wait 30 seconds, then verify
kubectl run test-ping --rm -i --restart=Never --image=busybox:latest -- ping -c 3 <loki-pod-ip>
```

**Make rules persistent:** To survive reboots, save iptables rules or enable UFW with rules:
```bash
# Option 1: Save iptables rules (varies by distro)
sudo iptables-save > /etc/iptables/rules.v4

# Option 2: Use UFW (if installed)
sudo ufw allow from 10.0.0.103 to any port 8472 proto udp  # On node-1
sudo ufw allow from 10.0.0.102 to any port 8472 proto udp  # On node-2
sudo ufw enable
```

### 9. Deploy Tempo for Distributed Tracing

**Prepare storage directory on Node 2:**
```bash
ssh node2 "sudo mkdir -p /mnt/k8s-storage/tempo"
ssh node2 "sudo chown -R 10001:10001 /mnt/k8s-storage/tempo"
```

**Create PersistentVolume and PersistentVolumeClaim:**
```bash
kubectl apply -f platform/o11y/06-tempo-storage.yaml
```

**Verify PV and PVC:**
```bash
kubectl get pv tempo-pv
kubectl get pvc -n logging tempo-pvc
```

**Install Tempo via Helm:**
```bash
# Add Grafana Helm repo (if not already added)
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Tempo
helm install tempo grafana/tempo \
  --namespace logging \
  --values platform/o11y/07-tempo-values.yaml
```

**Verify Tempo deployment:**
```bash
# Check pod is running on Node 2
kubectl get pods -n logging -o wide | grep tempo

# Check logs for any errors
kubectl logs -n logging tempo-0 --tail=50

# Test Tempo API
kubectl port-forward -n logging svc/tempo 3200:3200
curl http://localhost:3200/ready  # Should return "ready"
```

**Test trace ingestion:**
```bash
# Deploy a service with OpenTelemetry instrumentation (e.g., log-analyzer)
# Then check for traces in Tempo:
kubectl port-forward -n logging svc/tempo 3200:3200
curl http://localhost:3200/api/search?limit=10 | jq .
```

### 10. Update Grafana with Tempo Datasource

**Update Grafana datasources:**
```bash
# Upgrade Grafana with Tempo datasource configuration
helm upgrade grafana grafana/grafana \
  --namespace logging \
  --values platform/o11y/04-grafana-values.yaml \
  --reuse-values
```

**Verify in Grafana:**
1. Navigate to **Configuration** → **Data sources**
2. Verify **Tempo** datasource is present
3. Test connection (should show "Data source is working")
4. Navigate to **Explore** → Select **Tempo**
5. Search for recent traces

**Test trace-to-logs correlation:**
1. Generate a trace by calling an instrumented service (e.g., log-analyzer)
2. In **Explore** → **Tempo**, find the trace
3. Click on a span and look for **"Logs for this span"** button
4. Clicking should show correlated logs from Loki with matching trace_id

**Test logs-to-traces correlation:**
1. In **Explore** → **Loki**, query logs with trace context:
   ```logql
   {namespace="log-analyzer"} | json | trace_id != ""
   ```
2. Logs should have clickable trace_id links
3. Clicking should open the trace in Tempo

## Storage Sizing

**Current allocation on Samsung NVMe (/mnt/k8s-storage):**
- Loki: 200GB (PVC)
- Tempo: 50GB (PVC)
- **Total allocated:** 250GB out of 476GB

**Estimated capacity:**
- **Loki** (at 1GB/day ingestion): ~180 days buffer (7-day retention means plenty of headroom)
- **Tempo** (at 100MB/day trace data): ~450 days buffer (7-day retention is very safe)

**Remaining space:** ~220GB available for:
- Vector database in Phase 3B
- Model storage expansion
- Future observability needs

## Next Steps

Phase 2 is complete! The observability stack is fully deployed:
- ✅ Loki for log storage
- ✅ Grafana Alloy for log collection
- ✅ Grafana for visualization
- ✅ Tempo for distributed tracing
- ✅ Trace-to-logs correlation configured

**Proceed to Phase 3A:**
- Deploy log-analyzer FastAPI service with OpenTelemetry instrumentation
- Implement baseline time-based retrieval
- Build evaluation framework with golden dataset
- Measure extraction accuracy and latency
