namespace AkikazuHardwareCheck.Core.SharedDesktop;

/// <summary>
/// Versioned boundary between the shared host and the module registrations. Installers and the host read the same
/// value names; a module declares the minimum host interface it needs, and the host ignores modules it cannot host.
/// </summary>
public static class SharedDesktopContract
{
    public const int SCHEMA_VERSION = 1;
    public const int HOST_INTERFACE_VERSION = 1;

    public const string REGISTRY_PATH = @"Software\Akikazu\SharedDesktop";
    public const string MODULES_SUBKEY = "Modules";

    public const string MODULE_ARGUMENT = "--module";
    public const string TRAY_ARGUMENT = "--tray";
    public const string NO_ELEVATE_ARGUMENT = "--no-elevate";

    public const string INSTALL_IDENTITY_HARDWARE = "Akikazu.HardwareCheck";
    public const string INSTALL_IDENTITY_RESCUE = "Akikazu.NetworkRescue";
    public const string UNINSTALL_KEY_HARDWARE = "Akikazu.HardwareCheck";
    public const string UNINSTALL_KEY_RESCUE = "Akikazu.NetworkRescue";

    public const string VALUE_SCHEMA_VERSION = "SchemaVersion";
    public const string VALUE_HOST_INTERFACE_VERSION = "HostInterfaceVersion";
    public const string VALUE_MODULE_ID = "Id";
    public const string VALUE_VERSION = "Version";
    public const string VALUE_MIN_HOST_INTERFACE = "MinHostInterface";
    public const string VALUE_HOST_VERSION = "HostVersion";
    public const string VALUE_INSTALL_ROOT = "InstallRoot";
    public const string VALUE_HOST_PATH = "HostPath";
    public const string VALUE_ENTRY_ARGUMENTS = "EntryArguments";
    public const string VALUE_INSTALL_IDENTITY = "InstallIdentity";
    public const string VALUE_UNINSTALL_KEY = "UninstallKey";

    public static bool IsInterfaceCompatible(int minimumHostInterfaceVersion) =>
        minimumHostInterfaceVersion is > 0 and <= HOST_INTERFACE_VERSION;

    /// <summary>
    /// The Store package is the hardware test product; a website-installed rescue module must never appear inside it.
    /// The website/portable build may host both modules.
    /// </summary>
    public static bool AllowsModule(SharedModuleId module, bool storeChannel) =>
        !storeChannel || module == SharedModuleId.HardwareCheck;
}
