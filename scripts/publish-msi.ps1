param(
    [Parameter(Mandatory = $true)]
    [string]$WixExecutable,

    [Parameter(Mandatory = $true)]
    [switch]$ToolLicenseApproved
)

# WiX v6+ can require an Open Source Maintenance Fee for revenue-generating use. This script never downloads WiX or
# accepts its EULA. The caller must supply an approved executable after confirming the applicable terms.
$ErrorActionPreference = 'Stop'

if (-not $ToolLicenseApproved) {
    throw 'Confirm the WiX license before building the MSI.'
}

$root = Split-Path -Parent $PSScriptRoot
$wix = (Resolve-Path $WixExecutable).Path
$source = Join-Path $root 'packaging/msi/Package.wxs'
$version = ([xml](Get-Content (Join-Path $root 'Directory.Build.props'))).Project.PropertyGroup.Version
$payload = Join-Path $root "artifacts/release/AkikazuHardwareCheck-$version-win-x64"
$output = Join-Path $root 'artifacts/msi'
$msi = Join-Path $output "AkikazuHardwareCheck-$version-win-x64.msi"

& (Join-Path $PSScriptRoot 'publish.ps1')
if ($LASTEXITCODE -ne 0) {
    throw "Portable payload build failed with exit code $LASTEXITCODE"
}

New-Item -ItemType Directory -Force $output | Out-Null
& $wix build $source -arch x64 -d "ProductVersion=$version" -d "PayloadDir=$payload" -o $msi
if ($LASTEXITCODE -ne 0) {
    throw "WiX build failed with exit code $LASTEXITCODE"
}

$hash = (Get-FileHash $msi -Algorithm SHA256).Hash
Set-Content -Path (Join-Path $output 'SHA256.txt') -Value "$hash  $(Split-Path -Leaf $msi)" -Encoding ascii

Write-Output "Version: $version"
Write-Output 'Channel: Website'
Write-Output "Output: $msi"
Write-Output "SHA-256: $hash"
