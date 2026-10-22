$ErrorActionPreference = "Stop"

$profileName = [Environment]::GetEnvironmentVariable("DATABRICKS_CONFIG_PROFILE")
if ([string]::IsNullOrWhiteSpace($profileName)) {
    $profileName = "DEFAULT"
}

$profileValues = @{}
$configPath = Join-Path $env:USERPROFILE ".databrickscfg"

if (Test-Path -LiteralPath $configPath) {
    $activeProfile = ""
    foreach ($line in Get-Content -LiteralPath $configPath) {
        if ($line -match "^\s*\[([^\]]+)\]\s*$") {
            $activeProfile = $Matches[1]
            continue
        }

        if ($activeProfile -ieq $profileName -and $line -match "^\s*(host|token)\s*=\s*(.*?)\s*$") {
            $profileValues[$Matches[1].ToLowerInvariant()] = $Matches[2].Trim()
        }
    }
}

if ([string]::IsNullOrWhiteSpace($env:DATABRICKS_HOST) -and $profileValues.ContainsKey("host")) {
    $env:DATABRICKS_HOST = $profileValues["host"]
}

if ([string]::IsNullOrWhiteSpace($env:DATABRICKS_TOKEN) -and $profileValues.ContainsKey("token")) {
    $env:DATABRICKS_TOKEN = $profileValues["token"]
}

if ([string]::IsNullOrWhiteSpace($env:DATABRICKS_HOST) -or
    [string]::IsNullOrWhiteSpace($env:DATABRICKS_TOKEN)) {
    throw "Configure DATABRICKS_HOST and DATABRICKS_TOKEN locally or in your .databrickscfg profile."
}

$server = Get-Command "databricks-mcp-server.exe" -CommandType Application -ErrorAction SilentlyContinue
if ($server) {
    $serverPath = $server.Source
} else {
    $serverPath = Join-Path $env:USERPROFILE ".local\bin\databricks-mcp-server.exe"
}

if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
    throw "Install the approved databricks-mcp-server.exe on PATH or at $serverPath."
}

& $serverPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
