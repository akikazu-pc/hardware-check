using AkikazuHardwareCheck.Core.Localization;
using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.App;

/// <summary>
/// The rescue module's page. It reports local adapter and module facts only; it sends no packets, so it remains
/// useful when the internet is down. Driver installation and rollback are deliberately not part of this prototype.
/// </summary>
internal sealed class NetworkRescueView : UserControl
{
    private const float HEADING_FONT_SIZE = 12f;

    private readonly IReadOnlyList<InstalledModule> _modules;
    private readonly Label _heading = Ui.Label(isBold: true);
    private readonly Label _note = Ui.Label();
    private readonly Label _networkHeading = Ui.Label(isBold: true);
    private readonly Button _refresh = Ui.Button();
    private readonly ListView _adapters = ListViewTable.Create();
    private readonly Label _modulesHeading = Ui.Label(isBold: true);
    private readonly ListView _moduleList = ListViewTable.Create();
    private Translator _t;

    public NetworkRescueView(Translator t, IReadOnlyList<InstalledModule> modules)
    {
        _t = t;
        _modules = modules;
        Dock = DockStyle.Fill;
        Margin = new Padding(0);
        BackColor = SystemColors.Control;
        Padding = new Padding(Ui.SPACING * 2);

        _heading.Font = new Font(Font.FontFamily, HEADING_FONT_SIZE, FontStyle.Bold);
        _note.ForeColor = Ui.MutedTextColor;
        _refresh.Click += (_, _) => RefreshStatus();

        _adapters.Columns.Add("", 260);
        _adapters.Columns.Add("", 90);
        _adapters.Columns.Add("", 90);
        _adapters.Columns.Add("", 120);
        _adapters.Columns.Add("", 90);
        _moduleList.Columns.Add("", 260);
        _moduleList.Columns.Add("", 120);
        _moduleList.Columns.Add("", 120);

        Controls.Add(BuildLayout());
        ListViewTable.EnableSort(_adapters);
        ListViewTable.EnableSort(_moduleList);
        ListViewTable.EnableColumnMenu(_adapters, _t);
        ListViewTable.EnableColumnMenu(_moduleList, _t);
        ListViewTable.EnableCopy(_adapters, _t);
        ListViewTable.EnableCopy(_moduleList, _t);
        Resize += (_, _) => FitNote();
        ApplyLanguage(t);
    }

    public void ApplyLanguage(Translator t)
    {
        _t = t;
        _heading.Font = new Font(Font.FontFamily, HEADING_FONT_SIZE, FontStyle.Bold);
        _heading.Text = t["rescue.heading"];
        _note.Text = t["rescue.note"];
        _networkHeading.Text = t["rescue.network"];
        _refresh.Text = t["rescue.refresh"];
        _modulesHeading.Text = t["rescue.modules"];
        _adapters.Columns[0].Text = t["rescue.adapter"];
        _adapters.Columns[1].Text = t["rescue.kind"];
        _adapters.Columns[2].Text = t["rescue.state"];
        _adapters.Columns[3].Text = t["rescue.linkSpeed"];
        _adapters.Columns[4].Text = t["rescue.gateway"];
        _moduleList.Columns[0].Text = t["rescue.module"];
        _moduleList.Columns[1].Text = t["ui.aboutVersion"];
        _moduleList.Columns[2].Text = t["rescue.interface"];
        FitNote();
        RefreshStatus();
    }

    public void RefreshStatus()
    {
        if (IsDisposed)
        {
            return;
        }

        var status = LocalNetworkStatus.Read();
        _adapters.BeginUpdate();
        _adapters.Items.Clear();
        foreach (var adapter in status.Adapters)
        {
            var item = new ListViewItem(adapter.Name);
            item.SubItems.Add(adapter.Kind == LocalNetworkKind.Wireless ? _t["rescue.wireless"] : _t["rescue.wired"]);
            item.SubItems.Add(adapter.IsUp ? _t["rescue.up"] : _t["rescue.down"]);
            item.SubItems.Add(LocalNetworkStatus.FormatLinkSpeed(adapter.SpeedBitsPerSecond) ?? "");
            item.SubItems.Add(adapter.HasGateway ? _t["rescue.present"] : "");
            _adapters.Items.Add(item);
        }

        if (_adapters.Items.Count == 0)
        {
            _adapters.Items.Add(new ListViewItem(_t["rescue.noAdapter"]));
        }

        _adapters.EndUpdate();

        _moduleList.BeginUpdate();
        _moduleList.Items.Clear();
        foreach (var module in _modules)
        {
            var item = new ListViewItem(_t[module.Module.DisplayNameKey()]);
            item.SubItems.Add(module.Version);
            item.SubItems.Add(module.MinimumHostInterface.ToString(System.Globalization.CultureInfo.InvariantCulture));
            _moduleList.Items.Add(item);
        }

        if (_moduleList.Items.Count == 0)
        {
            _moduleList.Items.Add(new ListViewItem(_t["rescue.noModules"]));
        }

        _moduleList.EndUpdate();
    }

    private Control BuildLayout()
    {
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 6, Margin = new Padding(0) };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 55));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 45));

        var headingRow = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, Margin = new Padding(0) };
        headingRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        headingRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        _heading.Anchor = AnchorStyles.Left;
        _refresh.Anchor = AnchorStyles.Right;
        _refresh.Margin = new Padding(0, 0, 0, Ui.SPACING);
        headingRow.Controls.Add(_heading, 0, 0);
        headingRow.Controls.Add(_refresh, 1, 0);
        root.Controls.Add(headingRow, 0, 0);

        _note.Dock = DockStyle.Top;
        _note.Margin = new Padding(0, 0, 0, Ui.SPACING);
        root.Controls.Add(_note, 0, 1);

        _networkHeading.Margin = new Padding(0, Ui.SPACING, 0, Ui.SPACING / 2);
        root.Controls.Add(_networkHeading, 0, 2);

        _adapters.Margin = new Padding(0, 0, 0, Ui.SPACING);
        root.Controls.Add(_adapters, 0, 3);

        _modulesHeading.Margin = new Padding(0, Ui.SPACING, 0, Ui.SPACING / 2);
        root.Controls.Add(_modulesHeading, 0, 4);

        _moduleList.Margin = new Padding(0);
        root.Controls.Add(_moduleList, 0, 5);
        return root;
    }

    private void FitNote()
    {
        var width = Math.Max(LogicalToDeviceUnits(240), ClientSize.Width - Padding.Horizontal);
        _note.MaximumSize = new Size(width, 0);
    }
}
