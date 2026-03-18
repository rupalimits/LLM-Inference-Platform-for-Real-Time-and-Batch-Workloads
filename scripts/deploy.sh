#!/usr/bin/env bash
# Deploy to Kubernetes using raw manifests OR Helm (set USE_HELM=true).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USE_HELM="${USE_HELM:-false}"
NAMESPACE="${NAMESPACE:-llm-platform}"

# ── Ensure namespace exists ───────────────────────────────────────────────────
kubectl apply -f "$ROOT/k8s/namespace.yaml"

if [[ "$USE_HELM" == "true" ]]; then
  echo "==> Deploying with Helm"
  helm upgrade --install llm-platform "$ROOT/helm" \
    --namespace "$NAMESPACE" \
    --create-namespace \
    --values "$ROOT/helm/values.yaml" \
    --wait
else
  echo "==> Deploying with kubectl"
  kubectl apply -f "$ROOT/k8s/configmap.yaml"
  kubectl apply -f "$ROOT/k8s/redis-deployment.yaml"
  kubectl apply -f "$ROOT/k8s/inference-deployment.yaml"
  kubectl apply -f "$ROOT/k8s/inference-service.yaml"
  kubectl apply -f "$ROOT/k8s/worker-deployment.yaml"
fi

echo "==> Waiting for inference rollout..."
kubectl rollout status deployment/inference -n "$NAMESPACE" --timeout=300s

echo "==> Deployment complete"
kubectl get pods -n "$NAMESPACE"
