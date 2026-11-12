#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define USE_SP_ALTPLATFORM_INFO_V3 1
#include <windows.h>
#include <setupapi.h>

#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

struct Target {
    fs::path root;
    DWORD build;
};

static bool HasRegistryHiveHeader(const fs::path& path)
{
    std::ifstream file(path, std::ios::binary);
    std::array<char, 4> header{};
    return file.read(header.data(), header.size()) && header == std::array<char, 4>{ 'r', 'e', 'g', 'f' };
}

static DWORD ReadWindowsBuild(const fs::path& root)
{
    const auto config = root / L"Windows/System32/config";
    const auto kernel = root / L"Windows/System32/ntoskrnl.exe";
    if (!HasRegistryHiveHeader(config / L"SYSTEM") ||
        !HasRegistryHiveHeader(config / L"SOFTWARE")) {
        return 0;
    }

    std::ifstream file(kernel, std::ios::binary);
    IMAGE_DOS_HEADER dos{};
    DWORD signature{};
    IMAGE_FILE_HEADER header{};
    if (!file.read(reinterpret_cast<char*>(&dos), sizeof dos) || dos.e_magic != IMAGE_DOS_SIGNATURE ||
        dos.e_lfanew < sizeof dos || !file.seekg(dos.e_lfanew) ||
        !file.read(reinterpret_cast<char*>(&signature), sizeof signature) || signature != IMAGE_NT_SIGNATURE ||
        !file.read(reinterpret_cast<char*>(&header), sizeof header) || header.Machine != IMAGE_FILE_MACHINE_AMD64) {
        return 0;
    }

    const auto size = GetFileVersionInfoSizeW(kernel.c_str(), nullptr);
    std::vector<BYTE> buffer(size);
    if (size == 0 || !GetFileVersionInfoW(kernel.c_str(), 0, size, buffer.data())) {
        return 0;
    }
    void* value = nullptr;
    UINT length = 0;
    if (!VerQueryValueW(buffer.data(), L"\\", &value, &length) || length < sizeof(VS_FIXEDFILEINFO)) {
        return 0;
    }
    const auto& version = *static_cast<VS_FIXEDFILEINFO*>(value);
    return version.dwSignature == VS_FFI_SIGNATURE && version.dwFileVersionMS == MAKELONG(0, 10)
        ? HIWORD(version.dwFileVersionLS) : 0;
}

static std::vector<Target> DiscoverTargets()
{
    wchar_t windows[MAX_PATH]{};
    if (!GetWindowsDirectoryW(windows, MAX_PATH)) {
        return {};
    }

    std::vector<Target> targets;
    const DWORD drives = GetLogicalDrives();
    for (int index = 0; index < 26; ++index) {
        wchar_t root[] = { static_cast<wchar_t>(L'A' + index), L':', L'\\', L'\0' };
        if (!(drives & (1u << index)) || root[0] == towupper(windows[0]) ||
            GetDriveTypeW(root) != DRIVE_FIXED) {
            continue;
        }
        const auto build = ReadWindowsBuild(root);
        if (build >= 10240) {
            targets.push_back({ root, build });
        }
    }
    return targets;
}

static std::vector<std::wstring> ReadDeviceHardwareIds()
{
    std::vector<std::wstring> ids;
    const auto devices = SetupDiGetClassDevsW(nullptr, nullptr, nullptr, DIGCF_ALLCLASSES | DIGCF_PRESENT);
    if (devices == INVALID_HANDLE_VALUE) {
        return ids;
    }

    for (DWORD index = 0;; ++index) {
        SP_DEVINFO_DATA device{};
        device.cbSize = sizeof device;
        if (!SetupDiEnumDeviceInfo(devices, index, &device)) {
            break;
        }
        DWORD size = 0;
        SetupDiGetDeviceRegistryPropertyW(devices, &device, SPDRP_HARDWAREID, nullptr, nullptr, 0, &size);
        if (!size || size > 65536) {
            continue;
        }
        std::vector<wchar_t> values(size / sizeof(wchar_t) + 2);
        DWORD type = 0;
        if (!SetupDiGetDeviceRegistryPropertyW(devices, &device, SPDRP_HARDWAREID, &type,
                reinterpret_cast<PBYTE>(values.data()), size, nullptr) || type != REG_MULTI_SZ) {
            continue;
        }
        for (const wchar_t* id = values.data(); *id; id += wcslen(id) + 1) {
            if (_wcsnicmp(id, L"PCI\\VEN_", 8) == 0 || _wcsnicmp(id, L"USB\\VID_", 8) == 0) {
                ids.emplace_back(id);
            }
        }
    }
    SetupDiDestroyDeviceInfoList(devices);
    return ids;
}

static std::wstring InfField(INFCONTEXT& context, DWORD index)
{
    wchar_t value[1024]{};
    return SetupGetStringFieldW(&context, index, value, ARRAYSIZE(value), nullptr) ? value : L"";
}

static std::wstring MatchNetworkInf(const fs::path& path, DWORD build, const std::vector<std::wstring>& ids)
{
    const auto inf = SetupOpenInfFileW(path.c_str(), nullptr, INF_STYLE_WIN4, nullptr);
    if (inf == INVALID_HANDLE_VALUE) {
        return {};
    }

    INFCONTEXT line{};
    INFCONTEXT manufacturer{};
    std::wstring matched;
    if (SetupFindFirstLineW(inf, L"Version", L"ClassGuid", &line) &&
        _wcsicmp(InfField(line, 1).c_str(), L"{4d36e972-e325-11ce-bfc1-08002be10318}") == 0 &&
        SetupFindFirstLineW(inf, L"Manufacturer", nullptr, &manufacturer)) {
        SP_ALTPLATFORM_INFO platform{};
        platform.cbSize = sizeof platform;
        platform.Platform = VER_PLATFORM_WIN32_NT;
        platform.MajorVersion = 10;
        platform.ProcessorArchitecture = PROCESSOR_ARCHITECTURE_AMD64;
        platform.ProductType = VER_NT_WORKSTATION;
        platform.BuildNumber = build;
        do {
            wchar_t section[1024]{};
            if (!SetupDiGetActualModelsSectionW(&manufacturer, &platform, section, ARRAYSIZE(section), nullptr, nullptr) ||
                !SetupFindFirstLineW(inf, section, nullptr, &line)) {
                continue;
            }
            do {
                const auto model = InfField(line, 2);
                for (const auto& id : ids) {
                    if (_wcsicmp(model.c_str(), id.c_str()) == 0) {
                        matched = id;
                        break;
                    }
                }
            } while (matched.empty() && SetupFindNextLine(&line, &line));
        } while (matched.empty() && SetupFindNextLine(&manufacturer, &manufacturer));
    }
    SetupCloseInfFile(inf);
    return matched;
}

static bool VerifyNetworkDriver(const fs::path& path)
{
    SP_INF_SIGNER_INFO_W signer{};
    signer.cbSize = sizeof signer;
    return SetupVerifyInfFileW(path.c_str(), nullptr, &signer) != FALSE;
}

static DWORD RunDism(const Target& target, const std::wstring& arguments)
{
    wchar_t system[MAX_PATH]{};
    if (!GetSystemDirectoryW(system, MAX_PATH)) {
        return GetLastError();
    }
    const auto dism = fs::path(system) / L"dism.exe";
    auto command = L"\"" + dism.wstring() + L"\" /Image:\"" + (target.root / L".").wstring() +
        L"\" " + arguments;
    const auto scratch = target.root / L"Windows/Temp";
    std::error_code error;
    if (fs::is_directory(scratch, error)) {
        command += L" /ScratchDir:\"" + scratch.wstring() + L"\"";
    }
    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(dism.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr, nullptr,
            &startup, &process)) {
        return GetLastError();
    }
    CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = ERROR_GEN_FAILURE;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hProcess);
    return code;
}

static size_t ReadSelection(size_t maximum)
{
    std::wstring answer;
    std::getline(std::wcin, answer);
    wchar_t* end = nullptr;
    const auto value = wcstoul(answer.c_str(), &end, 10);
    return end != answer.c_str() && *end == L'\0' && value <= maximum ? value : 0;
}

int wmain(int argc, wchar_t** argv)
{
    const auto targets = DiscoverTargets();
    for (size_t i = 0; i < targets.size(); ++i) {
        std::wcout << i + 1 << L". " << targets[i].root.c_str() << L" Windows "
            << (targets[i].build < 22000 ? 10 : 11) << L" x64, kernel build " << targets[i].build << L'\n';
    }
    if (argc == 2 && wcscmp(argv[1], L"--list-targets") == 0) {
        std::wcout << L"Offline Windows installations: " << targets.size() << L'\n';
        return 0;
    }
    HKEY miniNt{};
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, L"SYSTEM\\CurrentControlSet\\Control\\MiniNT",
            0, KEY_READ, &miniNt) != ERROR_SUCCESS) {
        std::wcerr << L"Start this repair tool from WinPE.\n";
        return 1;
    }
    RegCloseKey(miniNt);
    if (targets.empty()) {
        std::wcerr << L"No accessible offline Windows 10/11 x64 installation found. Unlock locked volumes first.\n";
        return 2;
    }
    std::wcout << L"Select target Windows (0 to cancel): ";
    const auto selection = ReadSelection(targets.size());
    if (!selection) {
        return 0;
    }
    const auto& target = targets[selection - 1];

    wchar_t executable[MAX_PATH]{};
    if (!GetModuleFileNameW(nullptr, executable, MAX_PATH)) {
        return 3;
    }
    const auto directory = fs::path(executable).parent_path() / L"pe-drivers" /
        (target.build < 22000 ? L"windows10-x64" : L"windows11-x64");
    std::wcout << L"Scanning " << directory.c_str() << L'\n';
    const auto ids = ReadDeviceHardwareIds();
    std::vector<fs::path> candidates;
    std::error_code error;
    for (fs::recursive_directory_iterator it(directory, fs::directory_options::skip_permission_denied, error), end;
        !error && it != end; it.increment(error)) {
        if (!it->is_regular_file(error) || _wcsicmp(it->path().extension().c_str(), L".inf") != 0) {
            continue;
        }
        const auto match = MatchNetworkInf(it->path(), target.build, ids);
        if (!match.empty() && VerifyNetworkDriver(it->path())) {
            candidates.push_back(it->path());
            std::wcout << candidates.size() << L". " << it->path().c_str() << L" [" << match << L"]\n";
        }
    }
    if (error || candidates.empty()) {
        std::wcerr << L"No verified exact driver match. Check the target-specific driver folder.\n";
        return 4;
    }

    std::wcout << L"Select driver (0 to cancel): ";
    const auto driver = ReadSelection(candidates.size());
    if (!driver) {
        return 0;
    }
    const auto& inf = candidates[driver - 1];
    std::wcout << L"Stage " << inf.c_str() << L" in " << target.root.c_str()
        << L" Windows kernel build " << target.build << L"? [y/N] ";
    std::wstring confirmation;
    std::getline(std::wcin, confirmation);
    if (confirmation != L"y" && confirmation != L"Y") {
        return 0;
    }
    if (ReadWindowsBuild(target.root) != target.build || !VerifyNetworkDriver(inf)) {
        std::wcerr << L"The target or driver changed. Restart the scan.\n";
        return 5;
    }
    const auto result = RunDism(target, L"/Add-Driver /Driver:\"" + inf.wstring() + L"\"");
    std::wcout << L"DISM exit code: " << result << L'\n';
    if (result == ERROR_SUCCESS || result == ERROR_SUCCESS_REBOOT_REQUIRED) {
        const auto inventory = RunDism(target, L"/Get-Drivers");
        std::wcout << L"DISM driver inventory exit code: " << inventory
            << L"\nRestart into the target Windows and verify the device and connection.\n";
        return inventory == ERROR_SUCCESS ? 0 : 7;
    }
    return 6;
}
