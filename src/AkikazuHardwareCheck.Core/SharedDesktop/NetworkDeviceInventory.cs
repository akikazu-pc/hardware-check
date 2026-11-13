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
    string[] HardwareIds, string? SubsystemId, int? ProblemCode, NetworkCandidateKind Kind = NetworkCandidateKind.PciController,
    string? DriverVersion = null);

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
        var driverVersions = Wmi.Query(Wmi.CIM_SCOPE,
                "SELECT DeviceID, DriverVersion FROM Win32_PnPSignedDriver",
                item => (Id: Wmi.Text(item, "DeviceID"), Version: Wmi.Text(item, "DriverVersion")))
            .Where(pair => !string.IsNullOrWhiteSpace(pair.Id))
            .GroupBy(pair => pair.Id!, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(group => group.Key, group => group.First().Version, StringComparer.OrdinalIgnoreCase);

        var rows = Wmi.Query(Wmi.CIM_SCOPE,
            "SELECT DeviceID, HardwareID, CompatibleID, ConfigManagerErrorCode, PNPClass FROM Win32_PnPEntity WHERE Present = TRUE",
            item =>
            {
                var deviceId = Wmi.Text(item, "DeviceID");
                var version = deviceId is not null && driverVersions.TryGetValue(deviceId, out var found) ? found : null;
                return Classify(item["HardwareID"] as string[] ?? [], item["CompatibleID"] as string[] ?? [],
                    Wmi.Integer(item, "ConfigManagerErrorCode"), Wmi.Text(item, "PNPClass"), version);
            });

        return new NetworkDeviceDiagnostic(2, Environment.OSVersion.Version.Build,
            RuntimeInformation.OSArchitecture.ToString(), rows.OfType<NetworkDeviceCandidate>().ToArray());
    }

    public static NetworkDeviceCandidate? Classify(string[] hardwareIds, string[] compatibleIds, int? problemCode,
        string? setupClass = null, string? driverVersion = null)
    {
        var pciIds = hardwareIds.Where(id => id.StartsWith(@"PCI\VEN_", StringComparison.OrdinalIgnoreCase)).ToArray();
        var deviceIds = hardwareIds.Concat(compatibleIds);
        var ethernetProblem = problemCode > 0 && deviceIds.Any(id => HasPciClass(id, "CC_0200"));
        if (pciIds.Length > 0 && (ethernetProblem || deviceIds.Any(id => HasPciClass(id, "CC_0280"))))
        {
            var subsystemId = pciIds.SelectMany(id => id.Split('&'))
                .FirstOrDefault(segment => segment.StartsWith("SUBSYS_", StringComparison.OrdinalIgnoreCase));
            // Windows may put the vendor/device-only ID used by a signed INF in CompatibleID.
            var matchIds = pciIds.Concat(compatibleIds.Where(id => IsPciCompatibleDeviceId(id, pciIds)))
                .Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
            return new NetworkDeviceCandidate(matchIds, subsystemId, problemCode,
                ethernetProblem ? NetworkCandidateKind.PciEthernet : NetworkCandidateKind.PciController, driverVersion);
        }

        var usbIds = hardwareIds.Where(IsUsbProductId).ToArray();
        if (usbIds.Length == 0)
        {
            return null;
        }

        if (string.Equals(setupClass, "Net", StringComparison.OrdinalIgnoreCase))
        {
            return new NetworkDeviceCandidate(usbIds, null, problemCode, NetworkCandidateKind.UsbNetwork, driverVersion);
        }

        // Without a driver, the USB class may be unavailable. Keep these entries unclassified
        // until a network INF supplies an exact product/interface hardware ID.
        if (problemCode == 28 && (string.IsNullOrWhiteSpace(setupClass) ||
                string.Equals(setupClass, "Unknown", StringComparison.OrdinalIgnoreCase)))
        {
            return new NetworkDeviceCandidate(usbIds, null, problemCode, NetworkCandidateKind.UsbUnidentified, driverVersion);
        }

        return null;
    }

    public static string Export(NetworkDeviceDiagnostic report) => JsonSerializer.Serialize(report, ExportOptions);

    private static bool IsPciCompatibleDeviceId(string id, string[] hardwareIds)
    {
        const int pciChipsetLength = 21; // PCI\VEN_####&DEV_####
        var chipset = OfflineInfMatcher.ChipsetId(id);
        return id.StartsWith(@"PCI\VEN_", StringComparison.OrdinalIgnoreCase) && chipset.Length == pciChipsetLength &&
            (id.Length == chipset.Length ||
             (id.Length == chipset.Length + 7 && id.AsSpan(chipset.Length).StartsWith("&REV_", StringComparison.OrdinalIgnoreCase))) &&
            hardwareIds.Any(hardwareId => string.Equals(OfflineInfMatcher.ChipsetId(hardwareId), chipset,
                StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsUsbProductId(string id) =>
        id.StartsWith(@"USB\VID_", StringComparison.OrdinalIgnoreCase) &&
        id.Contains("&PID_", StringComparison.OrdinalIgnoreCase);

    private static bool HasPciClass(string id, string classCode) =>
        id.StartsWith(@"PCI\" + classCode, StringComparison.OrdinalIgnoreCase) ||
        (id.StartsWith(@"PCI\VEN_", StringComparison.OrdinalIgnoreCase) &&
         id.Split('&').Any(segment => segment.StartsWith(classCode, StringComparison.OrdinalIgnoreCase)));
}
