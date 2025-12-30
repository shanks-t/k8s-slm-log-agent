#!/usr/bin/env bash
# Test LOCAL FastAPI server (requires 'just dev' running)
set -euo pipefail

NAMESPACE="$1"
DURATION="$2"

# Calculate time range
source helpers/calc-time-range.sh "$DURATION"

echo "Testing log-analyzer (namespace: $NAMESPACE, duration: $DURATION)"
echo "Time range: $START → $END"

curl -N -X POST http://127.0.0.1:8000/v1/analyze/stream \
  -H "Content-Type: application/json" \
  -d "{
    \"time_range\": {
      \"start\": \"$START\",
      \"end\": \"$END\"
    },
    \"filters\": {
      \"namespace\": \"$NAMESPACE\"
    },
    \"limit\": 2
  }"
