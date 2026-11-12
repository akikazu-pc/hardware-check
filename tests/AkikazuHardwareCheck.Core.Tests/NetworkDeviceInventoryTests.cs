using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class NetworkDeviceInventoryTests
{
    [Fact]
    public void PreservesPciIdOrderForMissingDriver()
    {
        string[] ids = [@"PCI\VEN_8086&DEV_2725&SUBSYS_00248086&REV_1A", @"PCI\VEN_8086&DEV_2725"];
        var device = Assert.IsType<NetworkDeviceCandidate>(NetworkDeviceInventory.Classify(ids, [@"PCI\CC_028000"], 28));

        Assert.Equal(ids, device.HardwareIds);
        Assert.Equal("SUBSYS_00248086", device.SubsystemId);
        Assert.Equal(28, device.ProblemCode);
    }

    [Fact]
    public void AddsActualPciCompatibleDeviceIdsAfterSpecificHardwareIds()
    {
        const string specific = @"PCI\VEN_8086&DEV_125C&SUBSYS_88671043&REV_06";
        const string vendorDevice = @"PCI\VEN_8086&DEV_125C";
        const string revision = vendorDevice + "&REV_06";
        string[] compatible = [revision, vendorDevice, vendorDevice, @"PCI\VEN_8086&DEV_125B",
            @"PCI\VEN_8086&CC_0200", @"PCI\CC_020000"];

        var device = Assert.IsType<NetworkDeviceCandidate>(NetworkDeviceInventory.Classify([specific], compatible, 28));

        Assert.Equal([specific, revision, vendorDevice], device.HardwareIds);
        Assert.Equal("SUBSYS_88671043", device.SubsystemId);
        Assert.Equal(NetworkCandidateKind.PciEthernet, device.Kind);
    }

    [Theory]
    [InlineData(@"PCI\CC_0200", 28, true)]
    [InlineData(@"PCI\CC_020000", 28, true)]
    [InlineData(@"PCI\VEN_10EC&DEV_8168&CC_020000", 28, true)]
    [InlineData(@"PCI\CC_020000", 0, false)]
    [InlineData(@"PCI\CC_020000", 10, true)]
    [InlineData(@"PCI\CC_020000", 22, true)]
    [InlineData(@"PCI\CC_010000", 28, false)]
    public void FindsEthernetControllersWithDeviceProblems(string compatibleId, int code, bool expected)
    {
        string[] ids = [@"PCI\VEN_10EC&DEV_8168&SUBSYS_E0001458", @"PCI\VEN_10EC&DEV_8168"];
        var device = NetworkDeviceInventory.Classify(ids, [compatibleId], code);

        Assert.Equal(expected, device is not null);
        if (device is not null)
        {
            Assert.Equal(NetworkCandidateKind.PciEthernet, device.Kind);
            Assert.Equal(ids, device.HardwareIds);
            Assert.Equal("SUBSYS_E0001458", device.SubsystemId);
        }
    }

    [Fact]
    public void ExcludesUnrelatedUsbDevices()
    {
        Assert.Null(NetworkDeviceInventory.Classify([@"USB\VID_1234&PID_5678"], [], 28, "HIDClass"));
    }

    [Theory]
    [InlineData(null, 28, NetworkCandidateKind.UsbUnidentified)]
    [InlineData("Unknown", 28, NetworkCandidateKind.UsbUnidentified)]
    [InlineData("Net", 0, NetworkCandidateKind.UsbNetwork)]
    public void DistinguishesUsbNetworkFromUnidentifiedUsb(string? setupClass, int code, NetworkCandidateKind expected)
    {
        string[] ids = [@"USB\VID_2357&PID_0138&REV_0200", @"USB\VID_2357&PID_0138"];
        var device = Assert.IsType<NetworkDeviceCandidate>(NetworkDeviceInventory.Classify(ids, [], code, setupClass));
        Assert.Equal(ids, device.HardwareIds);
        Assert.Equal(expected, device.Kind);
        Assert.Null(device.SubsystemId);
    }
}
