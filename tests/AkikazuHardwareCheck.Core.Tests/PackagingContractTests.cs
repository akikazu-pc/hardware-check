namespace AkikazuHardwareCheck.Core.Tests;

public sealed class PackagingContractTests
{
    private static readonly string Root = FindRoot();

    [Fact]
    public void PortableBuildPinsWebsiteCapabilities()
    {
        var script = File.ReadAllText(Path.Combine(Root, "scripts", "publish.ps1"));

        Assert.Contains("-p:DistributionChannel=Website", script, StringComparison.Ordinal);
        Assert.Contains("-ExpectedPawnIo Present", script, StringComparison.Ordinal);
    }

    [Fact]
    public void StoreBuildPinsRestrictedCapabilities()
    {
        var script = File.ReadAllText(Path.Combine(Root, "scripts", "publish-store-payload.ps1"));

        Assert.Contains("-p:DistributionChannel=Store", script, StringComparison.Ordinal);
        Assert.Contains("-ExpectedPawnIo Absent", script, StringComparison.Ordinal);
    }

    [Fact]
    public void StoreWindowSmokeTestsBuildTheStoreChannel()
    {
        var script = File.ReadAllText(Path.Combine(Root, "scripts", "test-store.ps1"));

        Assert.Contains("-p:DistributionChannel=Store", script, StringComparison.Ordinal);
        Assert.Contains("AkikazuHardwareCheck.App.SmokeTests.exe", script, StringComparison.Ordinal);
    }

    [Fact]
    public void MsiUsesStablePerMachineUpgradeContract()
    {
        var source = File.ReadAllText(Path.Combine(Root, "scripts", "publish-msi.ps1"));

        Assert.Contains("UpgradeCode=$upgradeCode", source, StringComparison.Ordinal);
        Assert.Contains("{12B63A4E-3E26-4FF5-8A5B-1B0900C54A7A}", source, StringComparison.Ordinal);
        Assert.Contains("ALLUSERS=1", source, StringComparison.Ordinal);
        Assert.Contains("Simple (Freeware)", source, StringComparison.Ordinal);
        Assert.DoesNotContain("PawnIO", source, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void StoreManifestRequiresPartnerCenterIdentity()
    {
        var source = File.ReadAllText(Path.Combine(Root, "packaging", "store", "Package.appxmanifest.template"));

        Assert.Contains("{{IdentityName}}", source, StringComparison.Ordinal);
        Assert.Contains("{{Publisher}}", source, StringComparison.Ordinal);
        Assert.Contains("runFullTrust", source, StringComparison.Ordinal);
        Assert.DoesNotContain("PawnIO", source, StringComparison.OrdinalIgnoreCase);
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
