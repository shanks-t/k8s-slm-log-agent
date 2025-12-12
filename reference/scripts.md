
### pull qwen models for research agent
```sh
# Set OLLAMA_POD environment variable
export OLLAMA_POD=$(kubectl get pods -n llm-serving -l app=ollama -o jsonpath='{.items[0].metadata.name}')

# Pull planner model (1.8b)
kubectl exec -n llm-serving -it $OLLAMA_POD -- ollama pull qwen3:1.8b

# Alternative: pull 1.7b if you want smaller/faster
kubectl exec -n llm-serving -it $OLLAMA_POD -- ollama pull qwen3:1.7b

# Pull responder model (4b)
kubectl exec -n llm-serving -it $OLLAMA_POD -- ollama pull qwen3:4b

# List available models
kubectl exec -n llm-serving -it $OLLAMA_POD -- ollama list
```

### prompt ollama
```sh
kubectl exec -n llm-serving -it $OLLAMA_POD -- ollama run llama3.2:3b "Explain Kubernetes in one sentence"
```

```sh
curl http://10.0.0.101:30434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Why is the sky blue?",
  "stream": false
}'
```
ssh node1 "sudo /usr/local/bin/k3s-uninstall.sh"

 ssh node1 "sudo /usr/local/bin/k3s-agent-uninstall.sh"

 TOKEN=$(ssh node1 'sudo cat /var/lib/rancher/k3s/server/node-token')
echo $TOKEN

ssh node2 "curl -sfL https://get.k3s.io | K3S_URL=https://10.0.0.102:6443 \
K3S_TOKEN=$TOKEN \
sh -s - agent \
--node-label 'hardware=heavy'"

- helm envoy install:
```sh
helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.4.6 -n envoy-gateway-system --create-namespace

 kubectl get pods -n envoy-gateway-system -o wide

ssh node1 "sudo mkdir -p /etc/rancher/k3s

ssh node1 "echo 'disable:
    - traefik' | sudo tee /etc/rancher/k3s/config.yaml"
```


Work around because CRD manifests are too large to fit in helms default secret storage
apply just envoy CRDsply -
```sh
  kubectl apply -f
  https://github.com/envoyproxy/gateway/releases/download/v1.4.6/install.yaml
  --server-side
```

create gateway:
```sh
kubectl apply -f k8s/gateway/03-gateway.yaml
```

status:
```sh
kubectl get gateway -n envoy-gateway-system -w
```

check gateway:
```sh
k get gateway -n envoy-gateway-system

kubectl get pods -n envoy-gateway-system -o wide

kubectl get svc -n envoy-gateway-system

kubectl get events -n envoy-gateway-system --sort-by='.lastTimestamp' | tail -20

kubectl get gateway -n envoy-gateway-system -w

kubectl get pods -n envoy-gateway-system -o wide -l gateway.envoyproxy.io/owning-gateway-name=homelab-gateway

kubectl get svc -n envoy-gateway-system -l gateway.envoyproxy.io/owning-gateway-name=homelab-gateway
```
test loadbalancer:
```sh
curl http://10.0.0.102/test
```

update helm deployment for loki:
```sh
  helm upgrade loki grafana/loki \
    --namespace logging \
    --values k8s/logging/02-loki-values.yaml \
    --version 6.21.0
```

