#!/bin/bash
# Helper script to deploy llama.cpp to Kubernetes

set -e

echo "========================================="
echo "llama.cpp Kubernetes Deployment Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "Step 1: Checking prerequisites..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ kubectl not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ kubectl found${NC}"

# Check if node-2 exists and has correct label
if kubectl get node node-2 &> /dev/null; then
    echo -e "${GREEN}✓ node-2 exists${NC}"
else
    echo -e "${RED}✗ node-2 not found. Update 01-pv.yaml with correct hostname${NC}"
    exit 1
fi

# Check hardware label
if kubectl get node node-2 --show-labels | grep -q "hardware=heavy"; then
    echo -e "${GREEN}✓ node-2 has hardware=heavy label${NC}"
else
    echo -e "${YELLOW}⚠ Adding hardware=heavy label to node-2${NC}"
    kubectl label node node-2 hardware=heavy
fi

# Check taint
if kubectl get node node-2 -o json | jq -e '.spec.taints[] | select(.key=="heavy")' &> /dev/null; then
    echo -e "${GREEN}✓ node-2 has heavy taint${NC}"
else
    echo -e "${YELLOW}⚠ Adding taint to node-2${NC}"
    kubectl taint node node-2 heavy=true:NoSchedule
fi

echo ""
echo "Step 2: Checking model file..."

# Check if model exists on node-2
if ssh node2 "test -f /mnt/k8s-storage/models/llama-3.2-3b-instruct-q4_k_m.gguf"; then
    MODEL_SIZE=$(ssh node2 "ls -lh /mnt/k8s-storage/models/llama-3.2-3b-instruct-q4_k_m.gguf" | awk '{print $5}')
    echo -e "${GREEN}✓ Model file found ($MODEL_SIZE)${NC}"
else
    echo -e "${RED}✗ Model file not found at /mnt/k8s-storage/models/llama-3.2-3b-instruct-q4_k_m.gguf${NC}"
    echo ""
    echo "To fix, run on node-2:"
    echo "  ssh node2"
    echo "  sudo mkdir -p /mnt/k8s-storage/models"
    echo "  sudo chown -R \$USER:\$USER /mnt/k8s-storage/models"
    echo "  cp ~/.cache/llama.cpp/bartowski_Llama-3.2-3B-Instruct-GGUF_Llama-3.2-3B-Instruct-Q4_K_M.gguf \\"
    echo "     /mnt/k8s-storage/models/llama-3.2-3b-instruct-q4_k_m.gguf"
    exit 1
fi

echo ""
echo "Step 3: Applying Kubernetes manifests..."

# Create namespace first
kubectl apply -f k8s/llama-cpp/00-namespace.yaml
echo -e "${GREEN}✓ Namespace created${NC}"

# Apply manifests in order
kubectl apply -f k8s/llama-cpp/01-pv.yaml
echo -e "${GREEN}✓ PersistentVolume created${NC}"

kubectl apply -f k8s/llama-cpp/02-pvc.yaml
echo -e "${GREEN}✓ PersistentVolumeClaim created${NC}"

kubectl apply -f k8s/llama-cpp/03-deployment.yaml
echo -e "${GREEN}✓ Deployment created${NC}"

kubectl apply -f k8s/llama-cpp/04-service.yaml
echo -e "${GREEN}✓ Service created${NC}"

echo ""
echo "Step 4: Waiting for deployment..."
echo ""

# Wait for pod to be created
echo "Waiting for pod to be created..."
kubectl wait --for=condition=ready pod -l app=llama-cpp -n llm --timeout=180s || {
    echo -e "${RED}✗ Pod failed to become ready${NC}"
    echo ""
    echo "Check status with:"
    echo "  kubectl get pods -l app=llama-cpp -n llm"
    echo "  kubectl describe pod -l app=llama-cpp -n llm"
    echo "  kubectl logs -l app=llama-cpp -n llm"
    exit 1
}

echo -e "${GREEN}✓ Pod is ready!${NC}"

# Get pod info
POD_NAME=$(kubectl get pod -l app=llama-cpp -n llm -o jsonpath='{.items[0].metadata.name}')
POD_NODE=$(kubectl get pod -l app=llama-cpp -n llm -o jsonpath='{.items[0].spec.nodeName}')

echo ""
echo "Deployment successful!"
echo "  Pod: $POD_NAME"
echo "  Node: $POD_NODE"
echo ""

echo "Step 5: Testing API..."
echo ""

# Test health endpoint
echo "Testing health endpoint..."
HEALTH=$(kubectl run test-curl --rm -i --image=curlimages/curl --restart=Never -n llm -- \
  curl -s http://llama-cpp.llm.svc.cluster.local:8080/health)

if echo "$HEALTH" | grep -q "ok"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "Response: $HEALTH"
fi

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Service endpoint: llama-cpp.llm.svc.cluster.local:8080"
echo ""
echo "Next steps:"
echo "  1. View logs: kubectl logs -f $POD_NAME -n llm"
echo "  2. Test chat: see k8s/llama-cpp/README.md"
echo "  3. Monitor: kubectl top pod $POD_NAME -n llm"
echo ""
