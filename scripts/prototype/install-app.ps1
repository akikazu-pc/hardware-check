[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('hardware-check', 'network-rescue')]
    [string]$App,
    [string]$Version,
    [string]$HostVersion,
    [string]$PayloadPath,
    [string]$Root,
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SharedDesktopPrototype.psm1') -Force

Install-SharedApp -App $App -Version $Version -HostVersion $HostVersion -PayloadPath $PayloadPath -Root $Root -NoShortcut:$NoShortcut |
    Format-List
