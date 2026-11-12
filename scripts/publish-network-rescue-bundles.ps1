[CmdletBinding()]
param(
    [string]$RealtekVendorZip,
    [switch]$IncludeCatalog,
    [string]$VendorSourceDirectory,
    [string]$WlanArchive,
    [string]$PeEthernetPackDirectory,
    [string]$SevenZipExecutable
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if ($WlanArchive) {
    if (-not $IncludeCatalog) {
        throw 'Use -IncludeCatalog with -WlanArchive.'
    }
    if (-not $SevenZipExecutable) {
        throw 'Use -SevenZipExecutable with -WlanArchive to generate matching ZIP and 7z bundles.'
    }
    if (-not $PeEthernetPackDirectory) {
        throw 'Use -PeEthernetPackDirectory with -WlanArchive to include both Ethernet packs.'
    }
    $WlanArchive = (Resolve-Path -LiteralPath $WlanArchive).Path
}

if ($PeEthernetPackDirectory) {
    if (-not $WlanArchive) {
        throw 'Use -PeEthernetPackDirectory with -WlanArchive.'
    }
    $PeEthernetPackDirectory = (Resolve-Path -LiteralPath $PeEthernetPackDirectory).Path
}
if ($SevenZipExecutable) {
    if (-not $WlanArchive) {
        throw 'Use -SevenZipExecutable with -WlanArchive.'
    }
    $SevenZipExecutable = (Resolve-Path -LiteralPath $SevenZipExecutable).Path
}
if ($WlanArchive) {
    & (Join-Path $PSScriptRoot 'build-network-rescue-pe.cmd')
    if ($LASTEXITCODE -ne 0) {
        throw "Native PE helper build failed ($LASTEXITCODE)."
    }
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

    $flavors = @('online-install')
    if ($IncludeCatalog) {
        $flavors += $(if ($WlanArchive) { 'offline-full-portable' } else { 'offline-catalog-portable' })
    }
    if ($RealtekVendorZip -and -not $IncludeCatalog) {
        $flavors += 'offline-preview-portable'
    }

    foreach ($flavor in $flavors) {
        $bundleRoot = $staging.FullName
        if ($flavor -ne 'online-install') {
            $bundleRoot = Join-Path $staging.FullName 'portable'
            New-Item -ItemType Directory -Path $bundleRoot | Out-Null
            Get-ChildItem -LiteralPath $releasePayload | Copy-Item -Destination $bundleRoot -Recurse
            @"
@echo off
start "" "%~dp0AkikazuHardwareCheck.exe" --portable-rescue
"@ | Set-Content -LiteralPath (Join-Path $bundleRoot 'Run-Network-Rescue.cmd') -Encoding ascii
        }

        if ($flavor -eq 'offline-preview-portable') {
            $packRoot = Join-Path $bundleRoot 'driver-packs'
            New-Item -ItemType Directory -Path $packRoot | Out-Null
            & (Join-Path $PSScriptRoot 'prototype/prepare-realtek-wifi-pack.ps1') -VendorZip $RealtekVendorZip `
                -OutputDirectory (Join-Path $packRoot 'realtek-8852-wifi-6001.16.172.0')
        }

        if ($flavor -in 'offline-catalog-portable', 'offline-full-portable') {
            & (Join-Path $PSScriptRoot 'prepare-network-rescue-packs.ps1') -OutputDirectory $bundleRoot -VendorSourceDirectory $VendorSourceDirectory -ExcludeVendorArchives:($flavor -eq 'offline-full-portable')
        }

        if ($flavor -eq 'offline-full-portable') {
            & (Join-Path $PSScriptRoot 'prepare-sdio-wlan-library.ps1') -Archive $WlanArchive -OutputDirectory $bundleRoot
            Copy-Item -LiteralPath (Join-Path $root 'artifacts/network-rescue-pe/PeNetworkRescue.exe') -Destination $bundleRoot
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'prototype/Run-Network-Rescue.cmd') -Destination $bundleRoot -Force
            $packages = (Get-Content -LiteralPath (Join-Path $bundleRoot 'wifi-preview-packages.json') -Raw | ConvertFrom-Json).packages
            $peScope = @(
                '10240 sdio-wlan-wifi-26082'
                foreach ($package in $packages) {
                    $floor = if ($package.windows11Only) { 22000 } else { 10240 }
                    $minimum = [Math]::Max($floor, [int]$package.minimumWindowsBuild)
                    "$minimum $($package.id)-$($package.version)"
                }
            )
            Set-Content -LiteralPath (Join-Path $bundleRoot 'pe-driver-scope.txt') -Value $peScope -Encoding ascii

            foreach ($os in 10, 11) {
                $pack = Join-Path $PeEthernetPackDirectory "NetworkRescue-Realtek-Ethernet-Windows$os-x64.zip"
                $recorded = ((Get-Content -LiteralPath "$pack.sha256" -Raw).Trim() -split '\s+')[0]
                if ((Get-FileHash -LiteralPath $pack).Hash -ne $recorded) {
                    throw "PE Ethernet package hash mismatch: $pack"
                }
                $ethernetRoot = Join-Path $bundleRoot "pe-drivers/windows$os-x64"
                Expand-Archive -LiteralPath $pack -DestinationPath $ethernetRoot
                if (-not (Get-ChildItem -LiteralPath $ethernetRoot -Recurse -File -Filter '*.inf' | Select-Object -First 1)) {
                    throw "PE Ethernet package for Windows $os contains no INF."
                }
            }
        }

        Copy-Item -LiteralPath (Join-Path $root 'docs/network-rescue-driver-index.csv') -Destination $bundleRoot
        $name = "NetworkRescue-$version-$flavor-win-x64.zip"
        $archive = Join-Path $output $name
        if ($flavor -eq 'offline-full-portable') {
            $driverRoot = Join-Path $bundleRoot 'driver-packs'
            $wlanLibrary = Join-Path $driverRoot 'sdio-wlan-wifi-26082'
            $libraryInfCount = @(Get-ChildItem -LiteralPath $wlanLibrary -Recurse -File -Filter '*.inf').Count
            $driverInfCount = @(Get-ChildItem -LiteralPath $driverRoot -Recurse -File -Filter '*.inf').Count
            if ($libraryInfCount -eq 0 -or $driverInfCount -le $libraryInfCount) {
                throw 'The full bundle must contain both the WLAN library and OEM driver packs.'
            }

            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $temporaryArchive = Join-Path $staging.FullName 'portable.zip'
            [IO.Compression.ZipFile]::CreateFromDirectory(
                $bundleRoot, $temporaryArchive, [IO.Compression.CompressionLevel]::Fastest, $false)
            $expectedFiles = [Collections.Generic.Dictionary[string, IO.FileInfo]]::new([StringComparer]::Ordinal)
            foreach ($file in Get-ChildItem -LiteralPath $bundleRoot -Recurse -File) {
                $expectedFiles.Add($file.FullName.Substring($bundleRoot.Length + 1).Replace('\', '/'), $file)
            }

            $temporarySevenZip = Join-Path $staging.FullName 'portable.7z'
            $extracted = Join-Path $staging.FullName 'verified-7z'
            Push-Location -LiteralPath $bundleRoot
            try {
                & $SevenZipExecutable a -t7z -mx=5 -bb0 -bso0 -bsp0 $temporarySevenZip '*'
                if ($LASTEXITCODE -ne 0) { throw "7z creation failed ($LASTEXITCODE)." }
            } finally {
                Pop-Location
            }
            & $SevenZipExecutable x -bb0 -bso0 -bsp0 "-o$extracted" $temporarySevenZip
            if ($LASTEXITCODE -ne 0) { throw "7z extraction failed ($LASTEXITCODE)." }
            $extractedCount = @(Get-ChildItem -LiteralPath $extracted -Recurse -File).Count
            if ($extractedCount -ne $expectedFiles.Count) {
                throw "Unexpected 7z file count ($extractedCount, expected $($expectedFiles.Count))."
            }

            $zip = [IO.Compression.ZipFile]::OpenRead($temporaryArchive)
            try {
                foreach ($entry in $zip.Entries) {
                    if ($entry.FullName.EndsWith('/') -and $entry.Length -eq 0) { continue }
                    $file = $null
                    if (-not $expectedFiles.TryGetValue($entry.FullName, [ref]$file) -or
                        $entry.Length -ne $file.Length) {
                        throw "Unexpected ZIP entry: $($entry.FullName)"
                    }
                    $stream = $entry.Open()
                    try {
                        $stagedHash = (Get-FileHash -LiteralPath $file.FullName).Hash
                        if ((Get-FileHash -InputStream $stream).Hash -ne $stagedHash) {
                            throw "ZIP entry content differs from the staged file: $($entry.FullName)"
                        }
                    } finally {
                        $stream.Dispose()
                    }
                    $extractedFile = Join-Path $extracted $entry.FullName
                    if ((Get-FileHash -LiteralPath $extractedFile).Hash -ne $stagedHash) {
                        throw "7z entry content differs from the staged file: $($entry.FullName)"
                    }
                    [void]$expectedFiles.Remove($entry.FullName)
                }
                if ($expectedFiles.Count -ne 0) {
                    throw "The ZIP is missing $($expectedFiles.Count) staged files."
                }
            } finally {
                $zip.Dispose()
            }
            Move-Item -LiteralPath $temporaryArchive -Destination $archive -Force
            $sevenZipArchive = [IO.Path]::ChangeExtension($archive, '.7z')
            $sevenZipHash = (Get-FileHash -LiteralPath $temporarySevenZip).Hash
            Move-Item -LiteralPath $temporarySevenZip -Destination $sevenZipArchive -Force
            Set-Content -LiteralPath "$sevenZipArchive.sha256" -Value "$sevenZipHash  $([IO.Path]::GetFileName($sevenZipArchive))" -Encoding ascii
            Write-Output "Output: $sevenZipArchive"
        } else {
            Compress-Archive -Path (Join-Path $bundleRoot '*') -DestinationPath $archive -CompressionLevel Fastest -Force
        }
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
