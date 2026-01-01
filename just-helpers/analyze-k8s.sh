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

# Build JSON payload and write to temp file to avoid shell escaping issues
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
# Use kubectl cp to transfer JSON, then curl it
kubectl run analyze-test --rm -i --image=curlimages/curl --restart=Never -- \
  sh -c "cat <<'JSONEOF' | curl -X POST 'http://log-analyzer.log-analyzer.svc.cluster.local:8000/v1/analyze' -H 'Content-Type: application/json' -d @-
$(cat "$TMPFILE")
JSONEOF"
