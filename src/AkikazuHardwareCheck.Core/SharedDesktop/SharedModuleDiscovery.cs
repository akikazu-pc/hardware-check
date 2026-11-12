using System.Globalization;
using System.Security;
using Microsoft.Win32;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

/// <summary>
/// Reads the per-user module registrations. A broken or future registration is ignored instead of preventing the
/// host from starting; a missing registration is normal for a portable build.
/// </summary>
public static class SharedModuleDiscovery
{
    public static IReadOnlyList<InstalledModule> ReadCurrentUser(Func<string, bool>? hostExists = null)
    {
        try
        {
            using var root = Registry.CurrentUser.OpenSubKey(SharedDesktopContract.REGISTRY_PATH);
            return Read(root, hostExists ?? File.Exists);
        }
        catch (Exception exception) when (exception is SecurityException or UnauthorizedAccessException or IOException)
        {
            return [];
        }
    }

    public static IReadOnlyList<InstalledModule> Read(RegistryKey? root, Func<string, bool> hostExists)
    {
        if (root is null || !IsSchemaUnderstood(root.GetValue(SharedDesktopContract.VALUE_SCHEMA_VERSION)))
        {
            return [];
        }

        using var modulesKey = root.OpenSubKey(SharedDesktopContract.MODULES_SUBKEY);
        if (modulesKey is null)
        {
            return [];
        }

        var modules = new List<InstalledModule>();
        foreach (var keyName in modulesKey.GetSubKeyNames())
        {
            try
            {
                using var key = modulesKey.OpenSubKey(keyName);
                if (key is not null && ReadModule(key, keyName, hostExists) is { } module)
                {
                    modules.Add(module);
                }
            }
            catch (Exception exception) when (exception is SecurityException or UnauthorizedAccessException or IOException or FormatException or InvalidCastException)
            {
                // One damaged registration must not hide the other installed module.
            }
        }

        return modules;
    }

    private static InstalledModule? ReadModule(RegistryKey key, string keyName, Func<string, bool> hostExists)
    {
        if (!IsSchemaUnderstood(key.GetValue(SharedDesktopContract.VALUE_SCHEMA_VERSION))
            || !SharedModuleIds.TryParse(keyName, out var module))
        {
            return null;
        }

        var declaredId = key.GetValue(SharedDesktopContract.VALUE_MODULE_ID) as string;
        if (!string.IsNullOrWhiteSpace(declaredId)
            && (!SharedModuleIds.TryParse(declaredId, out var declaredModule) || declaredModule != module))
        {
            return null;
        }

        var version = key.GetValue(SharedDesktopContract.VALUE_VERSION) as string;
        var hostVersion = key.GetValue(SharedDesktopContract.VALUE_HOST_VERSION) as string;
        var installRoot = key.GetValue(SharedDesktopContract.VALUE_INSTALL_ROOT) as string;
        var hostPath = key.GetValue(SharedDesktopContract.VALUE_HOST_PATH) as string;
        var entryArguments = key.GetValue(SharedDesktopContract.VALUE_ENTRY_ARGUMENTS) as string;
        var installIdentity = key.GetValue(SharedDesktopContract.VALUE_INSTALL_IDENTITY) as string;
        var uninstallKey = key.GetValue(SharedDesktopContract.VALUE_UNINSTALL_KEY) as string;
        var minimumHostInterface = ReadInt(key.GetValue(SharedDesktopContract.VALUE_MIN_HOST_INTERFACE));
        if (!IsVersion(version)
            || !IsVersion(hostVersion)
            || string.IsNullOrWhiteSpace(installRoot)
            || string.IsNullOrWhiteSpace(hostPath)
            || !hostExists(hostPath)
            || string.IsNullOrWhiteSpace(entryArguments)
            || string.IsNullOrWhiteSpace(installIdentity)
            || string.IsNullOrWhiteSpace(uninstallKey)
            || !SharedDesktopContract.IsInterfaceCompatible(minimumHostInterface))
        {
            return null;
        }

        return new InstalledModule(
            module,
            version!,
            minimumHostInterface,
            hostVersion!,
            installRoot,
            hostPath,
            entryArguments,
            installIdentity,
            uninstallKey);
    }

    private static bool IsSchemaUnderstood(object? value) =>
        value is null || ReadInt(value) == SharedDesktopContract.SCHEMA_VERSION;

    private static int ReadInt(object? value) => value switch
    {
        int number => number,
        long number => checked((int)number),
        string text when int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var number) => number,
        _ => 0,
    };

    private static bool IsVersion(string? value) =>
        !string.IsNullOrWhiteSpace(value) && Version.TryParse(value, out _);
}
