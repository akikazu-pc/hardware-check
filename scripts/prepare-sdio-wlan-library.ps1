param(
    [Parameter(Mandatory)] [string]$Archive,
    [Parameter(Mandatory)] [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
$archiveName = 'DP_WLAN-WiFi_26082.7z'
$expectedHash = '148C3234DD52E9EDD7B065148AE7A593398EE8FDE976DB664A17F71368E24528'
if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ne $expectedHash) {
    throw "The WLAN archive does not match the pinned SDIO snapshot $archiveName."
}

$originals = Join-Path $OutputDirectory 'vendor-installers'
$drivers = Join-Path $OutputDirectory 'driver-packs/sdio-wlan-wifi-26082'
New-Item -ItemType Directory -Path $drivers | Out-Null
$copy = Join-Path $originals $archiveName
Copy-Item -LiteralPath $archivePath -Destination $copy
if ((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'The copied archive did not match its expected hash.'
}

& (Join-Path ([Environment]::SystemDirectory) 'tar.exe') -xf $copy -C $drivers
if ($LASTEXITCODE -ne 0) {
    throw "Unable to unpack $archiveName."
}

$infCount = @(Get-ChildItem -LiteralPath $drivers -Recurse -File -Filter '*.inf').Count
if ($infCount -ne 1634) {
    throw "Unexpected INF count in $archiveName ($infCount)."
}

[ordered]@{
    source = 'https://www.glenn.delahoy.com/downloads/sdio/SDIO_Update.torrent'
    archive = $archiveName
    sha256 = $expectedHash
    infCount = $infCount
    distribution = 'local-build-only'
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'sdio-wlan-source.json') -Encoding utf8
