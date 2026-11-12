param(
    [Parameter(Mandatory)] [string] $OutputDirectory,
    [string] $VendorSourceDirectory
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repo 'packaging/shared-desktop/wifi-preview-packages.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$tar = Join-Path ([Environment]::SystemDirectory) 'tar.exe'
$drivers = Join-Path $OutputDirectory 'driver-packs'
$originals = Join-Path $OutputDirectory 'vendor-installers'
New-Item -ItemType Directory -Path $drivers, $originals | Out-Null

$staging = New-Item -ItemType Directory -Path (Join-Path $OutputDirectory ('.wifi-inputs-' + [Guid]::NewGuid()))
try {
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
        } else {
            Expand-Archive -LiteralPath $archive -DestinationPath $sfxRoot
            New-Item -ItemType Directory -Path $payload | Out-Null
            $executables = @(Get-ChildItem -LiteralPath $sfxRoot -Filter '*.exe' -File)
            if ($executables.Count -ne 1) {
                throw "Expected exactly one self-extracting archive in $fileName."
            }
            & $tar -xf $executables[0].FullName -C $payload
            if ($LASTEXITCODE -ne 0) {
                throw "Could not unpack $fileName."
            }
        }

        $driver = Join-Path $payload $package.driverDirectory
        $packageRoot = Join-Path $drivers ($package.id + '-' + $package.version)
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
