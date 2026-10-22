# ADJ1DE skills

GitHub Copilot workspace setup.

Open this repository in VS Code with GitHub Copilot. The workspace skills are discovered from `.github/skills/`; no profile-wide skill installation is required.
The included local launchers target Windows; the npm-based servers are cross-platform.

## Included customizations

- 56 pstack skills, imported from the MIT-licensed Cursor pstack plugin. See [the pstack source and license](./.github/skills/pstack/README.md).
- A portable, workspace-level MCP configuration in [`.mcp.json`](./.mcp.json), covering Azure DevOps, Databricks, SlideForge, Chrome DevTools, Playwright, Power BI Modeling, and PowerPoint.
- MCP tool definitions are provided by each server at runtime; they are not separate files to upload.

The pstack skill files are shared here; Cursor-specific plugin automations and agents are not. No separate Copilot plugin is installed by this setup.

## Local prerequisites

Install Node.js and `npx` for Azure DevOps, Chrome DevTools, Playwright, and Power BI Modeling. Those packages are fetched from npm when their servers start.

Set these non-secret user environment variables before launching VS Code:

- `AZDO_ORG`: your Azure DevOps organization.
- `AZDO_DOMAINS`: the comma-separated Azure DevOps domains you need, such as `core,work-items`.

Authenticate with Azure DevOps using the MCP package's supported local authentication flow. Keep any PAT in a local secret store or user environment variable, never in this repository.

The Databricks launcher reads `DATABRICKS_HOST` and `DATABRICKS_TOKEN` from the user environment, or from the selected `.databrickscfg` profile (`DEFAULT` unless `DATABRICKS_CONFIG_PROFILE` is set). The custom `databricks-mcp-server.exe` is not included; install it from an approved distribution on `PATH` or at `%USERPROFILE%\.local\bin\databricks-mcp-server.exe`.

The custom `ppt-mcp.exe` is also not included. Install it from an approved distribution at `%USERPROFILE%\.local\bin\ppt-mcp.exe`. The launcher uses any proxy variables already configured in the user's environment.
If your network requires a proxy, configure an approved proxy in your local environment before launching VS Code; no proxy host is embedded here.

SlideForge may require network or account access. Power BI Modeling may require accepting its EULA and connecting to a model. Each colleague must use their own service credentials and permissions.

## Safety and scope

The MCP configuration contains no credentials, personal organization values, or proxy URLs. User-specific Databricks credentials and Azure DevOps settings remain local. Local MCP executables are prerequisites and are deliberately not committed.

MCP servers can expose tools that modify data or files. Review the server publisher and tool approvals, and use permissions appropriate to the task. Local servers run with the connecting user's access; remote services follow their own account and authorization model.

This bundle includes the MCP servers configured for Copilot. MCPs configured only in other clients are not added here.
