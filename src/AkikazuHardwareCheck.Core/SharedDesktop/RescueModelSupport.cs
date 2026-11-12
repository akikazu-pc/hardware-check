using AkikazuHardwareCheck.Core.Hardware;
using Microsoft.VisualBasic.FileIO;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record RescueModelSupport(string Model, bool IsLaptop, string? OfficialPage)
{
    private static readonly Lazy<IReadOnlyDictionary<string, string>> Pages = new(ReadPages);

    public static RescueModelSupport? Read()
    {
        var computer = ComputerCollector.Read();
        if (computer is { IsLaptop: true })
        {
            return Describe(computer.Model, true);
        }

        var board = Wmi.Query(Wmi.CIM_SCOPE, "SELECT Product, Version FROM Win32_BaseBoard",
            item => (Model: Wmi.Text(item, "Product"), Revision: Wmi.Text(item, "Version"))).FirstOrDefault();
        return Describe(board.Model, false, board.Revision);
    }

    public static RescueModelSupport? Describe(string? model, bool isLaptop, string? revision = null)
    {
        if (ComputerCollector.IsPlaceholder(model))
        {
            return null;
        }

        var page = Pages.Value.GetValueOrDefault(Normalize(model!));
        if (page is null && isLaptop)
        {
            page = Pages.Value.GetValueOrDefault(Normalize(model!.Split('_', 2)[0]));
        }
        if (page is null && !isLaptop && !string.IsNullOrWhiteSpace(revision))
        {
            page = Pages.Value.GetValueOrDefault(Normalize($"{model} rev. {revision.TrimStart('v', 'V')}"));
        }

        return new RescueModelSupport(model!, isLaptop, page);
    }

    private static IReadOnlyDictionary<string, string> ReadPages()
    {
        using var stream = typeof(RescueModelSupport).Assembly.GetManifestResourceStream("rescue.driver-index.csv")
            ?? throw new InvalidOperationException("The model support index is missing.");
        using var csv = new TextFieldParser(stream);
        csv.SetDelimiters(",");
        csv.ReadFields();
        var entries = new List<(string Model, string Page)>();
        while (csv.ReadFields() is { Length: >= 2 } row)
        {
            if (Uri.TryCreate(row[1], UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps)
            {
                foreach (var model in row[0].Split(';', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries))
                {
                    var parts = model.Split(" rev. ", 2, StringSplitOptions.None);
                    if (parts.Length == 2)
                    {
                        entries.AddRange(parts[1].Split('/').Select(revision =>
                            (Normalize($"{parts[0]} rev. {revision}"), row[1])));
                    }
                    else
                    {
                        entries.Add((Normalize(model), row[1]));
                    }
                    if (model.StartsWith("ASUS ROG ", StringComparison.Ordinal) ||
                        model.StartsWith("ASUS TUF Gaming ", StringComparison.Ordinal))
                    {
                        entries.Add((Normalize(model.Split(' ')[^1]), row[1]));
                    }
                }
            }
        }

        var pages = entries.GroupBy(entry => entry.Model)
            .Where(group => group.Select(entry => entry.Page).Distinct().Count() == 1)
            .ToDictionary(group => group.Key, group => group.First().Page);
        using var boardStream = typeof(RescueModelSupport).Assembly.GetManifestResourceStream("rescue.asus-board-index.csv")
            ?? throw new InvalidOperationException("The ASUS board index is missing.");
        using var boards = new TextFieldParser(boardStream);
        boards.SetDelimiters(",");
        boards.ReadFields();
        while (boards.ReadFields() is { Length: >= 5 } row)
        {
            if (Uri.TryCreate(row[4], UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps &&
                uri.Host.Equals("www.asus.com", StringComparison.OrdinalIgnoreCase))
            {
                pages.TryAdd(Normalize(row[2]), uri.GetLeftPart(UriPartial.Path).TrimEnd('/') + "/helpdesk_download/");
            }
        }

        return pages;
    }

    private static string Normalize(string model)
    {
        var value = model.Trim().ToUpperInvariant();
        foreach (var prefix in new[] { "ASUS ", "GIGABYTE ", "ALIENWARE " })
        {
            if (value.StartsWith(prefix, StringComparison.Ordinal))
            {
                value = value[prefix.Length..];
                break;
            }
        }

        return new string(value.Where(char.IsLetterOrDigit).ToArray());
    }
}
