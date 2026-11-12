[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('hardware-check', 'network-rescue')]
    [string]$App,
    [string]$Root,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SharedDesktopPrototype.psm1') -Force

$identity = Get-SharedIdentity -App $App
$manifest = Get-PrototypeManifest
Uninstall-SharedApp `
    -Id $identity.Id `
    -UninstallKey $identity.UninstallKey `
    -ShortcutName $identity.ShortcutName `
    -ShortcutFolder ([string]$manifest.ShortcutFolder) `
    -DisplayName $identity.DisplayName `
    -Root $Root `
    -Quiet:$Quiet
