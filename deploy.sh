#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Azure Container Apps deployment — Employee MCP + HR Agent
# Lowest-cost setup: Consumption plan, scale-to-zero, Basic ACR, 0.25 vCPU
#
# Usage:
#   OPENAI_API_KEY=sk-... ./deploy.sh
#   ./deploy.sh --delete   # tear everything down
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config (edit if needed) ──────────────────────────────────────────────────
RESOURCE_GROUP="hr-agent-rg"
LOCATION="eastus"                    # cheapest Azure region
ACR_NAME="hragentacr$(openssl rand -hex 4)"
ENVIRONMENT="hr-agent-env"
MCP_APP="employee-mcp"
AGENT_APP="hr-agent-api"

# ── Tear-down mode ───────────────────────────────────────────────────────────
if [[ "${1:-}" == "--delete" ]]; then
  echo "Deleting resource group $RESOURCE_GROUP …"
  az group delete --name "$RESOURCE_GROUP" --yes --no-wait
  echo "Deletion triggered (runs in background)."
  exit 0
fi

# ── Validate OPENAI_API_KEY ──────────────────────────────────────────────────
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY environment variable is required."
  echo "  export OPENAI_API_KEY=sk-... && ./deploy.sh"
  exit 1
fi

echo ""
echo "=== Deploying HR Agent stack to Azure Container Apps ==="
echo "    Resource group : $RESOURCE_GROUP"
echo "    Location       : $LOCATION"
echo "    ACR            : $ACR_NAME"
echo ""

# ── 1. Resource group ────────────────────────────────────────────────────────
echo "[1/7] Creating resource group…"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ── 2. Container Registry (Basic — cheapest tier, ~$5/mo) ───────────────────
echo "[2/7] Creating Azure Container Registry (Basic)…"
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true \
  --output none

ACR_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASS=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# ── 3. Build & push images via ACR Tasks (no local Docker needed) ────────────
echo "[3/7] Building employee-mcp image in ACR…"
az acr build \
  --registry "$ACR_NAME" \
  --image employee-mcp:latest \
  ./employee-mcp \
  --output none

echo "[4/7] Building hr-agent image in ACR…"
az acr build \
  --registry "$ACR_NAME" \
  --image hr-agent:latest \
  ./hr-agent \
  --output none

# ── 4. Container Apps Environment (Consumption — scale-to-zero) ─────────────
echo "[5/7] Creating Container Apps Environment…"
az containerapp env create \
  --name "$ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ── 5. Deploy employee-mcp ───────────────────────────────────────────────────
echo "[6/7] Deploying employee-mcp container app…"
az containerapp create \
  --name "$MCP_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "$ACR_SERVER/employee-mcp:latest" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8000 \
  --ingress external \
  --cpu 0.25 \
  --memory 0.5Gi \
  --min-replicas 0 \
  --max-replicas 1 \
  --output none

MCP_FQDN=$(az containerapp show \
  --name "$MCP_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

MCP_URL="https://${MCP_FQDN}/mcp"
echo "    MCP server URL : $MCP_URL"

# ── 6. Deploy hr-agent-api ───────────────────────────────────────────────────
echo "[7/7] Deploying hr-agent-api container app…"
az containerapp create \
  --name "$AGENT_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENVIRONMENT" \
  --image "$ACR_SERVER/hr-agent:latest" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8080 \
  --ingress external \
  --cpu 0.25 \
  --memory 0.5Gi \
  --min-replicas 0 \
  --max-replicas 1 \
  --secrets "openai-key=$OPENAI_API_KEY" \
  --env-vars \
    "EMPLOYEE_MCP_URL=$MCP_URL" \
    "OPENAI_API_KEY=secretref:openai-key" \
  --output none

AGENT_FQDN=$(az containerapp show \
  --name "$AGENT_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "✓ Deployment complete!"
echo ""
echo "  Employee MCP  →  https://${MCP_FQDN}/mcp"
echo "  HR Agent API  →  https://${AGENT_FQDN}"
echo ""
echo "Test:"
echo "  curl https://${AGENT_FQDN}/health"
echo "  curl -X POST https://${AGENT_FQDN}/ask \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"question\": \"Who earns the most?\"}'"
echo ""
echo "Tear down all resources:"
echo "  ./deploy.sh --delete"
