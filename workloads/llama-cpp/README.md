# llama.cpp Kubernetes Deployment

This directory contains manifests to deploy llama.cpp with Llama 3.2 3B on Node 2.

## Architecture

- **Model:** Llama 3.2 3B Instruct Q4_K_M (1.87 GB)
- **Performance:** ~19.75 tokens/sec (CPU-only with AVX_VNNI)
- **Node:** Node 2 only (hardware=heavy)
- **Storage:** `/mnt/k8s-storage/models` via local PersistentVolume
- **Resources:** 8-12 CPU cores, 3-4 GB memory

## Prerequisites

### 1. Verify Node 2 Hostname

Check the actual hostname of Node 2:

```bash
kubectl get nodes --show-labels | grep heavy
```

If the hostname is not `node-2`, update `01-pv.yaml` line 20 with the correct hostname.

### 2. Move Model to Persistent Storage

**On Node 2:**

```bash
ssh node2

# Create models directory
sudo mkdir -p /mnt/k8s-storage/models
sudo chown -R $USER:$USER /mnt/k8s-storage/models

# Copy the model from cache
cp /home/trey/.cache/llama.cpp/bartowski_Llama-3.2-3B-Instruct-GGUF_Llama-3.2-3B-Instruct-Q4_K_M.gguf \
   /mnt/k8s-storage/models/llama-3.2-3b-instruct-q4_k_m.gguf

# Verify
ls -lh /mnt/k8s-storage/models/llama-3.2-3b-instruct-q4_k_m.gguf
```

You should see: `~1.9G llama-3.2-3b-instruct-q4_k_m.gguf`

### 3. Verify Node Labels and Taints

```bash
# Check Node 2 has the correct label
kubectl get node node-2 --show-labels | grep hardware=heavy

# Check Node 2 has the correct taint
kubectl get node node-2 -o json | jq '.spec.taints'
```

Expected taint:
```json
[
  {
    "effect": "NoSchedule",
    "key": "heavy",
    "value": "true"
  }
]
```

If missing, add them:

```bash
# Add label
kubectl label node node-2 hardware=heavy

# Add taint
kubectl taint node node-2 heavy=true:NoSchedule
```

## Deployment

### Step 1: Apply Manifests

```bash
# From the k8s-log-agent directory
kubectl apply -f k8s/llama-cpp/01-pv.yaml
kubectl apply -f k8s/llama-cpp/02-pvc.yaml
kubectl apply -f k8s/llama-cpp/03-deployment.yaml
kubectl apply -f k8s/llama-cpp/04-service.yaml
```

### Step 2: Verify Deployment

```bash
# Check PV bound
kubectl get pv llama-models-pv

# Check PVC bound
kubectl get pvc llama-models-pvc

# Check pod status
kubectl get pods -l app=llama-cpp

# Watch logs (model loading takes 30-60 seconds)
kubectl logs -f -l app=llama-cpp
```

**Expected logs:**
```
llama_model_loader: loaded meta data with 30 key-value pairs and 291 tensors...
llama server listening on 0.0.0.0:8080
```

### Step 3: Check Pod Placement

Verify the pod is running on Node 2:

```bash
kubectl get pod -l app=llama-cpp -o wide
```

The `NODE` column should show `node-2`.

## Testing

### Test 1: Health Check

```bash
kubectl run test-curl --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/health
```

Expected: `{"status":"ok"}`

### Test 2: Model Info

```bash
kubectl run test-curl --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/v1/models | jq
```

### Test 3: Text Completion

```bash
kubectl run test-curl --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze this Kubernetes error: pod failed with ImagePullBackOff. Provide root cause and solution.",
    "max_tokens": 256,
    "temperature": 0.7
  }' | jq
```

### Test 4: OpenAI-Compatible Chat

```bash
kubectl run test-curl --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a Kubernetes troubleshooting expert."},
      {"role": "user", "content": "Why would a pod get OOMKilled?"}
    ],
    "max_tokens": 200,
    "temperature": 0.7
  }' | jq '.choices[0].message.content'
```

## Performance Monitoring

### View Resource Usage

```bash
# CPU and memory usage
kubectl top pod -l app=llama-cpp

# Detailed metrics
kubectl describe pod -l app=llama-cpp
```

### Check Prometheus Metrics

```bash
kubectl run test-curl --rm -it --image=curlimages/curl -- \
  curl -s http://llama-cpp:8080/metrics
```

## Troubleshooting

### Pod Not Starting

```bash
# Check events
kubectl describe pod -l app=llama-cpp

# Check logs
kubectl logs -l app=llama-cpp
```

**Common issues:**

1. **Model file not found:**
   - Verify file exists: `ssh node2 "ls -lh /mnt/k8s-storage/models/llama-3.2-3b-instruct-q4_k_m.gguf"`
   - Check PV is bound: `kubectl get pv llama-models-pv`

2. **Pod stuck in Pending:**
   - Check node taints/tolerations: `kubectl get nodes -o json | jq '.items[].spec.taints'`
   - Verify node has resources: `kubectl describe node node-2`

3. **OOMKilled:**
   - Increase memory limits in `03-deployment.yaml`
   - Check actual memory usage: `kubectl top pod -l app=llama-cpp`

4. **Slow startup:**
   - Normal! Model loading takes 30-60 seconds on first start
   - Check logs: `kubectl logs -f -l app=llama-cpp`

### Performance Tuning

If performance is slower than expected (~19 tok/s):

1. **Increase CPU allocation:**
   ```yaml
   resources:
     requests:
       cpu: "10000m"
     limits:
       cpu: "14000m"
   ```

2. **Increase thread count:**
   ```yaml
   args:
     - "--threads"
     - "12"  # Increase from 10
   ```

3. **Reduce parallel requests:**
   ```yaml
   args:
     - "--parallel"
     - "1"  # Reduce from 2 if single-request latency is priority
   ```

## API Documentation

llama.cpp server provides an **OpenAI-compatible API**.

**Endpoints:**
- `GET /health` - Health check
- `GET /v1/models` - List available models
- `POST /v1/completions` - Text completion
- `POST /v1/chat/completions` - Chat completion
- `GET /metrics` - Prometheus metrics

**Full API docs:** https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md

## Next Steps

Once llama.cpp is deployed and tested:

1. Deploy Chroma vector database
2. Deploy BGE-small embedding model
3. Build evaluation framework with golden dataset
4. Test end-to-end log analysis pipeline

## Cleanup

```bash
kubectl delete -f k8s/llama-cpp/
```

**Note:** The PersistentVolume has `Retain` policy, so the model file will remain on Node 2 after deletion.
