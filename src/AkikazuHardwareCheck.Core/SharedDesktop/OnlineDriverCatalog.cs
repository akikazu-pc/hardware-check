using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record OnlineDriverPackage(string Id, string Version, string Source, string ArchiveSha256,
    string DriverDirectory, string? ArchiveLayout, string[] DevicePrefixes, bool Windows11Only, int ArchiveOffset = 0,
    int MinimumWindowsBuild = 0, string? Scope = null, string? AdapterName = null);

public static class OnlineDriverCatalog
{
    private static readonly HttpClient Client = new() { Timeout = TimeSpan.FromMinutes(2) };
    private static readonly Lazy<OnlineDriverPackage[]> Packages = new(ReadEmbeddedIndex);

    public static IReadOnlyList<OnlineDriverPackage> Find(NetworkDeviceDiagnostic diagnostic, bool includeInstalled = false) =>
        Find(diagnostic, MatchesPrefix, includeInstalled);

    public static IReadOnlyList<OnlineDriverPackage> FindPossible(NetworkDeviceDiagnostic diagnostic, bool includeInstalled = false) =>
        Find(diagnostic, (id, prefix) => MatchesPrefix(id, OfflineInfMatcher.ChipsetId(prefix)) &&
            !MatchesPrefix(id, prefix), includeInstalled).Except(Find(diagnostic, includeInstalled)).ToArray();

    private static IReadOnlyList<OnlineDriverPackage> Find(NetworkDeviceDiagnostic diagnostic, Func<string, string, bool> matches,
        bool includeInstalled)
    {
        if (!string.Equals(diagnostic.Architecture, "X64", StringComparison.OrdinalIgnoreCase))
        {
            return [];
        }

        return Packages.Value.Where(package => (!package.Windows11Only || diagnostic.WindowsBuild >= 22000) &&
            diagnostic.WindowsBuild >= package.MinimumWindowsBuild &&
            diagnostic.Devices.Any(device => (includeInstalled || device.ProblemCode == 28) &&
                device.HardwareIds.Any(id => package.DevicePrefixes.Any(prefix => matches(id, prefix))))).ToArray();
    }

    public static async Task<string> DownloadAsync(OnlineDriverPackage package, string workspace, CancellationToken cancellationToken)
    {
        if (!Packages.Value.Contains(package))
        {
            throw new InvalidDataException("The driver package is not in the embedded catalog.");
        }

        var root = Path.Combine(workspace, package.Id);
        Directory.CreateDirectory(root);
        var archive = Path.Combine(root, package.ArchiveLayout == "inno" ? "vendor.exe" : "vendor.zip");
        await DownloadVerifiedAsync(package.Source, package.ArchiveSha256, archive, cancellationToken).ConfigureAwait(false);

        var payload = Path.Combine(root, "extracted");
        if (package.ArchiveLayout == "embedded-7z")
        {
            var embedded = Path.Combine(root, "payload.7z");
            await using (var input = File.OpenRead(archive))
            {
                if (package.ArchiveOffset <= 0 || package.ArchiveOffset >= input.Length)
                {
                    throw new InvalidDataException("The embedded archive offset is invalid.");
                }

                input.Position = package.ArchiveOffset;
                await using var output = File.Create(embedded);
                await input.CopyToAsync(output, cancellationToken).ConfigureAwait(false);
            }

            await ExtractArchiveAsync(embedded, payload, cancellationToken).ConfigureAwait(false);
        }
        else if (package.ArchiveLayout == "inno")
        {
            var toolArchive = Path.Combine(root, "innoextract.zip");
            await DownloadVerifiedAsync("https://github.com/dscharrer/innoextract/releases/download/1.9/innoextract-1.9-windows.zip",
                "6989342C9B026A00A72A38F23B62A8E6A22CC5DE69805CF47D68AC2FEC993065", toolArchive, cancellationToken).ConfigureAwait(false);
            var tool = Path.Combine(root, "innoextract");
            ZipFile.ExtractToDirectory(toolArchive, tool);
            await RunExtractorAsync(Path.Combine(tool, "innoextract.exe"),
                ["-s", "-d", payload, archive], cancellationToken).ConfigureAwait(false);
        }
        else
        {
            ZipFile.ExtractToDirectory(archive, payload);
            if (package.ArchiveLayout != "direct")
            {
                var wrappers = Directory.GetFiles(payload, "*.exe");
                if (wrappers.Length != 1)
                {
                    throw new InvalidDataException("The expected vendor archive wrapper was not found.");
                }

                payload = Path.Combine(root, "payload");
                await ExtractArchiveAsync(wrappers[0], payload, cancellationToken).ConfigureAwait(false);
            }
        }

        var driver = Path.Combine(payload, package.DriverDirectory);
        return Directory.Exists(driver) ? driver : throw new InvalidDataException("The expected driver folder was not found.");
    }

    private static async Task DownloadVerifiedAsync(string source, string expectedSha256, string archive, CancellationToken cancellationToken)
    {
        using (var download = await Client.GetStreamAsync(source, cancellationToken).ConfigureAwait(false))
        await using (var output = File.Create(archive))
        {
            await download.CopyToAsync(output, cancellationToken).ConfigureAwait(false);
        }

        await using var input = File.OpenRead(archive);
        var hash = await SHA256.HashDataAsync(input, cancellationToken).ConfigureAwait(false);
        if (!string.Equals(Convert.ToHexString(hash), expectedSha256, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException("The downloaded archive checksum changed.");
        }
    }

    private static Task ExtractArchiveAsync(string archive, string destination, CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(destination);
        return RunExtractorAsync(Path.Combine(Environment.SystemDirectory, "tar.exe"),
            ["-xf", archive, "-C", destination], cancellationToken);
    }

    private static async Task RunExtractorAsync(string executable, string[] arguments, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var start = new ProcessStartInfo(executable) { UseShellExecute = false, CreateNoWindow = true };
        foreach (var argument in arguments)
        {
            start.ArgumentList.Add(argument);
        }

        using var extract = Process.Start(start) ?? throw new IOException("Could not launch archive extraction.");
        using var cancel = cancellationToken.Register(() =>
        {
            try
            {
                extract.Kill();
            }
            catch (InvalidOperationException)
            {
                // The extractor already exited.
            }
        });
        await extract.WaitForExitAsync().ConfigureAwait(false);
        cancellationToken.ThrowIfCancellationRequested();
        if (extract.ExitCode != 0)
        {
            throw new InvalidDataException("The vendor archive could not be extracted.");
        }
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
