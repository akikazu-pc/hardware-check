using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class OfflineInfMatcherTests
{
    [Fact]
    public void UsesCurrentModelsSectionAndPrefersMostSpecificHardwareId()
    {
        var path = Path.Combine(Path.GetTempPath(), Guid.NewGuid() + ".inf");
        File.WriteAllText(path, """
            [Version]
            Signature="$Windows NT$"
            Class=Net
            ClassGuid={4d36e972-e325-11ce-bfc1-08002be10318}
            Provider=%Vendor%

            [Manufacturer]
            %Vendor%=Models,NTamd64,NTamd64.10.0...99999

            [Models.NTamd64]
            %Vendor%=Install,PCI\VEN_8086&DEV_2725,PCI\VEN_8086&DEV_1234
            %Vendor%=Install,PCI\VEN_8086&DEV_2725&SUBSYS_00248086

            [Models.NTamd64.10.0...99999]
            %Vendor%=Install,PCI\VEN_8086&DEV_5678

            [Strings]
            Vendor="Test"
            """);

        try
        {
            PciNetworkDevice[] devices =
            [
                new([@"PCI\VEN_8086&DEV_2725&SUBSYS_00248086", @"PCI\VEN_8086&DEV_2725"], "SUBSYS_00248086", 28),
                new([@"PCI\VEN_8086&DEV_1234"], null, 28),
                new([@"PCI\VEN_8086&DEV_5678"], null, 28),
            ];

            Assert.Null(OfflineDriverInstaller.Verify(path));
            var match = Assert.Single(OfflineInfMatcher.Match(path, devices));
            Assert.Equal(devices[0].HardwareIds[0], match.HardwareId);
            Assert.Equal("Models.NTamd64", match.ModelsSection, ignoreCase: true);
            Assert.Equal(match, OfflineDriverInstaller.SelectMissingMatch([match]));
            Assert.Null(OfflineDriverInstaller.SelectMissingMatch([match, match]));
            Assert.Null(OfflineDriverInstaller.SelectMissingMatch(
                [match with { Device = match.Device with { ProblemCode = 0 } }]));
        }
        finally
        {
            File.Delete(path);
        }
    }
}
