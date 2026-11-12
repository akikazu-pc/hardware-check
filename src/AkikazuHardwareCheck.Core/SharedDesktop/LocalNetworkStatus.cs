using System.Globalization;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using AkikazuHardwareCheck.Core.Hardware;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public enum LocalNetworkKind
{
    Wired,
    Wireless,
}

public enum NetworkRecoveryStage
{
    NoAdapter,
    Disconnected,
    NoUsableAddress,
    NoGateway,
    LocalOnly,
    SignInMayBeRequired,
    InternetReported,
    Unknown,
}

/// <summary>One physical adapter as seen locally. Link speed is the adapter's own rate, not the provider's plan.</summary>
public sealed record LocalNetworkAdapter(
    string Name,
    LocalNetworkKind Kind,
    bool IsUp,
    long SpeedBitsPerSecond,
    bool HasGateway,
    string? Description = null)
{
    public bool? HasUsableAddress { get; init; }
}

/// <summary>
/// Local-only network facts for the rescue page. It enumerates adapters and gateways and never sends a packet, so it
/// remains usable when the internet is down.
/// </summary>
public sealed record LocalNetworkStatus(bool IsNetworkAvailable, IReadOnlyList<LocalNetworkAdapter> Adapters)
{
    private const double BITS_PER_MEGABIT = 1_000_000;
    private const double BITS_PER_GIGABIT = 1_000_000_000;

    public NetworkRecoveryStage RecoveryStage { get; init; } = NetworkRecoveryStage.Unknown;

    public static LocalNetworkStatus Read()
    {
        try
        {
            return ReadCore();
        }
        catch (NetworkInformationException)
        {
            // A resetting adapter stack must not take down the rescue page.
            return new LocalNetworkStatus(false, []);
        }
    }

    private static LocalNetworkStatus ReadCore()
    {
        var adapters = new List<LocalNetworkAdapter>();
        foreach (var adapter in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (adapter.NetworkInterfaceType is not (NetworkInterfaceType.Ethernet or NetworkInterfaceType.Wireless80211)
                || !NetworkCollector.IsPhysical(adapter.Description))
            {
                continue;
            }

            var isUp = adapter.OperationalStatus == OperationalStatus.Up;
            var (hasGateway, hasAddress) = isUp ? ReadIpState(adapter) : (false, null);

            adapters.Add(new LocalNetworkAdapter(
                adapter.Name,
                adapter.NetworkInterfaceType == NetworkInterfaceType.Wireless80211
                    || NetworkCollector.IsWirelessCard(adapter.Description) ? LocalNetworkKind.Wireless : LocalNetworkKind.Wired,
                isUp,
                adapter.Speed,
                hasGateway,
                adapter.Description) { HasUsableAddress = hasAddress });
        }

        return new LocalNetworkStatus(
            NetworkInterface.GetIsNetworkAvailable(),
            adapters.OrderByDescending(adapter => adapter.HasGateway)
                .ThenByDescending(adapter => adapter.IsUp)
                .ThenBy(adapter => adapter.Name, StringComparer.CurrentCultureIgnoreCase)
                .ToList()) { RecoveryStage = Assess(adapters, ReadInternetHint()) };
    }

    public static NetworkRecoveryStage Assess(IReadOnlyList<LocalNetworkAdapter> adapters, NetworkRecoveryStage internetHint)
    {
        if (internetHint is NetworkRecoveryStage.InternetReported or NetworkRecoveryStage.SignInMayBeRequired)
        {
            return internetHint;
        }
        if (adapters.Count == 0)
        {
            return NetworkRecoveryStage.NoAdapter;
        }
        var connected = adapters.Where(adapter => adapter.IsUp).ToArray();
        if (connected.Length == 0)
        {
            return NetworkRecoveryStage.Disconnected;
        }
        if (connected.All(adapter => adapter.HasUsableAddress == false))
        {
            return NetworkRecoveryStage.NoUsableAddress;
        }
        if (connected.All(adapter => !adapter.HasGateway && adapter.HasUsableAddress is not null))
        {
            return NetworkRecoveryStage.NoGateway;
        }
        return internetHint;
    }

    private static (bool HasGateway, bool? HasUsableAddress) ReadIpState(NetworkInterface adapter)
    {
        try
        {
            var ip = adapter.GetIPProperties();
            var hasGateway = ip.GatewayAddresses.Any(gateway =>
                !gateway.Address.Equals(IPAddress.Any) && !gateway.Address.Equals(IPAddress.IPv6Any));
            var hasAddress = ip.UnicastAddresses.Any(entry =>
            {
                var address = entry.Address;
                if (address.AddressFamily == AddressFamily.InterNetwork)
                {
                    var bytes = address.GetAddressBytes();
                    return bytes[0] != 0 && !IPAddress.IsLoopback(address) && (bytes[0] != 169 || bytes[1] != 254);
                }
                return address.AddressFamily == AddressFamily.InterNetworkV6 && !address.IsIPv6LinkLocal
                    && !IPAddress.IsLoopback(address) && !address.Equals(IPAddress.IPv6Any);
            });
            return (hasGateway, hasAddress);
        }
        catch (NetworkInformationException)
        {
            return (false, null);
        }
    }

    private static NetworkRecoveryStage ReadInternetHint()
    {
        if (!OperatingSystem.IsWindowsVersionAtLeast(10, 0, 19041) || GetNetworkConnectivityHint(out var hint) != 0)
        {
            return NetworkRecoveryStage.Unknown;
        }
        return hint.Level switch
        {
            ConnectivityLevel.None or ConnectivityLevel.LocalAccess => NetworkRecoveryStage.LocalOnly,
            ConnectivityLevel.InternetAccess => NetworkRecoveryStage.InternetReported,
            ConnectivityLevel.ConstrainedInternetAccess => NetworkRecoveryStage.SignInMayBeRequired,
            _ => NetworkRecoveryStage.Unknown,
        };
    }

    private enum ConnectivityLevel { Unknown, None, LocalAccess, InternetAccess, ConstrainedInternetAccess }

    [StructLayout(LayoutKind.Sequential)]
    private struct ConnectivityHint
    {
        public ConnectivityLevel Level;
        public int Cost;
        public byte ApproachingDataLimit;
        public byte OverDataLimit;
        public byte Roaming;
    }

    [DllImport("iphlpapi.dll", ExactSpelling = true)]
    private static extern uint GetNetworkConnectivityHint(out ConnectivityHint hint);

    /// <summary>Null means the adapter did not report a rate; the page then omits the cell instead of showing zero.</summary>
    public static string? FormatLinkSpeed(long bitsPerSecond)
    {
        if (bitsPerSecond <= 0)
        {
            return null;
        }

        return bitsPerSecond >= BITS_PER_GIGABIT
            ? $"{(bitsPerSecond / BITS_PER_GIGABIT).ToString("0.#", CultureInfo.InvariantCulture)} Gbps"
            : $"{(bitsPerSecond / BITS_PER_MEGABIT).ToString("0", CultureInfo.InvariantCulture)} Mbps";
    }
}
