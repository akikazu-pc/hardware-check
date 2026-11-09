using AkikazuHardwareCheck.Core.Configuration;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class DistributionProfileTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("Website")]
    [InlineData("unexpected")]
    public void WebsiteIsTheSafeDefault(string? value)
    {
        var profile = DistributionProfile.FromMetadata(value);

        Assert.Equal(DistributionChannel.Website, profile.Channel);
        Assert.True(profile.AllowsElevation);
        Assert.True(profile.AllowsDriverManagement);
    }

    [Theory]
    [InlineData("Store")]
    [InlineData("store")]
    public void StoreBuildDisablesPrivilegedCapabilities(string value)
    {
        var profile = DistributionProfile.FromMetadata(value);

        Assert.Equal(DistributionChannel.Store, profile.Channel);
        Assert.False(profile.AllowsElevation);
        Assert.False(profile.AllowsDriverManagement);
    }
}
