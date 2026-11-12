# Windows 10/11 deployment metadata for laptop models with a catalog release-to-ship date from 2025.
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$CatalogXml,
    [Parameter(Mandatory)] [string]$OutputCsv
)

$ErrorActionPreference = 'Stop'
$catalog = [xml](Get-Content -LiteralPath $CatalogXml -Raw)
$recent = foreach ($pack in $catalog.DriverPackManifest.DriverPackage) {
    foreach ($brand in $pack.SupportedSystems.Brand) {
        if ($brand.Display.InnerText -notmatch 'Latitude|Notebook|Laptop') { continue }
        foreach ($model in $brand.Model) {
            if ($model.rtsDate -lt '2025-01-01' -or $model.name -match '\bTablet\b') { continue }
            foreach ($os in $pack.SupportedOperatingSystems.OperatingSystem) {
                if ($os.osCode -notin 'Windows10', 'Windows11') { continue }
                [pscustomobject]@{
                    model = $model.name
                    systemId = $model.systemID
                    releaseDate = $model.rtsDate.Substring(0, 10)
                    os = $os.osCode
                    architecture = $os.osArch
                    catalogDate = $pack.dateTime
                    metadata = if ($pack.DriverPackMetadataInfo.path) {
                        'https://downloads.dell.com/' + $pack.DriverPackMetadataInfo.path
                    } else { '' }
                }
            }
        }
    }
}

$latest = @($recent | Sort-Object catalogDate -Descending | Group-Object systemId,os,architecture |
    ForEach-Object { $_.Group[0] })
$urls = @($latest.metadata | Where-Object { $_ } | Sort-Object -Unique)
$results = $urls | ForEach-Object -ThrottleLimit 6 -Parallel {
    $url = $_
    try {
        $xml = [xml](Invoke-WebRequest -Uri $url -TimeoutSec 20 -ErrorAction Stop).Content
        [pscustomobject]@{ Url = $url; Xml = $xml; Error = $null }
    } catch {
        [pscustomobject]@{ Url = $url; Xml = $null; Error = $_.Exception.Message }
    }
}
$byUrl = @{}
foreach ($result in $results) { $byUrl[$result.Url] = $result }

$rows = foreach ($row in $latest) {
    $entry = $byUrl[$row.metadata]
    $system = $entry.Xml.Catalog.System | Where-Object SystemID -eq $row.systemId
    $os = $system.OS | Where-Object { $_.Name -eq $row.os -and $_.Arch -eq $row.architecture }
    $wlan = @($os.Release | Where-Object {
        $_.Category -eq 'network' -and $_.DeviceDescription -match 'Wi[\s-]*Fi|WLAN|Wireless LAN|FastConnect' -and
            @($_.Package | Where-Object SrcPath -Like '*.inf').Count
    })
    [pscustomobject]@{
        model = $row.model
        systemId = $row.systemId
        releaseDate = $row.releaseDate
        os = $row.os
        architecture = $row.architecture
        wlanEvidence = if ($wlan.Count) { 'oem-package-metadata' } elseif (!$entry.Xml) { 'metadata-unavailable' } elseif (!$system) { 'metadata-system-id-mismatch' } else { 'wlan-not-listed' }
        wlanReleaseIds = ($wlan.ReleaseID | Sort-Object -Unique) -join ';'
        wlanDescriptions = ($wlan.DeviceDescription | Sort-Object -Unique) -join ';'
        metadataUrl = $row.metadata
    }
}
$rows | Sort-Object model,systemId,os,architecture | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding utf8
$rows | Group-Object os,architecture,wlanEvidence | Select-Object Count,Name
