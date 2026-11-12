using System.Text;
using System.Text.RegularExpressions;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

internal static class RescueCatalogQuery
{
    private static readonly (string Alias, string Brand)[] Brands =
    [
        ("华硕", "ASUS"), ("華碩", "ASUS"), ("エイスース", "ASUS"), ("华擎", "ASRock"), ("華擎", "ASRock"),
        ("技嘉", "GIGABYTE"), ("微星", "MSI"), ("七彩虹", "Colorful"), ("联想", "Lenovo"), ("聯想", "Lenovo"),
        ("レノボ", "Lenovo"), ("戴尔", "Dell"), ("戴爾", "Dell"), ("デル", "Dell"), ("惠普", "HP"),
        ("宏碁", "Acer"), ("エイサー", "Acer"), ("富士通", "Fujitsu"), ("松下", "Panasonic"),
        ("パナソニック", "Panasonic"), ("ダイナブック", "Dynabook"), ("小米", "Xiaomi"), ("シャオミ", "Xiaomi"),
        ("荣耀", "HONOR"), ("榮耀", "HONOR"), ("友讯", "D-Link"), ("友訊", "D-Link"), ("微软", "Microsoft"),
        ("微軟", "Microsoft"), ("マイクロソフト", "Microsoft"), ("苹果", "Apple"), ("蘋果", "Apple"),
    ];

    private static readonly Regex LeadingBrand = new(
        $@"^\s*(?<brand>{string.Join('|', Brands.Select(row => row.Brand).Distinct().Select(Regex.Escape))})\s+",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    private static readonly (Regex Pattern, RescueDeviceCategory Category, RescueDeviceTag? Tag)[] Categories =
    [
        (Words("Windows 平板", "Windows タブレット", "Windows tablet", "平板电脑", "平板電腦", "平板"), RescueDeviceCategory.Other, RescueDeviceTag.WindowsTablet),
        (Words("Windows 掌机", "Windows 掌機", "Windows ハンドヘルド", "Windows handheld", "掌机", "掌機"), RescueDeviceCategory.Other, RescueDeviceTag.Handheld),
        (Words("迷你电脑", "迷你電腦", "ミニ PC", "mini pc"), RescueDeviceCategory.Other, RescueDeviceTag.MiniPc),
        (Words("一体机", "一體機", "一体型 PC", "all-in-one", "all in one", "aio"), RescueDeviceCategory.Other, RescueDeviceTag.AllInOne),
        (Words("独立网卡", "獨立網卡", "網路卡", "网卡", "ネットワークアダプター", "network adapter"), RescueDeviceCategory.Other, RescueDeviceTag.NetworkAdapter),
        (Words("单板电脑", "單板電腦", "シングルボードコンピューター", "single-board computer", "single board computer"), RescueDeviceCategory.Other, RescueDeviceTag.SingleBoardComputer),
        (Words("家庭影院电脑", "家庭劇院電腦", "ホームシアター PC", "htpc"), RescueDeviceCategory.Other, RescueDeviceTag.Htpc),
        (Words("Windows 手机", "Windows 手機", "Windows Phone"), RescueDeviceCategory.Other, RescueDeviceTag.WindowsPhone),
        (Words("改装 Chromebook", "改裝 Chromebook", "改造 Chromebook", "modified Chromebook"), RescueDeviceCategory.Other, RescueDeviceTag.ModifiedChromebook),
        (Words("品牌台式机", "品牌桌上型電腦", "メーカー製デスクトップ PC", "branded desktop"), RescueDeviceCategory.Other, RescueDeviceTag.BrandedDesktop),
        (Words("工作站", "ワークステーション", "workstation"), RescueDeviceCategory.Other, RescueDeviceTag.Workstation),
        (Words("主板", "主機板", "マザーボード", "motherboard"), RescueDeviceCategory.DiyDesktop, null),
        (Words("笔记本电脑", "筆記型電腦", "笔记本", "筆電", "ノートパソコン", "ノート PC", "ノートPC", "laptop", "notebook"), RescueDeviceCategory.Laptop, null),
    ];

    public static (string Text, RescueDeviceCategory? Category, RescueDeviceTag? Tag) Parse(string query)
    {
        var text = query.Normalize(NormalizationForm.FormKC);
        if (text.Any(character => character >= '\u3000'))
        {
            foreach (var (alias, brand) in Brands)
            {
                text = text.Replace(alias, $" {brand} ", StringComparison.Ordinal);
            }
        }

        foreach (var (pattern, category, tag) in Categories)
        {
            var match = pattern.Match(text);
            // A category qualifier must stand on its own or lead the query. This preserves actual names such as HP Z4 G4 Workstation.
            if (match.Success)
            {
                return (text[(match.Index + match.Length)..].Trim(), category, tag);
            }
        }

        var brandPrefix = LeadingBrand.Match(text);
        if (brandPrefix.Success)
        {
            var remainder = text[brandPrefix.Length..];
            foreach (var (pattern, category, tag) in Categories)
            {
                var match = pattern.Match(remainder);
                if (match.Success)
                {
                    return ($"{brandPrefix.Groups["brand"].Value} {remainder[match.Length..].Trim()}".TrimEnd(), category, tag);
                }
            }
        }

        return (text.Trim(), null, null);
    }

    private static Regex Words(params string[] aliases) => new(
        $@"^\s*(?:{string.Join('|', aliases.Select(alias => Regex.Escape(alias) + (char.IsAsciiLetter(alias[^1]) ? "(?![a-z])" : "")))})",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
}
