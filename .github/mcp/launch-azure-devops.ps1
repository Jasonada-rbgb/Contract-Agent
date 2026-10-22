$ErrorActionPreference = "Stop"

$organization = [Environment]::GetEnvironmentVariable("AZDO_ORG")
$domains = [Environment]::GetEnvironmentVariable("AZDO_DOMAINS")

if ([string]::IsNullOrWhiteSpace($organization)) {
    throw "Set AZDO_ORG in your user environment before starting Copilot."
}

if ([string]::IsNullOrWhiteSpace($domains)) {
    throw "Set AZDO_DOMAINS to the Azure DevOps domains you need before starting Copilot."
}

& npx -y "@azure-devops/mcp@latest" $organization -d $domains
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
