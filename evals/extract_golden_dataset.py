#!/usr/bin/env python3
"""
Extract diverse log samples from Loki to create a golden dataset for LLM evaluation.

This script queries Loki for logs across different namespaces, pods, and severity levels,
then saves them in a structured format for manual labeling.

Enhanced with:
- Noise filtering (CoreDNS warnings, routine Envoy logs, etc.)
- Severity detection and classification
- Intelligent deduplication by error signature
- Stratified sampling to meet target distribution
- High-value query targeting
"""

import requests
import json
import time
import re
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional
import sys

# Loki API endpoint (assuming port-forward is active)
LOKI_URL = "http://localhost:3100"

# Noise patterns to filter out (low-value logs)
NOISE_PATTERNS = [
    r'CoreDNS.*plugin/errors.*Corefile:.*file does not exist',  # Optional include warnings
    r'CoreDNS.*Corefile:.*No such file or directory',
    r'"GET /.*" (200|204|304) -',  # Successful HTTP requests
    r'Successfully synced',
    r'lvl=info.*msg=.*successfully',
    r'health check passed',
    r'reconciliation complete',
]

# Target distribution for stratified sampling
TARGET_DISTRIBUTION = {
    'INFO': 25,      # 25 samples (25%)
    'WARN': 25,      # 25 samples (25%)
    'ERROR': 40,     # 40 samples (40%)
    'CRITICAL': 10,  # 10 samples (10%)
}

# High-value queries targeting specific failure modes
LOG_QUERIES = [
    # Pod lifecycle issues
    '{job=~".+"} |~ "(?i)(backoff|crashloop|oomkilled|evicted)"',

    # Image problems
    '{job=~".+"} |~ "(?i)(imagepull|errimage|manifest unknown|failed to pull)"',

    # Loki-specific errors (valuable infrastructure logs)
    '{namespace="logging", pod=~"loki-.*"} |~ "(?i)(error|failed|panic|fatal)"',

    # DNS failures
    '{job=~".+"} |~ "(?i)(no such host|dns.*timeout|resolve.*failed|lookup.*failed)"',

    # Kubelet and containerd errors
    '{job=~".+"} |~ "(?i)(kubelet|containerd).*error"',

    # Probe failures
    '{job=~".+"} |~ "(?i)(readiness|liveness|startup).*failed"',

    # Network connectivity issues
    '{job=~".+"} |~ "(?i)(connection refused|dial tcp.*timeout|network unreachable)"',

    # Permission and RBAC errors
    '{job=~".+"} |~ "(?i)(forbidden|unauthorized|permission denied|rbac)"',

    # Resource exhaustion
    '{job=~".+"} |~ "(?i)(out of memory|disk full|quota exceeded|throttl)"',

    # Configuration errors
    '{job=~".+"} |~ "(?i)(configmap.*not found|secret.*not found|invalid.*configuration)"',

    # Storage and volume errors
    '{job=~".+"} |~ "(?i)(pvc|volume|mount).*(?:failed|error)"',

    # Service and endpoint issues
    '{job=~".+"} |~ "(?i)(service.*no endpoints|endpoint.*not found)"',

    # Certificate and TLS errors
    '{job=~".+"} |~ "(?i)(certificate|tls|x509).*(?:error|failed|invalid)"',

    # General errors (fallback)
    '{job=~".+"} |~ "(?i)(error|exception|fatal)" | line_format "{{.log}}" != "(?i)(successfully|health check|synced)"',

    # Warnings (for balance)
    '{job=~".+"} |~ "(?i)warning" | line_format "{{.log}}" != "(?i)(optional|skipping)"',
]

def detect_severity(log_line: str) -> str:
    """
    Detect severity level from log line.

    Returns: INFO, WARN, ERROR, or CRITICAL
    """
    line_lower = log_line.lower()

    # Critical indicators (highest priority)
    if any(word in line_lower for word in ['fatal', 'panic', 'oomkilled', 'crashloop']):
        return 'CRITICAL'

    # Error indicators
    if any(word in line_lower for word in ['error', 'exception', 'failed', 'failure', 'err=']):
        # Check if it's just mentioning errors in a success message
        if any(word in line_lower for word in ['0 errors', 'no errors', 'without error']):
            return 'INFO'
        return 'ERROR'

    # Warning indicators
    if any(word in line_lower for word in ['warning', 'warn', 'deprecated']):
        return 'WARN'

    # Default to INFO
    return 'INFO'


def is_noise(log_line: str) -> bool:
    """Check if log line matches noise patterns and should be filtered out."""
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, log_line, re.IGNORECASE):
            return True
    return False


def extract_error_signature(log_line: str) -> str:
    """
    Extract error signature for intelligent deduplication.

    Normalizes the log by removing dynamic values (timestamps, IPs, UUIDs, etc.)
    to group similar errors together.
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


def query_loki(query: str, limit: int = 50, hours: int = 24) -> Optional[Dict]:
    """Query Loki API for log entries."""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    params = {
        'query': query,
        'limit': limit,
        'start': int(start_time.timestamp() * 1e9),  # Nanoseconds
        'end': int(end_time.timestamp() * 1e9),
        'direction': 'backward',  # Most recent first
    }

    try:
        response = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying Loki: {e}", file=sys.stderr)
        return None

def parse_log_entries(loki_response: Dict) -> List[Dict]:
    """Parse Loki response into structured log entries with noise filtering."""
    if not loki_response or loki_response.get('status') != 'success':
        return []

    logs = []
    results = loki_response.get('data', {}).get('result', [])

    for stream in results:
        labels = stream.get('stream', {})
        values = stream.get('values', [])

        for timestamp_ns, log_line in values:
            log_line = log_line.strip()

            # Filter out noise
            if is_noise(log_line):
                continue

            # Detect severity
            severity = detect_severity(log_line)

            # Extract error signature for deduplication
            signature = extract_error_signature(log_line)
            sig_hash = compute_signature_hash(signature)

            logs.append({
                'timestamp': int(timestamp_ns) // 1e6,  # Convert to milliseconds
                'timestamp_human': datetime.fromtimestamp(int(timestamp_ns) / 1e9).isoformat(),
                'namespace': labels.get('namespace', 'unknown'),
                'pod': labels.get('pod', 'unknown'),
                'container': labels.get('container', 'unknown'),
                'node': labels.get('node', 'unknown'),
                'log_line': log_line,
                'detected_severity': severity,
                'signature': signature,
                'signature_hash': sig_hash,
                # Ground truth fields (to be manually filled)
                'root_cause': '',
                'severity': '',  # Manual override
                'component': '',
                'summary': '',
                'action_needed': '',
            })

    return logs

def deduplicate_logs(logs: List[Dict]) -> List[Dict]:
    """
    Intelligent deduplication by error signature.

    Strategy:
    - Group by signature hash
    - Keep only 1-2 examples per unique error signature
    - Prefer more recent logs
    - Preserve diversity across different error types
    """
    # Group by signature hash
    by_signature = defaultdict(list)
    for log in logs:
        by_signature[log['signature_hash']].append(log)

    print(f"\n=== Deduplication ===")
    print(f"Total logs before deduplication: {len(logs)}")
    print(f"Unique error signatures: {len(by_signature)}")

    deduplicated = []

    for sig_hash, sig_logs in by_signature.items():
        # Sort by timestamp (most recent first)
        sig_logs.sort(key=lambda x: x['timestamp'], reverse=True)

        # Keep at most 2 examples per signature
        # This preserves some context while removing excessive duplication
        max_per_signature = 2 if len(sig_logs) > 3 else len(sig_logs)
        deduplicated.extend(sig_logs[:max_per_signature])

    print(f"Logs after deduplication: {len(deduplicated)}")
    return deduplicated


def stratified_sample(logs: List[Dict], target_distribution: Dict[str, int]) -> List[Dict]:
    """
    Perform stratified sampling to meet target severity distribution.

    Args:
        logs: List of log entries with detected_severity
        target_distribution: Dict mapping severity to target count

    Returns:
        Sampled logs meeting the target distribution (or as close as possible)
    """
    # Group by detected severity
    by_severity = defaultdict(list)
    for log in logs:
        by_severity[log['detected_severity']].append(log)

    print("\n=== Severity Distribution (Before Sampling) ===")
    for severity in ['INFO', 'WARN', 'ERROR', 'CRITICAL']:
        count = len(by_severity[severity])
        target = target_distribution.get(severity, 0)
        print(f"  {severity:8s}: {count:4d} available, {target:3d} target")

    sampled = []

    # Sample from each severity level
    for severity, target_count in target_distribution.items():
        available = by_severity[severity]

        if len(available) <= target_count:
            # Take all available
            sampled.extend(available)
            if len(available) > 0:
                print(f"  → Taking all {len(available)} {severity} logs (less than target)")
        else:
            # Sample to meet target
            # Sort by timestamp to ensure variety across time
            available.sort(key=lambda x: x['timestamp'])

            # Take evenly distributed samples across time
            step = len(available) / target_count
            indices = [int(i * step) for i in range(target_count)]
            samples = [available[i] for i in indices]

            sampled.extend(samples)
            print(f"  → Sampled {len(samples)} {severity} logs from {len(available)} available")

    print(f"\nTotal sampled: {len(sampled)} logs")
    return sampled

def main():
    """Extract logs from Loki and create golden dataset."""
    print("=" * 70)
    print("GOLDEN DATASET EXTRACTION - Enhanced with Stratified Sampling")
    print("=" * 70)
    print(f"Loki URL: {LOKI_URL}")
    print(f"Target: 100 diverse log samples")
    print(f"Distribution: {TARGET_DISTRIBUTION}\n")

    all_logs = []

    # Query Loki with targeted queries
    for i, query in enumerate(LOG_QUERIES, 1):
        print(f"[{i}/{len(LOG_QUERIES)}] Querying: {query[:70]}...")
        result = query_loki(query, limit=50, hours=72)  # Extend to 72 hours for more diversity

        if result:
            logs = parse_log_entries(result)
            all_logs.extend(logs)
            print(f"  → Found {len(logs)} logs (after noise filtering)")
        else:
            print(f"  → Query failed or no results")

        time.sleep(0.5)  # Rate limiting

    print(f"\nTotal logs retrieved: {len(all_logs)}")

    if len(all_logs) == 0:
        print("\n❌ No logs found. Make sure:")
        print("  1. kubectl port-forward is running: kubectl port-forward -n logging svc/loki 3100:3100")
        print("  2. Loki has ingested logs in the past 72 hours")
        print("  3. The LOKI_URL is correct")
        sys.exit(1)

    # Deduplicate by error signature
    deduplicated_logs = deduplicate_logs(all_logs)

    # Stratified sampling to meet target distribution
    sampled_logs = stratified_sample(deduplicated_logs, TARGET_DISTRIBUTION)

    # Save to JSON
    output_file = "golden_dataset_real.json"
    with open(output_file, 'w') as f:
        json.dump(sampled_logs, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"✓ Saved {len(sampled_logs)} real logs to {output_file}")
    print(f"{'=' * 70}")

    # Print statistics
    print("\n=== Final Distribution ===")
    severity_counts = defaultdict(int)
    for log in sampled_logs:
        severity_counts[log['detected_severity']] += 1

    for severity in ['INFO', 'WARN', 'ERROR', 'CRITICAL']:
        count = severity_counts[severity]
        pct = (count / len(sampled_logs) * 100) if sampled_logs else 0
        print(f"  {severity:8s}: {count:3d} ({pct:5.1f}%)")

    print("\n=== Namespace Distribution ===")
    namespace_counts = defaultdict(int)
    for log in sampled_logs:
        namespace_counts[log['namespace']] += 1

    for namespace, count in sorted(namespace_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(sampled_logs) * 100) if sampled_logs else 0
        print(f"  {namespace:30s}: {count:3d} ({pct:5.1f}%)")

    print("\nNext steps:")
    print("  1. Run: python scripts/synthesize_logs.py to generate synthetic logs")
    print("  2. Run: python scripts/combine_datasets.py to merge real + synthetic")
    print("  3. Run: python scripts/dataset_analysis.py to review the final dataset")

    # Print sample
    if sampled_logs:
        print("\n=== Sample Log Entry ===")
        print(json.dumps(sampled_logs[0], indent=2))

if __name__ == "__main__":
    main()
