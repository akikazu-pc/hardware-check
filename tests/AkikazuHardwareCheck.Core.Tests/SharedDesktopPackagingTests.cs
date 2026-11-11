using System.Text.Json;
using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class SharedDesktopPackagingTests
{
    private static readonly string Root = FindRoot();

    [Fact]
    public void IdentityManifestDefinesTwoDistinctInstallIdentities()
    {
        using var document = JsonDocument.Parse(File.ReadAllText(Path.Combine(Root, "packaging", "shared-desktop", "app-identities.json")));
        var root = document.RootElement;
        Assert.Equal(1, root.GetProperty("SchemaVersion").GetInt32());
        Assert.Equal(1, root.GetProperty("HostInterfaceVersion").GetInt32());
        Assert.False(string.IsNullOrWhiteSpace(root.GetProperty("ShortcutFolder").GetString()));

        var modules = root.GetProperty("Modules").EnumerateArray().ToList();
        Assert.Equal(2, modules.Count);
        Assert.Equal(
            ["hardware-check", "network-rescue"],
            modules.Select(module => module.GetProperty("Id").GetString()).ToArray());
        Assert.Equal(
            ["Akikazu.HardwareCheck", "Akikazu.NetworkRescue"],
            modules.Select(module => module.GetProperty("InstallIdentity").GetString()).ToArray());
        Assert.Equal(
            ["--module hardware-check", "--module network-rescue"],
            modules.Select(module => module.GetProperty("EntryArguments").GetString()).ToArray());
        Assert.Equal(SharedDesktopContract.INSTALL_IDENTITY_HARDWARE, modules[0].GetProperty("InstallIdentity").GetString());
        Assert.Equal(SharedDesktopContract.INSTALL_IDENTITY_RESCUE, modules[1].GetProperty("InstallIdentity").GetString());
        Assert.Equal(SharedDesktopContract.UNINSTALL_KEY_HARDWARE, modules[0].GetProperty("UninstallKey").GetString());
        Assert.Equal(SharedDesktopContract.UNINSTALL_KEY_RESCUE, modules[1].GetProperty("UninstallKey").GetString());
        Assert.Equal(
            2,
            modules.Select(module => module.GetProperty("UpgradeCode").GetString()).Distinct(StringComparer.OrdinalIgnoreCase).Count());
    }

    [Fact]
    public void PrototypeInstallerUsesTheSameVersionedRegistryContract()
    {
        var source = File.ReadAllText(Path.Combine(Root, "scripts", "prototype", "SharedDesktopPrototype.psm1"));

        Assert.Contains(@"HKCU:\Software\Akikazu\SharedDesktop", source, StringComparison.Ordinal);
        Assert.Contains("MinHostInterface", source, StringComparison.Ordinal);
        Assert.Contains("HostInterfaceVersion", source, StringComparison.Ordinal);
        Assert.Contains("UninstallString", source, StringComparison.Ordinal);
        Assert.Contains("WScript.Shell", source, StringComparison.Ordinal);
        Assert.DoesNotContain("PawnIO", source, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("DistributionChannel=Store", source, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void PrototypeVerificationCoversTheRequiredScenarios()
    {
        var source = File.ReadAllText(Path.Combine(Root, "scripts", "prototype", "test-shared-desktop.ps1"));

        Assert.Contains("single install: hardware only", source, StringComparison.Ordinal);
        Assert.Contains("single install: rescue only", source, StringComparison.Ordinal);
        Assert.Contains("install order: rescue then hardware", source, StringComparison.Ordinal);
        Assert.Contains("independent upgrade: rescue host moves", source, StringComparison.Ordinal);
        Assert.Contains("independent upgrade: hardware host moves", source, StringComparison.Ordinal);
        Assert.Contains("concurrent launch", source, StringComparison.Ordinal);
        Assert.Contains("tray-hidden launch", source, StringComparison.Ordinal);
        Assert.Contains("registered uninstall command", source, StringComparison.Ordinal);
        Assert.Contains("offline-simulated", source, StringComparison.Ordinal);
        Assert.DoesNotContain(@"D:\Users", source, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void PrototypeScriptsDoNotCarryDevelopmentPaths()
    {
        foreach (var path in Directory.EnumerateFiles(Path.Combine(Root, "scripts", "prototype"), "*", SearchOption.AllDirectories))
        {
            Assert.DoesNotContain(@"D:\Users", File.ReadAllText(path), StringComparison.OrdinalIgnoreCase);
        }
    }

    private static string FindRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null && !File.Exists(Path.Combine(current.FullName, "AkikazuHardwareCheck.slnx")))
        {
            current = current.Parent;
        }

        return current?.FullName ?? throw new DirectoryNotFoundException("Repository root was not found.");
    }
}
