#!/usr/bin/env bash
# Deploy the MRE API to Azure Container Apps (session 2.4 CU3).
#
# Provider-swap boundary: this script and main.bicep are the ONLY Azure-aware
# artifacts. Builds/pushes the provider-agnostic image to ACR, then deploys the
# Bicep. Idempotent — safe to re-run to roll a new image tag.
#
# Prereqs: az CLI logged in (`az login`), Docker, an existing resource group
# and Azure Container Registry. Configure via env or deploy/azure/.env
# (see .env.example). Secrets come from the environment — never commit them.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../.." && pwd)"

# Load local, git-ignored config if present.
[ -f "$here/.env" ] && set -a && . "$here/.env" && set +a

: "${RESOURCE_GROUP:?set RESOURCE_GROUP}"
: "${ACR_NAME:?set ACR_NAME (registry name, without .azurecr.io)}"
: "${LOCATION:=eastus}"
: "${NAME:=mre}"
: "${IMAGE_TAG:=$(git -C "$repo_root" rev-parse --short HEAD 2>/dev/null || echo latest)}"
: "${ANTHROPIC_API_KEY:=}"   # optional; injected as a secret if set

registry_server="${ACR_NAME}.azurecr.io"
image="${registry_server}/mre-api:${IMAGE_TAG}"

echo ">> Building and pushing image via ACR: ${image}"
# ACR build keeps the (large ortools) build off the local machine and uses the
# same multi-stage Dockerfile — runtime target is the shipped image.
az acr build \
  --registry "$ACR_NAME" \
  --image "mre-api:${IMAGE_TAG}" \
  --target runtime \
  --file "$repo_root/Dockerfile" \
  "$repo_root"

echo ">> Resolving registry credentials"
reg_user="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
reg_pass="$(az acr credential show -n "$ACR_NAME" --query 'passwords[0].value' -o tsv)"

echo ">> Deploying Bicep to resource group ${RESOURCE_GROUP}"
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$here/main.bicep" \
  --parameters \
      name="$NAME" \
      location="$LOCATION" \
      image="$image" \
      registryServer="$registry_server" \
      registryUsername="$reg_user" \
      registryPassword="$reg_pass" \
      anthropicApiKey="$ANTHROPIC_API_KEY"

api_url="$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" --name main \
  --query properties.outputs.apiUrl.value -o tsv 2>/dev/null || true)"

echo ">> Deployed. API URL: ${api_url:-<see deployment outputs>}"
echo ">> Smoke it:  python deploy/smoke.py --base-url ${api_url:-https://<fqdn>}"
