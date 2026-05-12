[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$frontendDir = Join-Path $projectRoot 'frontend'
$logPath = Join-Path $frontendDir 'frontend-prod.log'

if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found: $frontendDir"
}

if ($SkipBuild -and $BuildOnly) {
    throw 'Use either -SkipBuild or -BuildOnly, not both.'
}

Set-Location $frontendDir

if (-not $SkipBuild) {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend build failed with exit code $LASTEXITCODE"
    }
}

if ($BuildOnly) {
    Write-Host 'Frontend build completed.'
    exit 0
}

$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"[$timestamp] Starting frontend production server" | Out-File -FilePath $logPath -Encoding utf8 -Append

& npm.cmd run serve:prod *>> $logPath
exit $LASTEXITCODE
