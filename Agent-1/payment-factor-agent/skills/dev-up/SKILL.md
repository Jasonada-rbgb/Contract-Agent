---
name: dev-up
description: Connect to Databricks and prepare the working environment for the Warranty Contract Agent. Use when starting development work, setting up authentication, or pulling app code from the Databricks workspace.
---

# Dev Up -- Connect to Databricks and Prepare Working Environment

## Purpose
Set up the Databricks connection and pull app code. Works in both local Cursor and Cloud Agent VMs.

## For Cloud Agents (no local files)

```bash
# 1. Configure auth from secrets
echo -e "[DEFAULT]\nhost = ${DATABRICKS_HOST}\ntoken = ${DATABRICKS_TOKEN}" > ~/.databrickscfg

# 2. Install CLI
pip install databricks-sdk databricks-cli 2>/dev/null

# 3. Verify connection
databricks workspace list "/Workspace/Users/adj1de@bosch.com/"

# 4. Pull app code
databricks workspace export-dir \
  "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk" \
  ./agent-contract

# 5. Work in ./agent-contract
cd ./agent-contract
```

## For Local Cursor (Windows)

```powershell
# 1. Set proxy
$env:HTTP_PROXY = "http://rb-proxy-de.bosch.com:8080"
$env:HTTPS_PROXY = "http://rb-proxy-de.bosch.com:8080"

# 2. Start sync (background)
databricks sync --watch "c:\Users\ADJ1DE\Documents\Agent Workflow\Agent-1\agent-contract\agent-openai-agents-sdk" "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk"

# 3. Deploy
databricks apps deploy agent-contract --source-code-path "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk"
```

## Push Changes Back (Cloud Agents)

```bash
# Push modified code
databricks workspace import-dir ./agent-contract \
  "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk" \
  --overwrite

# Deploy
databricks apps deploy agent-contract \
  --source-code-path "/Workspace/Users/adj1de@bosch.com/databricks_apps/agent-contract_2026_03_06-13_15/agent-openai-agents-sdk"
```

## Verify Deployment

```bash
databricks apps get agent-contract
```
Look for `compute_status.state: ACTIVE` and `active_deployment.status.state: SUCCEEDED`.

## App URL
https://agent-contract-2236441816741128.8.azure.databricksapps.com
