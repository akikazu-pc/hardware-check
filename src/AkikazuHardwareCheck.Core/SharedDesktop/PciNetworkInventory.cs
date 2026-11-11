using System.Runtime.InteropServices;
using System.Text.Json;
using AkikazuHardwareCheck.Core.Hardware;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record PciNetworkDevice(string[] HardwareIds, string? SubsystemId, int? ProblemCode);

public sealed record PciNetworkDiagnostic(int SchemaVersion, int WindowsBuild, string Architecture, IReadOnlyList<PciNetworkDevice> Devices);

public static class PciNetworkInventory
{
    private static readonly JsonSerializerOptions ExportOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true,
    };

    public static PciNetworkDiagnostic Read()
    {
        var rows = Wmi.Query(Wmi.CIM_SCOPE,
            "SELECT HardwareID, CompatibleID, ConfigManagerErrorCode FROM Win32_PnPEntity WHERE Present = TRUE",
            item => Classify(item["HardwareID"] as string[] ?? [],
                item["CompatibleID"] as string[] ?? [], Wmi.Integer(item, "ConfigManagerErrorCode")));

        return new PciNetworkDiagnostic(1, Environment.OSVersion.Version.Build,
            RuntimeInformation.OSArchitecture.ToString(), rows.OfType<PciNetworkDevice>().ToArray());
    }

    public static PciNetworkDevice? Classify(string[] hardwareIds, string[] compatibleIds, int? problemCode)
    {
        // PCI class 02/80 is an "other network controller", not proof of Wi-Fi.
        var ids = hardwareIds.Where(id => id.StartsWith(@"PCI\VEN_", StringComparison.OrdinalIgnoreCase)).ToArray();
        if (ids.Length == 0 || !hardwareIds.Concat(compatibleIds).Any(IsNetworkController))
        {
            return null;
        }

        var subsystemId = ids.SelectMany(id => id.Split('&'))
            .FirstOrDefault(segment => segment.StartsWith("SUBSYS_", StringComparison.OrdinalIgnoreCase));
        return new PciNetworkDevice(ids, subsystemId, problemCode);
    }

    public static string Export(PciNetworkDiagnostic report) => JsonSerializer.Serialize(report, ExportOptions);

    private static bool IsNetworkController(string id) =>
        id.StartsWith(@"PCI\CC_0280", StringComparison.OrdinalIgnoreCase) ||
        (id.StartsWith(@"PCI\VEN_", StringComparison.OrdinalIgnoreCase) &&
         id.Split('&').Any(segment => segment.StartsWith("CC_0280", StringComparison.OrdinalIgnoreCase)));
}
