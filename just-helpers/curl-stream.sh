#!/usr/bin/env bash
# Quick curl to local /v1/analyze/stream endpoint (streaming text)
# Simpler than test-stream.sh - uses current time with configurable lookback
set -euo pipefail

NAMESPACE="${1:-llm}"
SEVERITY="${2:-error}"
LOOKBACK="${3:-30m}"

# Calculate time range
source just-helpers/calc-time-range.sh "$LOOKBACK"

echo "🔍 Streaming analysis for $NAMESPACE namespace (severity: $SEVERITY, last $LOOKBACK)"
echo ""

curl -N -X POST http://localhost:8000/v1/analyze/stream \
  -H "Content-Type: application/json" \
  -d "{
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
