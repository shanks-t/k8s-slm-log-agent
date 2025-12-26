# Custom Resource Definitions (CRDs)

This directory contains Custom Resource Definitions (CRDs) that extend the Kubernetes API for the log intelligence platform.

## Purpose

These CRDs serve two goals:

1. **Learning Kubernetes API mechanics** - Understand how CRDs extend the Kubernetes API (Stage 2 of the learning roadmap)
2. **Domain-specific resource management** - Provide declarative storage for log analysis jobs and golden dataset samples

## CRDs Overview

### LogAnalysisJob

Represents a request to analyze logs using LLM-based extraction.

**Use cases:**
- Trigger root cause analysis for specific time ranges
- Generate summaries of errors in a namespace
- Perform triage ranking of log events
- Detect patterns or changes over time

**Key features:**
- Time-range based log queries
- Namespace and severity filtering
- Custom LogQL query support
- LLM configuration (model, temperature, max tokens)
- Status tracking (Pending → Running → Completed/Failed)
- Performance metrics (query duration, inference time)

### GoldenLogSample

Represents a labeled log entry for evaluation and testing.

**Use cases:**
- Store ground truth labels for log analysis evaluation
- Build a curated dataset for model testing
- Track evaluation accuracy over time
- Stratify dataset by category and difficulty

**Key features:**
- Raw log entry storage
- Context metadata (timestamp, namespace, pod, node)
- Ground truth labels (root cause, severity, component, etc.)
- Category classification (infra vs app, failure types)
- Evaluation result tracking
- Success rate calculation

## Installation

### Step 1: Install the CRDs

```bash
# From the k8s-slm-log-agent directory
kubectl apply -f k8s/crds/loganalysisjob-crd.yaml
kubectl apply -f k8s/crds/goldenlogsample-crd.yaml
```

### Step 2: Verify installation

```bash
# List installed CRDs
kubectl get crds | grep intelligence.homelab.io

# Expected output:
# loganalysisjobs.intelligence.homelab.io
# goldenlogsamples.intelligence.homelab.io
```

### Step 3: Explore the API

```bash
# Use kubectl explain to see the schema
kubectl explain loganalysisjob
kubectl explain loganalysisjob.spec
kubectl explain loganalysisjob.spec.timeRange
kubectl explain loganalysisjob.status

kubectl explain goldenlogsample
kubectl explain goldenlogsample.spec.groundTruth
```

## Usage Examples

### Creating a LogAnalysisJob

```bash
# Apply a sample job
kubectl apply -f k8s/crds/samples/loganalysisjob-root-cause.yaml

# List all jobs
kubectl get loganalysisjobs
# or use short name
kubectl get laj

# Get details
kubectl describe loganalysisjob analyze-pod-crashes

# Watch for status updates
kubectl get loganalysisjob analyze-pod-crashes -w
```

### Creating a GoldenLogSample

```bash
# Apply sample golden log entries
kubectl apply -f k8s/crds/samples/goldenlogsample-oom.yaml

# List all golden samples
kubectl get goldenlogsamples
# or use short name
kubectl get gls

# Filter by severity
kubectl get gls -l severity=critical

# Filter by category
kubectl get gls -l category=infra-pod-failure

# View details
kubectl describe goldenlogsample oom-killed-pod-001
```

### Querying via JSON/YAML

```bash
# Get as JSON
kubectl get laj analyze-pod-crashes -o json

# Get specific fields
kubectl get laj analyze-pod-crashes -o jsonpath='{.status.phase}'

# Get all samples with their success rates
kubectl get gls -o custom-columns=NAME:.metadata.name,SEVERITY:.spec.groundTruth.severity,SUCCESS_RATE:.status.successRate
```

### Custom Columns

The CRDs include custom printer columns for better output:

```bash
# LogAnalysisJob shows: Name, Phase, Analysis Type, Age
kubectl get laj

# With more details (priority 1 columns)
kubectl get laj -o wide
# Shows: Name, Phase, Analysis Type, Namespace, Logs, Age

# GoldenLogSample shows: Name, Severity, Category, Age
kubectl get gls

# With more details
kubectl get gls -o wide
# Shows: Name, Severity, Category, Source, Success Rate, Age
```

## Integration with FastAPI (Phase 3A)

These CRDs can be used WITHOUT controllers initially. Your FastAPI service can interact with them using the Kubernetes Python client.

**Option 1: Manual status updates (no controller)**
```python
from kubernetes import client, config

# Load kubeconfig
config.load_incluster_config()  # or load_kube_config() for local dev

# Create custom API client
api = client.CustomObjectsApi()

# List pending jobs
jobs = api.list_namespaced_custom_object(
    group="intelligence.homelab.io",
    version="v1alpha1",
    namespace="default",
    plural="loganalysisjobs"
)

for job in jobs['items']:
    if job['status'].get('phase') == 'Pending':
        # Process the job
        process_analysis_job(job)

        # Update status
        job['status']['phase'] = 'Running'
        api.patch_namespaced_custom_object_status(
            group="intelligence.homelab.io",
            version="v1alpha1",
            namespace="default",
            plural="loganalysisjobs",
            name=job['metadata']['name'],
            body=job
        )
```

**Option 2: With controller (Stage 3)**
The controller watches for new LogAnalysisJob resources and automatically processes them.

## API Access via REST

You can also access these resources via the Kubernetes REST API:

```bash
# Start kubectl proxy
kubectl proxy

# List all LogAnalysisJobs
curl http://localhost:8001/apis/intelligence.homelab.io/v1alpha1/namespaces/default/loganalysisjobs

# Get specific job
curl http://localhost:8001/apis/intelligence.homelab.io/v1alpha1/namespaces/default/loganalysisjobs/analyze-pod-crashes

# Create a job
curl -X POST http://localhost:8001/apis/intelligence.homelab.io/v1alpha1/namespaces/default/loganalysisjobs \
  -H "Content-Type: application/json" \
  -d @job.json
```

## Schema Validation

Both CRDs include extensive validation:

**LogAnalysisJob validations:**
- `timeRange.duration` must match pattern `^([0-9]+h)?([0-9]+m)?([0-9]+s)?$`
- `severity` items must be one of: INFO, WARN, ERROR, CRITICAL
- `analysisType` must be one of: root-cause, summary, triage, pattern-detection, what-changed
- `maxTokens` must be between 128-2048
- `temperature` must be between 0.0-2.0

**GoldenLogSample validations:**
- `groundTruth.severity` must be one of: INFO, WARN, ERROR, CRITICAL
- `category` must be a valid category enum
- `source` must be one of: real, synthetic, curated
- `difficulty` must be one of: easy, medium, hard

Try creating an invalid resource to see validation in action:

```yaml
apiVersion: intelligence.homelab.io/v1alpha1
kind: LogAnalysisJob
metadata:
  name: invalid-job
spec:
  timeRange:
    start: "2025-12-14T10:00:00Z"
    duration: "invalid"  # Should be like "1h" or "30m"
  analysisType: "invalid-type"  # Must be from enum
```

```bash
kubectl apply -f invalid-job.yaml
# Error: validation failed - Kubernetes rejects it before storing!
```

## Lifecycle Management

### Deleting Resources

```bash
# Delete specific job
kubectl delete loganalysisjob analyze-pod-crashes

# Delete all jobs
kubectl delete loganalysisjobs --all

# Delete specific golden sample
kubectl delete goldenlogsample oom-killed-pod-001

# Delete all golden samples
kubectl delete goldenlogsamples --all
```

### Uninstalling CRDs

```bash
# Remove the CRDs (this also deletes all resources of that type!)
kubectl delete crd loganalysisjobs.intelligence.homelab.io
kubectl delete crd goldenlogsamples.intelligence.homelab.io
```

WARNING: Deleting a CRD deletes ALL resources of that type!

## Next Steps

### Stage 2 Learning (Current)
- ✅ Install CRDs
- ✅ Create sample resources
- ✅ Query via kubectl and REST API
- ✅ Understand schema validation
- ⬜ Integrate with FastAPI for manual processing

### Stage 3 Learning (Future)
- Build controllers using Kubebuilder
- Implement reconciliation loops
- Add webhooks for validation/mutation
- Deploy as operators

### Phase 3A Integration (Upcoming)
- FastAPI reads LogAnalysisJob resources
- FastAPI updates job status after analysis
- Store golden dataset as GoldenLogSample resources
- Query golden samples for evaluation runs

## Reference

### LogAnalysisJob Spec Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timeRange.start` | string (date-time) | Yes | Start time in RFC3339 format |
| `timeRange.duration` | string | Yes | Duration (e.g., "1h", "30m") |
| `namespace` | string | No | Kubernetes namespace filter |
| `podSelector` | map[string]string | No | Label selector for pods |
| `severity` | array | No | Severity level filter |
| `analysisType` | string (enum) | Yes | Type of analysis |
| `llmModel` | string | No | LLM model name (default: "llama-3.2-3b") |
| `maxTokens` | integer | No | Max tokens (default: 512) |
| `temperature` | number | No | Temperature (default: 0.3) |
| `lokiQuery` | string | No | Custom LogQL query |

### LogAnalysisJob Status Fields

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string (enum) | Current phase: Pending, Running, Completed, Failed |
| `startTime` | string (date-time) | When job started |
| `completionTime` | string (date-time) | When job finished |
| `logsAnalyzed` | integer | Number of log entries analyzed |
| `result` | object | Analysis result with rootCause, severity, etc. |
| `error` | string | Error message if failed |
| `metrics` | object | Performance metrics |

### GoldenLogSample Spec Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `logEntry` | string | Yes | Raw log entry |
| `context` | object | No | Additional context (namespace, pod, etc.) |
| `groundTruth.rootCause` | string | Yes | Expected root cause |
| `groundTruth.severity` | string (enum) | Yes | Expected severity |
| `groundTruth.component` | string | Yes | Expected component |
| `groundTruth.summary` | string | No | Expected summary |
| `groundTruth.recommendedAction` | string | No | Expected action |
| `groundTruth.tags` | array | No | Classification tags |
| `category` | string (enum) | No | Sample category |
| `source` | string (enum) | No | Source: real, synthetic, curated |
| `difficulty` | string (enum) | No | Difficulty: easy, medium, hard |

## Troubleshooting

### CRD not found

```bash
# Check if CRD is installed
kubectl get crds | grep intelligence.homelab.io

# If not found, install it
kubectl apply -f k8s/crds/loganalysisjob-crd.yaml
```

### Validation errors

```bash
# Use kubectl explain to check schema
kubectl explain loganalysisjob.spec.timeRange

# Get detailed error
kubectl apply -f your-job.yaml --validate=true -v=8
```

### Can't create resources

```bash
# Check RBAC permissions
kubectl auth can-i create loganalysisjobs

# Check API server is serving the CRD
kubectl api-resources | grep intelligence
```

## Learning Resources

- [Kubernetes API Exploration Guide](../../docs/k8s-api-exploration.md) - Stage 1 learning
- [Kubebuilder Book](https://book.kubebuilder.io/) - For Stage 3 controller development
- [Kubernetes API Conventions](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
