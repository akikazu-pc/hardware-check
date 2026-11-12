[CmdletBinding()]
param([Parameter(Mandatory)] [string]$DriverDirectory)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$core = Join-Path $root 'src/AkikazuHardwareCheck.Core/bin/Release/net10.0-windows/win-x64/AkikazuHardwareCheck.Core.dll'
[void][Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $core).Path)

$hardwareIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$signedIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$infs = @(Get-ChildItem -LiteralPath $DriverDirectory -Recurse -File -Filter '*.inf')
$matchedInfCount = 0
$signedInfCount = 0
$unreadableInfCount = 0
$pattern = '(?i)(?:PCI\\VEN_[0-9A-F]{4}&DEV_[0-9A-F]{4}|USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4})(?:&[A-Z0-9_]+)*'

foreach ($inf in $infs) {
    $ids = @([regex]::Matches((Get-Content -LiteralPath $inf.FullName -Raw), $pattern) |
        ForEach-Object Value | Sort-Object -Unique)
    if (!$ids.Count) {
        continue
    }

    $devices = [AkikazuHardwareCheck.Core.SharedDesktop.NetworkDeviceCandidate[]]@(
        foreach ($id in $ids) {
            [AkikazuHardwareCheck.Core.SharedDesktop.NetworkDeviceCandidate]::new(
                [string[]]@($id), $null, 28, [AkikazuHardwareCheck.Core.SharedDesktop.NetworkCandidateKind]::PciController)
        }
    )
    try {
        $matches = [AkikazuHardwareCheck.Core.SharedDesktop.OfflineInfMatcher]::Match($inf.FullName, $devices)
    } catch {
        if ($_.Exception.InnerException -isnot [ComponentModel.Win32Exception]) { throw }
        $unreadableInfCount++
        continue
    }
    if (!$matches.Count) { continue }

    $matchedInfCount++
    $signature = [AkikazuHardwareCheck.Core.SharedDesktop.OfflineDriverInstaller]::Verify($inf.FullName)
    if ($signature) { $signedInfCount++ }
    foreach ($match in $matches) {
        [void]$hardwareIds.Add($match.HardwareId)
        if ($signature) { [void]$signedIds.Add($match.HardwareId) }
    }
}

[pscustomobject]@{
    WindowsBuild = [Environment]::OSVersion.Version.Build
    InfFiles = $infs.Count
    ApplicableMatchingInfs = $matchedInfCount
    SignatureVerifiedInfs = $signedInfCount
    MatchedLiteralHardwareIds = $hardwareIds.Count
    SignatureVerifiedPciIds = @($signedIds | Where-Object { $_ -like 'PCI\*' }).Count
    SignatureVerifiedUsbIds = @($signedIds | Where-Object { $_ -like 'USB\*' }).Count
    UnreadableInfsWithLiteralIds = $unreadableInfCount
}
