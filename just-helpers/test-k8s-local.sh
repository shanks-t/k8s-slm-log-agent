#!/usr/bin/env bash
# Test deployed log-analyzer via port-forward (self-contained)
set -euo pipefail

NAMESPACE="$1"
DURATION="$2"

# Calculate time range
source just-helpers/calc-time-range.sh "$DURATION"

echo "Setting up port-forward to log-analyzer..."

# Start port-forward in background
kubectl port-forward -n log-analyzer svc/log-analyzer 8000:8000 > /dev/null 2>&1 &
PF_PID=$!

# Ensure cleanup on exit (success or failure)
trap "echo 'Cleaning up port-forward...'; kill $PF_PID 2>/dev/null || true" EXIT

# Wait for port-forward to be ready
echo "Waiting for port-forward..."
just-helpers/wait-for.sh http://localhost:8000/health

echo "Testing log-analyzer (namespace: $NAMESPACE, duration: $DURATION)"
echo "Time range: $START → $END"
echo ""

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
    \"limit\": 15
  }"

# Trap will handle cleanup
