#!/usr/bin/env python3
"""
Combine real and synthetic logs into a final golden dataset.

This script:
1. Loads real logs from golden_dataset_real.json
2. Loads synthetic logs from golden_dataset_synthetic.json
3. Analyzes gaps in the real dataset
4. Fills gaps with synthetic logs
5. Creates a balanced final dataset
6. Saves to golden_dataset_unlabeled.json
"""

import json
import sys
from collections import defaultdict
from typing import List, Dict

# Target distribution for final dataset (150 samples)
TARGET_DISTRIBUTION = {
    'INFO': 37,      # 25%
    'WARN': 38,      # 25%
    'ERROR': 60,     # 40%
    'CRITICAL': 15,  # 10%
}

TOTAL_TARGET = sum(TARGET_DISTRIBUTION.values())  # 150


def load_dataset(filename: str) -> List[Dict]:
    """Load a dataset from JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠ Warning: {filename} not found, using empty dataset")
        return []


def analyze_distribution(logs: List[Dict], dataset_name: str):
    """Print distribution analysis for a dataset."""
    print(f"\n=== {dataset_name} Analysis ===")
    print(f"Total logs: {len(logs)}")

    # Severity distribution
    severity_counts = defaultdict(int)
    for log in logs:
        severity = log.get('detected_severity', log.get('severity', 'UNKNOWN').upper())
        severity_counts[severity] += 1

    print("\nSeverity distribution:")
    for severity in ['INFO', 'WARN', 'ERROR', 'CRITICAL']:
        count = severity_counts[severity]
        pct = (count / len(logs) * 100) if logs else 0
        print(f"  {severity:8s}: {count:3d} ({pct:5.1f}%)")

    # Category distribution (from root_cause)
    category_counts = defaultdict(int)
    for log in logs:
        root_cause = log.get('root_cause', 'unknown')
        if root_cause:  # Only count if labeled
            category_counts[root_cause] += 1

    if category_counts:
        print("\nTop failure categories:")
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = (count / len(logs) * 100) if logs else 0
            print(f"  {category:30s}: {count:3d} ({pct:5.1f}%)")

    return severity_counts


def calculate_gaps(real_counts: Dict[str, int], target_dist: Dict[str, int]) -> Dict[str, int]:
    """Calculate how many synthetic logs needed for each severity."""
    gaps = {}
    for severity, target in target_dist.items():
        real_count = real_counts.get(severity, 0)
        gap = max(0, target - real_count)
        gaps[severity] = gap
    return gaps


def merge_datasets(
    real_logs: List[Dict],
    synthetic_logs: List[Dict],
    target_dist: Dict[str, int]
) -> List[Dict]:
    """Merge real and synthetic datasets to meet target distribution."""
    print("\n" + "=" * 70)
    print("MERGING DATASETS")
    print("=" * 70)

    # Analyze real dataset
    real_severity_counts = defaultdict(int)
    for log in real_logs:
        severity = log.get('detected_severity', 'INFO')
        real_severity_counts[severity] += 1

    # Calculate gaps
    gaps = calculate_gaps(real_severity_counts, target_dist)

    print("\n=== Gap Analysis ===")
    for severity in ['INFO', 'WARN', 'ERROR', 'CRITICAL']:
        real_count = real_severity_counts[severity]
        target = target_dist[severity]
        gap = gaps[severity]
        print(f"  {severity:8s}: {real_count:3d} real, {target:3d} target, {gap:3d} gap")

    # Group synthetic logs by severity
    synthetic_by_severity = defaultdict(list)
    for log in synthetic_logs:
        severity = log.get('detected_severity', log.get('severity', 'INFO').upper())
        synthetic_by_severity[severity].append(log)

    # Start with all real logs
    merged = real_logs.copy()

    # Add synthetic logs to fill gaps
    print("\n=== Filling Gaps with Synthetic Logs ===")
    for severity, gap in gaps.items():
        if gap > 0:
            available = synthetic_by_severity[severity]
            if len(available) >= gap:
                # Take exactly what we need
                selected = available[:gap]
                merged.extend(selected)
                print(f"  {severity:8s}: Added {gap} synthetic logs")
            else:
                # Take all available
                merged.extend(available)
                print(f"  {severity:8s}: Added {len(available)} synthetic logs (wanted {gap}, short by {gap - len(available)})")

    print(f"\n✓ Merged dataset size: {len(merged)} logs")

    return merged


def add_dataset_metadata(logs: List[Dict]) -> List[Dict]:
    """Add metadata to indicate source of each log."""
    for log in logs:
        if 'source' not in log:
            log['source'] = 'real'  # Default to real if not marked
    return logs


def main():
    """Combine real and synthetic datasets."""
    print("=" * 70)
    print("DATASET COMBINATION TOOL")
    print("=" * 70)
    print(f"Target final dataset: {TOTAL_TARGET} logs")
    print(f"Distribution: {TARGET_DISTRIBUTION}\n")

    # Load datasets
    print("Loading datasets...")
    real_logs = load_dataset("golden_dataset_real.json")
    synthetic_logs = load_dataset("golden_dataset_synthetic.json")

    # Analyze each dataset
    real_counts = analyze_distribution(real_logs, "Real Logs")
    synthetic_counts = analyze_distribution(synthetic_logs, "Synthetic Logs")

    # Merge datasets
    merged_logs = merge_datasets(real_logs, synthetic_logs, TARGET_DISTRIBUTION)

    # Add source metadata
    merged_logs = add_dataset_metadata(merged_logs)

    # Final analysis
    analyze_distribution(merged_logs, "Final Merged Dataset")

    # Save merged dataset
    output_file = "golden_dataset_unlabeled.json"
    with open(output_file, 'w') as f:
        json.dump(merged_logs, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"✓ Saved {len(merged_logs)} logs to {output_file}")
    print(f"{'=' * 70}")

    # Print source breakdown
    print("\n=== Source Breakdown ===")
    source_counts = defaultdict(int)
    for log in merged_logs:
        source = log.get('source', 'unknown')
        source_counts[source] += 1

    for source, count in source_counts.items():
        pct = (count / len(merged_logs) * 100) if merged_logs else 0
        print(f"  {source:10s}: {count:3d} ({pct:5.1f}%)")

    # Guidance
    print("\nNext steps:")
    print("  1. Run: python scripts/dataset_analysis.py")
    print("  2. Review the dataset and manually label any missing ground truth fields")
    print("  3. Save labeled version as golden_dataset_labeled.json")

    # Check if target was met
    if len(merged_logs) < TOTAL_TARGET:
        print(f"\n⚠ Warning: Final dataset has {len(merged_logs)} logs, target was {TOTAL_TARGET}")
        print("  Consider generating more synthetic logs or extracting more real logs")


if __name__ == "__main__":
    main()
