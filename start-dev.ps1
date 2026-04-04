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
$backendVenvPython = Join-Path $backendDir "venv\Scripts\python.exe"

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

function Get-BackendCommand {
    if (Test-Path $backendVenvPython) {
        return "& '$backendVenvPython' app.py"
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python app.py"
    }

    Assert-CommandAvailable -Name "py"
    return "py -3 app.py"
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

if (-not $FrontendOnly) {
    $backendCommand = Get-BackendCommand
    Start-DevWindow -WorkingDirectory $backendDir -Command $backendCommand
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
