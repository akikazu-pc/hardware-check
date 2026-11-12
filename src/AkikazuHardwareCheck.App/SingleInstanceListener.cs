using System.Diagnostics;
using System.Text;
using System.Text.Json;
using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.App;

/// <summary>
/// A second launch leaves a small request file instead of opening another window. A file works across Windows
/// integrity levels (the hardware copy may be elevated while the rescue entry is not) and survives the short window
/// between the mutex being taken and the running window being ready. The running instance consumes the file on its
/// UI timer; the second process exits immediately.
/// </summary>
internal static class SingleInstanceListener
{
    private const string REQUEST_FILE_PATTERN = "*.json";
    private const string REQUEST_TEMP_SUFFIX = ".tmp";
    private static readonly TimeSpan STALE_REQUEST_AGE = TimeSpan.FromMinutes(2);
    private static readonly DateTime PROCESS_START_UTC = ReadProcessStartUtc();

    private static string RequestFolder => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "AkikazuHardwareCheck",
        "launch-requests",
        $"session-{Process.GetCurrentProcess().SessionId}");

    public static bool NotifyExisting(SharedModuleId? module)
    {
        try
        {
            Directory.CreateDirectory(RequestFolder);
            var name = $"{DateTime.UtcNow.Ticks:D19}-{Environment.ProcessId}-{Guid.NewGuid():N}.json";
            var path = Path.Combine(RequestFolder, name);
            var temporary = path + REQUEST_TEMP_SUFFIX;
            File.WriteAllText(
                temporary,
                JsonSerializer.Serialize(new LaunchRequest(module?.ToContractId(), DateTimeOffset.UtcNow)),
                new UTF8Encoding(false));
            File.Move(temporary, path);
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    /// <summary>Null means "show the existing window"; a module means "show it on that page".</summary>
    public static IReadOnlyList<SharedModuleId?> ConsumeRequests()
    {
        var requests = new List<SharedModuleId?>();
        try
        {
            if (!Directory.Exists(RequestFolder))
            {
                return requests;
            }

            foreach (var path in Directory.EnumerateFiles(RequestFolder, REQUEST_FILE_PATTERN).Order(StringComparer.Ordinal))
            {
                try
                {
                    var request = JsonSerializer.Deserialize<LaunchRequest>(File.ReadAllText(path, Encoding.UTF8));
                    requests.Add(SharedModuleIds.TryParse(request?.Module, out var module) ? module : null);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException or DecoderFallbackException)
                {
                    // A damaged request only loses its navigation hint; the window is still restored.
                    requests.Add(null);
                }
                finally
                {
                    TryDelete(path);
                }
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // If the folder is temporarily unavailable, the next tick tries again.
        }

        return requests;
    }

    /// <summary>
    /// Requests written by an earlier process must not pull this window to an old page. A request from a concurrent
    /// second launch is written after this process started, so it is kept even when it arrives before the timer runs.
    /// </summary>
    public static void ClearStaleRequests()
    {
        try
        {
            if (!Directory.Exists(RequestFolder))
            {
                return;
            }

            var cutoff = PROCESS_START_UTC.AddSeconds(-1);
            foreach (var path in Directory.EnumerateFiles(RequestFolder, REQUEST_FILE_PATTERN))
            {
                if (File.GetLastWriteTimeUtc(path) < cutoff)
                {
                    TryDelete(path);
                }
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Startup must not depend on cleaning a diagnostics folder.
        }
    }

    private static DateTime ReadProcessStartUtc()
    {
        try
        {
            return Process.GetCurrentProcess().StartTime.ToUniversalTime();
        }
        catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception or System.Security.SecurityException)
        {
            // If the process start time is unavailable, keep the conservative age-based cleanup.
            return DateTime.UtcNow - STALE_REQUEST_AGE;
        }
    }

    private static void TryDelete(string path)
    {
        try
        {
            File.Delete(path);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Another tick or a later launch can remove it.
        }
    }

    private sealed record LaunchRequest(string? Module, DateTimeOffset RequestedAt);
}
