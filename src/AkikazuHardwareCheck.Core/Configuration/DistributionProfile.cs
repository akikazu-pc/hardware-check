using System.Reflection;

namespace AkikazuHardwareCheck.Core.Configuration;

public enum DistributionChannel
{
    Website,
    Store,
}

/// <summary>Centralizes capabilities that differ between the full website build and the Microsoft Store build.</summary>
public sealed record DistributionProfile(DistributionChannel Channel)
{
    public static DistributionProfile Current { get; } = FromMetadata(
        typeof(DistributionProfile).Assembly.GetCustomAttributes<AssemblyMetadataAttribute>()
            .FirstOrDefault(attribute => attribute.Key == "DistributionChannel")?.Value);

    public bool AllowsElevation => Channel == DistributionChannel.Website;

    public bool AllowsDriverManagement => Channel == DistributionChannel.Website;

    public bool AllowsStartupRegistration => Channel == DistributionChannel.Website;

    public bool AllowsExternalUninstall => Channel == DistributionChannel.Website;

    public bool AllowsSystemCleanup => Channel == DistributionChannel.Website;

    public bool AllowsProcessMemoryOptimization => Channel == DistributionChannel.Website;

    public static DistributionProfile FromMetadata(string? value) =>
        new(string.Equals(value, nameof(DistributionChannel.Store), StringComparison.OrdinalIgnoreCase)
            ? DistributionChannel.Store
            : DistributionChannel.Website);
}
