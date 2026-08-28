[CmdletBinding()]
param(
    [switch]$FrontendOnly,
    [switch]$BackendOnly,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$frontendTaskName = 'ProductDbFrontend'
$composeFile = Join-Path $projectRoot 'docker-compose.server.yml'
$frontendLog = Join-Path $projectRoot 'frontend\frontend-prod.log'

if ($FrontendOnly -and $BackendOnly) {
    throw 'Use either -FrontendOnly or -BackendOnly, not both.'
}

function Restart-FrontendTask {
    Write-Host "Restarting scheduled task '$frontendTaskName'..."

    $task = Get-ScheduledTask -TaskName $frontendTaskName -ErrorAction Stop
    $taskInfo = Get-ScheduledTaskInfo -TaskName $frontendTaskName -ErrorAction Stop

    if ($task.State -eq 'Running') {
        Stop-ScheduledTask -TaskName $frontendTaskName
        Start-Sleep -Seconds 2
    }

    if (-not $SkipFrontendBuild) {
        Write-Host 'Building frontend before task start...'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'run-frontend-prod.ps1') -BuildOnly
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            throw "Frontend build/start script failed with exit code $exitCode"
        }
    }

    Start-ScheduledTask -TaskName $frontendTaskName
    Start-Sleep -Seconds 3

    $updatedTask = Get-ScheduledTask -TaskName $frontendTaskName -ErrorAction Stop
    $updatedInfo = Get-ScheduledTaskInfo -TaskName $frontendTaskName -ErrorAction Stop
    Write-Host ("Task state: {0}; LastTaskResult: {1}" -f $updatedTask.State, $updatedInfo.LastTaskResult)
}

function Restart-BackendStack {
    if (-not (Test-Path $composeFile)) {
        throw "Compose file not found: $composeFile"
    }

    Set-Location $projectRoot
    Write-Host 'Restarting backend stack via docker compose...'
    & docker compose -f $composeFile up -d --build
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "docker compose failed with exit code $exitCode"
    }
}

if (-not $FrontendOnly) {
    if ($BackendOnly -or (-not $FrontendOnly -and -not $BackendOnly)) {
        Restart-BackendStack
    }
}

if (-not $BackendOnly) {
    if ($FrontendOnly -or (-not $FrontendOnly -and -not $BackendOnly)) {
        Restart-FrontendTask
    }
}

Write-Host 'Restart flow completed.'
