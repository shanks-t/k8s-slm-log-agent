#!/usr/bin/env bash
# Analyze logs using DEPLOYED log-analyzer (non-streaming JSON endpoint)
# Creates ephemeral curl pod inside Kubernetes cluster
set -euo pipefail

NAMESPACE="${1:-log-analyzer}"
SEVERITY="${2:-all}"
DURATION="${3:-1h}"

# Calculate time range
source just-helpers/calc-time-range.sh "$DURATION"

echo "Analyzing logs via Kubernetes (namespace: $NAMESPACE, severity: $SEVERITY, duration: $DURATION)"
echo "Time range: $START → $END"
echo ""

# Build JSON payload
if [ "$SEVERITY" = "all" ]; then
    PAYLOAD="{
        \\\"time_range\\\": {
            \\\"start\\\": \\\"$START\\\",
            \\\"end\\\": \\\"$END\\\"
        },
        \\\"filters\\\": {
            \\\"namespace\\\": \\\"$NAMESPACE\\\"
        },
        \\\"limit\\\": 15
    }"
else
    PAYLOAD="{
        \\\"time_range\\\": {
            \\\"start\\\": \\\"$START\\\",
            \\\"end\\\": \\\"$END\\\"
        },
        \\\"filters\\\": {
            \\\"namespace\\\": \\\"$NAMESPACE\\\",
            \\\"severity\\\": \\\"$SEVERITY\\\"
        },
        \\\"limit\\\": 15
    }"
fi

# Test via kubectl run to call from inside the cluster
kubectl run analyze-test --rm -i --tty --image=curlimages/curl --restart=Never -- \
  curl -X POST "http://log-analyzer.log-analyzer.svc.cluster.local:8000/v1/analyze" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
