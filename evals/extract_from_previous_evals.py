#!/usr/bin/env python3
"""
Extract logs from previous evaluation runs to supplement the golden dataset.

Target namespace distribution:
- log-analyzer: 20%
- llm: 20%
- logging: ~13%
- kube-* (kube-system, kube-flannel, etc.): ~13%
- flux-system: ~13%
- envoy-gateway-system: ~13%
"""

import json
import os
from pathlib import Path
from datetime import datetime, UTC
from collections import defaultdict
from typing import List, Dict
import hashlib


def load_previous_evals(tmp_dir: str) -> List[Dict]:
    """Load all evaluation JSON files from tmp directory."""
    eval_files = list(Path(tmp_dir).glob("evaluation-*.json"))
    print(f"Found {len(eval_files)} evaluation files")

    all_logs = []
    for eval_file in eval_files:
        with open(eval_file, 'r') as f:
            data = json.load(f)
            raw_logs = data.get("raw_logs", {}).get("logs", [])
            print(f"  {eval_file.name}: {len(raw_logs)} logs")
            all_logs.extend(raw_logs)

    return all_logs


def normalize_namespace(namespace: str) -> str:
    """Normalize namespace for grouping (e.g., kube-system, kube-flannel -> kube)."""
    if namespace.startswith("kube-"):
        return "kube"
    return namespace


def convert_to_dataset_format(log: Dict) -> Dict:
    """Convert evaluation log format to golden dataset format."""
    labels = log["labels"]
    timestamp_ns = int(log["timestamp"])
    timestamp = datetime.fromtimestamp(timestamp_ns / 1e9, UTC)

    # Create a signature hash for deduplication
    message = log["message"].strip()
    signature = hashlib.md5(message.encode()).hexdigest()[:8]

    return {
        "timestamp": int(timestamp.timestamp() * 1000),  # milliseconds
        "timestamp_human": timestamp.isoformat(),
        "namespace": labels.get("namespace", "unknown"),
        "pod": labels.get("pod", "unknown"),
        "container": labels.get("container", "unknown"),
        "node": labels.get("node", "unknown"),
        "log_line": message,
        "detected_severity": labels.get("detected_level", "unknown").upper(),
        "signature": message,
        "signature_hash": signature,
        "source": "previous_eval",
        # Ground truth fields - to be labeled manually
        "root_cause": "",
        "severity": "",
        "component": "",
        "summary": "",
        "action_needed": ""
    }


def deduplicate_logs(logs: List[Dict]) -> List[Dict]:
    """Remove duplicate logs based on signature hash."""
    seen = set()
    unique_logs = []

    for log in logs:
        sig = log["signature_hash"]
        if sig not in seen:
            seen.add(sig)
            unique_logs.append(log)

    return unique_logs


def select_logs_by_priority(
    logs: List[Dict],
    target_total: int = 150,
    priorities: Dict[str, float] = None
) -> List[Dict]:
    """
    Select logs according to namespace priority distribution.

    Args:
        logs: List of all available logs
        target_total: Target total number of logs for dataset
        priorities: Dict mapping namespace group to target percentage
    """
    if priorities is None:
        priorities = {
            "log-analyzer": 0.20,  # 20%
            "llm": 0.20,           # 20%
            "logging": 0.13,       # ~13%
            "kube": 0.13,          # ~13% (kube-system, kube-flannel, etc.)
            "flux-system": 0.13,   # ~13%
            "envoy-gateway-system": 0.13,  # ~13%
        }

    # Group logs by namespace
    logs_by_namespace = defaultdict(list)
    for log in logs:
        ns = log["namespace"]
        normalized_ns = normalize_namespace(ns)
        logs_by_namespace[normalized_ns].append(log)

    print("\n=== Available logs by namespace ===")
    for ns, ns_logs in sorted(logs_by_namespace.items()):
        print(f"  {ns:25s}: {len(ns_logs):4d} logs")

    # Select logs according to priorities
    selected = []
    for ns_group, target_pct in priorities.items():
        target_count = int(target_total * target_pct)
        available = logs_by_namespace.get(ns_group, [])

        # Take up to target_count logs from this namespace
        selected_from_ns = available[:target_count]
        selected.extend(selected_from_ns)

        print(f"\n{ns_group:25s}: target={target_count:3d}, available={len(available):4d}, selected={len(selected_from_ns):3d}")

    return selected


def main():
    """Extract logs from previous evals and create a rebalanced dataset."""
    tmp_dir = "/Users/treyshanks/workspace/k8s-slm-log-agent/tmp"
    output_file = "golden_dataset_from_evals.json"

    print("=" * 70)
    print("EXTRACTING LOGS FROM PREVIOUS EVALUATIONS")
    print("=" * 70)

    # Load all evaluation logs
    raw_logs = load_previous_evals(tmp_dir)
    print(f"\nTotal raw logs loaded: {len(raw_logs)}")

    # Convert to dataset format
    converted = [convert_to_dataset_format(log) for log in raw_logs]
    print(f"Converted to dataset format: {len(converted)}")

    # Deduplicate
    unique = deduplicate_logs(converted)
    print(f"After deduplication: {len(unique)}")

    # Select logs by priority
    selected = select_logs_by_priority(unique, target_total=150)
    print(f"\n\nFinal selected logs: {len(selected)}")

    # Save to file
    with open(output_file, 'w') as f:
        json.dump(selected, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"✓ Saved {len(selected)} logs to {output_file}")
    print(f"{'=' * 70}")

    # Print distribution
    print("\n=== Final Distribution ===")
    ns_counts = defaultdict(int)
    for log in selected:
        ns = normalize_namespace(log["namespace"])
        ns_counts[ns] += 1

    for ns, count in sorted(ns_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(selected) * 100) if selected else 0
        print(f"  {ns:25s}: {count:3d} ({pct:5.1f}%)")

    # Show sample log
    if selected:
        print("\n=== Sample Log ===")
        print(json.dumps(selected[0], indent=2))


if __name__ == "__main__":
    main()
