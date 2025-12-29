#!/usr/bin/env python3
"""Evaluate log-analyzer by comparing LLM analysis with raw Loki logs."""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '5m', '2h', '24h' into timedelta."""
    unit = duration_str[-1]
    value = int(duration_str[:-1])

    if unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    else:
        raise ValueError(f"Invalid duration unit: {unit}. Use 'm', 'h', or 'd'")


def calculate_time_range(duration: str) -> tuple[str, str]:
    """Calculate start and end timestamps for the given duration."""
    end = datetime.now(timezone.utc)
    delta = parse_duration(duration)
    start = end - delta

    # Format as ISO 8601 with 'Z' suffix
    start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    return start_str, end_str


def setup_port_forward(namespace: str, service: str, port: int) -> subprocess.Popen:
    """Start kubectl port-forward in background."""
    cmd = [
        "kubectl", "port-forward",
        "-n", namespace,
        f"svc/{service}",
        f"{port}:{port}"
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return proc


def wait_for_endpoint(url: str, timeout: int = 30) -> bool:
    """Wait for HTTP endpoint to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)

    return False


def query_log_analyzer(namespace: str, start: str, end: str, limit: int = 15) -> dict:
    """Query the log-analyzer API."""
    url = "http://127.0.0.1:8000/v1/analyze"

    payload = {
        "time_range": {
            "start": start,
            "end": end
        },
        "filters": {
            "namespace": namespace
        },
        "limit": limit
    }

    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def query_loki(namespace: str, start: str, end: str, limit: int = 15) -> dict:
    """Query Loki directly for raw logs."""
    url = "http://localhost:3100/loki/api/v1/query_range"

    # Convert ISO timestamps to nanoseconds
    start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    start_ns = int(start_dt.timestamp() * 1e9)
    end_ns = int(end_dt.timestamp() * 1e9)

    params = {
        "query": f'{{namespace="{namespace}",container!="loki"}}',
        "start": start_ns,
        "end": end_ns,
        "limit": limit,
        "direction": "backward"
    }

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_raw_logs(loki_response: dict) -> list[dict]:
    """Extract and flatten logs from Loki response."""
    raw_logs = []
    results = loki_response.get("data", {}).get("result", [])

    for stream in results:
        labels = stream.get("stream", {})
        for ts_ns, line in stream.get("values", []):
            raw_logs.append({
                "timestamp": ts_ns,
                "message": line,
                "labels": labels
            })

    return raw_logs


def create_evaluation(
    analyzer_response: dict,
    raw_logs: list[dict],
    namespace: str,
    duration: str,
    start: str,
    end: str,
    timestamp: str
) -> dict:
    """Create the evaluation JSON structure."""
    analysis_text = analyzer_response.get("analysis", "")

    return {
        "metadata": {
            "timestamp": timestamp,
            "namespace": namespace,
            "duration": duration,
            "time_range": {
                "start": start,
                "end": end
            }
        },
        "query_params": {
            "namespace": namespace,
            "limit": 15,
            "filter": "container!=loki"
        },
        "llm_analysis": {
            "output": analysis_text,
            "char_count": len(analysis_text)
        },
        "raw_logs": {
            "count": len(raw_logs),
            "logs": raw_logs
        },
        "comparison": {
            "logs_analyzed": len(raw_logs),
            "analysis_length": len(analysis_text),
            "has_error_in_analysis": "error" in analysis_text.lower(),
            "has_no_logs": len(raw_logs) == 0
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate log-analyzer by comparing LLM analysis with raw Loki logs"
    )
    parser.add_argument("namespace", help="Kubernetes namespace to analyze")
    parser.add_argument("duration", help="Time duration (e.g., '5m', '2h', '24h')")

    args = parser.parse_args()

    # Calculate time range
    start, end = calculate_time_range(args.duration)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # Determine output file
    repo_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True
    ).strip()
    tmp_dir = Path(repo_root) / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    output_file = tmp_dir / f"evaluation-{timestamp}.json"

    # Print header
    print("=" * 42)
    print("Evaluation Run")
    print("=" * 42)
    print(f"Namespace:   {args.namespace}")
    print(f"Duration:    {args.duration}")
    print(f"Time Range:  {start} → {end}")
    print(f"Output:      {output_file}")
    print()

    # Setup port-forwards
    print("Setting up port-forwards...")
    pf_analyzer = setup_port_forward("log-analyzer", "log-analyzer", 8000)
    pf_loki = setup_port_forward("logging", "loki", 3100)

    try:
        # Wait for services
        print("Waiting for services...")
        if not wait_for_endpoint("http://localhost:8000/health"):
            print("ERROR: log-analyzer did not become ready", file=sys.stderr)
            return 1

        if not wait_for_endpoint("http://localhost:3100/ready"):
            print("ERROR: Loki did not become ready", file=sys.stderr)
            return 1

        # Query log-analyzer
        print()
        print("1. Querying log-analyzer (LLM analysis)...")
        analyzer_response = query_log_analyzer(args.namespace, start, end)

        # Query Loki
        print("2. Querying Loki (raw logs)...")
        loki_response = query_loki(args.namespace, start, end)
        raw_logs = extract_raw_logs(loki_response)

        # Create evaluation
        print("3. Creating evaluation file...")
        evaluation = create_evaluation(
            analyzer_response,
            raw_logs,
            args.namespace,
            args.duration,
            start,
            end,
            timestamp
        )

        # Write to file
        with open(output_file, "w") as f:
            json.dump(evaluation, f, indent=2)

        print(f"\n✓ Evaluation saved to: {output_file}")
        print(f"\nSummary:")
        print(f"  Raw logs found:     {len(raw_logs)}")
        print(f"  Analysis length:    {len(analyzer_response.get('analysis', ''))} chars")
        print(f"  LLM found issue:    {evaluation['comparison']['has_error_in_analysis']}")

        # Preview
        print()
        print("=" * 42)
        print("Quick Preview")
        print("=" * 42)
        print()
        print("LLM Analysis (first 500 chars):")
        analysis = analyzer_response.get("analysis", "")
        print(analysis[:500])
        if len(analysis) > 500:
            print("...")
        print()
        print(f"Raw Log Count: {len(raw_logs)} entries")
        print()
        print("=" * 42)
        print("Full evaluation saved to:")
        print(output_file)
        print("=" * 42)
        print()
        print("To review:")
        print(f"  cat {output_file} | jq .")
        print()

        return 0

    finally:
        # Cleanup port-forwards
        print("Cleaning up port-forwards...")
        pf_analyzer.terminate()
        pf_loki.terminate()
        try:
            pf_analyzer.wait(timeout=2)
            pf_loki.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pf_analyzer.kill()
            pf_loki.kill()


if __name__ == "__main__":
    sys.exit(main())
