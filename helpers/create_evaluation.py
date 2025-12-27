#!/usr/bin/env python3
"""Create evaluation file comparing LLM analysis with raw Loki logs."""

import json
import os
import sys

def main():
    # Read environment variables
    llm_file = os.environ["LLM_FILE"]
    loki_file = os.environ["LOKI_FILE"]
    output_file = os.environ["EVAL_FILE"]
    timestamp = os.environ["EVAL_TIMESTAMP"]
    namespace = os.environ["EVAL_NAMESPACE"]
    duration = os.environ["EVAL_DURATION"]
    start = os.environ["EVAL_START"]
    end = os.environ["EVAL_END"]

    # Read outputs
    with open(llm_file, "r") as f:
        llm_text = f.read()

    with open(loki_file, "r") as f:
        loki_data = json.load(f)

    # Extract logs from Loki response
    raw_logs = []
    results = loki_data.get("data", {}).get("result", [])
    for stream in results:
        labels = stream.get("stream", {})
        for ts_ns, line in stream.get("values", []):
            raw_logs.append({
                "timestamp": ts_ns,
                "message": line,
                "labels": labels
            })

    # Create evaluation structure
    evaluation = {
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
            "output": llm_text,
            "char_count": len(llm_text)
        },
        "raw_logs": {
            "count": len(raw_logs),
            "logs": raw_logs
        },
        "comparison": {
            "logs_analyzed": len(raw_logs),
            "analysis_length": len(llm_text),
            "has_error_in_analysis": "error" in llm_text.lower(),
            "has_no_logs": len(raw_logs) == 0
        }
    }

    # Write evaluation file
    with open(output_file, "w") as f:
        json.dump(evaluation, f, indent=2)

    print(f"\n✓ Evaluation saved to: {output_file}")
    print(f"\nSummary:")
    print(f"  Raw logs found:     {len(raw_logs)}")
    print(f"  Analysis length:    {len(llm_text)} chars")
    print(f"  LLM found issue:    {'error' in llm_text.lower()}")

if __name__ == "__main__":
    main()
