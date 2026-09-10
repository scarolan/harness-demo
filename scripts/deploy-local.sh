#!/bin/bash
set -e

# If you don't have docker locally because you are in WSL using Rancher Desktop or similar,
# you can use kubectl apply on the manifests.
# If you just want to update the deployment:
# kubectl set image deployment/ollama-demo ollama-demo=carolanio/harness-demo:latest -n ollama-demo

echo "=== Deploying to Kubernetes ==="
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

echo "=== Waiting for deployment to be ready ==="
kubectl rollout status deployment/ollama-demo -n ollama-demo --timeout=90s || true

echo "=== App deployed successfully ==="
echo "Access the app at: http://localhost:30080"
