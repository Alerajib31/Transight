param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

if ($BackendOnly -and $FrontendOnly) {
    throw "Use only one of -BackendOnly or -FrontendOnly."
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "server"
$frontendDir = Join-Path $projectRoot "client"
$localNodeDir = Join-Path $projectRoot ".tools\node-v20.20.2-win-x64"

function Assert-CommandAvailable {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available on PATH."
    }
}

function Get-FrontendCommand {
    if (Test-Path (Join-Path $localNodeDir "npm.cmd")) {
        return "& '$localNodeDir\\npm.cmd' run dev"
    }

    Assert-CommandAvailable -Name "npm"
    return "npm run dev"
}

function Start-DevWindow {
    param(
        [string]$WorkingDirectory,
        [string]$Command
    )

    Start-Process powershell `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList @("-NoExit", "-Command", $Command) | Out-Null
}

Assert-CommandAvailable -Name "py"

if (-not $FrontendOnly) {
    Start-DevWindow -WorkingDirectory $backendDir -Command "py -3 app.py"
    Write-Host "Backend window started in $backendDir"
}

if (-not $BackendOnly) {
    $frontendCommand = Get-FrontendCommand
    Start-DevWindow -WorkingDirectory $frontendDir -Command $frontendCommand
    Write-Host "Frontend window started in $frontendDir"
}

if (Test-Path $localNodeDir) {
    Write-Host "Frontend will use local Node from $localNodeDir"
}

Write-Host "Open http://localhost:3000 after both services finish starting."
