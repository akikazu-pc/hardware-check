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
    public void ExcludesPciEthernetAndUnrelatedUsbDevices()
    {
        Assert.Null(NetworkDeviceInventory.Classify([@"PCI\VEN_10EC&DEV_8168"], [@"PCI\CC_020000"], 0));
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
