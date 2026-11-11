namespace AkikazuHardwareCheck.Core.SharedDesktop;

/// <summary>The desktop modules that can share one main window.</summary>
public enum SharedModuleId
{
    HardwareCheck,
    NetworkRescue,
}

/// <summary>
/// Stable identifiers are the contract between the installers, the registry and the shared host. Do not rename them
/// without a schema version change: an older installer must remain understandable to this host.
/// </summary>
public static class SharedModuleIds
{
    public const string HARDWARE_CHECK = "hardware-check";
    public const string NETWORK_RESCUE = "network-rescue";

    public static string ToContractId(this SharedModuleId module) => module switch
    {
        SharedModuleId.HardwareCheck => HARDWARE_CHECK,
        SharedModuleId.NetworkRescue => NETWORK_RESCUE,
        _ => throw new ArgumentOutOfRangeException(nameof(module)),
    };

    public static bool TryParse(string? value, out SharedModuleId module)
    {
        if (string.Equals(value, HARDWARE_CHECK, StringComparison.OrdinalIgnoreCase))
        {
            module = SharedModuleId.HardwareCheck;
            return true;
        }

        if (string.Equals(value, NETWORK_RESCUE, StringComparison.OrdinalIgnoreCase))
        {
            module = SharedModuleId.NetworkRescue;
            return true;
        }

        module = default;
        return false;
    }

    /// <summary>A key in every language file. The window title and navigation use the same name.</summary>
    public static string DisplayNameKey(this SharedModuleId module) => module switch
    {
        SharedModuleId.HardwareCheck => "module.hardware",
        SharedModuleId.NetworkRescue => "module.rescue",
        _ => throw new ArgumentOutOfRangeException(nameof(module)),
    };

    public static string EntryArguments(this SharedModuleId module) =>
        $"{SharedDesktopContract.MODULE_ARGUMENT} {module.ToContractId()}";
}
