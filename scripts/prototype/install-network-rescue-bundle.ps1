[CmdletBinding()]
param([string]$Root, [switch]$NoShortcut)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'scripts/prototype/SharedDesktopPrototype.psm1') -Force

$installed = Install-SharedApp -App network-rescue -PayloadPath (Join-Path $PSScriptRoot 'payload') -Root $Root -NoShortcut:$NoShortcut
$sourcePack = Join-Path $PSScriptRoot 'driver-packs/realtek-8852-wifi-6001.16.172.0'
if (Test-Path -LiteralPath $sourcePack -PathType Container) {
    $installedPacks = Join-Path $installed.ModuleDirectory 'driver-packs'
    New-Item -ItemType Directory -Path $installedPacks -Force | Out-Null
    Copy-Item -LiteralPath $sourcePack -Destination $installedPacks -Recurse -Force
}

$installed | Format-List
