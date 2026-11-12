param(
    [Parameter(Mandatory)] [string] $VendorZip,
    [Parameter(Mandatory)] [string] $OutputDirectory
)

$ErrorActionPreference = 'Stop'
$vendorZipPath = (Resolve-Path -LiteralPath $VendorZip).Path
$expectedArchiveHash = 'A6CD81E7792678D6BCB7A9F791C2CBD1972BC653B7A3A4102D0AF342F8038725'
if ((Get-FileHash -LiteralPath $vendorZipPath -Algorithm SHA256).Hash -ne $expectedArchiveHash) {
    throw 'The ZIP does not match the pinned Gigabyte Realtek Wi-Fi 6001.16.172.0 archive.'
}

$outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
if (Test-Path -LiteralPath $outputPath) {
    throw 'Choose a new output directory.'
}

$outputParent = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputParent -PathType Container)) {
    throw 'The parent of the output directory must exist.'
}
$staging = New-Item -ItemType Directory -Path (Join-Path $outputParent ('.akikazu-wifi-' + [Guid]::NewGuid()))
try {
    $zipPath = Join-Path $staging.FullName 'archive'
    $payload = Join-Path $staging.FullName 'payload'
    Expand-Archive -LiteralPath $vendorZipPath -DestinationPath $zipPath
    New-Item -ItemType Directory -Path $payload | Out-Null
    $sfx = Join-Path $zipPath 'mb_driver_674_realtek8852wifi_6001.16.172.0.exe'
    & (Join-Path ([Environment]::SystemDirectory) 'tar.exe') -xf $sfx -C $payload
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not unpack the vendor archive.'
    }

    $driver = Join-Path $payload 'RTWLANE_Driver/Win10X64'
    $notice = Join-Path $payload 'Copyright Notice.txt'
    $expectedInfHash = '964C9F9D17BE4F1FA4965DCE8E681A399373FBFD12B0A1746A4BBD65A406753C'
    if ((Get-FileHash -LiteralPath (Join-Path $driver 'netrtwlane602.inf')).Hash -ne $expectedInfHash) {
        throw 'The extracted INF does not match the pinned driver.'
    }

    $package = Join-Path $staging.FullName 'realtek-8852-wifi-6001.16.172.0'
    New-Item -ItemType Directory -Path $package | Out-Null
    Copy-Item -LiteralPath $driver -Destination $package -Recurse
    Copy-Item -LiteralPath $notice -Destination $package
    Move-Item -LiteralPath $package -Destination $outputPath
}
finally {
    $resolvedStaging = (Resolve-Path -LiteralPath $staging.FullName).Path
    if ((Split-Path -Parent $resolvedStaging) -eq $outputParent -and
        (Split-Path -Leaf $resolvedStaging) -like '.akikazu-wifi-*') {
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
}
