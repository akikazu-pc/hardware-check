using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class PciNetworkInventoryTests
{
    [Fact]
    public void PreservesPciIdOrderForMissingDriver()
    {
        string[] ids = [@"PCI\VEN_8086&DEV_2725&SUBSYS_00248086&REV_1A", @"PCI\VEN_8086&DEV_2725"];
        var device = Assert.IsType<PciNetworkDevice>(PciNetworkInventory.Classify(ids, [@"PCI\CC_028000"], 28));

        Assert.Equal(ids, device.HardwareIds);
        Assert.Equal("SUBSYS_00248086", device.SubsystemId);
        Assert.Equal(28, device.ProblemCode);
    }

    [Fact]
    public void ExcludesWiredNetworkAndNonPciDevices()
    {
        Assert.Null(PciNetworkInventory.Classify([@"PCI\VEN_10EC&DEV_8168"], [@"PCI\CC_020000"], 0));
        Assert.Null(PciNetworkInventory.Classify([@"USB\VID_1234&PID_5678"], [@"PCI\CC_028000"], 28));
    }
}
