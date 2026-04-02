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

function Assert-CommandAvailable {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available on PATH."
    }
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
Assert-CommandAvailable -Name "npm"

if (-not $FrontendOnly) {
    Start-DevWindow -WorkingDirectory $backendDir -Command "py -3 app.py"
    Write-Host "Backend window started in $backendDir"
}

if (-not $BackendOnly) {
    Start-DevWindow -WorkingDirectory $frontendDir -Command "npm run dev"
    Write-Host "Frontend window started in $frontendDir"
}

Write-Host "Open http://localhost:3000 after both services finish starting."
