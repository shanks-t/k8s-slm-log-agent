#!/usr/bin/env bash
# Query Loki directly (bypass log-analyzer LLM)
# Useful for debugging LogQL queries and seeing raw log structure
set -euo pipefail

NAMESPACE="${1:-log-analyzer}"
SEVERITY="${2:-all}"
DURATION="${3:-1h}"
LIMIT="${4:-15}"

# Calculate time range
source just-helpers/calc-time-range.sh "$DURATION"

echo "=== Querying Loki Directly ==="
echo "Namespace: $NAMESPACE"
echo "Severity:  $SEVERITY"
echo "Duration:  $DURATION"
echo "Limit:     $LIMIT"
echo "Time:      $START → $END"
echo ""

# Convert ISO timestamps to nanoseconds (macOS and Linux compatible)
START_NS=$(date -jf "%Y-%m-%dT%H:%M:%SZ" "$START" "+%s" 2>/dev/null || date -d "$START" "+%s")
END_NS=$(date -jf "%Y-%m-%dT%H:%M:%SZ" "$END" "+%s" 2>/dev/null || date -d "$END" "+%s")
START_NS=$((START_NS * 1000000000))
END_NS=$((END_NS * 1000000000))

# Build LogQL query with severity filter
BASE_QUERY="{namespace=\"$NAMESPACE\",container!=\"loki\"}"

case "$SEVERITY" in
    info)
        QUERY="$BASE_QUERY |~ \"(?i)(INFO|DEBUG|TRACE|successful|started|completed|ready)\""
        ;;
    error)
        QUERY="$BASE_QUERY |~ \"(?i)(ERROR|FATAL|CRITICAL|EXCEPTION|failed|failure|panic|crash|killed|terminated)\""
        ;;
    all)
        QUERY="$BASE_QUERY"
        ;;
    *)
        echo "Error: Invalid severity '$SEVERITY'. Use: info, error, all" >&2
        exit 1
        ;;
esac

echo "LogQL: $QUERY"
echo ""

# Query Loki and format output
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode "query=$QUERY" \
  --data-urlencode "start=$START_NS" \
  --data-urlencode "end=$END_NS" \
  --data-urlencode "limit=$LIMIT" \
  --data-urlencode "direction=backward" \
  | jq -r '
    if .data.result | length == 0 then
      "No logs found matching criteria"
    else
      .data.result[] |
      .stream as $labels |
      .values[] |
      "\(.[0] | tonumber / 1000000000 | strftime("%Y-%m-%dT%H:%M:%SZ")) [\($labels.namespace)/\($labels.pod)] \(.[1])"
    end
  '
