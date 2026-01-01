#!/usr/bin/env bash
# Build log-analyzer Docker image for linux/amd64
# Tags with both 'latest' and git commit SHA for versioning

set -euo pipefail

# Ensure we're on main branch before building release images
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "❌ Error: Must be on 'main' branch to build release images"
    echo "   Current branch: $CURRENT_BRANCH"
    echo ""
    echo "To build a release:"
    echo "  1. git checkout main"
    echo "  2. git merge $CURRENT_BRANCH"
    echo "  3. just build"
    echo ""
    echo "For local development builds, use Docker directly:"
    echo "  cd workloads/log-analyzer && docker build ."
    exit 1
fi

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
