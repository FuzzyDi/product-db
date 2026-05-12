[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$UserName,

    [Parameter(Mandatory = $true)]
    [string]$Password,

    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$scriptPath = Join-Path $PSScriptRoot 'run-frontend-prod.ps1'
$taskName = 'ProductDbFrontend'

if (-not (Test-Path $scriptPath)) {
    throw "Launcher script not found: $scriptPath"
}

$skipBuildArg = if ($SkipBuild) { ' -SkipBuild' } else { '' }
$escapedScriptPath = '"' + $scriptPath + '"'
$arguments = "-NoProfile -ExecutionPolicy Bypass -File $escapedScriptPath$skipBuildArg"

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -User $UserName `
    -Password $Password `
    -RunLevel Highest `
    -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Write-Host "Scheduled task '$taskName' registered and started."
