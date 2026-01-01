#!/usr/bin/env bash
# Test LOCAL FastAPI server (requires 'just dev' running)
set -euo pipefail

NAMESPACE="${1:-kube-system}"
SEVERITY="${2:-all}"
DURATION="${3:-24h}"

# Calculate time range
source just-helpers/calc-time-range.sh "$DURATION"

echo "Testing log-analyzer (namespace: $NAMESPACE, severity: $SEVERITY, duration: $DURATION)"
echo "Time range: $START → $END"
echo ""

# Build JSON payload based on severity
if [ "$SEVERITY" = "all" ]; then
    PAYLOAD="{
        \"time_range\": {
            \"start\": \"$START\",
            \"end\": \"$END\"
        },
        \"filters\": {
            \"namespace\": \"$NAMESPACE\"
        },
        \"limit\": 15
    }"
else
    PAYLOAD="{
        \"time_range\": {
            \"start\": \"$START\",
            \"end\": \"$END\"
        },
        \"filters\": {
            \"namespace\": \"$NAMESPACE\",
            \"severity\": \"$SEVERITY\"
        },
        \"limit\": 15
    }"
fi

curl -N -X POST http://127.0.0.1:8000/v1/analyze/stream \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
