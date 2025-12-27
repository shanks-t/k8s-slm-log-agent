#!/usr/bin/env bash
# Calculate START and END timestamps from duration string
# Usage: source calc-time-range.sh "30m"
# Exports: START, END

DURATION="${1:-1h}"

# Parse duration using sed (portable)
VALUE=$(echo "$DURATION" | sed 's/[^0-9]//g')
UNIT=$(echo "$DURATION" | sed 's/[0-9]//g' | tr '[:upper:]' '[:lower:]')

# Validate format
if [[ -z "$VALUE" || -z "$UNIT" ]]; then
    echo "Error: Invalid duration format '$DURATION'. Use format like: 1h, 30m, 24h" >&2
    exit 1
fi

# Convert to date command arguments (cross-platform: macOS and Linux)
case "$UNIT" in
    h)
        MACOS_ARG="-${VALUE}H"
        LINUX_ARG="${VALUE} hours ago"
        ;;
    m)
        MACOS_ARG="-${VALUE}M"
        LINUX_ARG="${VALUE} minutes ago"
        ;;
    d)
        MACOS_ARG="-${VALUE}d"
        LINUX_ARG="${VALUE} days ago"
        ;;
    *)
        echo "Error: Invalid unit '$UNIT'. Use h (hours), m (minutes), or d (days)" >&2
        exit 1
        ;;
esac

# Calculate timestamps (try macOS format first, fall back to Linux)
START=$(date -u -v"$MACOS_ARG" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "$LINUX_ARG" +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Export for calling script
export START
export END
