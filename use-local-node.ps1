param()

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$localNodeDir = Join-Path $projectRoot ".tools\node-v20.20.2-win-x64"

if (-not (Test-Path $localNodeDir)) {
    throw "Local Node runtime not found at $localNodeDir"
}

$env:Path = "$localNodeDir;$env:Path"

Write-Host "Using local Node from $localNodeDir"
& (Join-Path $localNodeDir "node.exe") -v
& (Join-Path $localNodeDir "npm.cmd") -v
Write-Host "This shell now prefers the local Node runtime."
