using System.Diagnostics;

namespace AkikazuHardwareCheck.App;

/// <summary>
/// A second launch leaves a small request file instead of opening another window. A file works across Windows
/// integrity levels and survives the short window
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

    public static bool NotifyExisting()
    {
        try
        {
            Directory.CreateDirectory(RequestFolder);
            var name = $"{DateTime.UtcNow.Ticks:D19}-{Environment.ProcessId}-{Guid.NewGuid():N}.json";
            var path = Path.Combine(RequestFolder, name);
            var temporary = path + REQUEST_TEMP_SUFFIX;
            File.WriteAllText(temporary, "{}");
            File.Move(temporary, path);
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    public static bool ConsumeRequests()
    {
        var pending = false;
        try
        {
            if (Directory.Exists(RequestFolder))
            {
                foreach (var path in Directory.EnumerateFiles(RequestFolder, REQUEST_FILE_PATTERN))
                {
                    pending = true;
                    TryDelete(path);
                }
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Try again on the next tick if the folder is temporarily unavailable.
        }

        return pending;
    }

    /// <summary>
    /// Requests written by an earlier process must not restore this window. A request from a concurrent
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
}
