[CmdletBinding()]
param(
    [string]$BackendUrl = 'http://127.0.0.1:8001',
    [string]$FrontendUrl = 'http://127.0.0.1:3002',
    [string]$ApiKey,
    [string]$TaskName = 'ProductDbFrontend'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Check {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Details
    )

    [pscustomobject]@{
        Check   = $Name
        Status  = $Status
        Details = $Details
    }
}

function Get-HttpStatusCode {
    param(
        [scriptblock]$Request
    )

    try {
        $response = & $Request
        return [pscustomobject]@{
            StatusCode = [int]$response.StatusCode
            Error      = $null
        }
    } catch {
        $statusCode = $null
        $responseProperty = $_.Exception.PSObject.Properties['Response']
        if ($responseProperty -and $responseProperty.Value -and $responseProperty.Value.StatusCode) {
            $statusCode = [int]$responseProperty.Value.StatusCode
        }

        return [pscustomobject]@{
            StatusCode = $statusCode
            Error      = $_.Exception.Message
        }
    }
}

$results = New-Object System.Collections.Generic.List[object]
$headers = @{}
if ($ApiKey) {
    $headers['X-API-Key'] = $ApiKey
}

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
    $results.Add((Write-Check -Name 'ScheduledTask' -Status 'OK' -Details ("State={0}; LastTaskResult={1}" -f $task.State, $taskInfo.LastTaskResult)))
} catch {
    $results.Add((Write-Check -Name 'ScheduledTask' -Status 'FAIL' -Details $_.Exception.Message))
}

foreach ($port in 3002, 8001, 5436, 6382) {
    try {
        $conn = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop | Select-Object -First 1
        $results.Add((Write-Check -Name "Port $port" -Status 'OK' -Details ("Listening on {0}:{1}" -f $conn.LocalAddress, $conn.LocalPort)))
    } catch {
        $results.Add((Write-Check -Name "Port $port" -Status 'FAIL' -Details 'Not listening'))
    }
}

$backendHealth = Get-HttpStatusCode {
    Invoke-WebRequest -UseBasicParsing -Headers $headers -Uri ($BackendUrl.TrimEnd('/') + '/health') -TimeoutSec 10
}

if ($backendHealth.StatusCode -eq 200) {
    $results.Add((Write-Check -Name 'BackendHealth' -Status 'OK' -Details 'HTTP 200'))
} elseif (-not $ApiKey -and $backendHealth.StatusCode -eq 401) {
    $results.Add((Write-Check -Name 'BackendHealth' -Status 'WARN' -Details 'HTTP 401 (API key required)'))
} else {
    $details = if ($backendHealth.StatusCode) {
        "HTTP $($backendHealth.StatusCode)"
    } else {
        $backendHealth.Error
    }
    $results.Add((Write-Check -Name 'BackendHealth' -Status 'FAIL' -Details $details))
}

try {
    $frontendRoot = Invoke-WebRequest -UseBasicParsing -Uri $FrontendUrl -TimeoutSec 10
    $results.Add((Write-Check -Name 'FrontendRoot' -Status 'OK' -Details ("HTTP {0}" -f $frontendRoot.StatusCode)))
} catch {
    $results.Add((Write-Check -Name 'FrontendRoot' -Status 'FAIL' -Details $_.Exception.Message))
}

$proxyStats = Get-HttpStatusCode {
    Invoke-WebRequest `
        -UseBasicParsing `
        -Headers $headers `
        -Uri ($FrontendUrl.TrimEnd('/') + '/api/v1/stats/pipeline') `
        -TimeoutSec 15
}

if ($proxyStats.StatusCode -eq 200) {
    $results.Add((Write-Check -Name 'FrontendApiProxy' -Status 'OK' -Details 'HTTP 200'))
} elseif (-not $ApiKey -and $proxyStats.StatusCode -eq 401) {
    $results.Add((Write-Check -Name 'FrontendApiProxy' -Status 'WARN' -Details 'HTTP 401 (API key required)'))
} else {
    $details = if ($proxyStats.StatusCode) {
        "HTTP $($proxyStats.StatusCode)"
    } else {
        $proxyStats.Error
    }
    $results.Add((Write-Check -Name 'FrontendApiProxy' -Status 'FAIL' -Details $details))
}

$results | Format-Table -AutoSize

$okCount = @($results | Where-Object { $_.Status -eq 'OK' }).Count
$warnCount = @($results | Where-Object { $_.Status -eq 'WARN' }).Count
$failCount = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count

Write-Host ("SUMMARY OK={0} WARN={1} FAIL={2}" -f $okCount, $warnCount, $failCount)

$failed = @($results | Where-Object { $_.Status -eq 'FAIL' })
if ($failed.Count -gt 0) {
    exit 1
}
