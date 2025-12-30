#!/usr/bin/env bash
# Push log-analyzer image to GitHub Container Registry
# Authenticates with ghcr.io using GHCR_TOKEN from .env

set -euo pipefail

# Load environment variables
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi
source .env

if [ -z "${GITHUB_USER:-}" ] || [ -z "${GHCR_TOKEN:-}" ]; then
    echo "Error: GITHUB_USER or GHCR_TOKEN not set in .env"
    exit 1
fi

GIT_SHA=$(git rev-parse --short HEAD)

echo "Logging in to ghcr.io..."
echo "${GHCR_TOKEN}" | docker login ghcr.io -u ${GITHUB_USER} --password-stdin

echo "Pushing ghcr.io/${GITHUB_USER}/log-analyzer:latest..."
docker push ghcr.io/${GITHUB_USER}/log-analyzer:latest

echo "Pushing ghcr.io/${GITHUB_USER}/log-analyzer:${GIT_SHA}..."
docker push ghcr.io/${GITHUB_USER}/log-analyzer:${GIT_SHA}

echo "✓ Pushed both tags to ghcr.io"
