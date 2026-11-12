using System.Diagnostics;
using System.IO.Compression;
using AkikazuHardwareCheck.Core.Configuration;
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
    private readonly string? _portableDriverDirectory;
    private readonly Label _heading = Ui.Label(isBold: true);
    private readonly Label _note = Ui.Label();
    private readonly Label _networkHeading = Ui.Label(isBold: true);
    private readonly Button _refresh = Ui.Button();
    private readonly ListView _adapters = ListViewTable.Create();
    private readonly ListView _moduleList = ListViewTable.Create();
    private readonly Button _scan = Ui.Button();
    private readonly Button _export = Ui.Button();
    private readonly Button _preview = Ui.Button();
    private readonly Button _searchFolder = Ui.Button();
    private readonly Button _online = Ui.Button();
    private readonly Button _install = Ui.Button();
    private readonly LinkLabel _modelLink = new() { AutoSize = true };
    private readonly LinkLabel _adapterLink = new() { AutoSize = true };
    private readonly Label _modelCaption = Ui.Label();
    private readonly Label _adapterCaption = Ui.Label();
    private RescueModelSupport? _model;
    private string? _installedWifi;
    private string[] _bundledWifiNames = [];
    private readonly Label _scanStatus = Ui.Label();
    private readonly ListView _pciDevices = ListViewTable.Create();
    private readonly TabPage _pciPage = new();
    private readonly TabPage _modulesPage = new();
    private readonly TabPage _catalogPage = new();
    private readonly TextBox _catalogQuery = new() { Dock = DockStyle.Top };
    private readonly Label _catalogStatus = Ui.Label();
    private readonly ListView _catalogResults = ListViewTable.Create();
    private readonly TextBox _catalogDetails = new() { Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical };
    private readonly LinkLabel _catalogDriverPage = new() { AutoSize = true };
    private readonly LinkLabel _catalogSource = new() { AutoSize = true };
    private NetworkDeviceDiagnostic? _diagnostic;
    private string? _scanStatusKey;
    private Translator _t;

    public NetworkRescueView(Translator t, IReadOnlyList<InstalledModule> modules, string? portableDriverDirectory = null)
    {
        _t = t;
        _modules = modules;
        _portableDriverDirectory = portableDriverDirectory;
        Dock = DockStyle.Fill;
        Margin = new Padding(0);
        BackColor = SystemColors.Control;
        Padding = new Padding(Ui.SPACING * 2);

        _heading.Font = new Font(Font.FontFamily, HEADING_FONT_SIZE, FontStyle.Bold);
        _note.ForeColor = Ui.MutedTextColor;
        _refresh.Click += (_, _) => RefreshStatus();
        _scan.Click += async (_, _) => await ScanAsync();
        _export.Click += (_, _) => ExportDiagnostics();
        _preview.Click += async (_, _) => await PreviewInfAsync();
        _searchFolder.Click += async (_, _) => await SearchFolderAsync();
        _online.Click += async (_, _) => await DownloadDriverAsync();
        _install.Click += async (_, _) =>
        {
            if (Directory.Exists(BundledDriverDirectory))
            {
                await SearchFolderAsync(useBundled: true);
            }
            else if (HasOnlineCandidates())
            {
                await DownloadDriverAsync();
            }
            else
            {
                await SearchFolderAsync();
            }
        };
        _modelLink.LinkClicked += (_, _) => OpenOfficialPage();
        _catalogQuery.TextChanged += (_, _) => SearchCatalog();
        _catalogResults.SelectedIndexChanged += (_, _) => ShowCatalogDetails();
        _catalogDriverPage.LinkClicked += (_, _) => OpenCatalogPage(driverPage: true);
        _catalogSource.LinkClicked += (_, _) => OpenCatalogPage(driverPage: false);
        _adapterLink.LinkClicked += async (_, _) =>
        {
            if (_bundledWifiNames.Length > 0)
            {
                await SearchFolderAsync(useBundled: true, exportOnly: true);
            }
            else
            {
                await DownloadDriverAsync(downloadOnly: true);
            }
        };
        _online.EnabledChanged += (_, _) => UpdateDriverLinks();
        _searchFolder.EnabledChanged += (_, _) => UpdateDriverLinks();
        _scan.EnabledChanged += (_, _) => UpdateDriverLinks();
        _preview.Enabled = false;
        _searchFolder.Enabled = false;
        _online.Enabled = false;
        _export.Enabled = false;
        _pciDevices.Columns.Add("", 550);
        _pciDevices.Columns.Add("", 150);
        _pciDevices.Columns.Add("SUBSYS", 130);
        _pciDevices.Columns.Add("", 170);
        ListViewTable.EnableSort(_pciDevices);
        ListViewTable.EnableColumnMenu(_pciDevices, _t);
        ListViewTable.EnableCopy(_pciDevices, _t);
        _catalogResults.MultiSelect = false;
        _catalogResults.Columns.Add("", 105);
        _catalogResults.Columns.Add("", 350);
        _catalogResults.Columns.Add("", 250);
        ListViewTable.EnableSort(_catalogResults);
        ListViewTable.EnableColumnMenu(_catalogResults, _t);
        ListViewTable.EnableCopy(_catalogResults, _t);

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
        Load += async (_, _) =>
        {
            if (_diagnostic is null && _scan.Enabled)
            {
                await ScanAsync();
            }
        };
    }

    public void ApplyLanguage(Translator t)
    {
        _t = t;
        _heading.Font = new Font(Font.FontFamily, HEADING_FONT_SIZE, FontStyle.Bold);
        _heading.Text = t["rescue.heading"];
        _note.Text = t["rescue.note"];
        _networkHeading.Text = t["rescue.network"];
        _refresh.Text = t["rescue.refresh"];
        _modulesPage.Text = t["rescue.modules"];
        _pciPage.Text = t["rescue.pci"];
        _catalogPage.Text = t["rescue.catalog"];
        _catalogQuery.PlaceholderText = t["rescue.searchModel"];
        _catalogQuery.AccessibleName = _catalogQuery.PlaceholderText;
        _catalogDriverPage.Text = t["rescue.officialDrivers"];
        _catalogSource.Text = t["rescue.catalogSource"];
        _catalogResults.Columns[0].Text = t["rescue.catalogBrand"];
        _catalogResults.Columns[1].Text = t["rescue.catalogModel"];
        _catalogResults.Columns[2].Text = t["rescue.catalogPlatform"];
        SearchCatalog();
        _scan.Text = t["rescue.scan"];
        _export.Text = t["rescue.export"];
        _preview.Text = t["rescue.previewInf"];
        _searchFolder.Text = t["rescue.searchFolder"];
        _online.Text = t["rescue.online"];
        _install.Text = t["rescue.installDriver"];
        _pciDevices.Columns[0].Text = t["rescue.hardwareIds"];
        _pciDevices.Columns[1].Text = t["rescue.problemCode"];
        _pciDevices.Columns[3].Text = t["rescue.candidateType"];
        ShowDiagnostic();
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
        _installedWifi = string.Join(" / ", status.Adapters.Where(adapter => adapter.Kind == LocalNetworkKind.Wireless)
            .Select(adapter => adapter.Description ?? adapter.Name).Distinct());
        UpdateDriverLinks();
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

    private async Task ScanAsync()
    {
        _scan.Enabled = false;
        _export.Enabled = false;
        _preview.Enabled = false;
        _searchFolder.Enabled = false;
        _online.Enabled = false;
        _diagnostic = null;
        _bundledWifiNames = [];
        _scanStatusKey = "rescue.scanning";
        ShowDiagnostic();
        try
        {
            _diagnostic = await Task.Run(NetworkDeviceInventory.Read);
            _model = await Task.Run(RescueModelSupport.Read);
            if (BundledDriverDirectory is { } directory && Directory.Exists(directory))
            {
                var devices = _diagnostic.Devices;
                if (devices.Count > 0)
                {
                    _bundledWifiNames = await Task.Run(() => OfflinePackageSearch.Find(directory, devices).Candidates
                        .SelectMany(candidate => candidate.Matches).Select(match => match.AdapterName)
                        .OfType<string>().Where(name => !string.IsNullOrWhiteSpace(name)).Distinct().ToArray());
                }
            }
            _scanStatusKey = _diagnostic.Devices.Count == 0 ? "rescue.noPci" : null;
        }
        catch (Exception exception) when (exception is System.Management.ManagementException
            or System.Runtime.InteropServices.COMException or UnauthorizedAccessException or IOException)
        {
            _scanStatusKey = "rescue.scanFailed";
        }

        if (!IsDisposed)
        {
            _scan.Enabled = true;
            _export.Enabled = _diagnostic is not null;
            _preview.Enabled = _diagnostic?.Devices.Count > 0;
            _searchFolder.Enabled = _preview.Enabled;
            _online.Enabled = _diagnostic?.Devices.Any(device => device.ProblemCode == 28) == true;
            ShowDiagnostic();
        }
    }

    private void ShowDiagnostic()
    {
        UpdateDriverLinks();
        _scanStatus.Text = _scanStatusKey is { } key ? _t[key] : "";
        _pciDevices.Items.Clear();
        foreach (var device in _diagnostic?.Devices ?? [])
        {
            var item = new ListViewItem(string.Join(" | ", device.HardwareIds));
            item.SubItems.Add(device.ProblemCode == 28 ? _t["rescue.missingDriver"] : device.ProblemCode?.ToString() ?? "");
            item.SubItems.Add(device.SubsystemId ?? "");
            item.SubItems.Add(_t[device.Kind switch
            {
                NetworkCandidateKind.UsbNetwork => "rescue.usbNetwork",
                NetworkCandidateKind.UsbUnidentified => "rescue.usbUnknown",
                _ => "rescue.pciController",
            }]);
            _pciDevices.Items.Add(item);
        }
    }

    private string? BundledDriverDirectory => _portableDriverDirectory ??
        (_modules.FirstOrDefault(module => module.Module == SharedModuleId.NetworkRescue) is { } rescue
            ? Path.Combine(rescue.InstallRoot, "driver-packs") : null);

    private bool HasOnlineCandidates() => DistributionProfile.Current.Channel != DistributionChannel.Store &&
        _diagnostic is { } diagnostic &&
        (OnlineDriverCatalog.Find(diagnostic).Count > 0 || OnlineDriverCatalog.FindPossible(diagnostic).Count > 0);

    private void UpdateDriverLinks()
    {
        _modelCaption.Text = _t[_model?.IsLaptop == true ? "rescue.laptopModel" : "rescue.boardModel"];
        _modelLink.Text = _model?.Model ?? "";
        _modelLink.Links.Clear();
        _modelLink.LinkArea = new LinkArea(0, 0);
        if (_model?.OfficialPage is not null)
        {
            _modelLink.Links.Add(0, _modelLink.Text.Length);
        }
        _modelCaption.Visible = _modelLink.Visible = _model is not null;
        _adapterCaption.Text = _t["rescue.wifiModel"];
        var packages = _diagnostic is { } diagnostic
            ? OnlineDriverCatalog.Find(diagnostic, includeInstalled: true)
                .Concat(OnlineDriverCatalog.FindPossible(diagnostic, includeInstalled: true))
            : [];
        var names = string.Join(" / ", packages.Select(package => package.AdapterName ?? package.Id).Distinct());
        var localNames = string.Join(" / ", _bundledWifiNames);
        _adapterLink.Text = !string.IsNullOrEmpty(_installedWifi) ? _installedWifi :
            localNames.Length > 0 ? localNames : names;
        _adapterLink.Links.Clear();
        _adapterLink.LinkArea = new LinkArea(0, 0);
        if (DistributionProfile.Current.Channel != DistributionChannel.Store &&
            (localNames.Length > 0 || names.Length > 0))
        {
            _adapterLink.Links.Add(0, _adapterLink.Text.Length).Enabled = _scan.Enabled;
        }
        _adapterCaption.Visible = _adapterLink.Visible = _adapterLink.Text.Length > 0;
        _install.Enabled = _searchFolder.Enabled && _diagnostic?.Devices.Any(device => device.ProblemCode == 28) == true &&
            DistributionProfile.Current.Channel != DistributionChannel.Store;
        _install.Visible = DistributionProfile.Current.Channel != DistributionChannel.Store;
    }

    private void OpenOfficialPage()
    {
        OpenPage(_model?.OfficialPage);
    }

    private void OpenPage(string? page)
    {
        if (page is not null)
        {
            try
            {
                Process.Start(new ProcessStartInfo(page) { UseShellExecute = true });
            }
            catch (System.ComponentModel.Win32Exception)
            {
                ShowInstallResult("rescue.onlineFailed");
            }
        }
    }

    private void SearchCatalog()
    {
        var selected = SelectedCatalogEntry;
        var results = RescueModelCatalog.Search(_catalogQuery.Text);
        _catalogResults.BeginUpdate();
        _catalogResults.Items.Clear();
        foreach (var entry in results)
        {
            var qualifier = entry.Type == "laptop-os-record"
                ? string.Join(" · ", new[] { entry.Platform, entry.Windows }.Where(value => value.Length > 0))
                : entry.Type == "all-in-one" ? _t["rescue.catalogAllInOne"] : entry.Platform;
            var item = new ListViewItem(entry.Brand) { Tag = entry };
            item.SubItems.Add(entry.Model);
            item.SubItems.Add(qualifier);
            _catalogResults.Items.Add(item);
            item.Selected = entry == selected;
        }
        _catalogResults.EndUpdate();
        _catalogStatus.Text = string.IsNullOrWhiteSpace(_catalogQuery.Text) ? "" :
            results.Count == 0 ? _t["rescue.catalogNoResults"] : _t["rescue.catalogResults", results.Count];
        ShowCatalogDetails();
    }

    private void ShowCatalogDetails()
    {
        var entry = SelectedCatalogEntry;
        _catalogDriverPage.Visible = entry?.DriverPage is not null;
        _catalogSource.Visible = entry?.Source is not null && entry.Source != entry.DriverPage;
        _catalogDetails.Text = entry is null ? "" : string.Join(Environment.NewLine, new[]
        {
            $"{entry.Brand}  {entry.Model}",
            entry.IsSeries ? _t["rescue.catalogSeries"] : "",
            entry.Platform,
            entry.Type == "laptop-os-record" ? entry.Windows : "",
            $"{_t["rescue.wifiModel"]}  {(entry.Module.Length == 0 || entry.Module == "pending" ? _t["rescue.catalogPending"] : entry.Module)}",
            $"Windows 10 x64  {CatalogEvidence(entry.Windows10Evidence)}",
            $"Windows 11 x64  {CatalogEvidence(entry.Windows11Evidence)}",
        }.Where(value => value.Length > 0));
    }

    private string CatalogEvidence(string evidence) => _t[evidence switch
    {
        "oem-package-indexed" => "rescue.catalogIndexed",
        "oem-wlan-listed" => "rescue.catalogListed",
        "oem-driver-pack-listed" => "rescue.catalogDeployPack",
        "oem-os-upgrade-tested" => "rescue.catalogOsTested",
        "no-factory-wifi" => "rescue.catalogNoWifi",
        "outside-x64-record" => "rescue.catalogOutsideX64",
        _ => "rescue.catalogPending",
    }];

    private void OpenCatalogPage(bool driverPage)
    {
        if (SelectedCatalogEntry is { } entry)
        {
            OpenPage((driverPage ? entry.DriverPage : entry.Source)?.AbsoluteUri);
        }
    }

    private RescueCatalogModel? SelectedCatalogEntry =>
        _catalogResults.SelectedItems.Count == 1 ? _catalogResults.SelectedItems[0].Tag as RescueCatalogModel : null;

    private void ExportDiagnostics()
    {
        if (_diagnostic is not { } diagnostic)
        {
            return;
        }

        using var dialog = new SaveFileDialog { FileName = "wifi-diagnostics.json", DefaultExt = "json" };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        try
        {
            File.WriteAllText(dialog.FileName, NetworkDeviceInventory.Export(diagnostic));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            MessageBox.Show(this, _t["rescue.exportFailed"], _t["rescue.heading"], MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    private async Task PreviewInfAsync()
    {
        if (_diagnostic is not { Devices.Count: > 0 } diagnostic)
        {
            return;
        }

        using var dialog = new OpenFileDialog { Filter = _t["rescue.infFilter"] + " (*.inf)|*.inf" };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        await ReviewInfAsync(dialog.FileName, diagnostic.Devices);
    }

    private async Task ReviewInfAsync(string path, IReadOnlyList<NetworkDeviceCandidate> devices)
    {
        string message;
        try
        {
            var matches = OfflineInfMatcher.Match(path, devices);
            if (OfflineDriverInstaller.SelectMissingMatch(matches) is { } eligible &&
                DistributionProfile.Current.Channel != DistributionChannel.Store)
            {
                await ConfirmInstallAsync(path, eligible);
                return;
            }

            message = matches.Count == 0
                ? _t["rescue.infNoMatch"]
                : string.Join(Environment.NewLine,
                    matches.Select(match => $"{match.HardwareId} [{match.ModelsSection}]").Distinct())
                    + Environment.NewLine + Environment.NewLine + _t["rescue.infPreviewNote"];
        }
        catch (System.ComponentModel.Win32Exception)
        {
            message = _t["rescue.infReadFailed"];
        }

        MessageBox.Show(this, message, _t["rescue.infMatches", Path.GetFileName(path)],
            MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private async Task SearchFolderAsync(bool useBundled = false, bool exportOnly = false)
    {
        if (_diagnostic is not { Devices.Count: > 0 } diagnostic)
        {
            return;
        }

        using var folder = new FolderBrowserDialog { Description = _t["rescue.selectFolder"], ShowNewFolderButton = false };
        if (Directory.Exists(_portableDriverDirectory))
        {
            folder.SelectedPath = _portableDriverDirectory;
        }
        else if (_modules.FirstOrDefault(module => module.Module == SharedModuleId.NetworkRescue) is { } rescue)
        {
            var bundledPacks = Path.Combine(rescue.InstallRoot, "driver-packs");
            if (Directory.Exists(bundledPacks))
            {
                folder.SelectedPath = bundledPacks;
            }
        }

        if (!useBundled && folder.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        var root = useBundled ? BundledDriverDirectory : folder.SelectedPath;
        if (root is null || !Directory.Exists(root))
        {
            ShowInstallResult("rescue.folderReadFailed");
            return;
        }
        _scan.Enabled = _preview.Enabled = _searchFolder.Enabled = _online.Enabled = false;
        _scanStatusKey = "rescue.searchingFolder";
        _scanStatus.Text = _t[_scanStatusKey];
        OfflinePackageSearchResult? result = null;
        try
        {
            result = await Task.Run(() => OfflinePackageSearch.Find(root, diagnostic.Devices, includePossible: true));
            _scanStatusKey = null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            _scanStatusKey = "rescue.folderReadFailed";
        }

        if (IsDisposed)
        {
            return;
        }

        _scan.Enabled = _preview.Enabled = _searchFolder.Enabled = true;
        _online.Enabled = diagnostic.Devices.Any(device => device.ProblemCode == 28);
        _scanStatus.Text = _scanStatusKey is { } status ? _t[status] : "";
        if (result is null)
        {
            return;
        }

        var skipped = result.UnreadableInfCount > 0 ? _t["rescue.unreadableInfs", result.UnreadableInfCount] : "";
        if (result.Candidates.Count == 0)
        {
            MessageBox.Show(this, string.Join(Environment.NewLine, new[] { _t["rescue.infNoMatch"], skipped }
                .Where(text => text.Length > 0)), _t["rescue.driverCandidates"], MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        var candidate = exportOnly && result.Candidates.Count == 1
            ? result.Candidates[0]
            : SelectCandidate(root, result.Candidates, skipped);
        if (candidate is { } selected)
        {
            if (exportOnly && FindForm() is { } window)
            {
                await ExportDriverAsync(window, selected.InfPath);
                return;
            }

            if (selected.IsPossible)
            {
                ShowInstallResult("rescue.possibleNote");
                return;
            }

            await ReviewInfAsync(selected.InfPath, diagnostic.Devices);
        }
    }

    private async Task DownloadDriverAsync(bool downloadOnly = false)
    {
        if (_diagnostic is not { } diagnostic)
        {
            return;
        }

        var packages = OnlineDriverCatalog.Find(diagnostic, includeInstalled: downloadOnly);
        var possible = OnlineDriverCatalog.FindPossible(diagnostic, includeInstalled: downloadOnly);
        if (packages.Count == 0 && possible.Count == 0)
        {
            ShowInstallResult("rescue.onlineNoMatch");
            return;
        }

        var selected = packages.Count == 1 && possible.Count == 0
            ? packages[0]
            : SelectOnlinePackage(packages, possible, diagnostic);
        if (selected is null)
        {
            return;
        }

        var prompt = string.Join(Environment.NewLine, _t["rescue.onlineConfirm"], PackageLabel(selected), selected.Source);
        if (MessageBox.Show(this, prompt, _t["rescue.onlineCandidates"], MessageBoxButtons.YesNo,
                MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
        {
            return;
        }

        DirectoryInfo? workspace = null;
        string? driverDirectory = null;
        OfflinePackageSearchResult? result = null;
        _scan.Enabled = _preview.Enabled = _searchFolder.Enabled = _online.Enabled = false;
        _scanStatusKey = "rescue.onlineDownloading";
        _scanStatus.Text = _t[_scanStatusKey];
        try
        {
            try
            {
                workspace = Directory.CreateTempSubdirectory("akikazu-rescue-");
                using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(3));
                var root = workspace.FullName;
                driverDirectory = await Task.Run(() => OnlineDriverCatalog.DownloadAsync(selected, root, timeout.Token));
                result = await Task.Run(() => OfflinePackageSearch.Find(driverDirectory, diagnostic.Devices, includePossible: true));
                _scanStatusKey = null;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or HttpRequestException
                or OperationCanceledException or InvalidDataException or System.ComponentModel.Win32Exception)
            {
                _scanStatusKey = "rescue.onlineFailed";
            }

            if (IsDisposed)
            {
                return;
            }

            _scan.Enabled = _preview.Enabled = _searchFolder.Enabled = _online.Enabled = true;
            _scanStatus.Text = _scanStatusKey is { } status ? _t[status] : "";
            if (result is null || driverDirectory is null)
            {
                return;
            }

            if (result.Candidates.Count == 0)
            {
                ShowInstallResult("rescue.infNoMatch");
                return;
            }

            var candidate = downloadOnly && result.Candidates.Count == 1
                ? result.Candidates[0]
                : SelectCandidate(driverDirectory, result.Candidates, "");
            if (candidate is not null)
            {
                if (downloadOnly && FindForm() is { } window)
                {
                    await ExportDriverAsync(window, candidate.InfPath);
                    return;
                }

                if (candidate.IsPossible)
                {
                    ShowInstallResult("rescue.possibleNote");
                    return;
                }

                await ReviewInfAsync(candidate.InfPath, diagnostic.Devices);
            }
        }
        finally
        {
            try
            {
                workspace?.Delete(recursive: true);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // A third-party lock can delay removal of temporary files.
            }
        }
    }

    private OnlineDriverPackage? SelectOnlinePackage(IReadOnlyList<OnlineDriverPackage> matches,
        IReadOnlyList<OnlineDriverPackage> possible, NetworkDeviceDiagnostic diagnostic)
    {
        var packages = matches.Concat(possible).ToArray();
        using var dialog = new Form
        {
            Text = _t[matches.Count == 0 ? "rescue.possibleCandidates" : "rescue.onlineCandidates"],
            StartPosition = FormStartPosition.CenterParent,
            ClientSize = new Size(740, 330),
            MinimizeBox = false,
            ShowInTaskbar = false,
        };
        var list = new ListBox { Dock = DockStyle.Fill };
        foreach (var package in matches)
        {
            list.Items.Add(PackageLabel(package));
        }
        foreach (var package in possible)
        {
            list.Items.Add($"[{_t["rescue.possibleCandidates"]}] {PackageLabel(package)}");
        }

        var select = Ui.Button();
        select.Text = _t["rescue.onlineSelect"];
        select.DialogResult = DialogResult.OK;
        select.Enabled = false;
        list.SelectedIndexChanged += (_, _) => select.Enabled = list.SelectedIndex >= 0;
        var footer = new FlowLayoutPanel { Dock = DockStyle.Bottom, AutoSize = true };
        footer.Controls.Add(select);
        var details = new TextBox
        {
            Dock = DockStyle.Bottom,
            Height = 105,
            Multiline = true,
            ReadOnly = true,
            ScrollBars = ScrollBars.Vertical,
        };
        details.Text = possible.Count > 0 ? _t["rescue.possibleNote"] : "";
        list.SelectedIndexChanged += (_, _) =>
        {
            if (list.SelectedIndex >= 0)
            {
                var package = packages[list.SelectedIndex];
                var detected = diagnostic.Devices.Where(device => device.ProblemCode == 28)
                    .SelectMany(device => device.HardwareIds.Take(1));
                details.Lines = new[]
                {
                    possible.Contains(package) ? _t["rescue.possibleNote"] : "",
                    $"{_t["rescue.hardwareIds"]}  {string.Join(" | ", detected)}",
                    package.Scope ?? "",
                    package.Source,
                }.Concat(package.DevicePrefixes).ToArray();
            }
        };
        dialog.Controls.Add(list);
        dialog.Controls.Add(details);
        dialog.Controls.Add(footer);
        dialog.AcceptButton = select;
        return dialog.ShowDialog(this) == DialogResult.OK && list.SelectedIndex >= 0
            ? packages[list.SelectedIndex]
            : null;
    }

    private static string PackageLabel(OnlineDriverPackage package) => $"{package.Id} {package.Version}";

    private OfflinePackageCandidate? SelectCandidate(string root, IReadOnlyList<OfflinePackageCandidate> candidates, string skipped)
    {
        using var dialog = new Form
        {
            Text = _t["rescue.driverCandidates"],
            StartPosition = FormStartPosition.CenterParent,
            ClientSize = new Size(740, 360),
            MinimizeBox = false,
            ShowInTaskbar = false,
        };
        var list = ListViewTable.Create();
        list.MultiSelect = false;
        list.Columns.Add(_t["rescue.infPath"], 320);
        list.Columns.Add(_t["rescue.hardwareIds"], 380);
        foreach (var candidate in candidates)
        {
            var path = Path.GetRelativePath(root, candidate.InfPath);
            var row = new ListViewItem(candidate.IsPossible ? $"[{_t["rescue.possibleCandidates"]}] {path}" : path) { Tag = candidate };
            row.SubItems.Add(string.Join(" | ", candidate.Matches.Select(match => candidate.IsPossible
                ? $"{match.Device.HardwareIds.FirstOrDefault()} → {match.HardwareId}"
                : match.HardwareId).Distinct()));
            list.Items.Add(row);
        }

        ListViewTable.EnableSort(list);
        ListViewTable.EnableColumnMenu(list, _t);
        ListViewTable.EnableCopy(list, _t);
        var review = Ui.Button();
        review.Text = _t["rescue.reviewInf"];
        review.DialogResult = DialogResult.OK;
        review.Enabled = false;
        var export = Ui.Button();
        export.Text = _t["rescue.exportDriver"];
        export.Enabled = false;
        export.Click += async (_, _) =>
        {
            if (list.SelectedItems.Count == 1 && list.SelectedItems[0].Tag is OfflinePackageCandidate candidate)
            {
                await ExportDriverAsync(dialog, candidate.InfPath);
            }
        };
        list.SelectedIndexChanged += (_, _) => review.Enabled = export.Enabled = list.SelectedItems.Count == 1;
        if (list.Items.Count == 1)
        {
            list.Items[0].Selected = true;
        }
        var footer = new FlowLayoutPanel { Dock = DockStyle.Bottom, AutoSize = true };
        footer.Controls.Add(review);
        footer.Controls.Add(export);
        if (skipped.Length > 0 || candidates.Any(candidate => candidate.IsPossible))
        {
            var note = Ui.Label();
            note.Text = string.Join(Environment.NewLine, new[] { candidates.Any(candidate => candidate.IsPossible)
                ? _t["rescue.possibleNote"] : "", skipped }.Where(value => value.Length > 0));
            footer.Controls.Add(note);
        }

        dialog.Controls.Add(list);
        dialog.Controls.Add(footer);
        dialog.AcceptButton = review;
        return dialog.ShowDialog(this) == DialogResult.OK && list.SelectedItems.Count == 1
            ? (OfflinePackageCandidate?)list.SelectedItems[0].Tag
            : null;
    }

    private async Task ExportDriverAsync(Form owner, string infPath)
    {
        using var dialog = new SaveFileDialog
        {
            Filter = "ZIP (*.zip)|*.zip",
            FileName = Path.GetFileNameWithoutExtension(infPath) + ".zip",
        };
        if (dialog.ShowDialog(owner) != DialogResult.OK)
        {
            return;
        }

        owner.Enabled = false;
        try
        {
            await Task.Run(() =>
            {
                if (OfflineDriverInstaller.Verify(infPath) is null)
                {
                    throw new InvalidDataException();
                }

                var source = Path.GetDirectoryName(infPath)!;
                var destination = dialog.FileName;
                var relative = Path.GetRelativePath(source, destination);
                if (!Path.IsPathRooted(relative) && !relative.StartsWith(".." + Path.DirectorySeparatorChar, StringComparison.Ordinal))
                {
                    throw new InvalidDataException();
                }

                var temporary = destination + "." + Guid.NewGuid().ToString("N") + ".tmp";
                try
                {
                    using (var zip = ZipFile.Open(temporary, ZipArchiveMode.Create))
                    {
                        var options = new EnumerationOptions
                        {
                            RecurseSubdirectories = true,
                            AttributesToSkip = FileAttributes.ReparsePoint,
                            IgnoreInaccessible = false,
                        };
                        foreach (var file in Directory.EnumerateFiles(source, "*", options))
                        {
                            zip.CreateEntryFromFile(file, Path.GetRelativePath(source, file));
                        }
                    }
                    File.Move(temporary, destination, overwrite: true);
                }
                finally
                {
                    File.Delete(temporary);
                }
            });
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            MessageBox.Show(owner, _t["rescue.exportFailed"], _t["rescue.heading"], MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        finally
        {
            owner.Enabled = true;
        }
    }

    private async Task ConfirmInstallAsync(string path, OfflineInfMatch match)
    {
        OfflineDriverIdentity? identity;
        try
        {
            identity = OfflineDriverInstaller.Verify(path);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            identity = null;
        }

        if (identity is null)
        {
            MessageBox.Show(this, $"{match.HardwareId} [{match.ModelsSection}]" + Environment.NewLine +
                _t["rescue.packageRejected"], _t["rescue.infMatches", Path.GetFileName(path)],
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        var details = string.Join(Environment.NewLine, _t["rescue.installConfirm"], Path.GetFileName(path),
            $"{match.HardwareId} [{match.ModelsSection}]", $"{_t["rescue.signer"]}: {identity.Signer}");
        if (MessageBox.Show(this, details, _t["rescue.heading"], MessageBoxButtons.YesNo,
                MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes ||
            Environment.ProcessPath is not { } executable)
        {
            return;
        }

        _scan.Enabled = false;
        _preview.Enabled = false;
        _searchFolder.Enabled = false;
        _online.Enabled = false;
        _export.Enabled = false;
        string resultKey;
        try
        {
            var start = new ProcessStartInfo(executable) { UseShellExecute = true, Verb = "runas" };
            start.ArgumentList.Add(Program.INSTALL_NETWORK_DRIVER_ARGUMENT);
            start.ArgumentList.Add(path);
            start.ArgumentList.Add(match.HardwareId);
            start.ArgumentList.Add(identity.Sha256);
            using var helper = Process.Start(start);
            if (helper is null)
            {
                resultKey = "rescue.elevationCanceled";
            }
            else
            {
                await helper.WaitForExitAsync();
                resultKey = (OfflineInstallResult)helper.ExitCode switch
                {
                    OfflineInstallResult.Bound => "rescue.bound",
                    OfflineInstallResult.RestartRequired => "rescue.restartRequired",
                    OfflineInstallResult.BindingUnconfirmed => "rescue.bindingUnconfirmed",
                    OfflineInstallResult.NoEligibleDevice => "rescue.noEligibleDevice",
                    OfflineInstallResult.PackageRejected => "rescue.packageRejected",
                    _ => "rescue.installationFailed",
                };
            }
        }
        catch (System.ComponentModel.Win32Exception)
        {
            resultKey = "rescue.elevationCanceled";
        }

        if (!IsDisposed)
        {
            await ScanAsync();
            if (!IsDisposed)
            {
                ShowInstallResult(resultKey);
            }
        }
    }

    private void ShowInstallResult(string key) => MessageBox.Show(this, _t[key], _t["rescue.heading"],
        MessageBoxButtons.OK, MessageBoxIcon.Information);

    private Control BuildLayout()
    {
        var root = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5, Margin = new Padding(0) };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 40));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 60));

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

        var tabs = new TabControl { Dock = DockStyle.Fill };
        var scanLayout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4 };
        scanLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        scanLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        scanLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        scanLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        actions.Controls.Add(_scan);
        actions.Controls.Add(_export);
        actions.Controls.Add(_preview);
        actions.Controls.Add(_searchFolder);
        if (_portableDriverDirectory is null && DistributionProfile.Current.Channel != DistributionChannel.Store)
        {
            actions.Controls.Add(_online);
        }
        var deviceSummary = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, RowCount = 2 };
        deviceSummary.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        deviceSummary.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        deviceSummary.Controls.Add(_modelCaption, 0, 0);
        deviceSummary.Controls.Add(_modelLink, 1, 0);
        deviceSummary.Controls.Add(_adapterCaption, 0, 1);
        deviceSummary.Controls.Add(_adapterLink, 1, 1);
        _install.Font = new Font(Font.FontFamily, HEADING_FONT_SIZE, FontStyle.Bold);
        actions.Controls.Add(_install);
        actions.Controls.SetChildIndex(_install, 0);
        scanLayout.Controls.Add(deviceSummary, 0, 0);
        scanLayout.Controls.Add(actions, 0, 1);
        scanLayout.Controls.Add(_scanStatus, 0, 2);
        scanLayout.Controls.Add(_pciDevices, 0, 3);
        _pciPage.Controls.Add(scanLayout);
        _modulesPage.Controls.Add(_moduleList);
        tabs.TabPages.Add(_pciPage);
        _catalogPage.Controls.Add(BuildCatalogLayout());
        tabs.TabPages.Add(_catalogPage);
        tabs.SelectedIndexChanged += (_, _) =>
        {
            var browsing = tabs.SelectedTab == _catalogPage;
            root.SuspendLayout();
            _networkHeading.Visible = _adapters.Visible = !browsing;
            root.RowStyles[3].SizeType = browsing ? SizeType.Absolute : SizeType.Percent;
            root.RowStyles[3].Height = browsing ? 0 : 40;
            root.ResumeLayout(performLayout: true);
        };
        if (_portableDriverDirectory is null)
        {
            tabs.TabPages.Add(_modulesPage);
        }
        root.Controls.Add(tabs, 0, 4);
        return root;
    }

    private Control BuildCatalogLayout()
    {
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5, Padding = new Padding(Ui.SPACING) };
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 60));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 40));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        var links = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true };
        links.Controls.Add(_catalogDriverPage);
        links.Controls.Add(_catalogSource);
        layout.Controls.Add(_catalogQuery, 0, 0);
        layout.Controls.Add(_catalogStatus, 0, 1);
        layout.Controls.Add(_catalogResults, 0, 2);
        layout.Controls.Add(_catalogDetails, 0, 3);
        layout.Controls.Add(links, 0, 4);
        return layout;
    }

    private void FitNote()
    {
        var width = Math.Max(LogicalToDeviceUnits(240), ClientSize.Width - Padding.Horizontal);
        _note.MaximumSize = new Size(width, 0);
        _modelLink.MaximumSize = _adapterLink.MaximumSize = new Size(Math.Max(150, width - 170), 0);
    }
}
