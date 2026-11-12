using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
using AkikazuHardwareCheck.Core.Hardware;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

[JsonConverter(typeof(JsonStringEnumConverter<NetworkCandidateKind>))]
public enum NetworkCandidateKind
{
    PciController,
    UsbNetwork,
    UsbUnidentified,
    PciEthernet,
}

public sealed record NetworkDeviceCandidate(
    string[] HardwareIds, string? SubsystemId, int? ProblemCode, NetworkCandidateKind Kind = NetworkCandidateKind.PciController);

public sealed record NetworkDeviceDiagnostic(int SchemaVersion, int WindowsBuild, string Architecture, IReadOnlyList<NetworkDeviceCandidate> Devices);

public static class NetworkDeviceInventory
{
    private static readonly JsonSerializerOptions ExportOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true,
    };

    public static NetworkDeviceDiagnostic Read()
    {
        var rows = Wmi.Query(Wmi.CIM_SCOPE,
            "SELECT HardwareID, CompatibleID, ConfigManagerErrorCode, PNPClass FROM Win32_PnPEntity WHERE Present = TRUE",
            item => Classify(item["HardwareID"] as string[] ?? [], item["CompatibleID"] as string[] ?? [],
                Wmi.Integer(item, "ConfigManagerErrorCode"), Wmi.Text(item, "PNPClass")));

        return new NetworkDeviceDiagnostic(2, Environment.OSVersion.Version.Build,
            RuntimeInformation.OSArchitecture.ToString(), rows.OfType<NetworkDeviceCandidate>().ToArray());
    }

    public static NetworkDeviceCandidate? Classify(string[] hardwareIds, string[] compatibleIds, int? problemCode,
        string? setupClass = null)
    {
        var pciIds = hardwareIds.Where(id => id.StartsWith(@"PCI\VEN_", StringComparison.OrdinalIgnoreCase)).ToArray();
        var deviceIds = hardwareIds.Concat(compatibleIds);
        var ethernetProblem = problemCode > 0 && deviceIds.Any(id => HasPciClass(id, "CC_0200"));
        if (pciIds.Length > 0 && (ethernetProblem || deviceIds.Any(id => HasPciClass(id, "CC_0280"))))
        {
            var subsystemId = pciIds.SelectMany(id => id.Split('&'))
                .FirstOrDefault(segment => segment.StartsWith("SUBSYS_", StringComparison.OrdinalIgnoreCase));
            return new NetworkDeviceCandidate(pciIds, subsystemId, problemCode,
                ethernetProblem ? NetworkCandidateKind.PciEthernet : NetworkCandidateKind.PciController);
        }

        var usbIds = hardwareIds.Where(IsUsbProductId).ToArray();
        if (usbIds.Length == 0)
        {
            return null;
        }

        if (string.Equals(setupClass, "Net", StringComparison.OrdinalIgnoreCase))
        {
            return new NetworkDeviceCandidate(usbIds, null, problemCode, NetworkCandidateKind.UsbNetwork);
        }

        // Without a driver, the USB class may be unavailable. Keep these entries unclassified
        // until a network INF supplies an exact product/interface hardware ID.
        if (problemCode == 28 && (string.IsNullOrWhiteSpace(setupClass) ||
                string.Equals(setupClass, "Unknown", StringComparison.OrdinalIgnoreCase)))
        {
            return new NetworkDeviceCandidate(usbIds, null, problemCode, NetworkCandidateKind.UsbUnidentified);
        }

        return null;
    }

    public static string Export(NetworkDeviceDiagnostic report) => JsonSerializer.Serialize(report, ExportOptions);

    private static bool IsUsbProductId(string id) =>
        id.StartsWith(@"USB\VID_", StringComparison.OrdinalIgnoreCase) &&
        id.Contains("&PID_", StringComparison.OrdinalIgnoreCase);

    private static bool HasPciClass(string id, string classCode) =>
        id.StartsWith(@"PCI\" + classCode, StringComparison.OrdinalIgnoreCase) ||
        (id.StartsWith(@"PCI\VEN_", StringComparison.OrdinalIgnoreCase) &&
         id.Split('&').Any(segment => segment.StartsWith(classCode, StringComparison.OrdinalIgnoreCase)));
}
