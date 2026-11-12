using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using AkikazuHardwareCheck.Core.Configuration;
using AkikazuHardwareCheck.Core.Hardware;
using AkikazuHardwareCheck.Core.Localization;
using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.App;

internal static class Program
{
    public const string REMOVE_DRIVER_ARGUMENT = "--remove-driver";
    public const string KEYBOARD_JAPANESE_ARGUMENT = "--keyboard-106";

    public const string INSTALL_NETWORK_DRIVER_ARGUMENT = "--install-network-driver";

    private const string INSTANCE_MUTEX_NAME = "Local\\AkikazuHardwareCheck.SingleInstance";
    private const uint SEM_FAILCRITICALERRORS = 0x0001;
    private const uint SEM_NOGPFAULTERRORBOX = 0x0002;
    private const uint SEM_NOOPENFILEERRORBOX = 0x8000;
    private static readonly TimeSpan ParentExitTimeout = TimeSpan.FromSeconds(30);

    [STAThread]
    private static void Main(string[] args)
    {
        if (args is [REMOVE_DRIVER_ARGUMENT, var parentId, var removesPackage, var language])
        {
            RemoveDriverAfterExit(parentId, removesPackage, language);
            return;
        }

        if (args is [KEYBOARD_JAPANESE_ARGUMENT, var keyboardLanguage])
        {
            ApplyKeyboardFix(keyboardLanguage);
            return;
        }

        if (args is [INSTALL_NETWORK_DRIVER_ARGUMENT, var infPath, var hardwareId, var expectedHash])
        {
            Environment.ExitCode = (int)(DistributionProfile.Current.Channel != DistributionChannel.Store &&
                Elevation.IsAdministrator()
                    ? OfflineDriverInstaller.Install(infPath, hardwareId, expectedHash)
                    : OfflineInstallResult.InstallationFailed);
            return;
        }

        if (args is ["--portable-rescue"] && DistributionProfile.Current.Channel != DistributionChannel.Store)
        {
            RunPortableRescue();
            return;
        }

        StartupTrace.Record("main");
        var startup = SharedDesktopStartupPolicy.Resolve(
            args,
            SharedModuleDiscovery.ReadCurrentUser(),
            DistributionProfile.Current.Channel == DistributionChannel.Store);
        StartupTrace.Record("modules-ready");

        // CPU temperatures need administrator rights, so the hardware module asks for them right away and staff answer
        // one Windows prompt. The rescue module never asks at startup: only its later driver action may elevate.
        // Declining is not an error: this copy then keeps running with what ordinary rights can read.
        if (startup.ActiveModule == SharedModuleId.HardwareCheck &&
            DistributionProfile.Current.AllowsElevation &&
            !startup.NoElevate &&
            !Elevation.IsAdministrator() &&
            Environment.ProcessPath is { } path)
        {
            try
            {
                Process.Start(new ProcessStartInfo(path, ElevationArguments(args)) { UseShellExecute = true, Verb = "runas" })?.Dispose();
                StartupTrace.Record("elevated");
                return;
            }
            catch (Win32Exception)
            {
                // Declined, or elevation is not available on this account.
            }
        }

        ApplicationConfiguration.Initialize();
        InstallCrashGuard();
        StartupTrace.Record("guard-ready");

        // Only one main window is allowed across both entries. A second launch asks the existing window to show the
        // requested module, then exits without creating another window. The mutex is per Windows session (Local\).
        Mutex instance;
        bool createdNew;
        try
        {
            instance = new Mutex(true, INSTANCE_MUTEX_NAME, out createdNew);
        }
        catch (Exception exception) when (exception is UnauthorizedAccessException or IOException)
        {
            // An elevated first instance may own a mutex this process cannot open. Treat it as the existing instance
            // and use the file request, which works across integrity levels.
            SingleInstanceListener.NotifyExisting(startup.RequestedModule);
            StartupTrace.Record("second-instance");
            return;
        }

        using (instance)
        {
            if (!createdNew)
            {
                SingleInstanceListener.NotifyExisting(startup.RequestedModule);
                StartupTrace.Record("second-instance");
                return;
            }

            SingleInstanceListener.ClearStaleRequests();
            StartupTrace.Record("instance-acquired");

            // Lets standard controls and the title bar follow the Windows light or dark setting.
            Application.SetColorMode(SystemColorMode.System);
            try
            {
                StartupTrace.Record("main-form-start");
                var main = new MainForm(startup.StartHidden, startup);
                StartupTrace.Record("main-form-created");
                StartupTrace.Record("message-loop");
                Application.Run(main);
                StartupTrace.Record("exit");
            }
            catch (Exception exception)
            {
                StartupTrace.Record("crash");
                ExitSilently(exception);
            }
        }
    }

    private static void RunPortableRescue()
    {
        ApplicationConfiguration.Initialize();
        InstallCrashGuard();
        Application.SetColorMode(SystemColorMode.System);
        using var instance = new Mutex(true, @"Local\Akikazu.NetworkRescue.Portable", out var created);
        if (!created)
        {
            return;
        }

        var translator = Translator.Load(AppLanguage.FromCulture(CultureInfo.CurrentUICulture.Name));
        using var window = new Form
        {
            Text = translator[SharedModuleId.NetworkRescue.DisplayNameKey()],
            Icon = Ui.AppIcon,
            StartPosition = FormStartPosition.CenterScreen,
            ClientSize = new Size(1100, 720),
        };
        var languages = new ToolStripDropDownButton(translator["rescue.pe.language"]);
        var rescue = new NetworkRescueView(translator, [], Path.Combine(AppContext.BaseDirectory, "driver-packs"));
        string[] languageLabels = ["日本語", "简体中文", "繁體中文", "English"];
        var currentLanguage = AppLanguage.FromCulture(CultureInfo.CurrentUICulture.Name);
        foreach (var (language, label) in AppLanguage.Supported.Zip(languageLabels))
        {
            var item = new ToolStripMenuItem(label) { Checked = language == currentLanguage };
            item.Click += (_, _) =>
            {
                var selected = Translator.Load(language);
                window.Text = selected[SharedModuleId.NetworkRescue.DisplayNameKey()];
                languages.Text = selected["rescue.pe.language"];
                foreach (ToolStripMenuItem option in languages.DropDownItems)
                {
                    option.Checked = option == item;
                }
                rescue.ApplyLanguage(selected);
            };
            languages.DropDownItems.Add(item);
        }
        rescue.AddPortableMenus(languages);
        window.Controls.Add(rescue);
        Application.Run(window);
    }

    /// <summary>
    /// A hardware diagnostic tool must not put an exception dialog in front of the operator. UI, worker-thread and
    /// unobserved-task failures are written locally and terminate the process without a dialog.
    /// </summary>
    private static void InstallCrashGuard()
    {
        SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
        Application.ThreadException += (_, e) => ExitSilently(e.Exception);
        AppDomain.CurrentDomain.UnhandledException += (_, e) => ExitSilently(e.ExceptionObject as Exception);
        TaskScheduler.UnobservedTaskException += (_, e) =>
        {
            e.SetObserved();
            ExitSilently(e.Exception);
        };
    }

    private static void ExitSilently(Exception? exception)
    {
        try
        {
            var folder = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "AkikazuHardwareCheck");
            Directory.CreateDirectory(folder);
            File.AppendAllText(
                Path.Combine(folder, "error.log"),
                $"{DateTimeOffset.Now:O} stage={StartupTrace.LastStage ?? "none"}{Environment.NewLine}{exception}{Environment.NewLine}{Environment.NewLine}",
                new System.Text.UTF8Encoding(false));
        }
        catch
        {
            // Logging must never turn a silent exit into another dialog.
        }

        Environment.Exit(1);
    }

    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    private static extern uint SetErrorMode(uint mode);

    /// <summary>Runs in the elevated helper so the main window does not need to restart.</summary>
    private static void ApplyKeyboardFix(string language)
    {
        ApplicationConfiguration.Initialize();
        var t = Translator.Load(language);
        try
        {
            KeyboardLayoutFix.ApplyJapanese106();
            MessageBox.Show(t["keyboardFix.done"], t["keyboardFix.title"], MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (Exception exception) when (exception is UnauthorizedAccessException or InvalidOperationException or System.Security.SecurityException)
        {
            MessageBox.Show(t["keyboardFix.failed", exception.Message], t["keyboardFix.title"], MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    /// <summary>The driver can only stop once the main program has closed it, which is when that process ends.</summary>
    private static void RemoveDriverAfterExit(string parentId, string removesPackage, string language)
    {
        WaitForExit(parentId);
        if (PawnIoSetup.Uninstall(bool.Parse(removesPackage)))
        {
            return;
        }

        ApplicationConfiguration.Initialize();
        var t = Translator.Load(language);
        MessageBox.Show(t["ui.driverRemoveFailed"], t["ui.appName"], MessageBoxButtons.OK, MessageBoxIcon.Warning);
    }

    private static void WaitForExit(string processId)
    {
        try
        {
            using var parent = Process.GetProcessById(int.Parse(processId, CultureInfo.InvariantCulture));
            parent.WaitForExit(ParentExitTimeout);
        }
        catch (ArgumentException)
        {
            // Already gone.
        }
    }

    /// <summary>
    /// The elevated copy must keep the other switches, such as --tray from autostart, and must not ask to elevate twice.
    /// </summary>
    private static string ElevationArguments(string[] args) =>
        string.Join(
            ' ',
            args.Where(argument => !string.Equals(argument, SharedDesktopContract.NO_ELEVATE_ARGUMENT, StringComparison.OrdinalIgnoreCase))
                .Append(SharedDesktopContract.NO_ELEVATE_ARGUMENT)
                .Select(argument => argument.Contains(' ') ? $"\"{argument}\"" : argument));
}
