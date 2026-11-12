using System.ComponentModel;
using System.Management;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using AkikazuHardwareCheck.Core.Hardware;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public enum OfflineInstallResult
{
    Bound,
    RestartRequired,
    BindingUnconfirmed,
    NoEligibleDevice,
    PackageRejected,
    InstallationFailed,
}

public sealed record OfflineDriverIdentity(string Signer, string Sha256);

public static class OfflineDriverInstaller
{
    public static OfflineDriverIdentity? Verify(string path)
    {
        using var inf = File.OpenRead(path);
        return VerifyOpenInf(path, inf);
    }

    public static OfflineInstallResult Install(string path, string hardwareId, string expectedHash)
    {
        try
        {
            if (!Path.IsPathFullyQualified(path) ||
                !string.Equals(Path.GetExtension(path), ".inf", StringComparison.OrdinalIgnoreCase) ||
                string.IsNullOrWhiteSpace(hardwareId))
            {
                return OfflineInstallResult.PackageRejected;
            }

            // Hold the INF open for reading until Windows consumes it so it cannot be replaced after verification.
            using var inf = File.OpenRead(path);
            var identity = VerifyOpenInf(path, inf);
            if (identity is null || !string.Equals(identity.Sha256, expectedHash, StringComparison.OrdinalIgnoreCase))
            {
                return OfflineInstallResult.PackageRejected;
            }

            var candidates = PciNetworkInventory.Read().Devices;
            var eligible = SelectMissingMatch(OfflineInfMatcher.Match(path, candidates));
            var present = ReadDevices(hardwareId);
            if (eligible is null || !string.Equals(eligible.HardwareId, hardwareId, StringComparison.OrdinalIgnoreCase) ||
                present is not [{ InstanceId: { Length: > 0 } instanceId, ProblemCode: 28, Service: null or "" }])
            {
                return OfflineInstallResult.NoEligibleDevice;
            }

            // Zero flags leave Windows ranking and driver-package validation in effect.
            if (!UpdateDriverForPlugAndPlayDevices(IntPtr.Zero, hardwareId, path, 0, out var restartRequired))
            {
                return OfflineInstallResult.InstallationFailed;
            }

            if (restartRequired)
            {
                return OfflineInstallResult.RestartRequired;
            }

            try
            {
                return ReadDevices(hardwareId) is [{ InstanceId: var boundId, ProblemCode: 0, Service: { Length: > 0 } }] &&
                    string.Equals(boundId, instanceId, StringComparison.OrdinalIgnoreCase) &&
                    VerifyBoundPackage(instanceId, identity.Sha256, OfflineInfMatcher.ReadDriverVersion(path))
                    ? OfflineInstallResult.Bound
                    : OfflineInstallResult.BindingUnconfirmed;
            }
            catch (Exception exception) when (exception is ManagementException or COMException or UnauthorizedAccessException or IOException)
            {
                return OfflineInstallResult.BindingUnconfirmed;
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ManagementException
            or COMException or Win32Exception or ArgumentException or NotSupportedException)
        {
            return OfflineInstallResult.PackageRejected;
        }
    }

    public static OfflineInfMatch? SelectMissingMatch(IReadOnlyList<OfflineInfMatch> matches) =>
        matches is [{ Device.ProblemCode: 28 } match] ? match : null;

    private static OfflineDriverIdentity? VerifyOpenInf(string path, Stream inf)
    {
        var signer = new InfSignerInfo { Size = (uint)Marshal.SizeOf<InfSignerInfo>() };
        return SetupVerifyInfFile(path, IntPtr.Zero, ref signer)
            ? new OfflineDriverIdentity(signer.DigitalSigner, Convert.ToHexString(SHA256.HashData(inf)))
            : null;
    }

    private static PresentDevice[] ReadDevices(string hardwareId) =>
        Wmi.Query(Wmi.CIM_SCOPE,
            "SELECT DeviceID, HardwareID, ConfigManagerErrorCode, Service FROM Win32_PnPEntity WHERE Present = TRUE",
            item => (item["HardwareID"] as string[] ?? []).Contains(hardwareId, StringComparer.OrdinalIgnoreCase)
                ? new PresentDevice(Wmi.Text(item, "DeviceID"), Wmi.Integer(item, "ConfigManagerErrorCode"), Wmi.Text(item, "Service"))
                : null).OfType<PresentDevice>().ToArray();

    private static bool VerifyBoundPackage(string instanceId, string expectedHash, string? expectedVersion)
    {
        var bindings = Wmi.Query(Wmi.CIM_SCOPE, "SELECT DeviceID, InfName, DriverVersion FROM Win32_PnPSignedDriver",
            item => string.Equals(Wmi.Text(item, "DeviceID"), instanceId, StringComparison.OrdinalIgnoreCase)
                ? new DriverBinding(Wmi.Text(item, "InfName"), Wmi.Text(item, "DriverVersion"))
                : null).OfType<DriverBinding>().ToArray();

        if (bindings is not [{ InfName: { Length: > 0 } name, DriverVersion: var version }] ||
            !Version.TryParse(expectedVersion, out var expected) ||
            !Version.TryParse(version, out var actual) || actual != expected ||
            !string.Equals(name, Path.GetFileName(name), StringComparison.Ordinal) ||
            !string.Equals(Path.GetExtension(name), ".inf", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var storePath = new StringBuilder(4096);
        if (!SetupGetInfDriverStoreLocation(name, IntPtr.Zero, null, storePath, storePath.Capacity, out _))
        {
            return false;
        }

        using var storedInf = File.OpenRead(storePath.ToString());
        return string.Equals(Convert.ToHexString(SHA256.HashData(storedInf)), expectedHash, StringComparison.OrdinalIgnoreCase);
    }

    private sealed record PresentDevice(string? InstanceId, int? ProblemCode, string? Service);
    private sealed record DriverBinding(string? InfName, string? DriverVersion);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct InfSignerInfo
    {
        public uint Size;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string CatalogFile;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string DigitalSigner;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string DigitalSignerVersion;
    }

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupVerifyInfFile(string infName, IntPtr platform, ref InfSignerInfo signer);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupGetInfDriverStoreLocation(string fileName, IntPtr platform, string? locale,
        StringBuilder storePath, int size, out uint requiredSize);

    [DllImport("newdev.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool UpdateDriverForPlugAndPlayDevices(IntPtr parent, string hardwareId, string path,
        uint flags, [MarshalAs(UnmanagedType.Bool)] out bool restartRequired);
}
