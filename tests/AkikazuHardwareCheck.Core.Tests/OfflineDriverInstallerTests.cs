using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class OfflineDriverInstallerTests
{
    // IDs as Windows reports an Intel I226-V; the signed e2fn.inf matches the compatible ID only.
    private static readonly string[] I226HardwareIds =
    [
        @"PCI\VEN_8086&DEV_125C&SUBSYS_88671043&REV_06",
        @"PCI\VEN_8086&DEV_125C&SUBSYS_88671043",
        @"PCI\VEN_8086&DEV_125C&CC_020000",
        @"PCI\VEN_8086&DEV_125C&CC_0200",
    ];

    private static readonly string[] I226CompatibleIds =
    [
        @"PCI\VEN_8086&DEV_125C&REV_06",
        @"PCI\VEN_8086&DEV_125C",
        @"PCI\VEN_8086&CC_020000",
        @"PCI\VEN_8086&CC_0200",
        @"PCI\VEN_8086",
    ];

    [Theory]
    [InlineData(@"PCI\VEN_8086&DEV_125C&SUBSYS_88671043")]
    [InlineData(@"pci\ven_8086&dev_125c")]
    public void FindsTheDeviceByHardwareOrCompatibleId(string id) =>
        Assert.True(OfflineDriverInstaller.ReportsDeviceId(I226HardwareIds, I226CompatibleIds, id));

    [Fact]
    public void IgnoresOtherDevices() =>
        Assert.False(OfflineDriverInstaller.ReportsDeviceId(I226HardwareIds, I226CompatibleIds, @"PCI\VEN_8086&DEV_15F3"));
}
