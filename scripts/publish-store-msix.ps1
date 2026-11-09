param(
    [Parameter(Mandatory = $true)]
    [string]$IdentityName,

    [Parameter(Mandatory = $true)]
    [string]$Publisher,

    [Parameter(Mandatory = $true)]
    [string]$PublisherDisplayName,

    [string]$AssetsPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'packaging/store/Assets'),

    [Parameter(Mandatory = $true)]
    [string]$MakeAppxPath
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$version = ([xml](Get-Content (Join-Path $root 'Directory.Build.props'))).Project.PropertyGroup.Version
$msixVersion = "$version.0"
$payload = Join-Path $root "artifacts/store/AkikazuHardwareCheck-$version-win-x64"
$output = Join-Path $root 'artifacts/store'
$msix = Join-Path $output "AkikazuHardwareCheck-$version-win-x64.msix"
$template = Join-Path $root 'packaging/store/Package.appxmanifest.template'
$requiredAssets = @('StoreLogo.png', 'Square44x44Logo.png', 'Square150x150Logo.png', 'Wide310x150Logo.png')

foreach ($value in @($IdentityName, $Publisher, $PublisherDisplayName)) {
    if ([string]::IsNullOrWhiteSpace($value) -or $value.Contains('{{')) {
        throw 'Partner Center identity values must be real and non-empty.'
    }
}

$makeAppx = (Resolve-Path $MakeAppxPath).Path
$assetFolder = (Resolve-Path $AssetsPath).Path
foreach ($name in $requiredAssets) {
    if (-not (Test-Path (Join-Path $assetFolder $name))) {
        throw "Missing Store asset: $name"
    }
}

& (Join-Path $PSScriptRoot 'publish-store-payload.ps1')
if ($LASTEXITCODE -ne 0) {
    throw "Store payload build failed with exit code $LASTEXITCODE"
}

$staging = Join-Path $output "staging-$version"
if (Test-Path $staging) {
    Remove-Item -Recurse -Force $staging
}

Copy-Item -Recurse $payload $staging
$stagingAssets = Join-Path $staging 'Assets'
New-Item -ItemType Directory -Force $stagingAssets | Out-Null
foreach ($name in $requiredAssets) {
    Copy-Item (Join-Path $assetFolder $name) $stagingAssets
}

$manifest = Get-Content -Raw $template
$manifest = $manifest.Replace('{{IdentityName}}', $IdentityName)
$manifest = $manifest.Replace('{{Publisher}}', $Publisher)
$manifest = $manifest.Replace('{{PublisherDisplayName}}', $PublisherDisplayName)
$manifest = $manifest.Replace('{{Version}}', $msixVersion)
Set-Content -Path (Join-Path $staging 'AppxManifest.xml') -Value $manifest -Encoding utf8

& $makeAppx pack /d $staging /p $msix /o
if ($LASTEXITCODE -ne 0) {
    throw "MakeAppx failed with exit code $LASTEXITCODE"
}

$hash = (Get-FileHash $msix -Algorithm SHA256).Hash
Set-Content -Path (Join-Path $output 'MSIX-SHA256.txt') -Value "$hash  $(Split-Path -Leaf $msix)" -Encoding ascii

Write-Output "Version: $msixVersion"
Write-Output 'Channel: Store'
Write-Output "Output: $msix"
Write-Output "SHA-256: $hash"
