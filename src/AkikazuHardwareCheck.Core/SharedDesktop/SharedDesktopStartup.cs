namespace AkikazuHardwareCheck.Core.SharedDesktop;

/// <summary>What this launch should show, derived from the argument and the installed module registrations.</summary>
public sealed record SharedDesktopStartup(
    SharedModuleId ActiveModule,
    SharedModuleId PrimaryModule,
    SharedModuleId? RequestedModule,
    bool StartHidden,
    bool NoElevate,
    IReadOnlyList<SharedModuleId> AvailableModules,
    IReadOnlyList<InstalledModule> Modules)
{
    public bool HasModule(SharedModuleId module) => AvailableModules.Contains(module);

    public InstalledModule? Find(SharedModuleId module) =>
        Modules.FirstOrDefault(candidate => candidate.Module == module);
}

public static class SharedDesktopStartupPolicy
{
    public static SharedDesktopStartup Resolve(string[] args, IReadOnlyList<InstalledModule> installed, bool storeChannel)
    {
        // A portable or development run has no registration and is the hardware tool. A rescue-only install exposes
        // only the rescue page, so opening it must not silently fall back to an uninstalled hardware module.
        var modules = installed
            .Where(module => SharedDesktopContract.AllowsModule(module.Module, storeChannel))
            .GroupBy(module => module.Module)
            .Select(group => group.OrderByDescending(module => ParseVersion(module.Version)).First())
            .OrderBy(module => module.Module == SharedModuleId.HardwareCheck ? 0 : 1)
            .ToList();
        var available = modules.Select(module => module.Module).ToList();
        if (available.Count == 0)
        {
            available.Add(SharedModuleId.HardwareCheck);
        }

        var primary = available.Contains(SharedModuleId.HardwareCheck)
            ? SharedModuleId.HardwareCheck
            : available[0];
        var requested = ParseRequestedModule(args);
        var active = requested is { } candidate && available.Contains(candidate) ? candidate : primary;

        return new SharedDesktopStartup(
            active,
            primary,
            requested,
            HasArgument(args, SharedDesktopContract.TRAY_ARGUMENT),
            HasArgument(args, SharedDesktopContract.NO_ELEVATE_ARGUMENT),
            available,
            modules);
    }

    private static SharedModuleId? ParseRequestedModule(string[] args)
    {
        SharedModuleId? requested = null;
        for (var index = 0; index < args.Length; index++)
        {
            var argument = args[index];
            if (string.Equals(argument, SharedDesktopContract.MODULE_ARGUMENT, StringComparison.OrdinalIgnoreCase))
            {
                if (index + 1 < args.Length && SharedModuleIds.TryParse(args[index + 1], out var module))
                {
                    requested = module;
                }

                continue;
            }

            const string prefix = SharedDesktopContract.MODULE_ARGUMENT + "=";
            if (argument.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                && SharedModuleIds.TryParse(argument[prefix.Length..], out var inlineModule))
            {
                requested = inlineModule;
            }
        }

        return requested;
    }

    private static System.Version ParseVersion(string value) =>
        System.Version.TryParse(value, out var version) ? version : new System.Version(0, 0);

    private static bool HasArgument(string[] args, string expected) =>
        args.Any(argument => string.Equals(argument, expected, StringComparison.OrdinalIgnoreCase));
}
