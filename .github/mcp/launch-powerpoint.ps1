$ErrorActionPreference = "Stop"

$serverPath = Join-Path $env:USERPROFILE ".local\bin\ppt-mcp.exe"
if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
    throw "Install the approved ppt-mcp.exe at $serverPath before starting this MCP server."
}

foreach ($name in @("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")) {
    $value = [Environment]::GetEnvironmentVariable($name, "User")
    if ($value) {
        Set-Item "Env:$name" $value
    }
}

& $serverPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
