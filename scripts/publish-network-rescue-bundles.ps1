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
    if (-not $PeEthernetPackDirectory) {
        throw 'Use -PeEthernetPackDirectory with -WlanArchive to include both Ethernet packs.'
    }
    if (-not $SevenZipExecutable) {
        throw 'Use -SevenZipExecutable with -WlanArchive to extract the OEM NSIS driver.'
    }
    $SevenZipExecutable = (Resolve-Path -LiteralPath $SevenZipExecutable).Path
    $WlanArchive = (Resolve-Path -LiteralPath $WlanArchive).Path
}

if ($PeEthernetPackDirectory) {
    if (-not $WlanArchive) {
        throw 'Use -PeEthernetPackDirectory with -WlanArchive.'
    }
    $PeEthernetPackDirectory = (Resolve-Path -LiteralPath $PeEthernetPackDirectory).Path
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
            # Older Windows 10 builds can crash in CoreCLR before managed startup when the host opts into CET.
            # Separate intermediates keep the single-file host from being reused by the regular Website publish.
            $offlinePublish = Join-Path $staging.FullName 'offline-publish'
            $appProject = Join-Path $root 'src/AkikazuHardwareCheck.App/AkikazuHardwareCheck.App.csproj'
            dotnet publish $appProject -c Release --self-contained true -o $offlinePublish --nologo `
                --artifacts-path (Join-Path $staging.FullName 'offline-build') `
                -p:DistributionChannel=Website -p:DebugType=None -p:CETCompat=false
            if ($LASTEXITCODE -ne 0) {
                throw "Offline Network Rescue publish failed ($LASTEXITCODE)."
            }
            $appName = 'AkikazuHardwareCheck.exe'
            Copy-Item -LiteralPath (Join-Path $offlinePublish $appName) -Destination $bundleRoot -Force
            $appHash = (Get-FileHash -LiteralPath (Join-Path $bundleRoot $appName) -Algorithm SHA256).Hash
            Set-Content -LiteralPath (Join-Path $bundleRoot 'SHA256.txt') -Value "$appHash  $appName" -Encoding ascii

            & (Join-Path $PSScriptRoot 'prepare-sdio-wlan-library.ps1') -Archive $WlanArchive -OutputDirectory $bundleRoot
            Copy-Item -LiteralPath (Join-Path $root 'artifacts/network-rescue-pe/PeNetworkRescue.exe') -Destination $bundleRoot
            Copy-Item -LiteralPath (Join-Path $root 'artifacts/network-rescue-pe/NetworkRescue.exe') -Destination $bundleRoot
            $fontCache = Join-Path $root 'artifacts/network-rescue-pe/fonts'
            New-Item -ItemType Directory -Path $fontCache -Force | Out-Null
            $fontSource = 'https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004'
            $fontFiles = @(
                @{
                    Name = 'NotoSansCJK-Regular.ttc'
                    Path = 'Sans/OTC/NotoSansCJK-Regular.ttc'
                    Hash = 'B76B0433203017CA80401B2EE0DD69350349871C4B19D504C34DBDD80541690A'
                },
                @{
                    Name = 'NotoSansCJK-OFL.txt'
                    Path = 'LICENSE'
                    Hash = '6A73F9541C2DE74158C0E7CF6B0A58EF774F5A780BF191F2D7EC9CC53EFE2BF2'
                }
            )
            $peFonts = New-Item -ItemType Directory -Path (Join-Path $bundleRoot 'pe-fonts')
            foreach ($fontFile in $fontFiles) {
                $cached = Join-Path $fontCache $fontFile.Name
                if (-not (Test-Path -LiteralPath $cached)) {
                    Invoke-WebRequest -Uri "$fontSource/$($fontFile.Path)" -OutFile $cached
                }
                if ((Get-FileHash -LiteralPath $cached).Hash -ne $fontFile.Hash) {
                    throw "PE font hash mismatch: $($fontFile.Name)"
                }
                Copy-Item -LiteralPath $cached -Destination $peFonts.FullName
            }
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'prototype/Run-Network-Rescue.cmd') -Destination $bundleRoot -Force
            $packages = (Get-Content -LiteralPath (Join-Path $bundleRoot 'wifi-preview-packages.json') -Raw | ConvertFrom-Json).packages
            $peScope = @(
                '10240 sdio-wlan-wifi-26082'
                foreach ($package in $packages) {
                    if ($package.targetWindows) { continue }
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

            $scopedWlan = @(
                @{ Id = 'mt7902-b550-rev12'; Systems = 10, 11; Directory = 'mbdriver/WLAN' }
                @{ Id = 'rtl8851be-z790-win10'; Systems = 10; Directory = 'RTWLANE_Driver/Win10X64' }
                @{ Id = 'rtl8851be-z790-win11'; Systems = 11; Directory = 'RTWLANE_Driver/Win11' }
                @{ Id = 'asus-mb-rtl8922-win10'; Systems = 10; Directory = 'Win10X64'; Direct = $true }
            )
            $driverIndex = Import-Csv -LiteralPath (Join-Path $root 'docs/network-rescue-driver-index.csv')
            foreach ($driver in $scopedWlan) {
                $package = @($driverIndex | Where-Object packageId -eq $driver.Id)
                if ($package.Count -ne 1) { throw "Expected one index entry for $($driver.Id)." }
                $package = $package[0]
                $fileName = [IO.Path]::GetFileName(([uri]$package.downloadUrl).LocalPath)
                $inputRoot = Join-Path $staging.FullName $driver.Id
                New-Item -ItemType Directory -Path $inputRoot | Out-Null
                $vendorZip = Join-Path $inputRoot $fileName
                if ($VendorSourceDirectory) {
                    $vendorZip = Join-Path (Join-Path $VendorSourceDirectory $driver.Id) $fileName
                } else {
                    Invoke-WebRequest -Uri $package.downloadUrl -OutFile $vendorZip
                }
                if ((Get-FileHash -LiteralPath $vendorZip).Hash -ne $package.sha256) {
                    throw "OEM WLAN package hash mismatch: $fileName"
                }

                $outer = Join-Path $inputRoot 'outer'
                Expand-Archive -LiteralPath $vendorZip -DestinationPath $outer
                $payload = $outer
                if (-not $driver.Direct) {
                    $installers = @(Get-ChildItem -LiteralPath $outer -File -Filter '*.exe')
                    if ($installers.Count -ne 1) { throw "Expected one installer in $fileName." }
                    $payload = Join-Path $inputRoot 'payload'
                    & $SevenZipExecutable x -y -bso0 -bsp0 "-o$payload" $installers[0].FullName
                    if ($LASTEXITCODE -ne 0) { throw "Unable to extract $fileName ($LASTEXITCODE)." }
                }
                $driverSource = Join-Path $payload $driver.Directory
                if (-not (Get-ChildItem -LiteralPath $driverSource -Recurse -File -Filter '*.inf' | Select-Object -First 1)) {
                    throw "No extracted INF files in $fileName."
                }
                foreach ($os in $driver.Systems) {
                    $destination = Join-Path $bundleRoot "pe-drivers/windows$os-x64/$($driver.Id)"
                    Copy-Item -LiteralPath $driverSource -Destination $destination -Recurse
                    Get-ChildItem -LiteralPath $payload -File | Where-Object Name -Match 'copyright|license|eula' |
                        Copy-Item -Destination $destination
                }
            }
        }

        Copy-Item -LiteralPath (Join-Path $root 'docs/network-rescue-driver-index.csv') -Destination $bundleRoot
        $extension = if ($flavor -eq 'offline-full-portable') { 'esd' } else { 'zip' }
        $name = "NetworkRescue-$version-$flavor-win-x64.$extension"
        $archive = Join-Path $output $name
        if ($flavor -eq 'offline-full-portable') {
            $driverRoot = Join-Path $bundleRoot 'driver-packs'
            $wlanLibrary = Join-Path $driverRoot 'sdio-wlan-wifi-26082'
            $libraryInfCount = @(Get-ChildItem -LiteralPath $wlanLibrary -Recurse -File -Filter '*.inf').Count
            $driverInfCount = @(Get-ChildItem -LiteralPath $driverRoot -Recurse -File -Filter '*.inf').Count
            if ($libraryInfCount -eq 0 -or $driverInfCount -le $libraryInfCount) {
                throw 'The full bundle must contain both the WLAN library and OEM driver packs.'
            }

            $dism = Join-Path ([Environment]::SystemDirectory) 'dism.exe'
            $capture = Join-Path $staging.FullName 'offline.wim'
            $temporaryArchive = Join-Path $staging.FullName 'offline.esd'
            & $dism /Capture-Image "/ImageFile:$capture" "/CaptureDir:$bundleRoot" /Name:NetworkRescue /Compress:fast /CheckIntegrity
            if ($LASTEXITCODE -ne 0) {
                throw "DISM capture failed ($LASTEXITCODE). Run the full offline build from an elevated shell."
            }
            & $dism /Export-Image "/SourceImageFile:$capture" /SourceIndex:1 "/DestinationImageFile:$temporaryArchive" /Compress:recovery /CheckIntegrity
            if ($LASTEXITCODE -ne 0) {
                throw "DISM ESD export failed ($LASTEXITCODE)."
            }

            $GITHUB_ASSET_LIMIT_BYTES = 2GB
            if ((Get-Item -LiteralPath $temporaryArchive).Length -ge $GITHUB_ASSET_LIMIT_BYTES) {
                throw 'The full offline archive must be smaller than 2 GiB.'
            }

            $verificationRoot = Join-Path $staging.FullName 'verify-offline'
            New-Item -ItemType Directory -Path $verificationRoot | Out-Null
            & $dism /Apply-Image "/ImageFile:$temporaryArchive" /Index:1 "/ApplyDir:$verificationRoot" /CheckIntegrity
            if ($LASTEXITCODE -ne 0) {
                throw "DISM ESD verification failed ($LASTEXITCODE)."
            }

            $expectedFiles = @(Get-ChildItem -LiteralPath $bundleRoot -Recurse -File -Force)
            $actualCount = @(Get-ChildItem -LiteralPath $verificationRoot -Recurse -File -Force).Count
            if ($actualCount -ne $expectedFiles.Count) {
                throw "The ESD restored $actualCount files, expected $($expectedFiles.Count)."
            }
            foreach ($file in $expectedFiles) {
                $relative = [IO.Path]::GetRelativePath($bundleRoot, $file.FullName)
                $extracted = Join-Path $verificationRoot $relative
                if (!(Test-Path -LiteralPath $extracted -PathType Leaf) -or
                    (Get-FileHash -LiteralPath $extracted).Hash -ne (Get-FileHash -LiteralPath $file.FullName).Hash) {
                    throw "Restored file differs from the staged file: $relative"
                }
            }
            Move-Item -LiteralPath $temporaryArchive -Destination $archive -Force
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
