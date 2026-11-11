namespace AkikazuHardwareCheck.Core.SharedDesktop;

/// <summary>One installed module as recorded by its installer, not as compiled into this host.</summary>
public sealed record InstalledModule(
    SharedModuleId Module,
    string Version,
    int MinimumHostInterface,
    string HostVersion,
    string InstallRoot,
    string HostPath,
    string EntryArguments,
    string InstallIdentity,
    string UninstallKey);
