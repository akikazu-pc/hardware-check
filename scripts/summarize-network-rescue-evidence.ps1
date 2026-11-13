# Summarizes Network Rescue field acceptance evidence JSON files into a matrix.
# Read-only: it never touches the machine under test and only reads the collected JSON.
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$EvidenceDirectory,

    [string]$OutputPath,

    # Exit 1 when any scenario is not Pass (Inbox/Incomplete/Fail all count).
    [switch]$FailOnIncomplete
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

function Read-Evidence([string]$Directory) {
    $reports = @()
    foreach ($file in Get-ChildItem -LiteralPath $Directory -Filter '*.json' -File) {
        try {
            $report = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
        } catch {
            Write-Warning "Skip unreadable JSON: $($file.Name)"
            continue
        }
        if ($null -eq $report.stage -or $null -eq $report.scenario) {
            Write-Warning "Skip JSON without stage/scenario: $($file.Name)"
            continue
        }
        $reports += [pscustomobject]@{ File = $file.Name; Report = $report }
    }
    return $reports
}

function Get-Devices($Report) {
    if ($null -eq $Report.devices) { return @() }
    return @($Report.devices)
}

function Find-TargetDevice($Devices, $HardwareIds) {
    if ($null -eq $HardwareIds -or $HardwareIds.Count -eq 0) { return $null }
    foreach ($device in $Devices) {
        foreach ($candidate in @($device.hardwareIds)) {
            if ($HardwareIds -contains $candidate) { return $device }
        }
    }
    return $null
}

function Test-Final($Device, $Connectivity) {
    $results = [ordered]@{}
    $results['problemCode=0'] = ($Device.problemCode -eq 0)
    $results['signed driver'] = ($null -ne $Device.driver -and $Device.driver.isSigned -eq $true -and
        -not [string]::IsNullOrEmpty([string]$Device.driver.infName))
    $results['adapter Up'] = ($null -ne $Device.adapter -and $Device.adapter.status -eq 'Up')
    $results['gateway'] = ($null -ne $Device.adapter -and
        ($Device.adapter.hasIpv4Gateway -eq $true -or $Device.adapter.hasIpv6Gateway -eq $true))
    $results['DNS server'] = ($null -ne $Device.adapter -and $Device.adapter.dnsServerCount -gt 0)
    $results['DNS resolve'] = ($null -ne $Connectivity -and $Connectivity.dnsResolved -eq $true)
    $results['HTTPS 2xx/3xx'] = ($null -ne $Connectivity -and $null -ne $Connectivity.httpsStatus -and
        [int]$Connectivity.httpsStatus -ge 200 -and [int]$Connectivity.httpsStatus -le 399)
    return $results
}

$reports = Read-Evidence -Directory (Resolve-Path -LiteralPath $EvidenceDirectory).Path
if ($reports.Count -eq 0) { throw "No evidence JSON found in $EvidenceDirectory." }

$byScenario = [ordered]@{}
foreach ($entry in $reports) {
    $scenario = [string]$entry.Report.scenario
    if (-not $byScenario.Contains($scenario)) { $byScenario[$scenario] = @{} }
    $stage = [string]$entry.Report.stage
    $existing = $byScenario[$scenario][$stage]
    if ($null -eq $existing -or ([datetime]$entry.Report.recordedAtUtc) -gt ([datetime]$existing.Report.recordedAtUtc)) {
        $byScenario[$scenario][$stage] = $entry
    }
}

$rows = @()
$failures = 0
$incomplete = 0
$inbox = 0
$passed = 0

foreach ($scenario in $byScenario.Keys) {
    $stages = $byScenario[$scenario]
    $baseline = $stages['baseline']
    $final = $stages['after-restart']
    $finalName = 'after-restart'
    if ($null -eq $final) {
        $final = $stages['after-install']
        $finalName = 'after-install'
    }

    $verdict = 'Incomplete'
    $detail = ''
    $baselineText = ''
    $target = $null

    if ($null -ne $baseline) {
        $baselineDevices = Get-Devices $baseline.Report
        $targets = @($baselineDevices | Where-Object { $null -ne $_ -and $_.problemCode -eq 28 })
        if ($targets.Count -gt 0) {
            $target = $targets[0]
            $baselineText = "$($target.name) problemCode 28"
        } else {
            $bound = @($baselineDevices | Where-Object {
                $null -ne $_ -and $null -ne $_.driver -and $_.driver.isSigned -eq $true
            })
            if ($bound.Count -gt 0) {
                $verdict = 'Inbox'
                $baselineText = "$($bound[0].name) signed driver bound"
            } else {
                $verdict = 'Fail'
                $detail = 'baseline has no problemCode 28 device and no signed bound device'
            }
        }
    }

    if ($null -ne $baseline -and $null -ne $final -and $null -ne $target -and $verdict -ne 'Inbox') {
        $finalDevices = Get-Devices $final.Report
        $ids = @($target.hardwareIds)
        $device = Find-TargetDevice $finalDevices $ids
        $withAdapter = @($finalDevices | Where-Object { $null -ne $_ -and $null -ne $_.adapter })
        if ($null -eq $device -and $withAdapter.Count -gt 0) { $device = $withAdapter[0] }
        if ($null -eq $device) {
            $verdict = 'Fail'
            $detail = 'final stage has no network device'
        } else {
            $checks = Test-Final $device $final.Report.connectivity
            $failed = @($checks.Keys | Where-Object { -not $checks[$_] })
            if ($failed.Count -eq 0) {
                $verdict = 'Pass'
            } else {
                $verdict = 'Fail'
                $detail = 'failed: ' + ($failed -join ', ')
            }
        }
    } elseif ($null -eq $final -and $verdict -ne 'Inbox' -and $verdict -ne 'Fail') {
        $missing = 'after-install/after-restart'
        if ($null -eq $baseline) { $missing = 'baseline' }
        $detail = "missing $missing"
    }

    switch ($verdict) {
        'Pass' { $passed++ }
        'Inbox' { $inbox++ }
        'Incomplete' { $incomplete++ }
        default { $failures++ }
    }

    $finalStageText = ''
    if ($null -ne $final) { $finalStageText = $finalName }

    $rows += [pscustomobject]@{
        Scenario   = $scenario
        Baseline   = $baselineText
        FinalStage = $finalStageText
        Verdict    = $verdict
        Detail     = $detail
    }
}

$lines = @()
$lines += '| Scenario | Baseline | Final stage | Verdict | Detail |'
$lines += '| --- | --- | --- | --- | --- |'
foreach ($row in $rows) {
    $lines += "| $($row.Scenario) | $($row.Baseline) | $($row.FinalStage) | $($row.Verdict) | $($row.Detail) |"
}
$lines += ''
$lines += "Totals: Pass $passed, Inbox $inbox, Incomplete $incomplete, Fail $failures."

$text = $lines -join [Environment]::NewLine
Write-Output $text
if ($OutputPath) {
    $resolved = [IO.Path]::GetFullPath($OutputPath)
    [IO.File]::WriteAllText($resolved, $text, (New-Object Text.UTF8Encoding($false)))
    Write-Output "Wrote $resolved"
}

if ($FailOnIncomplete -and ($failures -gt 0 -or $incomplete -gt 0 -or $inbox -gt 0)) {
    exit 1
}
exit 0
