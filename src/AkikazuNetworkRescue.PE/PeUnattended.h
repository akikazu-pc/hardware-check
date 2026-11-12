#include <winioctl.h>
#include <memory>
#include <optional>
#include <functional>

struct CloseNativeHandle {
    void operator()(void* handle) const { CloseHandle(handle); }
};
using NativeHandle = std::unique_ptr<void, CloseNativeHandle>;

static NativeHandle OpenDeploymentFile(const fs::path& path, DWORD access, DWORD share)
{
    const auto handle = CreateFileW(path.c_str(), access, share, nullptr, OPEN_EXISTING, 0, nullptr);
    return NativeHandle(handle == INVALID_HANDLE_VALUE ? nullptr : handle);
}

static constexpr ULONGLONG MiB = 1024ull * 1024;
static constexpr ULONGLONG DeploymentWindowsMiB = 300 * 1024;
static constexpr ULONGLONG DeploymentReservedMiB = 260 + 16 + 1024 + 3;

struct BlankDisk {
    DWORD number;
    ULONGLONG bytes;
    STORAGE_BUS_TYPE bus;
    std::wstring model;
    std::wstring serial;
    GUID id;
};

static std::wstring PhysicalDiskPath(DWORD number)
{
    return L"\\\\.\\PhysicalDrive" + std::to_wstring(number);
}

static bool ReadBlankDisk(HANDLE handle, DWORD number, BlankDisk& disk)
{
    STORAGE_DEVICE_NUMBER_EX identity{};
    DWORD returned = 0;
    if (!DeviceIoControl(handle, IOCTL_STORAGE_GET_DEVICE_NUMBER_EX, nullptr, 0, &identity,
            sizeof identity, &returned, nullptr) || returned < sizeof identity ||
        identity.DeviceType != FILE_DEVICE_DISK || identity.DeviceNumber != number ||
        IsEqualGUID(identity.DeviceGuid, GUID{})) return false;

    STORAGE_PROPERTY_QUERY query{ StorageDeviceProperty, PropertyStandardQuery, {} };
    alignas(STORAGE_DEVICE_DESCRIPTOR) std::array<BYTE, 4096> device{};
    if (!DeviceIoControl(handle, IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof query, device.data(),
            static_cast<DWORD>(device.size()), &returned, nullptr) ||
        returned < FIELD_OFFSET(STORAGE_DEVICE_DESCRIPTOR, RawDeviceProperties)) return false;
    const auto* descriptor = reinterpret_cast<const STORAGE_DEVICE_DESCRIPTOR*>(device.data());
    if (descriptor->RemovableMedia) return false;
    switch (descriptor->BusType) {
    case BusTypeScsi: case BusTypeAta: case BusTypeSata: case BusTypeSas: case BusTypeRAID:
    case BusTypeNvme: case BusTypeVirtual: case BusTypeFileBackedVirtual:
        break;
    default: return false;
    }

    const auto field = [&](DWORD offset) -> std::wstring {
        if (offset == 0 || offset >= returned) return {};
        const auto* start = reinterpret_cast<const char*>(device.data() + offset);
        const auto* end = std::find(start, start + (returned - offset), '\0');
        return end == start + (returned - offset) ? std::wstring{} : std::wstring(start, end);
    };
    const auto model = field(descriptor->ProductIdOffset);
    const auto serial = field(descriptor->SerialNumberOffset);

    // Some storage drivers report a zeroed disk as MBR with zero entries.
    // HasEmptyDiskEdges independently rejects boot records and stale tables.
    DRIVE_LAYOUT_INFORMATION_EX layout{};
    if (!DeviceIoControl(handle, IOCTL_DISK_GET_DRIVE_LAYOUT_EX, nullptr, 0, &layout,
            sizeof layout, &returned, nullptr) || layout.PartitionCount != 0 ||
        (layout.PartitionStyle != PARTITION_STYLE_RAW && layout.PartitionStyle != PARTITION_STYLE_MBR)) return false;
    GET_DISK_ATTRIBUTES attributes{};
    if (!DeviceIoControl(handle, IOCTL_DISK_GET_DISK_ATTRIBUTES, nullptr, 0, &attributes,
            sizeof attributes, &returned, nullptr) ||
        (attributes.Attributes & (DISK_ATTRIBUTE_OFFLINE | DISK_ATTRIBUTE_READ_ONLY)) != 0) return false;
    GET_LENGTH_INFORMATION length{};
    if (!DeviceIoControl(handle, IOCTL_DISK_GET_LENGTH_INFO, nullptr, 0, &length, sizeof length,
            &returned, nullptr) || length.Length.QuadPart < static_cast<LONGLONG>(64 * 1024 * MiB)) return false;
    disk = { number, static_cast<ULONGLONG>(length.Length.QuadPart), descriptor->BusType, model, serial,
        identity.DeviceGuid };
    return true;
}

static bool HasEmptyDiskEdges(HANDLE handle, ULONGLONG bytes)
{
    // Reject raw volumes with common filesystem headers or stale partition tables.
    std::vector<BYTE> data(static_cast<size_t>(MiB));
    for (const auto offset : { 0ull, bytes - MiB }) {
        LARGE_INTEGER position{};
        position.QuadPart = static_cast<LONGLONG>(offset);
        DWORD read = 0;
        if (!SetFilePointerEx(handle, position, nullptr, FILE_BEGIN) ||
            !ReadFile(handle, data.data(), static_cast<DWORD>(data.size()), &read, nullptr) ||
            read != data.size()) return false;
        if (offset == 0) {
            // A virtual storage controller can expose a four-byte MBR disk
            // signature even though the boot code and partition table are empty.
            std::fill_n(data.begin() + 440, 4, BYTE{});
        }
        if (std::any_of(data.begin(), data.end(), [](BYTE byte) { return byte != 0; })) return false;
    }
    return true;
}

static std::vector<BlankDisk> DiscoverBlankDisks()
{
    std::vector<wchar_t> names(65536);
    if (!QueryDosDeviceW(nullptr, names.data(), static_cast<DWORD>(names.size()))) return {};
    std::vector<BlankDisk> disks;
    constexpr std::wstring_view prefix = L"PhysicalDrive";
    for (auto* name = names.data(); *name; name += wcslen(name) + 1) {
        if (std::wstring_view(name).substr(0, prefix.size()) != prefix) continue;
        wchar_t* end = nullptr;
        const auto number = wcstoul(name + prefix.size(), &end, 10);
        if (end == name + prefix.size() || *end) continue;
        auto handle = OpenDeploymentFile(PhysicalDiskPath(number), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE);
        BlankDisk disk{};
        if (handle && ReadBlankDisk(handle.get(), number, disk) && HasEmptyDiskEdges(handle.get(), disk.bytes)) {
            disks.push_back(std::move(disk));
        }
    }
    std::sort(disks.begin(), disks.end(), [](const BlankDisk& left, const BlankDisk& right) {
        return left.number < right.number;
    });
    return disks;
}

static ULONGLONG WindowsPartitionMiB(const BlankDisk& disk)
{
    return (std::min)(DeploymentWindowsMiB, disk.bytes / MiB - DeploymentReservedMiB);
}

static std::wstring DiskLabel(const BlankDisk& disk)
{
    return L"Disk " + std::to_wstring(disk.number) + L"  " + disk.model +
        (disk.serial.empty() ? L"" : L"  [" + disk.serial + L"]") + L"  " +
        std::to_wstring(disk.bytes / (1024 * MiB)) + L" GiB  →  C: " +
        std::to_wstring(WindowsPartitionMiB(disk)) + L" MiB";
}

static std::array<wchar_t, 3> FreeDeploymentLetters()
{
    const auto used = GetLogicalDrives();
    if (!used) return {};
    std::array<wchar_t, 3> letters{};
    size_t index = 0;
    for (wchar_t letter = L'Z'; letter >= L'D'; --letter) {
        if (letter != L'X' && !(used & (1u << (letter - L'A')))) {
            letters[index++] = letter;
            if (index == letters.size()) return letters;
        }
    }
    return {};
}

static bool VolumeIsOnDisk(wchar_t letter, DWORD number)
{
    const std::wstring path = std::wstring(L"\\\\.\\") + letter + L":";
    auto volume = OpenDeploymentFile(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE);
    VOLUME_DISK_EXTENTS extents{};
    DWORD returned = 0;
    return volume && DeviceIoControl(volume.get(), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, nullptr, 0,
        &extents, sizeof extents, &returned, nullptr) && extents.NumberOfDiskExtents == 1 &&
        extents.Extents[0].DiskNumber == number;
}

static bool SaveDeploymentFile(const fs::path& path, const std::wstring& text)
{
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    file.write(reinterpret_cast<const char*>(text.data()), static_cast<std::streamsize>(text.size() * sizeof(wchar_t)));
    file.close();
    return !!file;
}

static bool WriteDeploymentAnswer(const fs::path& path, const std::wstring& locale)
{
    const auto language = XmlEscape(locale);
    const auto xml = std::wstring(
        L"\uFEFF<?xml version=\"1.0\" encoding=\"utf-16\"?>"
        L"<unattend xmlns=\"urn:schemas-microsoft-com:unattend\" xmlns:wcm=\"http://schemas.microsoft.com/WMIConfig/2002/State\">"
        L"<settings pass=\"oobeSystem\">"
        L"<component name=\"Microsoft-Windows-International-Core\" processorArchitecture=\"amd64\" "
        L"publicKeyToken=\"31bf3856ad364e35\" language=\"neutral\" versionScope=\"nonSxS\">"
        L"<InputLocale>") + language + L"</InputLocale><SystemLocale>" + language +
        L"</SystemLocale><UILanguage>" + language + L"</UILanguage><UserLocale>" + language + L"</UserLocale></component>"
        L"<component name=\"Microsoft-Windows-Shell-Setup\" processorArchitecture=\"amd64\" "
        L"publicKeyToken=\"31bf3856ad364e35\" language=\"neutral\" versionScope=\"nonSxS\">"
        L"<OOBE><HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>"
        L"<HideOnlineAccountScreens>true</HideOnlineAccountScreens><HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>"
        L"<ProtectYourPC>3</ProtectYourPC></OOBE>"
        L"<UserAccounts><LocalAccounts><LocalAccount wcm:action=\"add\"><Name>user</Name><Group>Administrators</Group>"
        L"<Password><Value></Value><PlainText>true</PlainText></Password></LocalAccount></LocalAccounts></UserAccounts>"
        L"</component></settings></unattend>";
    return SaveDeploymentFile(path, xml);
}

static bool WriteDeploymentPartitions(const fs::path& path, const BlankDisk& disk, const std::array<wchar_t, 3>& letters)
{
    // Each format applies to a just-created partition in DiskPart. No clean, override or noerr.
    std::ofstream script(path);
    script << "select disk " << disk.number << "\nconvert gpt\n"
        << "create partition efi size=260\nformat quick fs=fat32 label=System\nassign letter=" << static_cast<char>(letters[0]) << '\n'
        << "create partition msr size=16\ncreate partition primary size=" << WindowsPartitionMiB(disk)
        << "\nformat quick fs=ntfs label=Windows\nassign letter=" << static_cast<char>(letters[1]) << '\n'
        << "create partition primary size=1024\nformat quick fs=ntfs label=Recovery\nassign letter=" << static_cast<char>(letters[2])
        << "\nset id=de94bba4-06d1-4d40-a16a-bfd50179d6ac\ngpt attributes=0x8000000000000001\nexit\n";
    script.close();
    return !!script;
}

static DWORD RunDeploymentTool(const fs::path& exe, const std::wstring& arguments)
{
    auto command = L"\"" + exe.wstring() + L"\" " + arguments;
    STARTUPINFOW start{};
    start.cb = sizeof start;
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(exe.c_str(), command.data(), nullptr, nullptr, FALSE,
            wizardOwner ? CREATE_NO_WINDOW : 0, nullptr, nullptr, &start, &process)) return GetLastError();
    CloseHandle(process.hThread);
    const NativeHandle running(process.hProcess);
    for (;;) {
        const auto wait = MsgWaitForMultipleObjects(1, &process.hProcess, FALSE, INFINITE, QS_ALLINPUT);
        if (wait == WAIT_OBJECT_0) break;
        if (wait != WAIT_OBJECT_0 + 1) return ERROR_GEN_FAILURE;
        MSG message{};
        while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
            if (message.message == WM_QUIT) continue;
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
    }
    DWORD code = ERROR_GEN_FAILURE;
    return GetExitCodeProcess(process.hProcess, &code) ? code : GetLastError();
}

static std::wstring DeploymentQuoted(const fs::path& path)
{
    return L"\"" + path.wstring() + L"\"";
}

static fs::path DeploymentRoot(wchar_t letter)
{
    return std::wstring(1, letter) + L":\\";
}

struct DeploymentWorkspace {
    fs::path path;
    ~DeploymentWorkspace()
    {
        if (!path.empty()) {
            std::error_code error;
            fs::remove_all(path, error);
        }
    }
};

static bool SameDisk(const BlankDisk& selected, const BlankDisk& now)
{
    return selected.bytes == now.bytes && selected.bus == now.bus && selected.serial == now.serial &&
        selected.model == now.model && IsEqualGUID(selected.id, now.id);
}

static bool SupportsUnattended(const SetupMedia& media)
{
    FIRMWARE_TYPE firmware{};
    return GetFirmwareType(&firmware) && firmware == FirmwareTypeUefi && !media.editions.empty() &&
        std::any_of(media.editions.begin(), media.editions.end(), [](const SetupImage& image) { return !image.locale.empty(); });
}

static DWORD DeployWindows(const SetupMedia& media, const SetupImage& edition, const BlankDisk& selected,
    const fs::path& inf, const PeText& text, const std::function<void(const wchar_t*)>& show,
    const wchar_t*& failedStep)
{
    failedStep = text.deployPreparing;
    show(failedStep);
    SetLastError(ERROR_SUCCESS);
    const NativeHandle mutex(CreateMutexW(nullptr, TRUE, L"Local\\AkikazuNetworkRescue.Deployment"));
    if (!mutex || GetLastError() == ERROR_ALREADY_EXISTS) return ERROR_BUSY;
    if (!SupportsUnattended(media) || IsSetupRunning()) return ERROR_NOT_SUPPORTED;
    auto source = OpenDeploymentFile(media.image, GENERIC_READ, FILE_SHARE_READ);
    if (!source) return GetLastError();
    std::vector<SetupImage> currentImages;
    if (ReadImageBuild(media.image, currentImages) != media.build ||
        std::none_of(currentImages.begin(), currentImages.end(), [&](const SetupImage& current) {
            return current.index == edition.index && current.name == edition.name && current.locale == edition.locale;
        })) return ERROR_INVALID_DATA;

    wchar_t system[MAX_PATH]{}, temp[MAX_PATH]{};
    const auto systemLength = GetSystemDirectoryW(system, MAX_PATH);
    const auto tempLength = GetTempPathW(MAX_PATH, temp);
    if (!systemLength || systemLength >= MAX_PATH || !tempLength || tempLength >= MAX_PATH) return ERROR_PATH_NOT_FOUND;
    const fs::path tools(system);
    const auto diskpart = tools / L"diskpart.exe";
    const auto dism = tools / L"dism.exe";
    const auto bcdboot = tools / L"bcdboot.exe";
    const auto wpeutil = tools / L"wpeutil.exe";
    std::error_code error;
    for (const auto& tool : { diskpart, dism, bcdboot, wpeutil }) {
        if (!fs::is_regular_file(tool, error)) return ERROR_FILE_NOT_FOUND;
    }
    const auto work = fs::path(temp) / (L"NetworkRescueDeploy-" + std::to_wstring(GetCurrentProcessId()));
    if (!fs::create_directory(work, error)) return ERROR_CANNOT_MAKE;
    const DeploymentWorkspace cleanup{ work };
    const auto driver = PrepareSetupDriver(inf, work);
    if (driver.empty() || !VerifyNetworkDriver(driver / inf.filename())) return ERROR_INVALID_DATA;
    const auto answer = work / L"Unattend.xml";
    const auto partitions = work / L"partitions.txt";
    const auto letters = FreeDeploymentLetters();
    if (!letters[0] || !WriteDeploymentAnswer(answer, edition.locale) ||
        !WriteDeploymentPartitions(partitions, selected, letters)) return ERROR_WRITE_FAULT;

    const auto systemRoot = DeploymentRoot(letters[0]);
    const auto windowsRoot = DeploymentRoot(letters[1]);
    const auto recoveryRoot = DeploymentRoot(letters[2]);
    const auto disk = OpenDeploymentFile(PhysicalDiskPath(selected.number), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE);
    BlankDisk current{};
    if (!disk || !ReadBlankDisk(disk.get(), selected.number, current) || !SameDisk(selected, current) ||
        !HasEmptyDiskEdges(disk.get(), current.bytes) || FreeDeploymentLetters() != letters) return ERROR_MEDIA_CHANGED;

    failedStep = text.deployPartitioning;
    show(failedStep);
    auto code = RunDeploymentTool(diskpart, L"/s " + DeploymentQuoted(partitions));
    if (code != ERROR_SUCCESS) return code;
    for (const auto letter : letters) {
        if (!VolumeIsOnDisk(letter, selected.number)) return ERROR_INVALID_DRIVE;
    }
    const auto scratch = windowsRoot / L"NetworkRescueDeployment";
    if (!fs::create_directory(scratch, error)) return ERROR_CANNOT_MAKE;
    const auto log = [&](const wchar_t* file) { return L" /LogPath:" + DeploymentQuoted(scratch / file); };
    const auto dismScratch = L" /ScratchDir:" + DeploymentQuoted(scratch);

    failedStep = text.deployApplying;
    show(failedStep);
    auto args = L"/Apply-Image /CheckIntegrity /ImageFile:" + DeploymentQuoted(media.image) +
        L" /Index:" + std::to_wstring(edition.index) + L" /ApplyDir:" + DeploymentQuoted(windowsRoot / L".") +
        dismScratch + log(L"apply.log");
    if (_wcsicmp(media.image.extension().c_str(), L".swm") == 0) {
        args += L" /SWMFile:" + DeploymentQuoted(media.image.parent_path() / L"install*.swm");
    }
    code = RunDeploymentTool(dism, args);
    if (code != ERROR_SUCCESS) return code;

    failedStep = text.deployDrivers;
    show(failedStep);
    code = RunDeploymentTool(dism, L"/Image:" + DeploymentQuoted(windowsRoot / L".") + L" /Add-Driver /Driver:" +
        DeploymentQuoted(driver / inf.filename()) + dismScratch + log(L"drivers.log"));
    if (code != ERROR_SUCCESS && code != ERROR_SUCCESS_REBOOT_REQUIRED) return code;

    failedStep = text.deployBoot;
    show(failedStep);
    const auto windows = windowsRoot / L"Windows";
    const auto panther = windows / L"Panther/Unattend";
    fs::create_directories(panther, error);
    if (error || !fs::copy_file(answer, panther / L"Unattend.xml", fs::copy_options::none, error)) return ERROR_WRITE_FAULT;
    code = RunDeploymentTool(bcdboot, DeploymentQuoted(windows) + L" /s " +
        std::wstring(1, letters[0]) + L": /f UEFI");
    if (code != ERROR_SUCCESS) return code;

    failedStep = text.deployRecovery;
    show(failedStep);
    const auto recovery = recoveryRoot / L"Recovery/WindowsRE";
    fs::create_directories(recovery, error);
    if (error || !fs::copy_file(windows / L"System32/Recovery/Winre.wim", recovery / L"Winre.wim",
            fs::copy_options::none, error)) return ERROR_WRITE_FAULT;
    code = RunDeploymentTool(windows / L"System32/ReAgentc.exe",
        L"/setreimage /path " + DeploymentQuoted(recovery) + L" /target " + DeploymentQuoted(windows));
    if (code != ERROR_SUCCESS) return code;
    return ERROR_SUCCESS;
}


struct DeploymentSelection {
    SetupImage edition;
    BlankDisk disk;
};

static std::wstring EditionLabel(const SetupImage& edition)
{
    return std::to_wstring(edition.index) + L". " + edition.name + L" [" + edition.locale + L"]";
}

static std::optional<DeploymentSelection> ChooseDeployment(const SetupMedia& media, const PeText& text,
    const std::function<int(const wchar_t*, const std::vector<std::wstring>&)>& choose,
    const std::function<void(const wchar_t*)>& notice)
{
    const auto disks = DiscoverBlankDisks();
    if (disks.empty()) {
        notice(text.deployNoDisk);
        return {};
    }
    std::vector<SetupImage> editions;
    std::vector<std::wstring> labels;
    for (const auto& image : media.editions) {
        if (image.locale.empty()) continue;
        editions.push_back(image);
        // Choice lists number their entries already; the image index stays in the confirmation details.
        labels.push_back(image.name + L" [" + image.locale + L"]");
    }
    const auto edition = editions.size() == 1 ? 0 : choose(text.deployEdition, labels);
    if (edition < 0) return {};
    labels.clear();
    for (const auto& disk : disks) labels.push_back(DiskLabel(disk));
    const auto disk = choose(text.deployDisk, labels);
    if (disk < 0) return {};
    return DeploymentSelection{ editions[edition], disks[disk] };
}

static std::wstring DeploymentDetails(const SetupMedia& media, const DeploymentSelection& plan,
    const fs::path& inf)
{
    return WindowsLabel(media.root, media.build) + L"  " + EditionLabel(plan.edition) + L"\n" +
        DiskLabel(plan.disk) + L"\n" + inf.filename().wstring();
}

static DWORD RunUnattended(const SetupMedia& media, const DeploymentSelection& plan, const fs::path& inf,
    const PeText& text, const std::function<void(const wchar_t*)>& show, const wchar_t*& step)
{
    const auto code = DeployWindows(media, plan.edition, plan.disk, inf, text, show, step);
    if (code != ERROR_SUCCESS) return code;
    step = text.deployRestart;
    show(step);
    wchar_t system[MAX_PATH]{};
    const auto length = GetSystemDirectoryW(system, MAX_PATH);
    return length && length < MAX_PATH
        ? RunDeploymentTool(fs::path(system) / L"wpeutil.exe", L"reboot")
        : ERROR_PATH_NOT_FOUND;
}

static std::wstring DeploymentFailure(const PeText& text, const wchar_t* step, DWORD code)
{
    return std::wstring(text.deployFailed) + L"\n" + step + L"  (" + std::to_wstring(code) + L")";
}

static int DeployWithUi(const SetupMedia& media, const DeploymentSelection& plan, const fs::path& inf,
    const PeText& text)
{
    const auto progress = CreateWindowExW(WS_EX_TOOLWINDOW, L"STATIC", text.deployPreparing,
        WS_POPUP | WS_CAPTION | WS_VISIBLE | SS_CENTER | SS_CENTERIMAGE,
        (GetSystemMetrics(SM_CXSCREEN) - 550) / 2, (GetSystemMetrics(SM_CYSCREEN) - 112) / 2,
        550, 112, wizardOwner, nullptr, GetModuleHandleW(nullptr), nullptr);
    if (!progress) {
        Notice(text, text.failed);
        return 6;
    }
    const auto font = WizardFont(text);
    if (font) SendMessageW(progress, WM_SETFONT, reinterpret_cast<WPARAM>(font), TRUE);
    EnableWindow(wizardOwner, FALSE);
    const auto show = [&](const wchar_t* message) {
        SetWindowTextW(progress, message);
        UpdateWindow(progress);
    };
    const wchar_t* step = text.deployPreparing;
    const auto code = RunUnattended(media, plan, inf, text, show, step);
    EnableWindow(wizardOwner, TRUE);
    DestroyWindow(progress);
    if (font) DeleteObject(font);
    if (code == ERROR_SUCCESS) return 0;
    Notice(text, DeploymentFailure(text, step, code).c_str());
    return 6;
}
