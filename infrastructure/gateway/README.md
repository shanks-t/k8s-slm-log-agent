# Envoy Gateway Configuration

This directory contains the Gateway API resources for your homelab infrastructure.

## Architecture Alignment

- **Gateway runs on Node 1** (via `nodeSelector: hardware=light`)
- **Uses NodePort** for simple homelab access
- **HTTP listener on port 80** (HTTPS can be added later)
- **Routes from any namespace** allowed

## Files Overview

1. **01-gatewayclass.yaml** - Defines that Envoy Gateway controller manages Gateways
2. **02-envoy-proxy-config.yaml** - Configures HOW Envoy Proxy deploys (NodePort, Node 1, etc.)
3. **03-gateway.yaml** - The actual Gateway (creates Envoy Proxy pods)
4. **04-test-httproute.yaml** - Test route + sample app to validate gateway works

## Apply Order

Apply in numerical order:

```bash
kubectl apply -f k8s/gateway/01-gatewayclass.yaml
kubectl apply -f k8s/gateway/02-envoy-proxy-config.yaml
kubectl apply -f k8s/gateway/03-gateway.yaml
kubectl apply -f k8s/gateway/04-test-httproute.yaml
```

Or apply all at once:

```bash
kubectl apply -f k8s/gateway/
```

## Validation Steps

### 1. Check GatewayClass is accepted
```bash
kubectl get gatewayclass
```
Expected: `eg` with `ACCEPTED=True`

### 2. Check Gateway is programmed
```bash
kubectl get gateway -n envoy-gateway-system
```
Expected: `homelab-gateway` with `PROGRAMMED=True`

### 3. Check Envoy Proxy pods are running on Node 1
```bash
kubectl get pods -n envoy-gateway-system -o wide -l app=envoy-proxy
```
Expected: Pods running on `node-1` (NOT `llm`)

### 4. Get the NodePort
```bash
kubectl get svc -n envoy-gateway-system
```
Look for the NodePort assigned to port 80 (will be 30000-32767 range)

### 5. Test the route
```bash
curl http://10.0.0.102:<nodeport>/test
```
Expected: `Hello from homelab gateway!`

### 6. Verify test app runs on Node 2
```bash
kubectl get pods -n default -o wide
```
Expected: `test-app` pod running on `llm` (Node 2)

This validates:
- Gateway runs on Node 1 ✓
- Taint prevents test-app from running on Node 2... wait, no!
- Test-app CAN run on Node 2 because it doesn't have the taint

**Important**: The taint `NoSchedule` only prevents NEW pods without tolerations.
If you want test-app on Node 1, you'd need to add `nodeSelector: hardware=light`.
But it's fine on Node 2 for testing purposes.

## Cleanup Test Resources

When you're done testing, remove the test route:

```bash
kubectl delete -f k8s/gateway/04-test-httproute.yaml
```

Keep files 01-03 - those are your permanent infrastructure.

## Troubleshooting

**HTTPRoute works but backend service returns 503 or connection errors:**

If the Gateway can route requests but connections to backend services fail, this is usually a **cross-node networking issue**.

**Symptoms:**
- HTTPRoute is accepted and bound to Gateway
- Gateway is PROGRAMMED
- Curl to gateway returns `upstream connect error` or `503 Service Unavailable`
- Backend service is running on a different node than the Gateway

**Root cause:** K3s uses Flannel CNI with VXLAN backend, which requires **UDP port 8472** to be open between nodes.

**Diagnosis:**
```bash
# Get the backend pod IP
kubectl get pods -n <backend-namespace> -o wide

# Test if Gateway pod can reach backend pod
kubectl exec -n envoy-gateway-system <gateway-pod-name> -- wget -O- --timeout=2 http://<backend-pod-ip>:<port>
```

**Fix:** Open UDP port 8472 between nodes
```bash
# Add iptables rules on both nodes
ssh node1 "sudo iptables -I INPUT -s 10.0.0.103 -p udp --dport 8472 -j ACCEPT"
ssh node2 "sudo iptables -I INPUT -s 10.0.0.102 -p udp --dport 8472 -j ACCEPT"

# Restart K3s to rebuild VXLAN tunnel
ssh node1 "sudo systemctl restart k3s"
ssh node2 "sudo systemctl restart k3s-agent"

# Verify connectivity
kubectl run test-ping --rm -i --restart=Never --image=busybox:latest -- ping -c 3 <backend-pod-ip>
```

See `k8s/logging/README.md` for detailed cross-node networking troubleshooting.

## Next Steps (Future Phases)

- **Phase 2**: Create HTTPRoutes for Grafana
- **Phase 4**: Create HTTPRoutes for FastAPI log analyzer
- **Later**: Add HTTPS listener with TLS certificates
