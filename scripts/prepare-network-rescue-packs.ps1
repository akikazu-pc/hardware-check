param(
    [Parameter(Mandatory)] [string] $OutputDirectory,
    [string] $VendorSourceDirectory,
    [switch] $ExcludeVendorArchives
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repo 'packaging/shared-desktop/wifi-preview-packages.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$tar = Join-Path ([Environment]::SystemDirectory) 'tar.exe'
$drivers = Join-Path $OutputDirectory 'driver-packs'
$staging = New-Item -ItemType Directory -Path (Join-Path $OutputDirectory ('.wifi-inputs-' + [Guid]::NewGuid()))
try {
    $archiveRoot = if ($ExcludeVendorArchives) { $staging.FullName } else { $OutputDirectory }
    $originals = Join-Path $archiveRoot 'vendor-installers'
    New-Item -ItemType Directory -Path $drivers, $originals | Out-Null
    foreach ($package in $manifest.packages) {
        $fileName = [IO.Path]::GetFileName(([uri]$package.source).LocalPath)
        $archive = Join-Path $originals $fileName
        if ($VendorSourceDirectory) {
            $inputPath = Join-Path (Join-Path $VendorSourceDirectory $package.id) $fileName
            Copy-Item -LiteralPath $inputPath -Destination $archive
        } else {
            Invoke-WebRequest -Uri $package.source -OutFile $archive
        }

        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $package.archiveSha256) {
            throw "Vendor archive hash mismatch: $fileName"
        }

        $inputRoot = Join-Path $staging.FullName $package.id
        $sfxRoot = Join-Path $inputRoot 'sfx'
        $payload = Join-Path $inputRoot 'payload'
        if ($package.archiveLayout -eq 'direct') {
            Expand-Archive -LiteralPath $archive -DestinationPath $payload
        } elseif ($package.archiveLayout -eq 'inno') {
            # Keep the extraction path short for InnoExtract 1.9 on Windows.
            $tempRoot = (Resolve-Path -LiteralPath ([IO.Path]::GetTempPath())).Path
            $innoRoot = New-Item -ItemType Directory -Path (Join-Path $tempRoot ('wifi-inno-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)))
            try {
                $toolArchive = Join-Path $innoRoot.FullName 'innoextract.zip'
                Invoke-WebRequest -Uri 'https://github.com/dscharrer/innoextract/releases/download/1.9/innoextract-1.9-windows.zip' -OutFile $toolArchive
                if ((Get-FileHash -LiteralPath $toolArchive -Algorithm SHA256).Hash -ne '6989342C9B026A00A72A38F23B62A8E6A22CC5DE69805CF47D68AC2FEC993065') {
                    throw 'InnoExtract ZIP hash mismatch.'
                }
                $tool = Join-Path $innoRoot.FullName 'tool'
                $innoPayload = Join-Path $innoRoot.FullName 'payload'
                Expand-Archive -LiteralPath $toolArchive -DestinationPath $tool
                & (Join-Path $tool 'innoextract.exe') -s -d $innoPayload $archive
                if ($LASTEXITCODE -ne 0) {
                    throw "Could not unpack $fileName."
                }
                New-Item -ItemType Directory -Path $inputRoot | Out-Null
                Copy-Item -LiteralPath $innoPayload -Destination $payload -Recurse
            } finally {
                $resolvedInnoRoot = (Resolve-Path -LiteralPath $innoRoot.FullName).Path
                if ((Split-Path -Parent $resolvedInnoRoot) -eq $tempRoot -and (Split-Path -Leaf $resolvedInnoRoot) -like 'wifi-inno-*') {
                    Remove-Item -LiteralPath $resolvedInnoRoot -Recurse -Force
                }
            }
        } else {
            New-Item -ItemType Directory -Path $payload | Out-Null
            if ($package.archiveLayout -eq 'embedded-7z') {
                $archiveToExtract = Join-Path $inputRoot 'payload.7z'
                $inputArchive = [IO.File]::OpenRead($archive)
                try {
                    $offset = [int]$package.archiveOffset
                    if ($offset -le 0 -or $offset -ge $inputArchive.Length) {
                        throw "Invalid embedded archive offset in $fileName."
                    }
                    $inputArchive.Position = $offset
                    $embeddedArchive = [IO.File]::Create($archiveToExtract)
                    try {
                        $inputArchive.CopyTo($embeddedArchive)
                    } finally {
                        $embeddedArchive.Dispose()
                    }
                } finally {
                    $inputArchive.Dispose()
                }
            } else {
                Expand-Archive -LiteralPath $archive -DestinationPath $sfxRoot
                $executables = @(Get-ChildItem -LiteralPath $sfxRoot -Filter '*.exe' -File)
                if ($executables.Count -eq 0) {
                    $executables = @(Get-ChildItem -LiteralPath $sfxRoot -Filter '*.exe' -File -Recurse)
                }
                if ($executables.Count -ne 1) {
                    throw "Expected exactly one self-extracting archive in $fileName."
                }
                $archiveToExtract = $executables[0].FullName
            }
            & $tar -xf $archiveToExtract -C $payload
            if ($LASTEXITCODE -ne 0) {
                throw "Could not unpack $fileName."
            }
        }

        $driver = Join-Path $payload $package.driverDirectory
        $destination = switch ($package.targetWindows) {
            'windows10' { Join-Path $OutputDirectory 'pe-drivers/windows10-x64' }
            'windows11' { Join-Path $OutputDirectory 'pe-drivers/windows11-x64' }
            $null { $drivers }
            default { throw "Invalid target Windows in $fileName." }
        }
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        $packageRoot = Join-Path $destination ($package.id + '-' + $package.version)
        if (-not (Get-ChildItem -LiteralPath $driver -Filter '*.inf' -Recurse -File | Select-Object -First 1)) {
            throw "No extracted INF files in $fileName."
        }

        Copy-Item -LiteralPath $driver -Destination $packageRoot -Recurse
        Get-ChildItem -LiteralPath $payload -File | Where-Object Name -Match 'copyright|license|eula' |
            Copy-Item -Destination $packageRoot
    }

    Copy-Item -LiteralPath $manifestPath -Destination $OutputDirectory
}
finally {
    $resolved = (Resolve-Path -LiteralPath $staging.FullName).Path
    if ((Split-Path -Parent $resolved) -eq (Resolve-Path -LiteralPath $OutputDirectory).Path -and
        (Split-Path -Leaf $resolved) -like '.wifi-inputs-*') {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
