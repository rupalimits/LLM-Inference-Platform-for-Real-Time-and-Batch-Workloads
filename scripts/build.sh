#!/usr/bin/env bash
# Build Docker images for inference server and batch worker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-latest}"
REGISTRY="${REGISTRY:-llm-platform}"

echo "==> Building inference image  ($REGISTRY/inference:$VERSION)"
docker build \
  -t "$REGISTRY/inference:$VERSION" \
  -f "$ROOT/inference/Dockerfile" \
  "$ROOT"

echo "==> Building worker image     ($REGISTRY/worker:$VERSION)"
docker build \
  -t "$REGISTRY/worker:$VERSION" \
  -f "$ROOT/worker/Dockerfile" \
  "$ROOT"

echo "==> Done. Images tagged as $REGISTRY/{inference,worker}:$VERSION"
