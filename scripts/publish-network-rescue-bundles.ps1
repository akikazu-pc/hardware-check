[CmdletBinding()]
param(
    [string]$RealtekVendorZip,
    [switch]$IncludeCatalog,
    [string]$VendorSourceDirectory,
    [string]$WlanArchive
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if ($WlanArchive) {
    if (-not $IncludeCatalog) {
        throw 'Use -IncludeCatalog with -WlanArchive.'
    }
    $WlanArchive = (Resolve-Path -LiteralPath $WlanArchive).Path
}

if ($RealtekVendorZip) {
    $RealtekVendorZip = (Resolve-Path -LiteralPath $RealtekVendorZip).Path
}

& (Join-Path $PSScriptRoot 'publish.ps1')
if ($LASTEXITCODE -ne 0) {
    throw "Self-contained payload build failed ($LASTEXITCODE)."
}

$version = ([xml](Get-Content (Join-Path $root 'Directory.Build.props'))).Project.PropertyGroup.Version
$releasePayload = Join-Path $root "artifacts/release/AkikazuHardwareCheck-$version-win-x64"
$output = Join-Path $root 'artifacts/network-rescue'
New-Item -ItemType Directory -Path $output -Force | Out-Null
$staging = New-Item -ItemType Directory -Path (Join-Path $output ('.bundle-' + [Guid]::NewGuid()))
try {
    $scripts = Join-Path $staging.FullName 'scripts/prototype'
    $manifest = Join-Path $staging.FullName 'packaging/shared-desktop'
    New-Item -ItemType Directory -Path $scripts, $manifest | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'prototype/SharedDesktopPrototype.psm1') -Destination $scripts
    Copy-Item -LiteralPath (Join-Path $root 'packaging/shared-desktop/app-identities.json') -Destination $manifest
    Copy-Item -LiteralPath (Join-Path $root 'Directory.Build.props') -Destination $staging.FullName
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'prototype/install-network-rescue-bundle.ps1') -Destination (Join-Path $staging.FullName 'install.ps1')
    Copy-Item -LiteralPath $releasePayload -Destination (Join-Path $staging.FullName 'payload') -Recurse
    @"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 pause
"@ | Set-Content -LiteralPath (Join-Path $staging.FullName 'Install.cmd') -Encoding ascii

    $flavors = @('slim')
    if ($IncludeCatalog) {
        $flavors += $(if ($WlanArchive) { 'offline-wlan-library' } else { 'offline-catalog' })
    }
    if ($RealtekVendorZip -and -not $IncludeCatalog) {
        $flavors += 'offline-preview'
    }

    foreach ($flavor in $flavors) {
        if ($flavor -eq 'offline-preview') {
            $packRoot = Join-Path $staging.FullName 'driver-packs'
            New-Item -ItemType Directory -Path $packRoot | Out-Null
            & (Join-Path $PSScriptRoot 'prototype/prepare-realtek-wifi-pack.ps1') -VendorZip $RealtekVendorZip `
                -OutputDirectory (Join-Path $packRoot 'realtek-8852-wifi-6001.16.172.0')
        }

        if ($flavor -in 'offline-catalog', 'offline-wlan-library') {
            & (Join-Path $PSScriptRoot 'prepare-network-rescue-packs.ps1') -OutputDirectory $staging.FullName -VendorSourceDirectory $VendorSourceDirectory
        }

        if ($flavor -eq 'offline-wlan-library') {
            & (Join-Path $PSScriptRoot 'prepare-sdio-wlan-library.ps1') -Archive $WlanArchive -OutputDirectory $staging.FullName
        }

        $name = "NetworkRescue-$version-$flavor-win-x64.zip"
        $archive = Join-Path $output $name
        Compress-Archive -Path (Join-Path $staging.FullName '*') -DestinationPath $archive -CompressionLevel Fastest -Force
        $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
        Set-Content -LiteralPath "$archive.sha256" -Value "$hash  $name" -Encoding ascii
        Write-Output "Output: $archive"
    }
}
finally {
    $resolvedStaging = (Resolve-Path -LiteralPath $staging.FullName).Path
    if ((Split-Path -Parent $resolvedStaging) -eq $output -and
        (Split-Path -Leaf $resolvedStaging) -like '.bundle-*') {
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
}
