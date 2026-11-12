using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record OnlineDriverPackage(string Id, string Version, string Source, string ArchiveSha256,
    string DriverDirectory, string? ArchiveLayout, string[] DevicePrefixes, bool Windows11Only);

public static class OnlineDriverCatalog
{
    private static readonly HttpClient Client = new() { Timeout = TimeSpan.FromMinutes(2) };
    private static readonly Lazy<OnlineDriverPackage[]> Packages = new(ReadEmbeddedIndex);

    public static IReadOnlyList<OnlineDriverPackage> Find(NetworkDeviceDiagnostic diagnostic)
    {
        if (!string.Equals(diagnostic.Architecture, "X64", StringComparison.OrdinalIgnoreCase))
        {
            return [];
        }

        return Packages.Value.Where(package => (!package.Windows11Only || diagnostic.WindowsBuild >= 22000) &&
            diagnostic.Devices.Any(device => device.ProblemCode == 28 &&
                device.HardwareIds.Any(id => package.DevicePrefixes.Any(prefix => MatchesPrefix(id, prefix))))).ToArray();
    }

    public static async Task<string> DownloadAsync(OnlineDriverPackage package, string workspace, CancellationToken cancellationToken)
    {
        if (!Packages.Value.Contains(package))
        {
            throw new InvalidDataException("The driver package is not in the embedded catalog.");
        }

        var root = Path.Combine(workspace, package.Id);
        Directory.CreateDirectory(root);
        var archive = Path.Combine(root, "vendor.zip");
        using (var download = await Client.GetStreamAsync(package.Source, cancellationToken).ConfigureAwait(false))
        await using (var output = File.Create(archive))
        {
            await download.CopyToAsync(output, cancellationToken).ConfigureAwait(false);
        }

        await using (var input = File.OpenRead(archive))
        {
            var hash = await SHA256.HashDataAsync(input, cancellationToken).ConfigureAwait(false);
            if (!string.Equals(Convert.ToHexString(hash), package.ArchiveSha256, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidDataException("The driver archive checksum changed.");
            }
        }

        var extracted = Path.Combine(root, "extracted");
        ZipFile.ExtractToDirectory(archive, extracted);
        var payload = extracted;
        if (package.ArchiveLayout != "direct")
        {
            var wrappers = Directory.GetFiles(extracted, "*.exe");
            if (wrappers.Length != 1)
            {
                throw new InvalidDataException("The expected vendor archive wrapper was not found.");
            }

            payload = Directory.CreateDirectory(Path.Combine(root, "payload")).FullName;
            var start = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "tar.exe"))
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                ArgumentList = { "-xf", wrappers[0], "-C", payload },
            };
            using var extract = Process.Start(start) ?? throw new IOException("Could not launch archive extraction.");
            await extract.WaitForExitAsync(cancellationToken).ConfigureAwait(false);
            if (extract.ExitCode != 0)
            {
                throw new InvalidDataException("The vendor archive could not be extracted.");
            }
        }

        var driver = Path.Combine(payload, package.DriverDirectory);
        return Directory.Exists(driver) ? driver : throw new InvalidDataException("The expected driver folder was not found.");
    }

    private static bool MatchesPrefix(string id, string prefix) =>
        id.Equals(prefix, StringComparison.OrdinalIgnoreCase) ||
        id.StartsWith(prefix + "&", StringComparison.OrdinalIgnoreCase);

    private static OnlineDriverPackage[] ReadEmbeddedIndex()
    {
        using var stream = typeof(OnlineDriverCatalog).Assembly.GetManifestResourceStream("rescue.wifi-preview-packages.json")
            ?? throw new InvalidOperationException("The offline vendor catalog is missing.");
        using var document = JsonDocument.Parse(stream);
        return document.RootElement.GetProperty("packages").Deserialize<OnlineDriverPackage[]>(
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true }) ?? [];
    }
}
