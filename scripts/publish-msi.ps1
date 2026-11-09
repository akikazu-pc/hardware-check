param(
    [string]$AdvancedInstallerPath = $env:ADVINST_COM
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($AdvancedInstallerPath)) {
    throw 'Advanced Installer Freeware is not installed. Install the current maintained Freeware edition, then rerun; v22+ exposes ADVINST_COM automatically.'
}

$root = Split-Path -Parent $PSScriptRoot
$tool = (Resolve-Path $AdvancedInstallerPath).Path
$version = ([xml](Get-Content (Join-Path $root 'Directory.Build.props'))).Project.PropertyGroup.Version
$payload = Join-Path $root "artifacts/release/AkikazuHardwareCheck-$version-win-x64"
$output = Join-Path $root 'artifacts/msi'
$project = Join-Path $output 'AkikazuHardwareCheck.aip'
$upgradeCode = '{12B63A4E-3E26-4FF5-8A5B-1B0900C54A7A}'

& (Join-Path $PSScriptRoot 'publish.ps1')
if ($LASTEXITCODE -ne 0) {
    throw "Portable payload build failed with exit code $LASTEXITCODE"
}

New-Item -ItemType Directory -Force $output | Out-Null
if (Test-Path $project) {
    Remove-Item -LiteralPath $project -Force
}

function Invoke-AdvancedInstaller([string[]]$Arguments) {
    & $tool @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Advanced Installer failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

# Omitting -type creates the permanently free Simple project type. Do not change this to professional/enterprise.
Invoke-AdvancedInstaller @('/newproject', $project, '-lang', 'ja', '-overwrite')
Invoke-AdvancedInstaller @('/edit', $project, '/SetProperty', 'ProductName=秋和PC 硬件测试工具')
Invoke-AdvancedInstaller @('/edit', $project, '/SetProperty', 'Manufacturer=株式会社秋和')
Invoke-AdvancedInstaller @('/edit', $project, '/SetProperty', "UpgradeCode=$upgradeCode")
Invoke-AdvancedInstaller @('/edit', $project, '/SetProperty', 'ALLUSERS=1')
Invoke-AdvancedInstaller @('/edit', $project, '/SetVersion', $version)
Invoke-AdvancedInstaller @('/edit', $project, '/SetPackageType', 'x64')
Invoke-AdvancedInstaller @('/edit', $project, '/SetAppdir', '-buildname', 'DefaultBuild', '-path', '[ProgramFiles64Folder]Akikazu\Hardware Check')
Invoke-AdvancedInstaller @('/edit', $project, '/AddFolder', 'APPDIR', $payload, '-install_in_parent_folder')
Invoke-AdvancedInstaller @('/edit', $project, '/NewShortcut', '-name', '秋和PC 硬件测试工具', '-dir', 'SHORTCUTDIR', '-target', 'APPDIR\AkikazuHardwareCheck.exe', '-wkdir', 'APPDIR')
Invoke-AdvancedInstaller @('/build', $project)

$msi = Get-ChildItem $output -Filter '*.msi' -Recurse | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -eq $msi) {
    throw 'Advanced Installer completed without producing an MSI under artifacts/msi.'
}

$target = Join-Path $output "AkikazuHardwareCheck-$version-win-x64.msi"
if ($msi.FullName -ne $target) {
    Copy-Item -LiteralPath $msi.FullName -Destination $target -Force
}

$hash = (Get-FileHash $target -Algorithm SHA256).Hash
Set-Content -Path (Join-Path $output 'SHA256.txt') -Value "$hash  $(Split-Path -Leaf $target)" -Encoding ascii

Write-Output "Version: $version"
Write-Output 'Channel: Website'
Write-Output 'Installer project type: Advanced Installer Simple (Freeware)'
Write-Output "Output: $target"
Write-Output "SHA-256: $hash"
