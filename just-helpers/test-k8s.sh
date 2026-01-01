#!/usr/bin/env bash
# Test log-analyzer service from inside Kubernetes cluster
set -euo pipefail

NAMESPACE="${1:-log-analyzer}"
SEVERITY="${2:-all}"
DURATION="${3:-1h}"

# Calculate time range
source just-helpers/calc-time-range.sh "$DURATION"

echo "Testing log-analyzer in Kubernetes (namespace: $NAMESPACE, severity: $SEVERITY, duration: $DURATION)"
echo "Time range: $START → $END"
echo ""

# Build JSON payload
TMPFILE=$(mktemp)
trap "rm -f $TMPFILE" EXIT

if [ "$SEVERITY" = "all" ]; then
    cat > "$TMPFILE" <<EOF
{
  "time_range": {
    "start": "$START",
    "end": "$END"
  },
  "filters": {
    "namespace": "$NAMESPACE"
  },
  "limit": 15
}
EOF
else
    cat > "$TMPFILE" <<EOF
{
  "time_range": {
    "start": "$START",
    "end": "$END"
  },
  "filters": {
    "namespace": "$NAMESPACE",
    "severity": "$SEVERITY"
  },
  "limit": 15
}
EOF
fi

# Test via kubectl run to call from inside the cluster
kubectl run test-log-analyzer --rm -i --tty --image=curlimages/curl --restart=Never -- \
  sh -c "cat <<'JSONEOF' | curl -N -X POST 'http://log-analyzer.log-analyzer.svc.cluster.local:8000/v1/analyze/stream' -H 'Content-Type: application/json' -d @-
$(cat "$TMPFILE")
JSONEOF"
