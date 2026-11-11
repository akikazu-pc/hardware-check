using System.Globalization;
using System.Net.NetworkInformation;
using AkikazuHardwareCheck.Core.Hardware;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public enum LocalNetworkKind
{
    Wired,
    Wireless,
}

/// <summary>One physical adapter as seen locally. Link speed is the adapter's own rate, not the provider's plan.</summary>
public sealed record LocalNetworkAdapter(
    string Name,
    LocalNetworkKind Kind,
    bool IsUp,
    long SpeedBitsPerSecond,
    bool HasGateway);

/// <summary>
/// Local-only network facts for the rescue page. It enumerates adapters and gateways and never sends a packet, so it
/// remains usable when the internet is down.
/// </summary>
public sealed record LocalNetworkStatus(bool IsNetworkAvailable, IReadOnlyList<LocalNetworkAdapter> Adapters)
{
    private const double BITS_PER_MEGABIT = 1_000_000;
    private const double BITS_PER_GIGABIT = 1_000_000_000;

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
            var hasGateway = isUp && HasGateway(adapter);
            // Disconnected cards add noise, especially Bluetooth and secondary radio entries; show connected links.
            if (!isUp)
            {
                continue;
            }

            adapters.Add(new LocalNetworkAdapter(
                adapter.Name,
                NetworkCollector.IsWirelessCard(adapter.Description) ? LocalNetworkKind.Wireless : LocalNetworkKind.Wired,
                isUp,
                adapter.Speed,
                hasGateway));
        }

        return new LocalNetworkStatus(
            NetworkInterface.GetIsNetworkAvailable(),
            adapters.OrderByDescending(adapter => adapter.HasGateway)
                .ThenBy(adapter => adapter.Name, StringComparer.CurrentCultureIgnoreCase)
                .ToList());
    }

    /// <summary>A transient adapter can fail while it is being reset; the page then simply shows no gateway.</summary>
    private static bool HasGateway(NetworkInterface adapter)
    {
        try
        {
            return adapter.GetIPProperties().GatewayAddresses.Any(gateway =>
                !gateway.Address.Equals(System.Net.IPAddress.Any)
                && !gateway.Address.Equals(System.Net.IPAddress.IPv6Any));
        }
        catch (NetworkInformationException)
        {
            return false;
        }
    }

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
