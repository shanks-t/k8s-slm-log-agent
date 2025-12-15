# Phase 3A: FastAPI Log Analyzer with CRD Integration

This document outlines how to integrate the Custom Resource Definitions (LogAnalysisJob and GoldenLogSample) into the FastAPI log analyzer service for Phase 3A.

## Goals

1. Build FastAPI service for baseline time-based log retrieval and LLM analysis
2. Use LogAnalysisJob CRD for declarative job management
3. Store golden dataset as GoldenLogSample resources
4. Establish baseline extraction accuracy
5. Prepare for controller-based automation in Stage 3

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User/Client                          │
└────────┬──────────────────────────────────┬─────────────┘
         │                                  │
         │ kubectl create                   │ HTTP POST
         │ loganalysisjob                   │ /api/v1/analyze
         │                                  │
         ▼                                  ▼
┌─────────────────────┐          ┌──────────────────────┐
│  Kubernetes API     │          │  FastAPI Service     │
│  (CRD Storage)      │◄─────────│  (Node 1)            │
└─────────────────────┘  watch/  └──────────────────────┘
         │               poll            │        │
         │                               │        │
         │                               ▼        ▼
         │                      ┌──────────┐  ┌────────┐
         │                      │  Loki    │  │ LLM    │
         │                      │ (Node 2) │  │(Node 2)│
         │                      └──────────┘  └────────┘
         │
         ▼
┌─────────────────────┐
│  Golden Samples     │
│  (GoldenLogSample)  │
└─────────────────────┘
```

## Implementation Approach

### Option A: Dual Interface (Recommended for Phase 3A)

Support BOTH traditional REST API and Kubernetes-native CRD approach:

**REST API (for quick testing and external clients):**
- `POST /api/v1/analyze` - Direct analysis request
- Returns JSON response immediately (synchronous)

**CRD-based (Kubernetes-native):**
- User creates `LogAnalysisJob` via kubectl
- FastAPI polls for pending jobs
- Updates job status as it processes
- Users query status via kubectl

**Benefits:**
- Learn both approaches
- REST API for development/debugging
- CRD approach prepares for controller migration
- Flexibility in client choice

### Option B: CRD-Only (More Kubernetes-native)

All requests go through LogAnalysisJob CRD:
- No traditional REST endpoints
- Forces Kubernetes-native thinking
- Cleaner transition to controller in Stage 3

**Recommendation:** Use Option A for Phase 3A to maintain flexibility while learning.

## Project Structure

```
log-analyzer-service/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration
│   ├── models.py               # Pydantic models (REST API)
│   ├── k8s/
│   │   ├── client.py           # Kubernetes client wrapper
│   │   ├── job_processor.py   # LogAnalysisJob processor
│   │   └── golden_samples.py  # GoldenLogSample manager
│   ├── loki/
│   │   ├── client.py           # Loki query client
│   │   └── queries.py          # LogQL query builder
│   ├── llm/
│   │   ├── client.py           # LLM inference client
│   │   └── prompts.py          # Prompt templates
│   ├── evaluation/
│   │   ├── metrics.py          # Accuracy calculations
│   │   └── evaluator.py        # Evaluation runner
│   └── api/
│       ├── v1/
│       │   ├── analyze.py      # REST API endpoints
│       │   └── evaluation.py   # Evaluation endpoints
│       └── background.py       # Background job processor
└── k8s/
    ├── 00-namespace.yaml
    ├── 01-deployment.yaml
    ├── 02-service.yaml
    ├── 03-httproute.yaml
    └── 04-rbac.yaml
```

## Implementation Steps

### Step 1: Setup Kubernetes Client

```python
# app/k8s/client.py

from kubernetes import client, config
from typing import Dict, List, Optional
import os

class K8sClient:
    def __init__(self):
        # Load config (in-cluster for production, local for dev)
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            config.load_incluster_config()
        else:
            config.load_kube_config()

        self.api = client.CustomObjectsApi()
        self.group = "intelligence.homelab.io"
        self.version = "v1alpha1"

    def list_analysis_jobs(self, namespace: str = "default", phase: Optional[str] = None) -> List[Dict]:
        """List LogAnalysisJob resources"""
        jobs = self.api.list_namespaced_custom_object(
            group=self.group,
            version=self.version,
            namespace=namespace,
            plural="loganalysisjobs"
        )

        items = jobs.get('items', [])

        # Filter by phase if specified
        if phase:
            items = [job for job in items if job.get('status', {}).get('phase') == phase]

        return items

    def get_analysis_job(self, name: str, namespace: str = "default") -> Dict:
        """Get specific LogAnalysisJob"""
        return self.api.get_namespaced_custom_object(
            group=self.group,
            version=self.version,
            namespace=namespace,
            plural="loganalysisjobs",
            name=name
        )

    def update_job_status(self, name: str, namespace: str, status: Dict) -> Dict:
        """Update LogAnalysisJob status"""
        # Get current job
        job = self.get_analysis_job(name, namespace)

        # Update status
        job['status'] = status

        # Patch the status subresource
        return self.api.patch_namespaced_custom_object_status(
            group=self.group,
            version=self.version,
            namespace=namespace,
            plural="loganalysisjobs",
            name=name,
            body=job
        )

    def list_golden_samples(self, namespace: str = "default",
                           category: Optional[str] = None,
                           difficulty: Optional[str] = None) -> List[Dict]:
        """List GoldenLogSample resources"""
        samples = self.api.list_namespaced_custom_object(
            group=self.group,
            version=self.version,
            namespace=namespace,
            plural="goldenlogsamples"
        )

        items = samples.get('items', [])

        # Filter by category/difficulty
        if category:
            items = [s for s in items if s.get('spec', {}).get('category') == category]
        if difficulty:
            items = [s for s in items if s.get('spec', {}).get('difficulty') == difficulty]

        return items
```

### Step 2: Build Loki Client

```python
# app/loki/client.py

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class LokiClient:
    def __init__(self, base_url: str = "http://loki.logging.svc.cluster.local:3100"):
        self.base_url = base_url

    def query_range(self, query: str, start: datetime, duration: str) -> List[Dict]:
        """Query Loki for logs in a time range"""
        # Calculate end time
        end = self._parse_duration(start, duration)

        # Build query URL
        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {
            'query': query,
            'start': int(start.timestamp() * 1e9),  # nanoseconds
            'end': int(end.timestamp() * 1e9),
            'limit': 1000
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        return self._parse_results(data)

    def build_query(self, namespace: Optional[str] = None,
                   pod_selector: Optional[Dict[str, str]] = None,
                   severity: Optional[List[str]] = None) -> str:
        """Build LogQL query from filters"""
        # Start with namespace filter
        labels = []
        if namespace:
            labels.append(f'namespace="{namespace}"')

        # Add pod selector labels
        if pod_selector:
            for key, value in pod_selector.items():
                labels.append(f'{key}="{value}"')

        # Build label matcher
        label_matcher = '{' + ','.join(labels) + '}' if labels else '{}'

        # Add severity filter (assumes JSON logs)
        if severity:
            severity_filter = ' or '.join([f'severity="{s}"' for s in severity])
            return f'{label_matcher} | json | {severity_filter}'

        return f'{label_matcher} | json'

    def _parse_duration(self, start: datetime, duration: str) -> datetime:
        """Parse duration string like '1h', '30m', '2h30m'"""
        import re
        total_seconds = 0

        hours = re.search(r'(\d+)h', duration)
        if hours:
            total_seconds += int(hours.group(1)) * 3600

        minutes = re.search(r'(\d+)m', duration)
        if minutes:
            total_seconds += int(minutes.group(1)) * 60

        seconds = re.search(r'(\d+)s', duration)
        if seconds:
            total_seconds += int(seconds.group(1))

        return start + timedelta(seconds=total_seconds)

    def _parse_results(self, data: Dict) -> List[Dict]:
        """Parse Loki query results into log entries"""
        logs = []
        for stream in data.get('data', {}).get('result', []):
            labels = stream.get('stream', {})
            for timestamp, line in stream.get('values', []):
                logs.append({
                    'timestamp': timestamp,
                    'labels': labels,
                    'line': line
                })
        return logs
```

### Step 3: Build LLM Client

```python
# app/llm/client.py

import requests
from typing import Dict, Optional
import json

class LLMClient:
    def __init__(self, base_url: str = "http://llama-cpp.llm.svc.cluster.local:8080"):
        self.base_url = base_url

    def analyze_logs(self, logs: str, analysis_type: str,
                    max_tokens: int = 512,
                    temperature: float = 0.3) -> Dict:
        """Analyze logs using LLM"""
        from .prompts import build_prompt

        # Build prompt based on analysis type
        prompt = build_prompt(analysis_type, logs)

        # Call LLM
        response = self._chat_completion(prompt, max_tokens, temperature)

        # Parse JSON response
        try:
            result = json.loads(response)
            return result
        except json.JSONDecodeError:
            # Fallback: return raw response
            return {"rawResponse": response}

    def _chat_completion(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call OpenAI-compatible chat endpoint"""
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": "You are a Kubernetes log analysis expert."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        return data['choices'][0]['message']['content']
```

### Step 4: Build Job Processor

```python
# app/k8s/job_processor.py

from datetime import datetime
from .client import K8sClient
from ..loki.client import LokiClient
from ..llm.client import LLMClient
import time

class JobProcessor:
    def __init__(self):
        self.k8s = K8sClient()
        self.loki = LokiClient()
        self.llm = LLMClient()

    def process_job(self, job: dict):
        """Process a single LogAnalysisJob"""
        name = job['metadata']['name']
        namespace = job['metadata']['namespace']
        spec = job['spec']

        print(f"Processing job {namespace}/{name}")

        # Update status to Running
        self._update_status(name, namespace, {
            'phase': 'Running',
            'startTime': datetime.utcnow().isoformat() + 'Z'
        })

        try:
            # Step 1: Query Loki
            start_time = time.time()
            logs = self._query_loki(spec)
            loki_duration = int((time.time() - start_time) * 1000)

            if not logs:
                raise ValueError("No logs found for the specified criteria")

            # Step 2: Prepare log context
            log_text = self._format_logs(logs)

            # Step 3: Call LLM
            start_time = time.time()
            result = self.llm.analyze_logs(
                log_text,
                spec['analysisType'],
                spec.get('maxTokens', 512),
                spec.get('temperature', 0.3)
            )
            llm_duration = int((time.time() - start_time) * 1000)

            # Step 4: Update status to Completed
            self._update_status(name, namespace, {
                'phase': 'Completed',
                'completionTime': datetime.utcnow().isoformat() + 'Z',
                'logsAnalyzed': len(logs),
                'result': result,
                'metrics': {
                    'lokiQueryDurationMs': loki_duration,
                    'llmInferenceDurationMs': llm_duration,
                    'totalDurationMs': loki_duration + llm_duration
                }
            })

            print(f"Job {namespace}/{name} completed successfully")

        except Exception as e:
            # Update status to Failed
            self._update_status(name, namespace, {
                'phase': 'Failed',
                'completionTime': datetime.utcnow().isoformat() + 'Z',
                'error': str(e)
            })
            print(f"Job {namespace}/{name} failed: {e}")

    def _query_loki(self, spec: dict) -> list:
        """Query Loki based on job spec"""
        # Use custom query if provided
        if 'lokiQuery' in spec:
            query = spec['lokiQuery']
        else:
            # Build query from filters
            query = self.loki.build_query(
                namespace=spec.get('namespace'),
                pod_selector=spec.get('podSelector'),
                severity=spec.get('severity')
            )

        # Parse time range
        start = datetime.fromisoformat(spec['timeRange']['start'].replace('Z', '+00:00'))
        duration = spec['timeRange']['duration']

        return self.loki.query_range(query, start, duration)

    def _format_logs(self, logs: list) -> str:
        """Format logs for LLM input"""
        # Take most recent 50 logs (to fit in context window)
        recent_logs = logs[-50:]

        formatted = []
        for log in recent_logs:
            formatted.append(log['line'])

        return '\n'.join(formatted)

    def _update_status(self, name: str, namespace: str, status_update: dict):
        """Helper to update job status"""
        # Get current job
        job = self.k8s.get_analysis_job(name, namespace)
        current_status = job.get('status', {})

        # Merge updates
        new_status = {**current_status, **status_update}

        # Update
        self.k8s.update_job_status(name, namespace, new_status)
```

### Step 5: Background Worker

```python
# app/api/background.py

import asyncio
from ..k8s.client import K8sClient
from ..k8s.job_processor import JobProcessor

async def job_watcher():
    """Background task that polls for pending jobs"""
    k8s = K8sClient()
    processor = JobProcessor()

    while True:
        try:
            # List pending jobs
            jobs = k8s.list_analysis_jobs(phase='Pending')

            # Process each job
            for job in jobs:
                processor.process_job(job)

        except Exception as e:
            print(f"Error in job watcher: {e}")

        # Poll every 5 seconds
        await asyncio.sleep(5)
```

### Step 6: Main FastAPI App

```python
# app/main.py

from fastapi import FastAPI, BackgroundTasks
from contextlib import asynccontextmanager
import asyncio
from .api.background import job_watcher
from .api.v1 import analyze, evaluation

# Background task handle
watcher_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background job watcher
    global watcher_task
    watcher_task = asyncio.create_task(job_watcher())

    yield

    # Shutdown: Cancel background task
    if watcher_task:
        watcher_task.cancel()

app = FastAPI(
    title="Log Intelligence API",
    version="0.1.0",
    lifespan=lifespan
)

# Include routers
app.include_router(analyze.router, prefix="/api/v1", tags=["Analysis"])
app.include_router(evaluation.router, prefix="/api/v1", tags=["Evaluation"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
```

## Kubernetes Manifests

### RBAC Configuration

```yaml
# k8s/04-rbac.yaml

apiVersion: v1
kind: ServiceAccount
metadata:
  name: log-analyzer
  namespace: log-analyzer

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: log-analyzer-role
  namespace: default
rules:
  # LogAnalysisJob permissions
  - apiGroups: ["intelligence.homelab.io"]
    resources: ["loganalysisjobs"]
    verbs: ["get", "list", "watch", "patch", "update"]
  - apiGroups: ["intelligence.homelab.io"]
    resources: ["loganalysisjobs/status"]
    verbs: ["get", "patch", "update"]

  # GoldenLogSample permissions
  - apiGroups: ["intelligence.homelab.io"]
    resources: ["goldenlogsamples"]
    verbs: ["get", "list", "watch", "patch", "update"]
  - apiGroups: ["intelligence.homelab.io"]
    resources: ["goldenlogsamples/status"]
    verbs: ["get", "patch", "update"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: log-analyzer-binding
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: log-analyzer-role
subjects:
  - kind: ServiceAccount
    name: log-analyzer
    namespace: log-analyzer
```

## Usage Flow

### Create and Process a Job

```bash
# Step 1: Create a LogAnalysisJob
kubectl apply -f - <<EOF
apiVersion: intelligence.homelab.io/v1alpha1
kind: LogAnalysisJob
metadata:
  name: analyze-errors
  namespace: default
spec:
  timeRange:
    start: "2025-12-14T10:00:00Z"
    duration: "1h"
  namespace: "logging"
  severity: ["ERROR"]
  analysisType: root-cause
EOF

# Step 2: Watch status updates
kubectl get laj analyze-errors -w

# You'll see:
# NAME              PHASE     ANALYSIS TYPE   AGE
# analyze-errors    Pending   root-cause      0s
# analyze-errors    Running   root-cause      5s
# analyze-errors    Completed root-cause      12s

# Step 3: View results
kubectl get laj analyze-errors -o jsonpath='{.status.result}' | jq
```

## Evaluation Workflow

```python
# Example: Run evaluation on golden dataset

from app.k8s.client import K8sClient
from app.k8s.job_processor import JobProcessor
from app.evaluation.metrics import calculate_accuracy

k8s = K8sClient()

# Get all golden samples
samples = k8s.list_golden_samples()

results = []
for sample in samples:
    spec = sample['spec']

    # Create analysis job for this sample
    # (simplified - in practice, use the job processor)
    predicted = analyze_log(spec['logEntry'])
    ground_truth = spec['groundTruth']

    # Calculate accuracy
    accuracy = calculate_accuracy(predicted, ground_truth)

    results.append({
        'sample': sample['metadata']['name'],
        'accuracy': accuracy
    })

# Report overall accuracy
avg_accuracy = sum(r['accuracy'] for r in results) / len(results)
print(f"Overall accuracy: {avg_accuracy:.2%}")
```

## Benefits of This Approach

1. **Declarative job management** - Jobs are Kubernetes resources
2. **Auditable** - All jobs persisted in etcd with full history
3. **kubectl integration** - Use standard Kubernetes tooling
4. **Prepares for controllers** - Easy migration to event-driven controllers in Stage 3
5. **Separation of concerns** - API logic separate from job orchestration
6. **Testable** - Can test with mock Kubernetes API

## Next Steps

After Phase 3A baseline is working:

1. **Measure baseline accuracy** on golden dataset
2. **Add Phase 3B**: Vector DB + hybrid retrieval
3. **Stage 3**: Build controller using Kubebuilder to replace polling
4. **Add webhooks**: Validation and defaulting for LogAnalysisJob

## Migration Path to Controller (Stage 3)

The background polling approach in Phase 3A easily transitions to a controller:

**Phase 3A (Current):**
```python
# Poll every 5 seconds
while True:
    jobs = k8s.list_analysis_jobs(phase='Pending')
    for job in jobs:
        process_job(job)
    await asyncio.sleep(5)
```

**Stage 3 (Controller):**
```go
// Watch for events (push-based, instant)
func (r *LogAnalysisJobReconciler) Reconcile(ctx context.Context, req ctrl.Request) {
    // Triggered automatically on create/update/delete
    job := &intelligenceV1.LogAnalysisJob{}
    r.Get(ctx, req.NamespacedName, job)

    if job.Status.Phase == "Pending" {
        processJob(job)
    }
}
```

The controller version is:
- **Faster** - event-driven, no polling delay
- **More efficient** - only processes changes
- **More Kubernetes-native** - follows standard patterns

But both share the same underlying logic and resource definitions!
