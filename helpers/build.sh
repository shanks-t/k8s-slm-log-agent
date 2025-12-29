#!/usr/bin/env bash
# Build log-analyzer Docker image for linux/amd64
# Tags with both 'latest' and git commit SHA for versioning

set -euo pipefail

# Load environment variables
if [ ! -f .env ]; then
    echo "Error: .env file not found. Copy .env.example and fill in your credentials."
    exit 1
fi
source .env

if [ -z "${GITHUB_USER:-}" ]; then
    echo "Error: GITHUB_USER not set in .env"
    exit 1
fi

# Get git commit SHA for tagging
GIT_SHA=$(git rev-parse --short HEAD)

echo "Building log-analyzer:latest and log-analyzer:${GIT_SHA}..."
docker build --platform linux/amd64 \
    -t ghcr.io/${GITHUB_USER}/log-analyzer:latest \
    -t ghcr.io/${GITHUB_USER}/log-analyzer:${GIT_SHA} \
    workloads/log-analyzer

echo "✓ Built ghcr.io/${GITHUB_USER}/log-analyzer:latest"
echo "✓ Built ghcr.io/${GITHUB_USER}/log-analyzer:${GIT_SHA}"
