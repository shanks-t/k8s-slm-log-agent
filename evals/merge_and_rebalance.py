#!/usr/bin/env python3
"""
Merge logs from multiple sources and rebalance to achieve target distribution.

Sources:
1. Real logs from Loki (golden_dataset_real.json)
2. Logs from previous evals (golden_dataset_from_evals.json)
3. Synthetic logs (golden_dataset_synthetic.json) - to fill gaps

Target distribution (150 total logs):
- log-analyzer: 20% (~30 logs)
- llm: 20% (~30 logs)
- logging: 13% (~20 logs)
- kube-*: 13% (~20 logs)
- flux-system: 13% (~20 logs)
- envoy-gateway-system: 13% (~20 logs)
- other: remaining
"""

import json
import random
from pathlib import Path
from collections import defaultdict
from typing import List, Dict


def normalize_namespace(namespace: str) -> str:
    """Normalize namespace for grouping."""
    if namespace.startswith("kube-"):
        return "kube"
    return namespace


def load_logs(file_path: str) -> List[Dict]:
    """Load logs from JSON file."""
    if not Path(file_path).exists():
        print(f"⚠️  File not found: {file_path}")
        return []

    with open(file_path, 'r') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} logs from {Path(file_path).name}")
    return data


def deduplicate_by_signature(logs: List[Dict]) -> List[Dict]:
    """Remove duplicate logs based on signature hash."""
    seen = set()
    unique = []

    for log in logs:
        # Use signature_hash if available, otherwise create one
        sig = log.get("signature_hash", "")
        if not sig and "log_line" in log:
            import hashlib
            sig = hashlib.md5(log["log_line"].encode()).hexdigest()[:8]
            log["signature_hash"] = sig

        if sig not in seen:
            seen.add(sig)
            unique.append(log)

    return unique


def group_by_namespace(logs: List[Dict]) -> Dict[str, List[Dict]]:
    """Group logs by normalized namespace."""
    grouped = defaultdict(list)
    for log in logs:
        ns = normalize_namespace(log["namespace"])
        grouped[ns].append(log)
    return grouped


def select_stratified_sample(
    grouped_logs: Dict[str, List[Dict]],
    target_total: int = 150,
    priorities: Dict[str, float] = None
) -> List[Dict]:
    """
    Select logs to match target distribution.

    Strategy:
    1. Calculate target count for each namespace group
    2. Randomly sample from available logs (prefer real > eval > synthetic)
    3. If insufficient logs for a namespace, use what's available
    """
    if priorities is None:
        priorities = {
            "log-analyzer": 0.20,
            "llm": 0.20,
            "logging": 0.13,
            "kube": 0.13,
            "flux-system": 0.13,
            "envoy-gateway-system": 0.13,
        }

    selected = []

    print("\n=== Stratified Sampling ===")
    for ns_group, target_pct in sorted(priorities.items(), key=lambda x: x[1], reverse=True):
        target_count = int(target_total * target_pct)
        available = grouped_logs.get(ns_group, [])

        # Prioritize by source: real > previous_eval > synthetic
        def source_priority(log):
            source = log.get("source", "real")
            if source == "real":
                return 0
            elif source == "previous_eval":
                return 1
            else:
                return 2

        available_sorted = sorted(available, key=source_priority)

        # Sample logs (take all if fewer than target)
        if len(available_sorted) <= target_count:
            selected_from_ns = available_sorted
        else:
            # Randomly sample, but keep source priority distribution
            selected_from_ns = available_sorted[:target_count]

        selected.extend(selected_from_ns)

        # Show source breakdown
        sources = defaultdict(int)
        for log in selected_from_ns:
            sources[log.get("source", "real")] += 1

        print(f"{ns_group:25s}: target={target_count:3d}, available={len(available):3d}, selected={len(selected_from_ns):3d}")
        print(f"  Sources: real={sources['real']}, eval={sources['previous_eval']}, synthetic={sources.get('synthetic', 0)}")

    return selected


def print_distribution(logs: List[Dict], title: str):
    """Print namespace and source distribution."""
    print(f"\n{'=' * 70}")
    print(f"{title}")
    print(f"{'=' * 70}")

    # Namespace distribution
    ns_counts = defaultdict(int)
    for log in logs:
        ns = normalize_namespace(log["namespace"])
        ns_counts[ns] += 1

    print("\nNamespace Distribution:")
    for ns, count in sorted(ns_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(logs) * 100) if logs else 0
        print(f"  {ns:25s}: {count:3d} ({pct:5.1f}%)")

    # Source distribution
    source_counts = defaultdict(int)
    for log in logs:
        source = log.get("source", "real")
        source_counts[source] += 1

    print("\nSource Distribution:")
    for source, count in sorted(source_counts.items()):
        pct = (count / len(logs) * 100) if logs else 0
        print(f"  {source:15s}: {count:3d} ({pct:5.1f}%)")

    # Labeling status
    labeled = sum(1 for log in logs if log.get("root_cause"))
    unlabeled = len(logs) - labeled
    print(f"\nLabeling Status:")
    print(f"  Labeled:   {labeled:3d} ({labeled/len(logs)*100:5.1f}%)")
    print(f"  Unlabeled: {unlabeled:3d} ({unlabeled/len(logs)*100:5.1f}%)")


def main():
    """Merge and rebalance logs from all sources."""
    print("=" * 70)
    print("MERGING AND REBALANCING GOLDEN DATASET")
    print("=" * 70)

    # Load logs from all sources
    real_logs = load_logs("golden_dataset_real.json")
    eval_logs = load_logs("golden_dataset_from_evals.json")
    synthetic_logs = load_logs("golden_dataset_synthetic.json")

    # Merge all logs
    all_logs = real_logs + eval_logs + synthetic_logs
    print(f"\nTotal logs before deduplication: {len(all_logs)}")

    # Deduplicate
    unique_logs = deduplicate_by_signature(all_logs)
    print(f"Total logs after deduplication: {len(unique_logs)}")

    print_distribution(unique_logs, "Before Rebalancing")

    # Group by namespace
    grouped = group_by_namespace(unique_logs)

    # Select stratified sample
    final_dataset = select_stratified_sample(grouped, target_total=150)

    print_distribution(final_dataset, "After Rebalancing")

    # Save final dataset
    output_file = "golden_dataset_unlabeled_v2.json"
    with open(output_file, 'w') as f:
        json.dump(final_dataset, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"✓ Saved {len(final_dataset)} logs to {output_file}")
    print(f"{'=' * 70}")

    print("\n📋 Next Steps:")
    print("  1. Review the dataset distribution above")
    print("  2. Manually label unlabeled logs with ground truth")
    print("  3. Run: python dataset_analysis.py to verify quality")
    print("  4. Version the dataset: cp golden_dataset_unlabeled_v2.json golden_v1.json")


if __name__ == "__main__":
    main()
