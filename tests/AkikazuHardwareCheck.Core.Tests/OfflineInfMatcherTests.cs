using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class OfflineInfMatcherTests
{
    [Fact]
    public void PortableDriverRootsRespectTargetWindowsBuild()
    {
        var bundle = Directory.CreateTempSubdirectory();
        try
        {
            var drivers = bundle.CreateSubdirectory("driver-packs");
            var common = drivers.CreateSubdirectory("common").FullName;
            var win11 = drivers.CreateSubdirectory("win11_version").FullName;
            var modern = drivers.CreateSubdirectory("modern").FullName;
            var win10Scoped = bundle.CreateSubdirectory("pe-drivers/windows10-x64").FullName;
            var win11Scoped = bundle.CreateSubdirectory("pe-drivers/windows11-x64").FullName;
            File.WriteAllLines(Path.Combine(bundle.FullName, "pe-driver-scope.txt"),
                ["10240 common", "22000 win11_version", "26100 modern", "10240 ../pe-drivers", "bad invalid"]);

            Assert.Equal(new[] { common, win10Scoped }, OfflinePackageSearch.GetPortableRoots(drivers.FullName, 19045, "X64"));
            Assert.Equal(new[] { common, win11, win11Scoped }, OfflinePackageSearch.GetPortableRoots(drivers.FullName, 22631, "X64"));
            Assert.Equal(new[] { common, win11, modern, win11Scoped }, OfflinePackageSearch.GetPortableRoots(drivers.FullName, 26300, "X64"));
            File.Delete(Path.Combine(bundle.FullName, "pe-driver-scope.txt"));
            Assert.Equal(new[] { drivers.FullName, win10Scoped }, OfflinePackageSearch.GetPortableRoots(drivers.FullName, 19045, "X64"));
        }
        finally
        {
            bundle.Delete(recursive: true);
        }
    }

    [Fact]
    public void UsesCurrentModelsSectionAndPrefersMostSpecificHardwareId()
    {
        var directory = Directory.CreateTempSubdirectory();
        var path = Path.Combine(directory.CreateSubdirectory("vendor").FullName, "wifi.inf");
        File.WriteAllText(path, """
            [Version]
            Signature="$Windows NT$"
            Class=Net
            ClassGuid={4d36e972-e325-11ce-bfc1-08002be10318}
            DriverVer=10/16/2025,6001.16.172.0
            Provider=%Vendor%

            [Manufacturer]
            %Vendor%=Models,NTamd64,NTamd64.10.0...99999

            [Models.NTamd64]
            %Vendor%=Install,PCI\VEN_8086&DEV_2725,PCI\VEN_8086&DEV_1234
            %Vendor%=Install,PCI\VEN_8086&DEV_2725&SUBSYS_00248086
            %Vendor%=Install,USB\VID_2357&PID_0138

            [Models.NTamd64.10.0...99999]
            %Vendor%=Install,PCI\VEN_8086&DEV_5678

            [Strings]
            Vendor="Test"
            """);

        try
        {
            NetworkDeviceCandidate[] devices =
            [
                new([@"PCI\VEN_8086&DEV_2725&SUBSYS_00248086", @"PCI\VEN_8086&DEV_2725"], "SUBSYS_00248086", 28),
                new([@"PCI\VEN_8086&DEV_1234"], null, 28),
                new([@"PCI\VEN_8086&DEV_5678"], null, 28),
            ];

            var alternate = directory.CreateSubdirectory("alternate").FullName;
            File.WriteAllText(Path.Combine(alternate, "bad.inf"), "invalid");
            File.WriteAllText(Path.Combine(alternate, "generic.inf"), File.ReadAllText(path)
                .Replace(@"%Vendor%=Install,PCI\VEN_8086&DEV_2725&SUBSYS_00248086", ""));
            var search = OfflinePackageSearch.Find(directory.FullName, devices);
            var expected = new[] { path, Path.Combine(alternate, "generic.inf") };
            Assert.Equal(expected, search.Candidates.Select(candidate => candidate.InfPath));
            Assert.Equal(1, search.UnreadableInfCount);

            var combined = OfflinePackageSearch.Find([Path.GetDirectoryName(path)!, alternate], devices, includePossible: true);
            Assert.Equal(expected, combined.Candidates.Select(candidate => candidate.InfPath));
            Assert.Equal(1, combined.UnreadableInfCount);

            var unmatched = new NetworkDeviceCandidate([@"PCI\VEN_8086&DEV_2725&SUBSYS_FFFFFFFF"], null, 28);
            Assert.Empty(OfflinePackageSearch.Find(directory.FullName, [unmatched]).Candidates);
            var possible = OfflinePackageSearch.Find(directory.FullName, [unmatched], includePossible: true).Candidates;
            Assert.NotEmpty(possible);
            Assert.All(possible, candidate => Assert.True(candidate.IsPossible));
            Assert.Empty(OfflineInfMatcher.Match(path, [unmatched]));
            Assert.All(OfflinePackageSearch.Find(directory.FullName, devices, includePossible: true).Candidates,
                candidate => Assert.False(candidate.IsPossible));

            Assert.Equal("6001.16.172.0", OfflineInfMatcher.ReadDriverVersion(path));
            Assert.Null(OfflineDriverInstaller.Verify(path));
            var match = Assert.Single(OfflineInfMatcher.Match(path, devices));
            Assert.Equal(devices[0].HardwareIds[0], match.HardwareId);
            Assert.Equal("Models.NTamd64", match.ModelsSection, ignoreCase: true);
            var usb = Assert.IsType<NetworkDeviceCandidate>(
                NetworkDeviceInventory.Classify([@"USB\VID_2357&PID_0138"], [], 28));
            Assert.Equal(usb, Assert.Single(OfflineInfMatcher.Match(path, [usb])).Device);
            Assert.Equal(match, OfflineDriverInstaller.SelectMissingMatch([match], match.HardwareId));
            Assert.Null(OfflineDriverInstaller.SelectMissingMatch([match, match], match.HardwareId));
            Assert.Null(OfflineDriverInstaller.SelectMissingMatch(
                [match with { Device = match.Device with { ProblemCode = 0 } }], match.HardwareId));
        }
        finally
        {
            directory.Delete(recursive: true);
        }
    }

    [Fact]
    public void SelectsOneMissingAdapterEvenWhenTheInfMatchesAnotherAdapter()
    {
        const string firstId = @"PCI\VEN_8086&DEV_125C";
        const string secondId = @"PCI\VEN_8086&DEV_15F3";
        var first = new NetworkDeviceCandidate([firstId], null, 28, NetworkCandidateKind.PciEthernet);
        var second = new NetworkDeviceCandidate([secondId], null, 28, NetworkCandidateKind.PciEthernet);
        var firstMatch = new OfflineInfMatch(first, firstId, "Models");
        var secondMatch = new OfflineInfMatch(second, secondId, "Models");
        var working = second with { ProblemCode = 0 };
        var workingMatch = secondMatch with { Device = working };

        Assert.Equal(firstMatch, OfflineDriverInstaller.SelectMissingMatch([firstMatch, workingMatch], firstId.ToLowerInvariant()));
        Assert.Equal(secondMatch, OfflineDriverInstaller.SelectMissingMatch([firstMatch, secondMatch], secondId));
        Assert.Equal([firstMatch, secondMatch], OfflineDriverInstaller.FindInstallableMatches([firstMatch, secondMatch], [first, second]));
        Assert.Equal([firstMatch], OfflineDriverInstaller.FindInstallableMatches([firstMatch, workingMatch], [first, working]));
        Assert.Empty(OfflineDriverInstaller.FindInstallableMatches([firstMatch], [first, working with { HardwareIds = [secondId, firstId] }]));
    }
}
