using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class OnlineDriverCatalogTests
{
    [Theory]
    [InlineData(19045, @"PCI\VEN_8086&DEV_125C", "intel-ethernet-25g-w10")]
    [InlineData(26100, @"PCI\VEN_8086&DEV_125C", "intel-ethernet-25g-w11")]
    [InlineData(19045, @"PCI\VEN_8086&DEV_15B8", "intel-ethernet-gbe-w10")]
    [InlineData(26100, @"PCI\VEN_8086&DEV_15B8", "intel-ethernet-gbe-w11")]
    [InlineData(19045, @"USB\VID_0BDA&PID_8156", "asus-usb-ethernet-w10")]
    [InlineData(26100, @"USB\VID_0BDA&PID_8156", "asus-usb-ethernet-w11")]
    public void OffersOnlyTheEthernetPackageForTheSelectedWindowsFamily(int build, string id, string expected)
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, build, "X64", [new([id], null, 28)]);

        var package = Assert.Single(OnlineDriverCatalog.Find(diagnostic));
        Assert.Equal(expected, package.Id);
    }

    [Fact]
    public void RejectsTheIntelEthernetPackageBelowItsMinimumWindows10Build()
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, 17134, "X64", [new([@"PCI\VEN_8086&DEV_125C"], null, 28)]);

        Assert.Empty(OnlineDriverCatalog.Find(diagnostic));
    }

    [Theory]
    [InlineData(19045)]
    [InlineData(26300)]
    public void OffersDLinkEthernetOnlyForItsRecordedUsbId(int build)
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, build, "X64",
            [new([@"USB\VID_2001&PID_4A00&REV_0100"], null, 28, NetworkCandidateKind.UsbUnidentified)]);
        Assert.Equal("dlink-dub1312-reva", Assert.Single(OnlineDriverCatalog.Find(diagnostic)).Id);
        Assert.Empty(OnlineDriverCatalog.Find(diagnostic with
        {
            Devices = [new([@"USB\VID_2001&PID_4A01"], null, 28, NetworkCandidateKind.UsbUnidentified)],
        }));
    }

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

    [Theory]
    [InlineData(26000, @"PCI\VEN_14C3&DEV_0616&SUBSYS_061614C3", false)]
    [InlineData(26100, @"PCI\VEN_14C3&DEV_0616&SUBSYS_061614C3&REV_01", true)]
    [InlineData(26100, @"PCI\VEN_14C3&DEV_0616&SUBSYS_FFFFFFFF", false)]
    public void OffersAsusPackageOnlyForSupportedBuildAndSubsystem(int build, string hardwareId, bool expected)
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, build, "X64", [new([hardwareId], null, 28)]);

        Assert.Equal(expected, OnlineDriverCatalog.Find(diagnostic).Any(package => package.Id == "asus-tuf-mt7922"));
    }

    [Theory]
    [InlineData(26100, @"PCI\VEN_14C3&DEV_0616&SUBSYS_FFFFFFFF", true)]
    [InlineData(26100, @"PCI\VEN_14C3&DEV_0616", true)]
    [InlineData(26100, @"PCI\VEN_14C3&DEV_0616&SUBSYS_061614C3", false)]
    [InlineData(26100, @"PCI\VEN_14C3&DEV_0617&SUBSYS_FFFFFFFF", false)]
    [InlineData(26000, @"PCI\VEN_14C3&DEV_0616&SUBSYS_FFFFFFFF", false)]
    public void ListsUnconfirmedSubsystemsOnlyForTheSameSupportedChipset(int build, string hardwareId, bool expected)
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, build, "X64", [new([hardwareId], null, 28)]);

        Assert.Equal(expected, OnlineDriverCatalog.FindPossible(diagnostic).Any(package => package.Id == "asus-tuf-mt7922"));
    }

    [Fact]
    public void FindsTheInstalledAdapterForDownloadOnly()
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, 26300, "X64",
            [new([@"PCI\VEN_14C3&DEV_7925&SUBSYS_60001A3B"], "SUBSYS_60001A3B", 0)]);

        Assert.Empty(OnlineDriverCatalog.Find(diagnostic));
        Assert.Contains(OnlineDriverCatalog.Find(diagnostic, includeInstalled: true),
            package => package.Id == "asus-rog-b860g-mt7925");
    }

    [Theory]
    [InlineData(19045, false)]
    [InlineData(26100, true)]
    public void KeepsDualSystemPackagesAndFiltersWindows11OnlyOptions(int build, bool windows11)
    {
        var diagnostic = new NetworkDeviceDiagnostic(2, build, "X64",
        [
            new([@"PCI\VEN_10EC&DEV_B852&SUBSYS_00AB1E26"], null, 28),
            new([@"PCI\VEN_14C3&DEV_7925&SUBSYS_60001A3B"], null, 28),
            new([@"PCI\VEN_14C3&DEV_0616&SUBSYS_FFFFFFFF"], null, 28),
        ]);

        var exact = OnlineDriverCatalog.Find(diagnostic);
        Assert.Contains(exact, package => package.Id == "asus-prime-b650ma-ax-rtl8852be");
        Assert.Equal(windows11, exact.Any(package => package.Id == "asus-rog-b860g-mt7925"));
        Assert.Equal(windows11, OnlineDriverCatalog.FindPossible(diagnostic)
            .Any(package => package.Id == "asus-tuf-mt7922"));
    }
}
