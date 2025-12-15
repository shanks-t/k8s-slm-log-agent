# Kubernetes API Exploration Guide

This guide walks you through exploring the Kubernetes REST API directly to understand how your log intelligence platform's resources are structured and accessed.

## Goal

Understand:
- How Kubernetes API is organized (groups, versions, resources)
- How your YAML manifests map to REST API objects
- How kubectl commands translate to HTTP calls
- What CRDs are already installed in your cluster
- How resources reference each other (ownerReferences, labels, selectors)

## Prerequisites

Start the kubectl proxy to safely access the API server:

```bash
kubectl proxy
```

This starts a proxy on `http://localhost:8001` that handles authentication for you.

Keep this running in one terminal and open a new terminal for the exploration commands below.

## Part 1: Discover API Groups and Versions

### List all API groups

```bash
curl -s http://localhost:8001/apis | jq '.groups[] | {name: .name, preferredVersion: .preferredVersion.version}'
```

**What you're seeing:**
- Core resources (Pods, Services, etc.) are under `/api/v1` (no group)
- Everything else is under `/apis/<group>/<version>`
- Each group can have multiple versions (v1alpha1, v1beta1, v1)

### Explore the core API

```bash
# List all core resources (no group name)
curl -s http://localhost:8001/api/v1 | jq '.resources[] | {name: .name, kind: .kind, namespaced: .namespaced}'
```

**Key resources to note:**
- `pods`, `services`, `configmaps`, `secrets`, `persistentvolumes`, `persistentvolumeclaims`, `namespaces`

### Explore apps/v1 API group

```bash
# List resources in apps/v1 (Deployments, StatefulSets, DaemonSets)
curl -s http://localhost:8001/apis/apps/v1 | jq '.resources[] | {name: .name, kind: .kind, verbs: .verbs}'
```

**Verbs** show what operations you can perform:
- `get`, `list`, `watch` - read operations
- `create`, `update`, `patch` - write operations
- `delete`, `deletecollection` - delete operations

### Explore Gateway API (Envoy Gateway uses this)

```bash
# List Gateway API resources
curl -s http://localhost:8001/apis/gateway.networking.k8s.io/v1 | jq '.resources[] | {name: .name, kind: .kind}'
```

You should see: `gateways`, `httproutes`, `grpcroutes`, etc.

## Part 2: Explore Your Deployed Resources

### Examine Loki Deployment

```bash
# Get Loki deployment as JSON
curl -s http://localhost:8001/apis/apps/v1/namespaces/logging/deployments/loki | jq '.'
```

**Compare with kubectl:**
```bash
kubectl get deployment -n logging loki -o json
```

They return the same data - kubectl is just a client for the REST API.

### Examine key fields in the deployment

```bash
# Look at metadata
curl -s http://localhost:8001/apis/apps/v1/namespaces/logging/deployments/loki | jq '.metadata | {name, namespace, labels, annotations}'

# Look at spec
curl -s http://localhost:8001/apis/apps/v1/namespaces/logging/deployments/loki | jq '.spec | {replicas, selector, strategy}'

# Look at status
curl -s http://localhost:8001/apis/apps/v1/namespaces/logging/deployments/loki | jq '.status | {replicas, availableReplicas, conditions}'
```

**Key insight:** Every Kubernetes resource has this structure:
- `metadata` - names, labels, annotations, ownerReferences
- `spec` - desired state (what you declare)
- `status` - observed state (what the controller reports)

### Examine llama.cpp Pod

```bash
# List pods in llm namespace
curl -s http://localhost:8001/api/v1/namespaces/llm/pods | jq '.items[] | {name: .metadata.name, node: .spec.nodeName, phase: .status.phase}'

# Get specific pod (replace POD_NAME with actual pod name from above)
export POD_NAME=$(kubectl get pod -n llm -l app=llama-cpp -o jsonpath='{.items[0].metadata.name}')
curl -s http://localhost:8001/api/v1/namespaces/llm/pods/$POD_NAME | jq '.'
```

### Look at ownerReferences

```bash
# Pods are owned by ReplicaSets, which are owned by Deployments
curl -s http://localhost:8001/api/v1/namespaces/llm/pods/$POD_NAME | jq '.metadata.ownerReferences'
```

**What this shows:**
- The chain of ownership: Deployment → ReplicaSet → Pod
- When you delete a Deployment, it cascades to ReplicaSets and Pods
- This is how Kubernetes implements garbage collection

### Examine PersistentVolume and PersistentVolumeClaim

```bash
# Get Loki PV (not namespaced)
curl -s http://localhost:8001/api/v1/persistentvolumes/loki-pv | jq '{capacity: .spec.capacity, storageClass: .spec.storageClassName, hostPath: .spec.hostPath, claimRef: .spec.claimRef}'

# Get Loki PVC (namespaced)
curl -s http://localhost:8001/api/v1/namespaces/logging/persistentvolumeclaims/loki-pvc | jq '{volumeName: .spec.volumeName, storageClass: .spec.storageClassName, resources: .spec.resources}'
```

**Key insight:**
- PV has `claimRef` pointing to PVC
- PVC has `volumeName` pointing to PV
- This bidirectional binding is how they're matched

## Part 3: Explore Gateway API (Envoy Gateway)

### List all HTTPRoutes

```bash
curl -s http://localhost:8001/apis/gateway.networking.k8s.io/v1/httproutes | jq '.items[] | {name: .metadata.name, namespace: .metadata.namespace}'
```

### Examine Grafana HTTPRoute

```bash
# Get Grafana HTTPRoute details
curl -s http://localhost:8001/apis/gateway.networking.k8s.io/v1/namespaces/envoy-gateway-system/httproutes/grafana-route | jq '.'

# Focus on the routing rules
curl -s http://localhost:8001/apis/gateway.networking.k8s.io/v1/namespaces/envoy-gateway-system/httproutes/grafana-route | jq '.spec | {parentRefs, hostnames, rules}'
```

**Compare with your manifest:**
```bash
cat k8s/gateway/05-grafana-httproute.yaml
```

See how the YAML structure maps exactly to the JSON structure.

### Examine Gateway resource

```bash
# List all Gateways
curl -s http://localhost:8001/apis/gateway.networking.k8s.io/v1/gateways | jq '.items[] | {name: .metadata.name, namespace: .metadata.namespace}'

# Get details of your gateway
curl -s http://localhost:8001/apis/gateway.networking.k8s.io/v1/namespaces/envoy-gateway-system/gateways/eg | jq '{listeners: .spec.listeners, addresses: .status.addresses}'
```

## Part 4: Discover Custom Resource Definitions (CRDs)

### List all CRDs in your cluster

```bash
curl -s http://localhost:8001/apis/apiextensions.k8s.io/v1/customresourcedefinitions | jq '.items[] | .metadata.name' | sort
```

**What you'll see:**
- Gateway API CRDs (gateways, httproutes, etc.) - installed by Envoy Gateway
- Potentially Grafana/Loki related CRDs from Helm charts
- Any other operators you've installed

### Examine a specific CRD (HTTPRoute)

```bash
curl -s http://localhost:8001/apis/apiextensions.k8s.io/v1/customresourcedefinitions/httproutes.gateway.networking.k8s.io | jq '.'
```

**Focus on the schema:**
```bash
curl -s http://localhost:8001/apis/apiextensions.k8s.io/v1/customresourcedefinitions/httproutes.gateway.networking.k8s.io | jq '.spec | {group, names, versions: .versions[].name}'
```

**See the OpenAPI schema:**
```bash
curl -s http://localhost:8001/apis/apiextensions.k8s.io/v1/customresourcedefinitions/httproutes.gateway.networking.k8s.io | jq '.spec.versions[0].schema.openAPIV3Schema.properties.spec' | head -50
```

**Key insight:** This schema is what makes `kubectl explain` work:

```bash
kubectl explain httproute.spec
kubectl explain httproute.spec.rules
```

The explain output comes from this OpenAPI schema in the CRD.

## Part 5: Watch for Real-Time Updates

### Watch pod changes

```bash
# Watch pods in logging namespace (leave this running)
curl -s "http://localhost:8001/api/v1/namespaces/logging/pods?watch=true"
```

In another terminal, create/delete a pod:
```bash
kubectl run test-pod -n logging --image=nginx
kubectl delete pod test-pod -n logging
```

**What you see:**
- Each change triggers a watch event: `ADDED`, `MODIFIED`, `DELETED`
- This is how controllers stay up-to-date - they watch for changes
- More efficient than polling

## Part 6: Understanding kubectl → REST API Translation

### How kubectl maps to API calls

| kubectl command | REST API equivalent |
|----------------|---------------------|
| `kubectl get pods -n logging` | `GET /api/v1/namespaces/logging/pods` |
| `kubectl get pod loki-0 -n logging` | `GET /api/v1/namespaces/logging/pods/loki-0` |
| `kubectl create -f pod.yaml` | `POST /api/v1/namespaces/{ns}/pods` |
| `kubectl delete pod test -n default` | `DELETE /api/v1/namespaces/default/pods/test` |
| `kubectl get httproutes` | `GET /apis/gateway.networking.k8s.io/v1/httproutes` |

### See actual API calls kubectl makes

```bash
# Add --v=8 to see HTTP requests
kubectl get pods -n logging --v=8 2>&1 | grep "GET https://"
```

## Part 7: Explore Resource Relationships

### How Services find Pods (label selectors)

```bash
# Get llama-cpp Service selector
curl -s http://localhost:8001/api/v1/namespaces/llm/services/llama-cpp | jq '.spec.selector'

# Find pods with matching labels
curl -s http://localhost:8001/api/v1/namespaces/llm/pods | jq '.items[] | select(.metadata.labels.app=="llama-cpp") | {name: .metadata.name, labels: .metadata.labels, podIP: .status.podIP}'
```

**Key insight:** Services use label selectors to find Pods dynamically.

### How Deployments manage ReplicaSets

```bash
# Get Loki Deployment's selector
curl -s http://localhost:8001/apis/apps/v1/namespaces/logging/deployments/loki | jq '.spec.selector'

# Find ReplicaSets with matching labels
curl -s http://localhost:8001/apis/apps/v1/namespaces/logging/replicasets | jq '.items[] | select(.metadata.labels."app.kubernetes.io/name"=="loki") | {name: .metadata.name, replicas: .spec.replicas}'
```

## Part 8: Hands-On Exercise

Create a simple Pod and observe it through the API:

```bash
# Create a test pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: api-test-pod
  namespace: default
  labels:
    purpose: api-learning
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    resources:
      requests:
        memory: "64Mi"
        cpu: "100m"
      limits:
        memory: "128Mi"
        cpu: "200m"
EOF

# Retrieve it via API
curl -s http://localhost:8001/api/v1/namespaces/default/pods/api-test-pod | jq '.'

# Look at different parts
curl -s http://localhost:8001/api/v1/namespaces/default/pods/api-test-pod | jq '.metadata | {name, namespace, labels, creationTimestamp}'
curl -s http://localhost:8001/api/v1/namespaces/default/pods/api-test-pod | jq '.spec.containers[] | {name, image, resources}'
curl -s http://localhost:8001/api/v1/namespaces/default/pods/api-test-pod | jq '.status | {phase, podIP, hostIP, conditions}'

# Clean up
kubectl delete pod api-test-pod
```

## Key Takeaways

1. **Everything in Kubernetes is an API resource** accessed via REST endpoints
2. **kubectl is just a REST API client** - every kubectl command maps to HTTP calls
3. **Resource structure is consistent**: metadata + spec + status
4. **CRDs extend the API** by adding new resource types with custom schemas
5. **Controllers watch resources** and reconcile actual state with desired state
6. **Label selectors** are how resources find each other dynamically
7. **OwnerReferences** create parent-child relationships for garbage collection
8. **Versioning** allows API evolution (v1alpha1 → v1beta1 → v1)

## Next Steps

Now that you understand how the API works:

1. Look at your existing manifests in `k8s/` and trace how they map to API objects
2. Create your own CRDs to extend the API (Stage 2)
3. Write controllers that watch your custom resources and reconcile state (Stage 3)

## Resources

- API Reference: Run `kubectl proxy` and visit http://localhost:8001
- Explore resources: `kubectl api-resources`
- Explore schemas: `kubectl explain <resource>` (e.g., `kubectl explain pod.spec`)
- Official docs: https://kubernetes.io/docs/reference/using-api/
