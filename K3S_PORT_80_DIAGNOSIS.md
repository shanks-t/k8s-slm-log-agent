# K3S Port 80 ClusterIP Service Issue - Root Cause Analysis

**Date:** 2025-12-28
**Cluster:** K3S v1.33.6+k3s1 (two-node homelab)
**Status:** Under Investigation

---

## Summary of Issue

**Symptom:** Pods cannot connect to ClusterIP services on port 80, but nodes CAN connect to the same services.

**Error:** `dial tcp <ClusterIP>:80: connect: connection refused`

**Criticality:** Blocking - Flux controllers cannot communicate, migration cannot proceed

---

## Evidence Gathered

### What WORKS ✅

1. **Pod → Pod (Direct IP, Port 9090)**
   ```bash
   kubectl run test-pod-ip --image=curlimages/curl --rm -i --restart=Never -- \
     curl http://10.42.0.152:9090/
   # Result: SUCCESS (200 OK)
   ```

2. **Pod → ClusterIP Service (Port 9090)**
   ```bash
   kubectl run test-9090 --image=curlimages/curl --rm -i --restart=Never -- \
     curl http://source-controller.flux-system.svc.cluster.local:9090/
   # Result: SUCCESS (200 OK)
   ```

3. **Node → ClusterIP Service (Port 80)**
   ```bash
   ssh node1 'curl http://10.43.143.185/'
   # Result: SUCCESS (200 OK)
   ```

4. **Node → ClusterIP Service (Port 9090)**
   - Not explicitly tested but assumed working based on node → port 80 success

### What FAILS ❌

1. **Pod → ClusterIP Service (Port 80)**
   ```bash
   kubectl run test-port80 --image=curlimages/curl --rm -i --restart=Never -- \
     curl http://source-controller.flux-system.svc.cluster.local/
   # Result: FAILED (connection refused)
   # Error: dial tcp 10.43.143.185:80: connect: connection refused
   ```

2. **Pod → Different Service on Port 80 (Grafana)**
   ```bash
   kubectl run test-grafana --image=curlimages/curl --rm -i --restart=Never -- \
     curl http://grafana.logging.svc.cluster.local:80/
   # Result: FAILED (connection refused)
   # Confirms this is NOT Flux-specific
   ```

3. **Flux Controllers Communicating**
   ```
   kustomize-controller → source-controller:80 (FAILED)
   source-controller → notification-controller:80 (FAILED)
   ```

### Service and Pod Configuration

**Source Controller Pod:**
```yaml
containerPort: 9090
name: http
```

**Source Controller Service:**
```yaml
port: 80
targetPort: http  # References container port "http" = 9090
```

**Service Routing:**
- Client connects to: `ClusterIP:80`
- Service routes to: `PodIP:9090` (via targetPort mapping)
- This configuration is correct and standard

---

## What We've Ruled Out

### 1. NetworkPolicy Blocking ❌
- **Test:** Deleted all NetworkPolicies in flux-system namespace
- **Result:** Port 80 still failed after deletion
- **Confirmed:** `kubectl get networkpolicy -A` → No resources found
- **Conclusion:** NOT a NetworkPolicy issue (though NetworkPolicies DO cause problems when present)

### 2. Flux-Specific Issue ❌
- **Test:** Tested Grafana service (non-Flux) on port 80
- **Result:** Also failed
- **Conclusion:** This is a K3S-wide issue, not Flux-specific

### 3. DNS Resolution ❌
- **Test:** Used ClusterIP directly instead of DNS name
- **Result:** Same failure
- **Conclusion:** DNS is working correctly

### 4. Pod Security Context ❌
- **Observation:** Pods run with restricted security context (capabilities dropped)
- **Evaluation:** Standard Kubernetes security, unlikely to block outbound connections
- **Conclusion:** Unlikely to be the cause

### 5. Service Misconfiguration ❌
- **Observation:** Service targetPort correctly maps to container port
- **Test:** Port 9090 works with same service/pod configuration
- **Conclusion:** Service configuration is correct

---

## Network Architecture Analysis

### K3S Networking Components

**CNI:** Flannel (vxlan backend)
- Pod CIDR: 10.42.0.0/16
- Cross-node communication via VXLAN (UDP 8472)

**Service Proxy:** Embedded kube-proxy (iptables mode)
- Service CIDR: 10.43.0.0/16
- Uses iptables DNAT rules to route service IPs to pod IPs

**NetworkPolicy Enforcement:** kube-router
- Implements NetworkPolicy via iptables
- Known to have issues with Flux's default NetworkPolicies

### iptables Routing Path

**Node → ClusterIP:80 (WORKS):**
1. Traffic originates from node network namespace
2. iptables NAT PREROUTING chain intercepts
3. DNAT rule: `ClusterIP:80` → `PodIP:9090`
4. Connection succeeds

**Pod → ClusterIP:80 (FAILS):**
1. Traffic originates from pod network namespace
2. Goes through veth pair to node network namespace
3. iptables NAT PREROUTING chain intercepts
4. DNAT rule should apply: `ClusterIP:80` → `PodIP:9090`
5. **Connection refused** ← Something goes wrong here

---

## Current Hypothesis

### Primary Theory: Pod Network Namespace iptables Filtering

**Hypothesis:** Port 80 traffic from pod network namespaces is being filtered/blocked by iptables rules before reaching the DNAT stage.

**Reasoning:**
1. Node traffic works (node network namespace)
2. Pod traffic fails (pod network namespace)
3. Only port 80 affected (port 9090 works)
4. Affects all services cluster-wide

**Potential Causes:**
- K3S-specific iptables rules blocking port 80 in pod namespaces
- Flannel CNI iptables rules interfering with port 80
- kube-router remnants from NetworkPolicy enforcement
- Pod security policy or admission controller blocking port 80

### Secondary Theory: K3S Traefik Conflict

**Hypothesis:** Even though Traefik is disabled, remnant iptables rules or port reservations are blocking port 80.

**K3S Configuration:**
- Traefik was disabled in favor of Envoy Gateway
- Need to verify no Traefik iptables rules remain

**Test Needed:**
```bash
ssh node1 'sudo iptables-save | grep -i "80\|traefik"'
```

### Tertiary Theory: CNI/VXLAN Port Conflict

**Hypothesis:** Flannel VXLAN or CNI plugin has a port 80 restriction for pod-to-service traffic.

**Less Likely Because:**
- Port 80 would be an unusual CNI restriction
- Node traffic works (goes through same iptables)

---

## Debugging Steps Needed

### 1. iptables Analysis (HIGH PRIORITY)

**From Node:**
```bash
ssh node1 'sudo iptables-save > /tmp/iptables-dump.txt'
scp node1:/tmp/iptables-dump.txt .

# Look for:
# - Port 80 specific rules
# - Traefik remnants
# - kube-router rules
# - KUBE-SVC chains for our services
```

**From Pod Network Namespace:**
```bash
# Get pod's network namespace
POD=$(kubectl get pod -n flux-system -l app=source-controller -o name | head -1)
NODE=$(kubectl get $POD -n flux-system -o jsonpath='{.spec.nodeName}')

# Enter pod's netns on the node
ssh $NODE "sudo crictl inspect <container-id> | grep pid"
ssh $NODE "sudo nsenter -t <pid> -n iptables-save"
```

### 2. tcpdump Packet Capture (HIGH PRIORITY)

**Capture on Node:**
```bash
# Terminal 1: Start capture
ssh node1 'sudo tcpdump -i any -nn "port 80 and host 10.43.143.185" -w /tmp/port80.pcap'

# Terminal 2: Trigger test
kubectl run test-debug --image=curlimages/curl --rm -i --restart=Never -- \
  curl -v http://10.43.143.185/

# Analyze: Look for SYN packets, RST packets, where they're coming from/to
```

### 3. K3S Service Configuration Check (MEDIUM PRIORITY)

**Check K3S startup flags:**
```bash
ssh node1 'ps aux | grep k3s'
ssh node1 'cat /etc/systemd/system/k3s.service'

# Look for:
# - --disable traefik (should be present)
# - Network plugin options
# - Service CIDR configuration
```

### 4. Kernel Conntrack/Netfilter (LOW PRIORITY)

**Check connection tracking:**
```bash
ssh node1 'sudo conntrack -L | grep "dport=80"'
```

### 5. K3S GitHub Issues Search (MEDIUM PRIORITY)

Search for:
- "k3s port 80 connection refused"
- "k3s clusterip port 80"
- "k3s flannel port 80"
- "k3s pods cannot reach services port 80"

---

## Workaround Status

**Current Workaround:** Change all Flux services from port 80 to port 9090

**Issues with Workaround:**
1. Flux will reconcile services back to port 80 from Git
2. Requires patching gotk-components.yaml in Git
3. Not a sustainable solution (port 80 is standard)
4. Doesn't solve the underlying problem for other services

**Blocker:** Service patch fails with "Duplicate value: http" error, indicating Flux is trying to recreate the service during reconciliation.

---

## Next Steps

**Immediate (To Unblock Migration):**
1. Capture iptables rules from node and pod namespace
2. Run tcpdump to see where packets are being dropped
3. Check K3S service configuration for Traefik remnants
4. Search K3S issues for similar reports

**If Root Cause Found:**
- Fix the underlying iptables/CNI/K3S configuration
- Remove all workarounds
- Re-bootstrap Flux with clean config

**If No Quick Fix:**
- Patch gotk-components.yaml in Git to use port 9090 for all services
- Update Flux URLs to use explicit :9090 port
- Document this as K3S-specific limitation
- Plan eventual migration to full K8S if issue persists

---

## Questions to Answer

1. **Are there any iptables rules specifically blocking pod → ClusterIP:80 traffic?**
2. **Is this a documented K3S limitation or bug?**
3. **Does K3S reserve port 80 for something (Traefik, ingress controller)?**
4. **Is there a K3S configuration flag that would fix this?**
5. **Why does port 9090 work but port 80 doesn't, given they use the same routing path?**

---

## References

- K3S Version: v1.33.6+k3s1
- Flannel Backend: vxlan
- Service Proxy: kube-proxy (iptables mode)
- NetworkPolicy Controller: kube-router
- Previous Issue: NetworkPolicies blocked ALL pod-to-service traffic (resolved by deleting policies)
- Current Issue: Port 80 specifically blocked for pod-to-service traffic

---

**Last Updated:** 2025-12-28 15:25 UTC
**Investigator:** Claude Code
**Status:** Awaiting iptables/tcpdump analysis
