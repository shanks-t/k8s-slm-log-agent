#!/usr/bin/env python3
"""
Extract logs with namespace priorities and severity filtering.

Strategy:
- Target log-analyzer and llm namespaces (40% of dataset)
- Use severity filters to exclude most INFO logs
- Extend time windows to 7-14 days to capture rare errors
- Balance across ERROR, WARN, CRITICAL
"""

import requests
import json
import hashlib
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional

LOKI_URL = "http://localhost:3100"

# Namespace-specific extraction configs
NAMESPACE_CONFIGS = [
    {
        "namespace": "log-analyzer",
        "target_count": 30,
        "lookback_days": 7,
        "severity_filter": '|~ "(?i)(error|warn|critical|exception|failed)"',
        "priority": 1,
    },
    {
        "namespace": "llm",
        "target_count": 30,
        "lookback_days": 7,
        "severity_filter": '|~ "(?i)(error|warn|critical|failed|timeout)"',
        "priority": 1,
    },
    {
        "namespace": "logging",
        "target_count": 20,
        "lookback_days": 14,
        "severity_filter": '|~ "(?i)(error|warn|critical|failed)" !~ "(?i)info"',
        "priority": 2,
    },
    {
        "namespace": "kube-system",
        "target_count": 20,
        "lookback_days": 14,
        "severity_filter": '|~ "(?i)(error|warn|critical|failed|evicted|oom)"',
        "priority": 2,
    },
    {
        "namespace": "flux-system",
        "target_count": 20,
        "lookback_days": 14,
        "severity_filter": '|~ "(?i)(error|warn|failed|reconciliation.*failed)"',
        "priority": 2,
    },
    {
        "namespace": "envoy-gateway-system",
        "target_count": 20,
        "lookback_days": 14,
        "severity_filter": '|~ "(?i)(error|warn|critical)"',
        "priority": 2,
    },
]

# Noise patterns to filter out
NOISE_PATTERNS = [
    r'health check',
    r'Successfully synced',
    r'reconciliation complete',
    r'"(GET|POST|PUT|DELETE) .* (200|204|304)',
    r'lvl=info.*msg=.*success',
]


def is_noise(log_line: str) -> bool:
    """Check if log line matches noise patterns."""
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, log_line, re.IGNORECASE):
            return True
    return False


def detect_severity(log_line: str) -> str:
    """Detect severity level from log line."""
    log_lower = log_line.lower()

    # Check for explicit severity markers
    if any(marker in log_lower for marker in ['critical', 'fatal', 'panic', 'emergency']):
        return 'CRITICAL'
    if any(marker in log_lower for marker in ['error', 'err', 'failed', 'failure', 'exception']):
        return 'ERROR'
    if any(marker in log_lower for marker in ['warn', 'warning', 'degraded']):
        return 'WARN'

    # Structured logging patterns
    if re.search(r'level[=:]?\s*(critical|fatal)', log_lower):
        return 'CRITICAL'
    if re.search(r'level[=:]?\s*(error|err)', log_lower):
        return 'ERROR'
    if re.search(r'level[=:]?\s*(warn|warning)', log_lower):
        return 'WARN'
    if re.search(r'level[=:]?\s*info', log_lower):
        return 'INFO'

    return 'INFO'  # Default to INFO if unknown


def extract_error_signature(log_line: str) -> str:
    """
    Normalize log line for deduplication.

    Replaces dynamic values (timestamps, IPs, UUIDs, pod names) with placeholders
    so similar errors can be grouped together.
    """
    signature = log_line

    # Remove timestamps
    signature = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?', '<TIMESTAMP>', signature)
    signature = re.sub(r'\d{10,13}', '<TIMESTAMP>', signature)

    # Remove IP addresses
    signature = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<IP>', signature)

    # Remove UUIDs
    signature = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<UUID>', signature)

    # Remove hex IDs
    signature = re.sub(r'\b[0-9a-f]{12,}\b', '<HEXID>', signature)

    # Remove pod names with random suffixes
    signature = re.sub(r'(\w+)-[0-9a-z]{5,10}-[0-9a-z]{5}', r'\1-<POD>', signature)

    # Remove port numbers
    signature = re.sub(r':\d{2,5}\b', ':<PORT>', signature)

    # Remove memory addresses
    signature = re.sub(r'0x[0-9a-f]+', '<ADDR>', signature)

    # Remove numbers that look like counts/sizes
    signature = re.sub(r'\b\d+\s*(bytes?|KB|MB|GB|ms|seconds?)\b', '<SIZE>', signature, flags=re.IGNORECASE)

    return signature


def compute_signature_hash(signature: str) -> str:
    """Compute hash of error signature for grouping."""
    return hashlib.md5(signature.encode()).hexdigest()[:8]


def query_loki(namespace: str, severity_filter: str, limit: int = 100, days: int = 7) -> Optional[Dict]:
    """
    Query Loki for logs from a specific namespace with severity filtering.

    Args:
        namespace: Kubernetes namespace to query
        severity_filter: LogQL line filter for severity (e.g., '|~ "(?i)(error|warn)"')
        limit: Maximum number of logs to return
        days: Lookback period in days
    """
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    # Build LogQL query with severity filter
    query = f'{{namespace="{namespace}"}} {severity_filter}'

    params = {
        'query': query,
        'limit': limit,
        'start': int(start_time.timestamp() * 1e9),
        'end': int(end_time.timestamp() * 1e9),
        'direction': 'backward',
    }

    print(f"\nQuerying: {namespace} (last {days} days)")
    print(f"  Filter: {severity_filter}")
    print(f"  LogQL: {query}")

    try:
        response = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params=params,
            timeout=15
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error: {e}")
        return None


def parse_logs(loki_response: Dict) -> List[Dict]:
    """Parse Loki response into structured log entries."""
    if not loki_response or loki_response.get('status') != 'success':
        return []

    logs = []
    results = loki_response.get('data', {}).get('result', [])

    for stream in results:
        labels = stream.get('stream', {})
        values = stream.get('values', [])

        for timestamp_ns, log_line in values:
            log_line = log_line.strip()

            # Filter noise
            if is_noise(log_line):
                continue

            # Detect severity
            severity = detect_severity(log_line)

            # Extract signature for deduplication
            signature = extract_error_signature(log_line)
            sig_hash = compute_signature_hash(signature)

            logs.append({
                'timestamp': int(timestamp_ns) // 1e6,
                'timestamp_human': datetime.fromtimestamp(int(timestamp_ns) / 1e9).isoformat(),
                'namespace': labels.get('namespace', 'unknown'),
                'pod': labels.get('pod', 'unknown'),
                'container': labels.get('container', 'unknown'),
                'node': labels.get('node', 'unknown'),
                'log_line': log_line,
                'detected_severity': severity,
                'signature': signature,
                'signature_hash': sig_hash,
                'source': 'real',
                # Ground truth - to be labeled
                'root_cause': '',
                'severity': '',
                'component': '',
                'summary': '',
                'action_needed': '',
            })

    return logs


def deduplicate_logs(logs: List[Dict], max_per_signature: int = 2) -> List[Dict]:
    """
    Deduplicate logs by signature hash.

    Keep only max_per_signature examples of each unique error pattern.
    """
    by_signature = defaultdict(list)
    for log in logs:
        by_signature[log['signature_hash']].append(log)

    deduplicated = []
    for sig_hash, sig_logs in by_signature.items():
        # Sort by timestamp (most recent first)
        sig_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        # Keep up to max_per_signature
        deduplicated.extend(sig_logs[:max_per_signature])

    return deduplicated


def extract_by_namespace():
    """Extract logs for each namespace with severity filtering."""
    print("=" * 70)
    print("EXTRACTING LOGS BY NAMESPACE WITH SEVERITY FILTERS")
    print("=" * 70)

    all_logs = []

    for config in NAMESPACE_CONFIGS:
        ns = config['namespace']
        target = config['target_count']
        days = config['lookback_days']
        severity_filter = config['severity_filter']

        # Query Loki
        response = query_loki(
            namespace=ns,
            severity_filter=severity_filter,
            limit=target * 3,  # Over-fetch for deduplication
            days=days
        )

        if not response:
            print(f"  ⚠️  No response from Loki")
            continue

        # Parse logs
        logs = parse_logs(response)
        print(f"  📊 Parsed: {len(logs)} logs")

        if not logs:
            print(f"  ⚠️  No logs found")
            continue

        # Deduplicate
        deduped = deduplicate_logs(logs, max_per_signature=2)
        print(f"  🔍 After dedup: {len(deduped)} logs ({len(set(l['signature_hash'] for l in deduped))} unique signatures)")

        # Sample to target count
        sampled = deduped[:target] if len(deduped) > target else deduped
        print(f"  ✓ Selected: {len(sampled)} logs")

        all_logs.extend(sampled)

        # Show severity breakdown
        severity_counts = defaultdict(int)
        for log in sampled:
            severity_counts[log['detected_severity']] += 1
        print(f"  Severity: {dict(severity_counts)}")

    # Save to file
    output_file = "golden_dataset_severity_filtered.json"
    with open(output_file, 'w') as f:
        json.dump(all_logs, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"✓ Saved {len(all_logs)} logs to {output_file}")
    print(f"{'=' * 70}")

    # Print final distribution
    print("\n=== Final Distribution ===")

    # By namespace
    ns_counts = defaultdict(int)
    for log in all_logs:
        ns_counts[log['namespace']] += 1

    print("\nNamespace:")
    for ns, count in sorted(ns_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(all_logs) * 100) if all_logs else 0
        print(f"  {ns:25s}: {count:3d} ({pct:5.1f}%)")

    # By severity
    sev_counts = defaultdict(int)
    for log in all_logs:
        sev_counts[log['detected_severity']] += 1

    print("\nSeverity:")
    for sev in ['CRITICAL', 'ERROR', 'WARN', 'INFO']:
        count = sev_counts.get(sev, 0)
        pct = (count / len(all_logs) * 100) if all_logs else 0
        print(f"  {sev:10s}: {count:3d} ({pct:5.1f}%)")


if __name__ == "__main__":
    extract_by_namespace()
