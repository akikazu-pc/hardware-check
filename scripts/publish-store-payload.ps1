# Builds the unprivileged payload that will be placed in the Microsoft Store MSIX package.
# Partner Center identity and visual assets are intentionally handled by the later packaging step.
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'src/AkikazuHardwareCheck.App/AkikazuHardwareCheck.App.csproj'
$version = ([xml](Get-Content (Join-Path $root 'Directory.Build.props'))).Project.PropertyGroup.Version
$output = Join-Path $root "artifacts/store/AkikazuHardwareCheck-$version-win-x64"

if (Test-Path $output) {
    Remove-Item -Recurse -Force $output
}

# Keep the same single-file application layout as the website build. MSIX packaging is a separate later step.
dotnet publish $project -c Release --self-contained true -o $output --nologo `
    -p:DistributionChannel=Store -p:DebugType=None
if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish failed with exit code $LASTEXITCODE"
}

$corePath = Join-Path $root 'src/AkikazuHardwareCheck.Core/bin/Release/net10.0-windows/win-x64/AkikazuHardwareCheck.Core.dll'
$core = [System.Reflection.Assembly]::LoadFile($corePath)
$resources = $core.GetManifestResourceNames()
if ($resources -contains 'pawnio.setup.exe') {
    throw 'Store payload contains the PawnIO installer.'
}

$channel = $core.GetCustomAttributesData() |
    Where-Object { $_.AttributeType.Name -eq 'AssemblyMetadataAttribute' } |
    Where-Object { $_.ConstructorArguments[0].Value -eq 'DistributionChannel' } |
    ForEach-Object { $_.ConstructorArguments[1].Value }
if ($channel -ne 'Store') {
    throw "Unexpected distribution channel: $channel"
}

$licenses = Join-Path $output 'licenses'
Copy-Item -Recurse (Join-Path $root 'licenses') $licenses
Copy-Item (Join-Path $root 'THIRD-PARTY-NOTICES.md') $output
Copy-Item (Join-Path $root 'LICENSE') $output

Write-Output "Version: $version"
Write-Output "Channel: $channel"
Write-Output 'PawnIO installer: excluded'
Write-Output "Output: $output"
