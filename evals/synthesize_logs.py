#!/usr/bin/env python3
"""
Generate synthetic Kubernetes logs from templates to fill gaps in the golden dataset.

This script:
1. Loads log templates from log_templates.json
2. Generates realistic variations by substituting variables
3. Creates proper Kubernetes log metadata
4. Saves synthetic logs in the same format as real logs
"""

import json
import random
import string
from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

# Load templates
def load_templates(template_file: str = "scripts/log_templates.json") -> Dict:
    """Load log templates from JSON file."""
    with open(template_file, 'r') as f:
        return json.load(f)


def generate_pod_uid() -> str:
    """Generate a realistic pod UID."""
    return ''.join(random.choices(string.hexdigits.lower(), k=8)) + '-' + \
           ''.join(random.choices(string.hexdigits.lower(), k=4)) + '-' + \
           ''.join(random.choices(string.hexdigits.lower(), k=4)) + '-' + \
           ''.join(random.choices(string.hexdigits.lower(), k=4)) + '-' + \
           ''.join(random.choices(string.hexdigits.lower(), k=12))


def generate_timestamp() -> tuple[int, str]:
    """Generate a timestamp within the last 7 days."""
    now = datetime.now()
    random_offset = timedelta(
        days=random.randint(0, 7),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )
    timestamp = now - random_offset
    timestamp_ms = int(timestamp.timestamp() * 1000)
    timestamp_human = timestamp.isoformat()
    return timestamp_ms, timestamp_human


def substitute_variables(template: str, pools: Dict[str, List[str]]) -> str:
    """Substitute template variables with random values from pools."""
    result = template

    # Extract all {variable} placeholders
    import re
    variables = re.findall(r'\{(\w+)\}', template)

    for var in variables:
        if var in pools:
            # Pick a random value from the pool
            value = random.choice(pools[var])
            result = result.replace(f'{{{var}}}', value, 1)
        else:
            # Generate synthetic values for variables not in pools
            if var == 'timestamp':
                value = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            elif var == 'line_num':
                value = str(random.randint(50, 500))
            elif var == 'bytes':
                value = str(random.randint(100, 10000))
            elif var == 'duration':
                value = str(random.randint(10, 5000))
            elif var == 'pod_uid':
                value = generate_pod_uid()
            elif var.endswith('_name') and var not in pools:
                value = f"{var.replace('_name', '')}-{random.randint(1000, 9999)}"
            else:
                value = f"<{var}>"

            result = result.replace(f'{{{var}}}', value, 1)

    return result


def create_log_entry(template: Dict, pools: Dict[str, List[str]]) -> Dict:
    """Create a synthetic log entry from a template."""
    # Generate log line
    log_line = substitute_variables(template['template'], pools)

    # Generate timestamps
    timestamp_ms, timestamp_human = generate_timestamp()

    # Pick a random namespace (prefer namespaces that match the template context)
    if template['category'] in ['infrastructure_error', 'monitoring_error']:
        namespace = random.choice(['logging', 'monitoring', 'kube-system'])
    else:
        namespace = random.choice(pools['namespace'])

    # Generate pod name based on template
    if 'pod_name' in template['template']:
        pod_base = random.choice(pools['pod_name'])
    else:
        pod_base = random.choice(['app', 'service', 'worker'])

    pod_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5)) + '-' + \
                 ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    pod_name = f"{pod_base}-{pod_suffix}"

    # Pick a random container
    container = random.choice(pools['container']) if 'container' in pools else 'app'

    # Pick a node
    node = random.choice(pools['node_name']) if 'node_name' in pools else 'node1'

    # Create log entry in same format as real logs
    return {
        'timestamp': timestamp_ms,
        'timestamp_human': timestamp_human,
        'namespace': namespace,
        'pod': pod_name,
        'container': container,
        'node': node,
        'log_line': log_line,
        'detected_severity': template['severity'],
        'signature': log_line,  # For synthetic logs, signature is the same as log_line
        'signature_hash': '',  # Will be computed if needed
        # Ground truth (pre-filled from template)
        'root_cause': template['root_cause'],
        'severity': template['severity'].lower(),
        'component': template['component'],
        'summary': template['summary'],
        'action_needed': template['action_needed'],
        'source': 'synthetic'  # Mark as synthetic
    }


def generate_synthetic_dataset(
    templates_file: str = "scripts/log_templates.json",
    target_counts: Dict[str, int] = None,
    output_file: str = "golden_dataset_synthetic.json"
) -> List[Dict]:
    """
    Generate synthetic logs to meet target distribution.

    Args:
        templates_file: Path to templates JSON
        target_counts: Dict mapping severity to count (e.g., {'ERROR': 20, 'WARN': 15})
        output_file: Where to save synthetic logs

    Returns:
        List of synthetic log entries
    """
    # Default target if not specified
    if target_counts is None:
        target_counts = {
            'INFO': 15,
            'WARN': 15,
            'ERROR': 25,
            'CRITICAL': 5
        }

    # Load templates
    data = load_templates(templates_file)
    templates = data['templates']
    pools = data['variable_pools']

    # Group templates by severity
    templates_by_severity = defaultdict(list)
    for template in templates:
        templates_by_severity[template['severity']].append(template)

    print("=" * 70)
    print("SYNTHETIC LOG GENERATION")
    print("=" * 70)
    print(f"Templates file: {templates_file}")
    print(f"Target counts: {target_counts}")
    print(f"\nAvailable templates by severity:")
    for severity in ['INFO', 'WARN', 'ERROR', 'CRITICAL']:
        count = len(templates_by_severity[severity])
        print(f"  {severity:8s}: {count:2d} templates")

    synthetic_logs = []

    # Generate logs for each severity level
    for severity, target_count in target_counts.items():
        available_templates = templates_by_severity[severity]

        if not available_templates:
            print(f"\n⚠ Warning: No templates available for {severity}")
            continue

        print(f"\nGenerating {target_count} {severity} logs...")

        for i in range(target_count):
            # Pick a random template
            template = random.choice(available_templates)

            # Generate log entry
            log_entry = create_log_entry(template, pools)
            synthetic_logs.append(log_entry)

        print(f"  → Generated {target_count} logs")

    # Save to file
    with open(output_file, 'w') as f:
        json.dump(synthetic_logs, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"✓ Saved {len(synthetic_logs)} synthetic logs to {output_file}")
    print(f"{'=' * 70}")

    # Print statistics
    print("\n=== Category Distribution ===")
    category_counts = defaultdict(int)
    for log in synthetic_logs:
        # Extract category from root_cause or component
        category_counts[log['root_cause']] += 1

    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        pct = (count / len(synthetic_logs) * 100) if synthetic_logs else 0
        print(f"  {category:30s}: {count:3d} ({pct:5.1f}%)")

    # Sample log
    if synthetic_logs:
        print("\n=== Sample Synthetic Log ===")
        print(json.dumps(synthetic_logs[0], indent=2))

    return synthetic_logs


def main():
    """Generate synthetic logs with default settings."""
    target_counts = {
        'INFO': 15,
        'WARN': 15,
        'ERROR': 25,
        'CRITICAL': 5
    }

    synthetic_logs = generate_synthetic_dataset(
        templates_file="log_templates.json",
        target_counts=target_counts,
        output_file="golden_dataset_synthetic.json"
    )

    print("\nNext steps:")
    print("  1. Review golden_dataset_synthetic.json")
    print("  2. Run: python scripts/combine_datasets.py to merge real + synthetic")
    print("  3. Run: python scripts/dataset_analysis.py to analyze the final dataset")


if __name__ == "__main__":
    main()
