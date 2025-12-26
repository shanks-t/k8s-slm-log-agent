#!/usr/bin/env python3
"""
Analyze the golden dataset quality and distribution.

This script provides detailed analysis of the dataset including:
- Severity distribution
- Category/failure mode coverage
- Namespace and component distribution
- Labeling completeness
- Sample quality checks
"""

import json
import sys
from collections import defaultdict
from typing import List, Dict

def load_dataset(filename: str) -> List[Dict]:
    """Load dataset from JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {filename} not found")
        sys.exit(1)


def analyze_severity_distribution(logs: List[Dict]):
    """Analyze and visualize severity distribution."""
    print("\n" + "=" * 70)
    print("SEVERITY DISTRIBUTION")
    print("=" * 70)

    severity_counts = defaultdict(int)
    for log in logs:
        severity = log.get('detected_severity', log.get('severity', 'UNKNOWN').upper())
        severity_counts[severity] += 1

    target_dist = {
        'INFO': 25,
        'WARN': 25,
        'ERROR': 40,
        'CRITICAL': 10
    }

    print(f"\n{'Severity':<12} {'Count':<8} {'Actual %':<10} {'Target %':<10} {'Visual'}")
    print("-" * 70)

    for severity in ['INFO', 'WARN', 'ERROR', 'CRITICAL']:
        count = severity_counts[severity]
        actual_pct = (count / len(logs) * 100) if logs else 0
        target_pct = target_dist[severity]

        # Visual bar
        bar_length = int(actual_pct / 2)  # Scale to 50 chars max
        bar = '█' * bar_length

        diff = actual_pct - target_pct
        status = "✓" if abs(diff) < 5 else "⚠"

        print(f"{severity:<12} {count:<8} {actual_pct:>6.1f}%    {target_pct:>6.1f}%    {bar} {status}")

    return severity_counts


def analyze_failure_categories(logs: List[Dict]):
    """Analyze failure mode coverage."""
    print("\n" + "=" * 70)
    print("FAILURE CATEGORY COVERAGE")
    print("=" * 70)

    category_counts = defaultdict(int)
    for log in logs:
        root_cause = log.get('root_cause', '')
        if root_cause:
            category_counts[root_cause] += 1

    if not category_counts:
        print("\n⚠ Warning: No logs have root_cause labeled")
        return

    print(f"\nTotal unique failure categories: {len(category_counts)}\n")
    print(f"{'Root Cause':<35} {'Count':<8} {'%':<8} {'Visual'}")
    print("-" * 70)

    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(logs) * 100) if logs else 0
        bar_length = int(pct)
        bar = '▪' * min(bar_length, 30)
        print(f"{category:<35} {count:<8} {pct:>5.1f}%   {bar}")


def analyze_component_distribution(logs: List[Dict]):
    """Analyze component distribution."""
    print("\n" + "=" * 70)
    print("COMPONENT DISTRIBUTION")
    print("=" * 70)

    component_counts = defaultdict(int)
    for log in logs:
        component = log.get('component', '')
        if component:
            component_counts[component] += 1

    if not component_counts:
        print("\n⚠ Warning: No logs have component labeled")
        return

    print(f"\nTotal unique components: {len(component_counts)}\n")
    print(f"{'Component':<30} {'Count':<8} {'%'}")
    print("-" * 50)

    for component, count in sorted(component_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
        pct = (count / len(logs) * 100) if logs else 0
        print(f"{component:<30} {count:<8} {pct:>5.1f}%")


def analyze_namespace_distribution(logs: List[Dict]):
    """Analyze namespace distribution."""
    print("\n" + "=" * 70)
    print("NAMESPACE DISTRIBUTION")
    print("=" * 70)

    namespace_counts = defaultdict(int)
    for log in logs:
        namespace = log.get('namespace', 'unknown')
        namespace_counts[namespace] += 1

    print(f"\n{'Namespace':<30} {'Count':<8} {'%'}")
    print("-" * 50)

    for namespace, count in sorted(namespace_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(logs) * 100) if logs else 0
        print(f"{namespace:<30} {count:<8} {pct:>5.1f}%")


def analyze_labeling_completeness(logs: List[Dict]):
    """Check labeling completeness."""
    print("\n" + "=" * 70)
    print("LABELING COMPLETENESS")
    print("=" * 70)

    fields = ['root_cause', 'severity', 'component', 'summary', 'action_needed']
    field_completeness = defaultdict(int)

    for log in logs:
        for field in fields:
            if log.get(field) and log.get(field) != '':
                field_completeness[field] += 1

    print(f"\n{'Field':<20} {'Labeled':<10} {'Unlabeled':<10} {'%':<10} {'Status'}")
    print("-" * 70)

    for field in fields:
        labeled = field_completeness[field]
        unlabeled = len(logs) - labeled
        pct = (labeled / len(logs) * 100) if logs else 0

        if pct == 100:
            status = "✓ Complete"
        elif pct >= 80:
            status = "⚠ Mostly complete"
        else:
            status = "❌ Needs work"

        print(f"{field:<20} {labeled:<10} {unlabeled:<10} {pct:>5.1f}%    {status}")


def analyze_source_distribution(logs: List[Dict]):
    """Analyze real vs synthetic distribution."""
    print("\n" + "=" * 70)
    print("DATA SOURCE DISTRIBUTION")
    print("=" * 70)

    source_counts = defaultdict(int)
    for log in logs:
        source = log.get('source', 'real')  # Default to real if not marked
        source_counts[source] += 1

    print(f"\n{'Source':<15} {'Count':<10} {'%'}")
    print("-" * 40)

    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(logs) * 100) if logs else 0
        print(f"{source:<15} {count:<10} {pct:>5.1f}%")


def analyze_action_needed(logs: List[Dict]):
    """Analyze action_needed distribution."""
    print("\n" + "=" * 70)
    print("ACTION NEEDED DISTRIBUTION")
    print("=" * 70)

    action_counts = defaultdict(int)
    for log in logs:
        action = log.get('action_needed', '')
        if action:
            action_counts[action] += 1

    if not action_counts:
        print("\n⚠ Warning: No logs have action_needed labeled")
        return

    print(f"\n{'Action':<20} {'Count':<10} {'%'}")
    print("-" * 45)

    for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(logs) * 100) if logs else 0
        print(f"{action:<20} {count:<10} {pct:>5.1f}%")


def show_sample_logs(logs: List[Dict], num_samples: int = 3):
    """Show sample logs from dataset."""
    print("\n" + "=" * 70)
    print(f"SAMPLE LOGS (showing {num_samples} random examples)")
    print("=" * 70)

    import random
    samples = random.sample(logs, min(num_samples, len(logs)))

    for i, log in enumerate(samples, 1):
        print(f"\n--- Sample {i} ---")
        print(f"Source:    {log.get('source', 'real')}")
        print(f"Severity:  {log.get('detected_severity', 'N/A')}")
        print(f"Namespace: {log.get('namespace', 'N/A')}")
        print(f"Pod:       {log.get('pod', 'N/A')}")
        print(f"Log:       {log.get('log_line', 'N/A')[:100]}...")
        print(f"Root cause: {log.get('root_cause', 'NOT LABELED')}")
        print(f"Component:  {log.get('component', 'NOT LABELED')}")
        print(f"Action:     {log.get('action_needed', 'NOT LABELED')}")


def generate_summary_report(logs: List[Dict]):
    """Generate overall summary and recommendations."""
    print("\n" + "=" * 70)
    print("DATASET QUALITY SUMMARY")
    print("=" * 70)

    # Calculate metrics
    total_logs = len(logs)

    # Labeling completeness
    fully_labeled = sum(1 for log in logs if all([
        log.get('root_cause'),
        log.get('severity'),
        log.get('component'),
        log.get('summary'),
        log.get('action_needed')
    ]))

    labeling_pct = (fully_labeled / total_logs * 100) if total_logs else 0

    # Category diversity
    unique_categories = len(set(log.get('root_cause', '') for log in logs if log.get('root_cause')))

    # Source breakdown
    real_count = sum(1 for log in logs if log.get('source', 'real') == 'real')
    synthetic_count = sum(1 for log in logs if log.get('source', 'real') == 'synthetic')

    print(f"\nTotal logs: {total_logs}")
    print(f"Fully labeled: {fully_labeled} ({labeling_pct:.1f}%)")
    print(f"Unique failure categories: {unique_categories}")
    print(f"Real logs: {real_count}")
    print(f"Synthetic logs: {synthetic_count}")

    # Quality assessment
    print("\n=== Quality Assessment ===")

    issues = []
    recommendations = []

    if total_logs < 100:
        issues.append(f"Dataset size ({total_logs}) is below recommended minimum (150)")
        recommendations.append("Generate more synthetic logs or extract more real logs")

    if labeling_pct < 80:
        issues.append(f"Only {labeling_pct:.1f}% of logs are fully labeled")
        recommendations.append("Complete labeling for all ground truth fields")

    if unique_categories < 15:
        issues.append(f"Only {unique_categories} failure categories (recommended: 20+)")
        recommendations.append("Add more diverse failure scenarios")

    if synthetic_count > real_count:
        issues.append(f"More synthetic ({synthetic_count}) than real ({real_count}) logs")
        recommendations.append("Extract more real logs from your cluster")

    if not issues:
        print("✓ Dataset quality looks good!")
    else:
        print("\n⚠ Issues found:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")

        print("\n💡 Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")


def main():
    """Run dataset analysis."""
    import sys

    filename = "golden_dataset_unlabeled.json"
    if len(sys.argv) > 1:
        filename = sys.argv[1]

    print("=" * 70)
    print("GOLDEN DATASET ANALYSIS TOOL")
    print("=" * 70)
    print(f"Analyzing: {filename}\n")

    # Load dataset
    logs = load_dataset(filename)
    print(f"✓ Loaded {len(logs)} logs")

    # Run analyses
    analyze_severity_distribution(logs)
    analyze_failure_categories(logs)
    analyze_component_distribution(logs)
    analyze_namespace_distribution(logs)
    analyze_action_needed(logs)
    analyze_source_distribution(logs)
    analyze_labeling_completeness(logs)
    show_sample_logs(logs, num_samples=3)
    generate_summary_report(logs)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
