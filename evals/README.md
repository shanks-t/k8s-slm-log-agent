# Golden Dataset Generation Workflow

This directory contains scripts to create a high-quality golden dataset for LLM evaluation of Kubernetes log analysis.

## Overview

The workflow combines **real logs** from your Loki deployment with **synthetic logs** generated from templates to create a diverse, balanced dataset of ~150 log samples.

### Scripts

1. **extract_golden_dataset.py** - Extracts and filters real logs from Loki
2. **log_templates.json** - Templates for generating synthetic Kubernetes logs
3. **synthesize_logs.py** - Generates synthetic logs from templates
4. **combine_datasets.py** - Merges real and synthetic logs
5. **dataset_analysis.py** - Analyzes dataset quality and distribution

## Workflow

### Step 1: Extract Real Logs from Loki

First, ensure Loki is accessible via port-forward:

```bash
kubectl port-forward -n logging svc/loki 3100:3100
```

Then run the extraction script:

```bash
cd /Users/treyshanks/workspace/k8s-log-agent
uv run python scripts/extract_golden_dataset.py
```

**What this does:**
- Queries Loki with 15 targeted LogQL queries for different failure modes
- Filters out noise (CoreDNS warnings, routine Envoy logs, etc.)
- Detects severity levels (INFO, WARN, ERROR, CRITICAL)
- Deduplicates by error signature
- Performs stratified sampling to get ~100 diverse logs
- Saves to `golden_dataset_real.json`

**Expected output:**
- ~60-100 real logs
- Automatic severity detection
- Deduplication by error pattern
- Distribution report

### Step 2: Generate Synthetic Logs

Generate synthetic logs to fill gaps in the dataset:

```bash
uv run python scripts/synthesize_logs.py
```

**What this does:**
- Loads templates from `log_templates.json` (30+ failure scenarios)
- Generates realistic variations with randomized values
- Creates proper Kubernetes metadata (pod names, namespaces, timestamps)
- Pre-fills ground truth labels from templates
- Saves to `golden_dataset_synthetic.json`

**Expected output:**
- ~60 synthetic logs
- Pre-labeled with ground truth
- Covers failure modes missing from real logs

### Step 3: Combine Datasets

Merge real and synthetic logs into the final dataset:

```bash
uv run python scripts/combine_datasets.py
```

**What this does:**
- Loads both real and synthetic datasets
- Analyzes gaps in the real dataset
- Fills gaps with synthetic logs
- Targets final distribution: 25% INFO, 25% WARN, 40% ERROR, 10% CRITICAL
- Saves to `golden_dataset_unlabeled.json`

**Expected output:**
- ~150 total logs
- Balanced severity distribution
- Mix of real (~60-70%) and synthetic (~30-40%)

### Step 4: Analyze Dataset Quality

Review the final dataset:

```bash
uv run python scripts/dataset_analysis.py
```

**What this does:**
- Severity distribution vs targets
- Failure category coverage
- Component and namespace distribution
- Labeling completeness check
- Data source breakdown (real vs synthetic)
- Quality assessment with recommendations
- Sample log previews

**Expected output:**
- Comprehensive quality report
- Visual distribution charts
- Recommendations for improvement

### Step 5: Manual Review & Labeling

At this point:

1. **Review the dataset** - Look through `golden_dataset_unlabeled.json`
2. **Fill in missing labels** - Real logs need manual labeling:
   - `root_cause`: e.g., "dns_resolution_failed", "container_crash"
   - `severity`: "info", "warn", "error", "critical"
   - `component`: e.g., "kubelet", "loki_ingester"
   - `summary`: 1-2 sentence description
   - `action_needed`: "investigate", "fix_config", "scale", "monitor", "ignore"
3. **Save labeled version** - Save as `golden_dataset_labeled.json`

## Target Distribution

The scripts aim for this distribution across 150 logs:

| Severity  | Count | Percentage |
|-----------|-------|------------|
| INFO      | 37    | 25%        |
| WARN      | 38    | 25%        |
| ERROR     | 60    | 40%        |
| CRITICAL  | 15    | 10%        |

## Failure Categories Covered

The synthetic templates cover 30+ failure scenarios:

**Pod Lifecycle:**
- CrashLoopBackOff
- ImagePullBackOff
- OOMKilled
- Pod eviction

**Network:**
- DNS failures
- Connection refused/timeout
- Service no endpoints
- NetworkPolicy denials

**Storage:**
- PVC mount failures
- PVC pending
- Disk pressure

**Configuration:**
- ConfigMap/Secret not found
- Invalid YAML
- RBAC permission denied

**Infrastructure:**
- Loki ingester/memberlist errors
- Prometheus scrape failures
- Envoy upstream errors
- Node NotReady

**Probes:**
- Readiness/Liveness/Startup failures

**Certificates:**
- TLS errors
- Certificate expired

## Customization

### Adjust Target Distribution

Edit the target counts in any script:

```python
TARGET_DISTRIBUTION = {
    'INFO': 30,
    'WARN': 30,
    'ERROR': 50,
    'CRITICAL': 20
}
```

### Add Custom Templates

Add new failure scenarios to `log_templates.json`:

```json
{
  "id": "my_custom_error",
  "template": "Custom error message with {variable}",
  "severity": "ERROR",
  "category": "custom_category",
  "root_cause": "custom_failure",
  "component": "my_component",
  "summary": "Description of the error",
  "action_needed": "investigate"
}
```

### Adjust Noise Filters

Modify `NOISE_PATTERNS` in `extract_golden_dataset.py`:

```python
NOISE_PATTERNS = [
    r'pattern_to_filter_out',
    # Add more patterns...
]
```

## Troubleshooting

### No logs extracted from Loki

- Ensure port-forward is running
- Check Loki has logs from the past 72 hours
- Verify LOKI_URL in the script

### Dataset too small

- Increase time window: `hours=168` (7 days)
- Increase query limit: `limit=100`
- Generate more synthetic logs

### Too much duplication

- Adjust deduplication threshold
- Reduce `max_per_signature` in `deduplicate_logs()`

### Unbalanced distribution

- Adjust `TARGET_DISTRIBUTION` values
- Generate more synthetic logs for underrepresented severities

## Next Steps

Once you have a quality golden dataset (`golden_dataset_labeled.json`):

1. Build the LLM evaluator (Phase 3 of agents.md)
2. Test extraction accuracy against ground truth
3. Iterate on prompts based on evaluation metrics
4. Build the RAG pipeline (Phase 4)

## Files Generated

| File | Description | Size |
|------|-------------|------|
| `golden_dataset_real.json` | Real logs from Loki | ~60-100 logs |
| `golden_dataset_synthetic.json` | Generated synthetic logs | ~60 logs |
| `golden_dataset_unlabeled.json` | Merged dataset (needs labeling) | ~150 logs |
| `golden_dataset_labeled.json` | Manually labeled (you create this) | ~150 logs |

## Script Dependencies

All scripts use Python 3.11+ and standard library only:
- `requests` - for Loki API calls
- `json`, `re`, `hashlib`, `datetime`, `collections`, `random` - standard library
