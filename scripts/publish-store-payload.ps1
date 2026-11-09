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
$shell = (Get-Process -Id $PID).Path
& $shell -NoProfile -File (Join-Path $PSScriptRoot 'assert-distribution.ps1') `
    -AssemblyPath $corePath -ExpectedChannel Store -ExpectedPawnIo Absent
if ($LASTEXITCODE -ne 0) {
    throw "Distribution assertion failed with exit code $LASTEXITCODE"
}

$licenses = Join-Path $output 'licenses'
Copy-Item -Recurse (Join-Path $root 'licenses') $licenses
Copy-Item (Join-Path $root 'THIRD-PARTY-NOTICES.md') $output
Copy-Item (Join-Path $root 'LICENSE') $output

Write-Output "Version: $version"
Write-Output 'Channel: Store'
Write-Output 'PawnIO installer: excluded'
Write-Output "Output: $output"
