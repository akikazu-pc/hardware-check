using AkikazuHardwareCheck.Core.SharedDesktop;
using Microsoft.Win32;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class SharedDesktopTests
{
    [Fact]
    public void PortableRunWithoutRegistrationIsTheHardwareTool()
    {
        var startup = SharedDesktopStartupPolicy.Resolve([], [], storeChannel: false);

        Assert.Equal(SharedModuleId.HardwareCheck, startup.ActiveModule);
        Assert.Equal(SharedModuleId.HardwareCheck, startup.PrimaryModule);
        Assert.Equal([SharedModuleId.HardwareCheck], startup.AvailableModules);
        Assert.Empty(startup.Modules);
    }

    [Fact]
    public void RescueOnlyInstallOpensTheRescuePage()
    {
        var startup = SharedDesktopStartupPolicy.Resolve(
            ["--module", SharedModuleIds.NETWORK_RESCUE],
            [Module(SharedModuleId.NetworkRescue)],
            storeChannel: false);

        Assert.Equal(SharedModuleId.NetworkRescue, startup.ActiveModule);
        Assert.Equal(SharedModuleId.NetworkRescue, startup.PrimaryModule);
        Assert.False(startup.HasModule(SharedModuleId.HardwareCheck));
    }

    [Fact]
    public void DualInstallNavigatesByEntry()
    {
        InstalledModule[] modules = [Module(SharedModuleId.HardwareCheck), Module(SharedModuleId.NetworkRescue)];

        var hardware = SharedDesktopStartupPolicy.Resolve(["--module", SharedModuleIds.HARDWARE_CHECK], modules, storeChannel: false);
        var rescue = SharedDesktopStartupPolicy.Resolve(["--module", SharedModuleIds.NETWORK_RESCUE], modules, storeChannel: false);
        var plain = SharedDesktopStartupPolicy.Resolve([], modules, storeChannel: false);

        Assert.Equal(SharedModuleId.HardwareCheck, hardware.ActiveModule);
        Assert.Equal(SharedModuleId.NetworkRescue, rescue.ActiveModule);
        Assert.Equal(SharedModuleId.HardwareCheck, plain.ActiveModule);
        Assert.Equal(2, plain.AvailableModules.Count);
    }

    [Fact]
    public void EntryForAnUninstalledModuleFallsBackToTheInstalledOne()
    {
        var startup = SharedDesktopStartupPolicy.Resolve(
            ["--module", SharedModuleIds.HARDWARE_CHECK],
            [Module(SharedModuleId.NetworkRescue)],
            storeChannel: false);

        Assert.Equal(SharedModuleId.NetworkRescue, startup.ActiveModule);
        Assert.Equal(SharedModuleId.HardwareCheck, startup.RequestedModule);
    }

    [Fact]
    public void StoreBuildNeverShowsTheRescueModule()
    {
        InstalledModule[] modules = [Module(SharedModuleId.HardwareCheck), Module(SharedModuleId.NetworkRescue)];

        var rescueEntry = SharedDesktopStartupPolicy.Resolve(
            ["--module", SharedModuleIds.NETWORK_RESCUE],
            modules,
            storeChannel: true);

        Assert.Equal(SharedModuleId.HardwareCheck, rescueEntry.ActiveModule);
        Assert.Equal([SharedModuleId.HardwareCheck], rescueEntry.AvailableModules);
        Assert.Single(rescueEntry.Modules);
    }

    [Fact]
    public void ArgumentsAreParsedInBothForms()
    {
        var startup = SharedDesktopStartupPolicy.Resolve(
            ["--module=network-rescue", "--tray", "--no-elevate"],
            [Module(SharedModuleId.HardwareCheck), Module(SharedModuleId.NetworkRescue)],
            storeChannel: false);

        Assert.Equal(SharedModuleId.NetworkRescue, startup.ActiveModule);
        Assert.True(startup.StartHidden);
        Assert.True(startup.NoElevate);
    }

    [Theory]
    [InlineData(0, null)]
    [InlineData(-1, null)]
    [InlineData(100_000_000, "100 Mbps")]
    [InlineData(2_500_000_000, "2.5 Gbps")]
    [InlineData(1_000_000_000, "1 Gbps")]
    public void LinkSpeedOmitsAMissingRate(long bitsPerSecond, string? expected)
    {
        Assert.Equal(expected, LocalNetworkStatus.FormatLinkSpeed(bitsPerSecond));
    }

    [Fact]
    public void DiscoveryReadsAValidModule()
    {
        using var registry = new TestRegistry();
        using var root = registry.Open();
        WriteModule(root, SharedModuleId.HardwareCheck, version: "0.2.0", minimumInterface: 1);

        var modules = SharedModuleDiscovery.Read(root, _ => true);

        var module = Assert.Single(modules);
        Assert.Equal(SharedModuleId.HardwareCheck, module.Module);
        Assert.Equal("0.2.0", module.Version);
        Assert.Equal("0.2.0", module.HostVersion);
    }

    [Fact]
    public void DiscoveryIgnoresIncompatibleAndMalformedRegistrations()
    {
        using var registry = new TestRegistry();
        using var root = registry.Open();
        WriteModule(root, SharedModuleId.HardwareCheck, version: "0.2.0", minimumInterface: 1);
        WriteModule(root, SharedModuleId.NetworkRescue, version: "0.1.0", minimumInterface: SharedDesktopContract.HOST_INTERFACE_VERSION + 1);

        var modules = SharedModuleDiscovery.Read(root, _ => true);

        Assert.Single(modules);
        Assert.Equal(SharedModuleId.HardwareCheck, modules[0].Module);
    }

    [Fact]
    public void DiscoverySkipsAModuleWhoseHostFileIsMissing()
    {
        using var registry = new TestRegistry();
        using var root = registry.Open();
        WriteModule(root, SharedModuleId.HardwareCheck, version: "0.2.0", minimumInterface: 1);

        Assert.Empty(SharedModuleDiscovery.Read(root, _ => false));
    }

    [Fact]
    public void RemovingOneRegistrationKeepsTheOther()
    {
        using var registry = new TestRegistry();
        using var root = registry.Open();
        WriteModule(root, SharedModuleId.HardwareCheck, version: "0.2.0", minimumInterface: 1);
        WriteModule(root, SharedModuleId.NetworkRescue, version: "0.1.0", minimumInterface: 1);

        using (var modules = root.OpenSubKey(SharedDesktopContract.MODULES_SUBKEY, writable: true))
        {
            modules!.DeleteSubKeyTree(SharedModuleIds.HARDWARE_CHECK);
        }

        var remaining = Assert.Single(SharedModuleDiscovery.Read(root, _ => true));
        Assert.Equal(SharedModuleId.NetworkRescue, remaining.Module);
    }

    [Fact]
    public void ANewerRootSchemaIsNotGuessed()
    {
        using var registry = new TestRegistry();
        using var root = registry.Open();
        root.SetValue(SharedDesktopContract.VALUE_SCHEMA_VERSION, SharedDesktopContract.SCHEMA_VERSION + 1, RegistryValueKind.DWord);
        WriteModule(root, SharedModuleId.HardwareCheck, version: "0.2.0", minimumInterface: 1);

        Assert.Empty(SharedModuleDiscovery.Read(root, _ => true));
    }

    private static InstalledModule Module(SharedModuleId module) => new(
        module,
        "0.2.0",
        1,
        "0.2.0",
        $@"C:\ProgramData\Akikazu\{module}",
        $@"C:\ProgramData\Akikazu\host\AkikazuHardwareCheck.exe",
        module.EntryArguments(),
        module == SharedModuleId.HardwareCheck
            ? SharedDesktopContract.INSTALL_IDENTITY_HARDWARE
            : SharedDesktopContract.INSTALL_IDENTITY_RESCUE,
        module == SharedModuleId.HardwareCheck
            ? SharedDesktopContract.UNINSTALL_KEY_HARDWARE
            : SharedDesktopContract.UNINSTALL_KEY_RESCUE);

    private static void WriteModule(RegistryKey root, SharedModuleId module, string version, int minimumInterface)
    {
        using var modules = root.CreateSubKey(SharedDesktopContract.MODULES_SUBKEY, writable: true);
        using var key = modules.CreateSubKey(module.ToContractId(), writable: true);
        key.SetValue(SharedDesktopContract.VALUE_SCHEMA_VERSION, SharedDesktopContract.SCHEMA_VERSION, RegistryValueKind.DWord);
        key.SetValue(SharedDesktopContract.VALUE_MODULE_ID, module.ToContractId(), RegistryValueKind.String);
        key.SetValue(SharedDesktopContract.VALUE_VERSION, version, RegistryValueKind.String);
        key.SetValue(SharedDesktopContract.VALUE_MIN_HOST_INTERFACE, minimumInterface, RegistryValueKind.DWord);
        key.SetValue(SharedDesktopContract.VALUE_HOST_VERSION, version, RegistryValueKind.String);
        key.SetValue(SharedDesktopContract.VALUE_INSTALL_ROOT, $@"C:\ProgramData\Akikazu\{module}", RegistryValueKind.String);
        key.SetValue(SharedDesktopContract.VALUE_HOST_PATH, @"C:\ProgramData\Akikazu\host\AkikazuHardwareCheck.exe", RegistryValueKind.String);
        key.SetValue(SharedDesktopContract.VALUE_ENTRY_ARGUMENTS, module.EntryArguments(), RegistryValueKind.String);
        key.SetValue(
            SharedDesktopContract.VALUE_INSTALL_IDENTITY,
            module == SharedModuleId.HardwareCheck
                ? SharedDesktopContract.INSTALL_IDENTITY_HARDWARE
                : SharedDesktopContract.INSTALL_IDENTITY_RESCUE,
            RegistryValueKind.String);
        key.SetValue(
            SharedDesktopContract.VALUE_UNINSTALL_KEY,
            module == SharedModuleId.HardwareCheck
                ? SharedDesktopContract.UNINSTALL_KEY_HARDWARE
                : SharedDesktopContract.UNINSTALL_KEY_RESCUE,
            RegistryValueKind.String);
    }

    private sealed class TestRegistry : IDisposable
    {
        private readonly string _path = $@"Software\Akikazu\SharedDesktopTests\{Guid.NewGuid():N}";

        public RegistryKey Open()
        {
            var root = Registry.CurrentUser.CreateSubKey(_path, writable: true);
            root.SetValue(SharedDesktopContract.VALUE_SCHEMA_VERSION, SharedDesktopContract.SCHEMA_VERSION, RegistryValueKind.DWord);
            return root;
        }

        public void Dispose()
        {
            Registry.CurrentUser.DeleteSubKeyTree(_path, throwOnMissingSubKey: false);
        }
    }
}
