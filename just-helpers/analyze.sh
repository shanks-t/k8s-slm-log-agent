#!/usr/bin/env bash
# Analyze logs using LOCAL FastAPI server (non-streaming JSON endpoint)
# Requires: 'just dev' running in another terminal
set -euo pipefail

NAMESPACE="${1:-log-analyzer}"
SEVERITY="${2:-all}"
DURATION="${3:-1h}"

# Calculate time range
source just-helpers/calc-time-range.sh "$DURATION"

echo "Analyzing logs (namespace: $NAMESPACE, severity: $SEVERITY, duration: $DURATION)"
echo "Time range: $START → $END"
echo ""

# Build JSON payload based on whether severity is provided
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

curl -X POST http://127.0.0.1:8000/v1/analyze \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" | jq .
