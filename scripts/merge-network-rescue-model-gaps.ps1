[CmdletBinding()]
param(
    [string]$CatalogDirectory = (Join-Path $PSScriptRoot '../docs')
)

$ErrorActionPreference = 'Stop'
$CatalogDirectory = (Resolve-Path -LiteralPath $CatalogDirectory).Path
$gapPath = Join-Path $CatalogDirectory 'network-rescue-model-gaps.csv'
$existing = @(Import-Csv -LiteralPath $gapPath)
if ($existing.Count -eq 0) {
    throw "Model gap index is empty: $gapPath"
}
$supplements = @(
    @{ Type = 'motherboard'; File = 'asrock-motherboard-discovery.csv' }
    @{ Type = 'motherboard'; File = 'additional-motherboard-discovery.csv' }
    @{ Type = 'laptop'; File = 'network-rescue-oem-laptops.csv' }
    @{ Type = 'all-in-one'; File = 'network-rescue-oem-all-in-ones.csv' }
)

$keys = @{}
foreach ($row in $existing) {
    # Dell's system/OS rows are a separate evidence stream.
    if ($row.type -ne 'laptop-os-record') {
        $keys["$($row.type)|$($row.brand)|$($row.model)"] = $row
    }
}

$added = [Collections.Generic.List[object]]::new()
$changed = $false
foreach ($supplement in $supplements) {
    $inputPath = Join-Path $CatalogDirectory $supplement.File
    $catalog = @(Import-Csv -LiteralPath $inputPath)
    if ($catalog.Count -eq 0) {
        throw "Supplemental catalog is empty: $inputPath"
    }

    foreach ($entry in $catalog) {
        $brand = ([string]$entry.brand).Trim()
        $model = ([string]$entry.model).Trim()
        $platform = ([string]$entry.platform).Trim()
        if (!$brand -or !$model -or ($supplement.Type -eq 'motherboard' -and !$platform) -or
            $entry.officialUrl -notmatch '^https://[^/]+/') {
            throw "Incomplete official catalog row for $brand $model in $inputPath"
        }

        $key = "$($supplement.Type)|$brand|$model"
        $windows10 = if ($entry.windows10Evidence) { $entry.windows10Evidence } else { 'pending' }
        $windows11 = if ($entry.windows11Evidence) { $entry.windows11Evidence } else { 'pending' }
        if ($keys.ContainsKey($key)) {
            $row = $keys[$key]
            if ($row.wlanEvidence -in 'oem-model-catalog', 'oem-series-catalog' -and
                $entry.urlKind -eq 'support' -and $row.source -ne $entry.officialUrl) {
                $row.source = $entry.officialUrl
                $changed = $true
            }
            if ($row.windows10X64Evidence -eq 'pending' -and $windows10 -ne 'pending') {
                $row.windows10X64Evidence = $windows10
                $changed = $true
            }
            if ($row.windows11X64Evidence -eq 'pending' -and $windows11 -ne 'pending') {
                $row.windows11X64Evidence = $windows11
                $changed = $true
            }
            continue
        }

        $isSeries = $entry.modelGranularity -eq 'series'
        $row = [pscustomobject][ordered]@{
            type = $supplement.Type
            brand = $brand
            model = $model
            platform = $platform
            os = ''
            wlanEvidence = if ($isSeries) { 'oem-series-catalog' } else { 'oem-model-catalog' }
            module = ''
            gap = if ($isSeries) { 'sku-and-wifi-variant-driver-install' } else { 'factory-wifi-status-module-driver-install' }
            source = $entry.officialUrl
            windows10X64Evidence = $windows10
            windows11X64Evidence = $windows11
            deviceCategory = $entry.deviceCategory
            deviceTag = $entry.deviceTag
        }
        $keys[$key] = $row
        $added.Add($row)
        $changed = $true
    }
}

$all = $existing + @($added | Sort-Object type,brand,platform,model)
$otherTags = 'BrandedDesktop', 'MiniPc', 'WindowsTablet', 'Handheld', 'AllInOne', 'Htpc',
    'SingleBoardComputer', 'WindowsPhone', 'Mac', 'ModifiedChromebook'
foreach ($row in $all) {
    if (!$row.deviceCategory) {
        $category = switch ($row.type) {
            'motherboard' { 'DiyDesktop' }
            { $_ -in 'laptop', 'laptop-os-record' } { 'Laptop' }
            default { 'Other' }
        }
        $row | Add-Member -NotePropertyName deviceCategory -NotePropertyValue $category -Force
        $changed = $true
    }
    if (!$row.PSObject.Properties['deviceTag'] -or (!$row.deviceTag -and $row.type -eq 'all-in-one')) {
        $tag = if ($row.type -eq 'all-in-one') { 'AllInOne' } else { '' }
        $row | Add-Member -NotePropertyName deviceTag -NotePropertyValue $tag -Force
        $changed = $true
    }
    if ($row.deviceCategory -cnotin 'DiyDesktop', 'Laptop', 'Other' -or
        ($row.deviceTag -and ($row.deviceCategory -cne 'Other' -or $row.deviceTag -cnotin $otherTags))) {
        throw "Invalid device category or tag for $($row.brand) $($row.model)"
    }
}

if ($changed) {
    $temporaryPath = $gapPath + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        $all | Export-Csv -LiteralPath $temporaryPath -NoTypeInformation -Encoding utf8
        Move-Item -LiteralPath $temporaryPath -Destination $gapPath -Force
    } finally {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath
        }
    }
}

$all | Group-Object type,brand | ForEach-Object {
    $windows10 = @($_.Group | Where-Object { $_.type -ne 'laptop-os-record' -or $_.os -eq 'Windows10 x64' })
    $windows11 = @($_.Group | Where-Object { $_.type -ne 'laptop-os-record' -or $_.os -eq 'Windows11 x64' })
    [pscustomobject]@{
        group = $_.Name
        records = $_.Count
        windows10Records = $windows10.Count
        windows10Pending = @($windows10 | Where-Object windows10X64Evidence -eq 'pending').Count
        windows11Records = $windows11.Count
        windows11Pending = @($windows11 | Where-Object windows11X64Evidence -eq 'pending').Count
    }
}
