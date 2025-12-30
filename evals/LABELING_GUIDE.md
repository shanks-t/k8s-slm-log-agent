# Golden Dataset Labeling Guide

This guide explains how to label the remaining 85 logs in `golden_dataset_severity_filtered.json`.

## Quick Reference

I've labeled 30 diverse logs as examples in `sample_labeled.json`. Use these as reference patterns.

## Label Fields

### 1. `root_cause` (Technical identifier)

**Format:** `snake_case` identifier describing the technical root cause

**Examples from labeled samples:**
- `tempo_unavailable` - service cannot be reached
- `empty_query_result` - query returned no results
- `context_size_exceeded` - LLM request too large
- `metrics_server_missing` - API discovery failure
- `helm_chart_invalid_reference` - malformed config
- `apiserver_not_ready` - control plane not ready

**Pattern**: Think "what would I grep for to find similar issues?"

---

### 2. `severity` (Lowercase: info/warn/error/critical)

**Guidelines:**
- **info**: Informational messages, expected warnings (e.g., "No GPU support" for CPU-only deployment)
- **warn**: Transient errors with automatic retry, missing optional components
- **error**: Failures requiring investigation (exceptions, failed requests, reconciliation errors)
- **critical**: System-wide failures, exhausted retries, data loss risk

**Common patterns:**
- Retrying automatically → `warn`
- Stacktrace fragments → `error`
- "Failed after max retries" → `critical`
- API unavailable during startup → `error`
- Empty query results → `warn`

---

### 3. `component` (System component)

**Format:** `snake_case` component name

**Common components:**
- `opentelemetry_exporter` - OTel trace/metric exporters
- `log_analyzer_api` - FastAPI log analysis service
- `llama_cpp` - LLM inference server
- `loki` - Log storage and query
- `kube_controller_manager` - K8s controller manager
- `flux_helm_controller` - Flux Helm operator
- `flux_source_controller` - Flux source manager
- `envoy_gateway` - Envoy Gateway controller

**Pattern**: Which service/binary generated this log?

---

### 4. `summary` (One sentence, plain English)

**Format:** Clear, concise explanation for an SRE

**Good examples:**
- "OpenTelemetry exporter cannot reach Tempo service, retrying with backoff"
- "LLM request exceeded configured context window size"
- "Flux exhausted retry attempts and cannot remediate failed Grafana release"

**Bad examples:**
- ❌ "Error occurred" (too vague)
- ❌ "The opentelemetry.exporter.otlp.proto.grpc.exporter module..." (too technical)

**Pattern**: Explain the problem and impact, not just restate the error message

---

### 5. `action_needed` (Operator action)

**Common values:**
- `none` - No action needed (transient, expected, or auto-recovering)
- `monitor` - Watch for recurrence, no immediate action
- `investigate` - Look into the issue (exceptions, unexpected errors)
- `increase_context_size` - Specific remediation action
- `fix_helm_chart_spec` - Fix configuration
- `update_helm_repo_url` - Update URL/reference
- `manual_helm_intervention` - Manual cleanup required
- `check_apiserver_connectivity` - Networking issue
- `wait_for_apiserver` - Transient startup issue

**Pattern**: What would you tell an on-call engineer?

---

## Labeling Workflow

### Step 1: Identify the Pattern

Look at the log and match it to a category:

1. **Transient connectivity** → `warn`, `action_needed: monitor`
2. **Expected missing components** → `warn`/`info`, `action_needed: none`
3. **Configuration errors** → `error`, `action_needed: fix_config`
4. **Stacktraces/exceptions** → `error`, `action_needed: investigate`
5. **Exhausted retries** → `critical`, `action_needed: manual_*`
6. **Startup errors** → `error`, `action_needed: wait_for_*`

### Step 2: Cross-reference with Examples

Search `sample_labeled.json` for similar logs:

```bash
# Find similar logs by namespace
grep -A 5 '"namespace": "llm"' sample_labeled.json

# Find similar components
grep -A 5 '"component": "flux' sample_labeled.json
```

### Step 3: Fill in Labels

Use the pattern from similar logs, adjusting for specifics.

---

## Common Labeling Scenarios

### Scenario: Flux Reconciliation Errors

**Pattern in samples:**
```json
{
  "root_cause": "helm_chart_reconciliation_stalled",
  "severity": "error",
  "component": "flux_source_controller",
  "summary": "Flux source controller cannot reconcile HelmChart due to missing chart name",
  "action_needed": "fix_helm_chart_spec"
}
```

**When to use:**
- Flux errors about HelmChart, HelmRelease, or HelmRepository
- "reconciliation stalled", "invalid chart reference", "404 Not Found"

---

### Scenario: Kubernetes API Not Ready (Startup)

**Pattern in samples:**
```json
{
  "root_cause": "apiserver_not_ready",
  "severity": "error",
  "component": "envoy_gateway",
  "summary": "Envoy Gateway cannot watch Deployments because API server is not ready",
  "action_needed": "wait_for_apiserver"
}
```

**When to use:**
- "apiserver not ready", "connection refused" during pod startup
- Usually timestamp is within minutes of pod start

---

### Scenario: LLM Context Size Errors

**Pattern in samples:**
```json
{
  "root_cause": "context_size_exceeded",
  "severity": "error",
  "component": "llama_cpp",
  "summary": "LLM request exceeded configured context window size",
  "action_needed": "increase_context_size"
}
```

**When to use:**
- llama.cpp errors about "context size"
- This is a real error that should be fixed

---

### Scenario: Missing Optional Components

**Pattern in samples:**
```json
{
  "root_cause": "metrics_server_missing",
  "severity": "warn",
  "component": "kube_controller_manager",
  "summary": "Garbage collector cannot discover metrics API (metrics-server not installed)",
  "action_needed": "none"
}
```

**When to use:**
- K8s errors about metrics.k8s.io, monitoring components
- Not critical for cluster operation

---

## Tips

### Use `detected_severity` as a Starting Point

The auto-detected severity is often right, but verify:
- **Upgrade** to `critical` if retries exhausted or data loss risk
- **Downgrade** to `warn` or `info` if transient/expected

### Context Matters

Same error message can have different severity:
- "Connection refused" during startup → `error` + `wait_for_apiserver`
- "Connection refused" during runtime → `error` + `investigate`

### Be Specific in `root_cause`

Good: `helm_repo_url_invalid`, `context_size_exceeded`, `tempo_unavailable`
Bad: `error`, `failed`, `unavailable`

---

## Merge Script

After labeling, merge your labels back into the full dataset:

```python
# TODO: Create merge script
python merge_labels.py \
  --full golden_dataset_severity_filtered.json \
  --labeled sample_labeled.json \
  --output golden_dataset_labeled.json
```

---

## Questions?

Check `sample_labeled.json` for 30 fully labeled examples covering all major patterns.
