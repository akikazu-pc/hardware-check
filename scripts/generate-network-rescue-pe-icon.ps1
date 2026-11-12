param(
    [Parameter(Mandatory)] [string]$Source,
    [Parameter(Mandatory)] [string]$Destination
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing.Common
$icon = [IO.File]::ReadAllBytes($Source)
$count = [BitConverter]::ToUInt16($icon, 4)
$frames = foreach ($size in 16, 32) {
    $entry = 6
    while ($entry -lt 6 + 16 * $count -and $icon[$entry] -ne $size) { $entry += 16 }
    if ($entry -ge 6 + 16 * $count -or $icon[$entry + 1] -ne $size) {
        throw "Missing ${size}x${size} application icon."
    }
    $length = [BitConverter]::ToInt32($icon, $entry + 8)
    $offset = [BitConverter]::ToInt32($icon, $entry + 12)
    $inputStream = [IO.MemoryStream]::new($icon, $offset, $length)
    $outputStream = [IO.MemoryStream]::new()
    $frame = [IO.BinaryWriter]::new($outputStream)
    $image = $null
    try {
        $image = [Drawing.Bitmap]::new($inputStream)
        # An uncompressed icon DIB includes the color plane and the 1-bit AND mask.
        foreach ($field in 40, $size, (2 * $size)) { $frame.Write([int]$field) }
        $frame.Write([uint16]1)
        $frame.Write([uint16]32)
        foreach ($field in 1..6) { $frame.Write([int]0) }
        $mask = [byte[]]::new(4 * $size)
        for ($y = $size - 1; $y -ge 0; $y--) {
            for ($x = 0; $x -lt $size; $x++) {
                $pixel = $image.GetPixel($x, $y)
                $frame.Write($pixel.ToArgb())
                if ($pixel.A -eq 0) {
                    $index = ($size - 1 - $y) * 4 + ($x -shr 3)
                    $mask[$index] = $mask[$index] -bor (128 -shr ($x -band 7))
                }
            }
        }
        $frame.Write($mask)
        @{ Size = $size; Bytes = $outputStream.ToArray() }
    } finally {
        if ($image) { $image.Dispose() }
        $frame.Dispose()
        $inputStream.Dispose()
    }
}

$writer = [IO.BinaryWriter]::new([IO.File]::Create($Destination))
try {
    foreach ($field in 0, 1, $frames.Count) { $writer.Write([uint16]$field) }
    $offset = 6 + 16 * $frames.Count
    foreach ($frame in $frames) {
        foreach ($field in $frame.Size, $frame.Size, 0, 0) { $writer.Write([byte]$field) }
        $writer.Write([uint16]1)
        $writer.Write([uint16]32)
        $writer.Write([int]$frame.Bytes.Length)
        $writer.Write([int]$offset)
        $offset += $frame.Bytes.Length
    }
    foreach ($frame in $frames) { $writer.Write($frame.Bytes) }
} finally {
    $writer.Dispose()
}
