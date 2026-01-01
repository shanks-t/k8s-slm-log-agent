#!/usr/bin/env bash
# Test log-analyzer service from inside Kubernetes cluster
set -euo pipefail

NAMESPACE="$1"
DURATION="$2"

# Calculate time range
source just-helpers/calc-time-range.sh "$DURATION"

echo "Testing log-analyzer in Kubernetes (namespace: $NAMESPACE, duration: $DURATION)"
echo "Time range: $START → $END"

# Test via kubectl run to call from inside the cluster
kubectl run test-log-analyzer --rm -i --tty --image=curlimages/curl --restart=Never -- \
  curl -N -X POST "http://log-analyzer.log-analyzer.svc.cluster.local:8000/v1/analyze/stream" \
  -H "Content-Type: application/json" \
  -d "{
    \"time_range\": {
      \"start\": \"$START\",
      \"end\": \"$END\"
    },
    \"filters\": {
      \"namespace\": \"$NAMESPACE\"
    },
    \"limit\": 15
  }"
