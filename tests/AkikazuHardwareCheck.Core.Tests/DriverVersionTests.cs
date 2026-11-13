using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class DriverVersionTests
{
    [Theory]
    [InlineData("3.5.2.1376", "3.4.2.1046", true)]
    [InlineData("3.4.2.1046", "3.5.2.1376", false)]
    [InlineData("3.5.2.1376", "3.5.2.1376", false)]
    [InlineData("3.5.2.1376", "3.5.2", true)]
    [InlineData("1.2", "1.2.0.0", false)]
    [InlineData("2", "1.9.9", true)]
    [InlineData("1.0.0.10", "1.0.0.9", true)]
    [InlineData("", "1.0", false)]
    [InlineData("1.0", "", false)]
    [InlineData("1.a", "1.0", false)]
    [InlineData("1.0", "1.a", false)]
    public void ComparesDottedNumericVersions(string candidate, string installed, bool expected) =>
        Assert.Equal(expected, DriverVersion.IsNewer(candidate, installed));

    [Fact]
    public void IgnoresNullInputs()
    {
        Assert.False(DriverVersion.IsNewer(null, "1.0"));
        Assert.False(DriverVersion.IsNewer("1.0", null));
    }
}
