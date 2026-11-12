using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class RescueModelSupportTests
{
    [Theory]
    [InlineData("PRIME B650M-A AX", false, null, "asus.com")]
    [InlineData("ROG Strix G16 G615LR_G615LR", true, null, "asus.com")]
    [InlineData("Alienware 16X Aurora AC16251", true, null, "dell.com")]
    [InlineData("B550M DS3H AC", false, "1.2", "gigabyte.com")]
    [InlineData("B550M DS3H AC", false, "1.7", null)]
    [InlineData("PRIME B650M-A AX imaginary", false, null, null)]
    [InlineData("B850M AYW GAMING WIFI-CSM", false, null, "asus.com")]
    public void UsesTheExactModelAndKnownBoardRevision(string model, bool laptop, string? revision, string? host)
    {
        var found = Assert.IsType<RescueModelSupport>(RescueModelSupport.Describe(model, laptop, revision));
        Assert.Equal(model, found.Model);
        Assert.Equal(laptop, found.IsLaptop);
        Assert.Equal(host, found.OfficialPage is { } url ? new Uri(url).Host.Replace("www.", "") : null);
    }
}
