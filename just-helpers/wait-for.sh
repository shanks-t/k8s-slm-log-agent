#!/usr/bin/env bash
set -e

URL="$1"

echo "Waiting for $URL"

until curl -sf "$URL" > /dev/null; do
  sleep 1
done
