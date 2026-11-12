using AkikazuHardwareCheck.Core.Hardware;
using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class NetworkRecoveryTests
{
    [Fact]
    public void ExcludesTheWindowsKernelDebugAdapter() =>
        Assert.False(NetworkCollector.IsPhysical("Microsoft Kernel Debug Network Adapter"));

    [Theory]
    [InlineData(false, false, null, NetworkRecoveryStage.Disconnected)]
    [InlineData(true, false, false, NetworkRecoveryStage.NoUsableAddress)]
    [InlineData(true, false, true, NetworkRecoveryStage.NoGateway)]
    [InlineData(true, false, null, NetworkRecoveryStage.LocalOnly)]
    [InlineData(true, true, true, NetworkRecoveryStage.LocalOnly)]
    public void AssessesLocalConnectionWithoutReportingInternet(bool isUp, bool hasGateway, bool? hasAddress,
        NetworkRecoveryStage expected)
    {
        var adapter = new LocalNetworkAdapter("Ethernet", LocalNetworkKind.Wired, isUp, 0, hasGateway)
        {
            HasUsableAddress = hasAddress,
        };

        Assert.Equal(expected, LocalNetworkStatus.Assess([adapter], NetworkRecoveryStage.LocalOnly));
    }

    [Theory]
    [InlineData(NetworkRecoveryStage.InternetReported)]
    [InlineData(NetworkRecoveryStage.SignInMayBeRequired)]
    public void RetainsMachineWideInternetHintWhenNoPhysicalAdapterIsListed(NetworkRecoveryStage hint) =>
        Assert.Equal(hint, LocalNetworkStatus.Assess([], hint));

    [Fact]
    public void DoesNotBlameOneAdaptersMissingGatewayWhenAnotherHasOne()
    {
        var wifi = new LocalNetworkAdapter("Wi-Fi", LocalNetworkKind.Wireless, true, 0, false)
            { HasUsableAddress = false };
        var ethernet = new LocalNetworkAdapter("Ethernet", LocalNetworkKind.Wired, true, 0, true)
            { HasUsableAddress = true };

        Assert.Equal(NetworkRecoveryStage.LocalOnly,
            LocalNetworkStatus.Assess([wifi, ethernet], NetworkRecoveryStage.LocalOnly));
    }
}
