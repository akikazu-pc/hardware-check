using AkikazuHardwareCheck.Core.Configuration;
using AkikazuHardwareCheck.Core.SharedDesktop;
using Microsoft.Win32;

namespace AkikazuHardwareCheck.App;

/// <summary>
/// Current-user auto-start. It never needs administrator rights and never touches machine-wide entries. The value
/// points at the primary installed module's host, not at whichever version happened to be running; the installer
/// rewrites it again on install, upgrade and uninstall.
/// </summary>
internal static class StartupRegistration
{
    internal const string RUN_KEY = @"Software\Microsoft\Windows\CurrentVersion\Run";
    internal const string VALUE_NAME = "AkikazuHardwareCheck";
    private const string TRAY_ARGUMENT = "--tray";

    public static bool IsEnabled()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RUN_KEY, writable: false);
        return key?.GetValue(VALUE_NAME) is string value && value.Contains(TRAY_ARGUMENT, StringComparison.OrdinalIgnoreCase);
    }

    public static void Set(bool enabled)
    {
        if (!enabled)
        {
            // Disabling must also remove a value left by an earlier installation, including in a Store build.
            using var existing = Registry.CurrentUser.OpenSubKey(RUN_KEY, writable: true);
            existing?.DeleteValue(VALUE_NAME, throwOnMissingValue: false);
            return;
        }

        if (!DistributionProfile.Current.AllowsStartupRegistration)
        {
            return;
        }

        if ((PrimaryInstalledHostPath() ?? Environment.ProcessPath) is not { } path)
        {
            return;
        }

        using var key = Registry.CurrentUser.CreateSubKey(RUN_KEY, writable: true);
        key.SetValue(VALUE_NAME, $"\"{path}\" {TRAY_ARGUMENT}", RegistryValueKind.String);
    }

    private static string? PrimaryInstalledHostPath()
    {
        // A portable copy must keep pointing at itself; only a process that is itself a registered shared host
        // should be redirected to the primary installed module.
        if (Environment.ProcessPath is not { } processPath)
        {
            return null;
        }

        var modules = SharedModuleDiscovery.ReadCurrentUser();
        if (!modules.Any(module => string.Equals(module.HostPath, processPath, StringComparison.OrdinalIgnoreCase)))
        {
            return null;
        }

        return (modules.FirstOrDefault(module => module.Module == SharedModuleId.HardwareCheck)
                ?? modules.FirstOrDefault(module => module.Module == SharedModuleId.NetworkRescue))
            ?.HostPath;
    }
}
