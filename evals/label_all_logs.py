#!/usr/bin/env python3
"""
Label all logs in golden_dataset_severity_filtered.json using patterns from sample_labeled.json.

This script:
1. Loads labeled samples as reference
2. Reuses labels for logs with matching signature_hash
3. Labels remaining logs based on patterns
4. Saves complete labeled dataset as golden_dataset.json
"""

import json
import re


def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)


def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def label_log(log):
    """Label a single log based on patterns."""
    log_line = log['log_line']
    namespace = log['namespace']
    detected_sev = log['detected_severity']

    # Default labels
    labels = {
        'root_cause': '',
        'severity': detected_sev.lower(),
        'component': '',
        'summary': '',
        'action_needed': ''
    }

    # log-analyzer patterns
    if namespace == 'log-analyzer':
        if 'opentelemetry.exporter.otlp' in log_line and 'UNAVAILABLE' in log_line:
            labels.update({
                'root_cause': 'tempo_unavailable',
                'severity': 'warn',
                'component': 'opentelemetry_exporter',
                'summary': 'OpenTelemetry exporter cannot reach Tempo service, retrying with backoff',
                'action_needed': 'monitor'
            })
        elif 'No logs found in Loki' in log_line:
            labels.update({
                'root_cause': 'empty_query_result',
                'severity': 'warn',
                'component': 'log_analyzer_api',
                'summary': 'User query returned no logs from Loki',
                'action_needed': 'none'
            })
        elif 'File "' in log_line and '.py' in log_line:
            labels.update({
                'root_cause': 'exception_stacktrace',
                'severity': 'error',
                'component': 'log_analyzer_api',
                'summary': 'Python exception stacktrace fragment from FastAPI handler',
                'action_needed': 'investigate'
            })
        elif 'HTTPStatusError' in log_line or 'httpx' in log_line:
            labels.update({
                'root_cause': 'http_client_error',
                'severity': 'error',
                'component': 'log_analyzer_api',
                'summary': 'HTTP client error when calling downstream service',
                'action_needed': 'investigate'
            })

    # llm patterns
    elif namespace == 'llm':
        if 'exceeds the available context size' in log_line:
            labels.update({
                'root_cause': 'context_size_exceeded',
                'severity': 'error',
                'component': 'llama_cpp',
                'summary': 'LLM request exceeded configured context window size',
                'action_needed': 'increase_context_size'
            })
        elif 'compiled without GPU support' in log_line:
            labels.update({
                'root_cause': 'no_gpu_acceleration',
                'severity': 'info',
                'component': 'llama_cpp',
                'summary': 'llama.cpp running without GPU acceleration (expected for CPU-only deployment)',
                'action_needed': 'none'
            })
        elif 'consult docs/build.md' in log_line:
            labels.update({
                'root_cause': 'build_info_message',
                'severity': 'info',
                'component': 'llama_cpp',
                'summary': 'Informational message about llama.cpp build documentation',
                'action_needed': 'none'
            })
        elif 'LLAMA_ARG_HOST' in log_line and 'overwritten by command line' in log_line:
            labels.update({
                'root_cause': 'config_override_warning',
                'severity': 'warn',
                'component': 'llama_cpp',
                'summary': 'Environment variable overridden by command-line argument (benign config precedence)',
                'action_needed': 'none'
            })
        elif 'all slots are idle' in log_line:
            labels.update({
                'root_cause': 'slots_idle',
                'severity': 'info',
                'component': 'llama_cpp',
                'summary': 'All LLM processing slots are idle (normal operational state)',
                'action_needed': 'none'
            })

    # logging (Loki) patterns
    elif namespace == 'logging':
        if 'failed mapping AST' in log_line and 'context canceled' in log_line:
            labels.update({
                'root_cause': 'query_canceled',
                'severity': 'warn',
                'component': 'loki',
                'summary': 'Loki query canceled by client before completion',
                'action_needed': 'none'
            })
        elif 'error notifying scheduler about finished query' in log_line and 'EOF' in log_line:
            labels.update({
                'root_cause': 'scheduler_communication_error',
                'severity': 'error',
                'component': 'loki',
                'summary': 'Loki querier lost connection to scheduler while reporting query completion',
                'action_needed': 'monitor'
            })
        elif 'error processing requests from scheduler' in log_line and 'context canceled' in log_line:
            labels.update({
                'root_cause': 'scheduler_context_canceled',
                'severity': 'error',
                'component': 'loki',
                'summary': 'Loki querier stopped processing requests due to context cancellation',
                'action_needed': 'monitor'
            })

    # kube-system patterns
    elif namespace == 'kube-system':
        if 'failed to discover some groups' in log_line and 'metrics.k8s.io' in log_line:
            labels.update({
                'root_cause': 'metrics_server_missing',
                'severity': 'warn',
                'component': 'kube_controller_manager',
                'summary': 'Garbage collector cannot discover metrics API (metrics-server not installed)',
                'action_needed': 'none'
            })

    # flux-system patterns
    elif namespace == 'flux-system':
        if 'invalid chart reference' in log_line and 'no chart name found' in log_line:
            if 'reconciliation stalled' in log_line:
                labels.update({
                    'root_cause': 'helm_chart_reconciliation_stalled',
                    'severity': 'error',
                    'component': 'flux_source_controller',
                    'summary': 'Flux source controller cannot reconcile HelmChart due to missing chart name',
                    'action_needed': 'fix_helm_chart_spec'
                })
            else:
                labels.update({
                    'root_cause': 'helm_chart_invalid_reference',
                    'severity': 'error',
                    'component': 'flux_helm_controller',
                    'summary': 'Flux cannot find chart name in HelmChart resource configuration',
                    'action_needed': 'fix_helm_chart_spec'
                })
        elif 'release is in a failed state' in log_line:
            labels.update({
                'root_cause': 'helm_release_failed',
                'severity': 'error',
                'component': 'flux_helm_controller',
                'summary': f"Helm release is in failed state",
                'action_needed': 'check_helm_release'
            })
        elif 'failed to fetch' in log_line and '404 Not Found' in log_line:
            labels.update({
                'root_cause': 'helm_repo_url_invalid',
                'severity': 'error',
                'component': 'flux_source_controller',
                'summary': 'Helm repository index URL returns 404 (likely wrong URL or moved)',
                'action_needed': 'update_helm_repo_url'
            })
        elif 'exceeded maximum retries' in log_line and 'cannot remediate' in log_line:
            labels.update({
                'root_cause': 'helm_release_max_retries',
                'severity': 'critical',
                'component': 'flux_helm_controller',
                'summary': 'Flux exhausted retry attempts and cannot remediate failed release',
                'action_needed': 'manual_helm_intervention'
            })

    # envoy-gateway-system patterns
    elif namespace == 'envoy-gateway-system':
        if 'prefer a domain-qualified finalizer name' in log_line:
            labels.update({
                'root_cause': 'k8s_api_deprecation_warning',
                'severity': 'info',
                'component': 'envoy_gateway',
                'summary': 'Kubernetes API warning about finalizer naming convention (non-critical)',
                'action_needed': 'none'
            })
        elif 'Failed to update lock' in log_line and 'connection refused' in log_line:
            labels.update({
                'root_cause': 'leader_election_apiserver_unavailable',
                'severity': 'error',
                'component': 'envoy_gateway',
                'summary': 'Envoy Gateway cannot reach API server for leader election, using fallback',
                'action_needed': 'check_apiserver_connectivity'
            })
        elif 'Failed to watch' in log_line and 'apiserver not ready' in log_line:
            labels.update({
                'root_cause': 'apiserver_not_ready',
                'severity': 'error',
                'component': 'envoy_gateway',
                'summary': f"Envoy Gateway cannot watch resources because API server is not ready",
                'action_needed': 'wait_for_apiserver'
            })

    # If still unlabeled, provide generic labels
    if not labels['root_cause']:
        labels['root_cause'] = 'unknown'
        labels['component'] = namespace.replace('-', '_')
        labels['summary'] = f"Log from {namespace} requiring manual review"
        labels['action_needed'] = 'investigate'

    return labels


def main():
    print("=" * 70)
    print("LABELING ALL LOGS FOR GOLDEN DATASET")
    print("=" * 70)

    # Load data
    print("\nLoading datasets...")
    full_dataset = load_json('golden_dataset_severity_filtered.json')
    labeled_samples = load_json('sample_labeled.json')

    print(f"  Full dataset: {len(full_dataset)} logs")
    print(f"  Labeled samples: {len(labeled_samples)} logs")

    # Create mapping by signature_hash
    labeled_by_hash = {log['signature_hash']: log for log in labeled_samples}

    # Label all logs
    print("\nLabeling logs...")
    labeled_count = 0
    new_labels_count = 0

    for i, log in enumerate(full_dataset):
        # Check if already labeled in samples
        if log['signature_hash'] in labeled_by_hash:
            # Copy labels from sample
            sample = labeled_by_hash[log['signature_hash']]
            log['root_cause'] = sample['root_cause']
            log['severity'] = sample['severity']
            log['component'] = sample['component']
            log['summary'] = sample['summary']
            log['action_needed'] = sample['action_needed']
            labeled_count += 1
        else:
            # Generate new labels
            labels = label_log(log)
            log.update(labels)
            new_labels_count += 1

        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(full_dataset)} logs...")

    print(f"\n✓ Labeled {len(full_dataset)} logs total")
    print(f"  - Reused from samples: {labeled_count}")
    print(f"  - Newly labeled: {new_labels_count}")

    # Save
    output_file = 'golden_dataset.json'
    save_json(output_file, full_dataset)

    print(f"\n{'=' * 70}")
    print(f"✓ Saved complete labeled dataset to {output_file}")
    print(f"{'=' * 70}")

    # Statistics
    print("\n=== Label Distribution ===")

    # By severity
    from collections import defaultdict
    sev_counts = defaultdict(int)
    for log in full_dataset:
        sev_counts[log['severity']] += 1

    print("\nSeverity:")
    for sev in ['info', 'warn', 'error', 'critical']:
        count = sev_counts.get(sev, 0)
        pct = (count / len(full_dataset) * 100) if full_dataset else 0
        print(f"  {sev:10s}: {count:3d} ({pct:5.1f}%)")

    # By action_needed
    action_counts = defaultdict(int)
    for log in full_dataset:
        action_counts[log['action_needed']] += 1

    print("\nAction Needed:")
    for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(full_dataset) * 100) if full_dataset else 0
        print(f"  {action:30s}: {count:3d} ({pct:5.1f}%)")

    # By component
    comp_counts = defaultdict(int)
    for log in full_dataset:
        comp_counts[log['component']] += 1

    print("\nComponent:")
    for comp, count in sorted(comp_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        pct = (count / len(full_dataset) * 100) if full_dataset else 0
        print(f"  {comp:30s}: {count:3d} ({pct:5.1f}%)")


if __name__ == '__main__':
    main()
