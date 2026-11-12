using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class OnlineDriverCatalogTests
{
    [Fact]
    public void OffersKnownUsbPackageForAnUnidentifiedMissingDriver()
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, 19045, "X64",
            [new([@"USB\VID_2357&PID_0138&REV_0200"], null, 28, NetworkCandidateKind.UsbUnidentified)]);

        var package = Assert.Single(OnlineDriverCatalog.Find(diagnostic));
        Assert.Equal("archer-t3u-plus", package.Id);
        Assert.Empty(OnlineDriverCatalog.Find(diagnostic with { Architecture = "Arm64" }));
        Assert.Empty(OnlineDriverCatalog.Find(diagnostic with { Devices = [diagnostic.Devices[0] with { ProblemCode = 0 }] }));
    }

    [Fact]
    public void DoesNotOfferWindows11OnlyPackageForWindows10()
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, 19045, "X64",
            [new([@"PCI\VEN_17CB&DEV_1107&SUBSYS_337817CB&REV_01"], null, 28)]);

        Assert.Empty(OnlineDriverCatalog.Find(diagnostic));
        Assert.Equal("qualcomm-wifi7", Assert.Single(OnlineDriverCatalog.Find(diagnostic with { WindowsBuild = 26300 })).Id);
    }
}
