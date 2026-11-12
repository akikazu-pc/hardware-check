#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define USE_SP_ALTPLATFORM_INFO_V3 1
#include <windows.h>
#include <setupapi.h>
#include <cfgmgr32.h>
#include <cfg.h>
#include <bcrypt.h>
#include <shellapi.h>
#include <fcntl.h>
#include <io.h>

#include <algorithm>
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

static DWORD ReadWindowsFileBuild(const fs::path& file)
{
    const auto size = GetFileVersionInfoSizeW(file.c_str(), nullptr);
    std::vector<BYTE> buffer(size);
    if (size == 0 || !GetFileVersionInfoW(file.c_str(), 0, size, buffer.data())) {
        return 0;
    }
    void* value = nullptr;
    UINT length = 0;
    if (!VerQueryValueW(buffer.data(), L"\\", &value, &length) || length < sizeof(VS_FIXEDFILEINFO)) {
        return 0;
    }
    const auto& version = *static_cast<VS_FIXEDFILEINFO*>(value);
    // Windows Setup PE can report 6.2 in the kernel's file version while
    // preserving 10.0 in the product version and the correct file build.
    const auto windows10Version = MAKELONG(0, 10);
    return version.dwSignature == VS_FFI_SIGNATURE &&
        (version.dwProductVersionMS == windows10Version || version.dwFileVersionMS == windows10Version)
        ? HIWORD(version.dwFileVersionLS) : 0;
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

    return ReadWindowsFileBuild(kernel);
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

static std::vector<std::wstring> ReadDeviceHardwareIds(bool missingOnly = false)
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
        if (missingOnly) {
            ULONG status = 0;
            ULONG problem = 0;
            if (CM_Get_DevNode_Status(&status, &problem, device.DevInst, 0) != CR_SUCCESS ||
                !(status & DN_HAS_PROBLEM) || problem != CM_PROB_FAILED_INSTALL) {
                continue;
            }
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

static std::wstring MatchNetworkInf(const fs::path& path, DWORD build, const std::vector<std::wstring>& ids,
    std::wstring& name)
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
                        name = InfField(line, 0);
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

static std::vector<fs::path> DriverDirectories(const fs::path& bundle, DWORD build)
{
    const auto scopedDrivers = bundle / L"pe-drivers" / (build < 22000 ? L"windows10-x64" : L"windows11-x64");
    std::vector<fs::path> directories{ scopedDrivers };
    std::ifstream scope(bundle / L"pe-driver-scope.txt");
    DWORD minimum = 0;
    std::string name;
    // OEM packages share the desktop library. The generated list carries the OEM OS floor.
    while (scope >> minimum >> name) {
        if (minimum <= build && name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.") == std::string::npos &&
            name != "." && name != "..") {
            directories.push_back(bundle / L"driver-packs" / name);
        }
    }
    return directories;
}

struct DriverMatch {
    fs::path path;
    std::wstring id;
    std::wstring name;
};

static std::vector<DriverMatch> ScanDrivers(const fs::path& bundle, DWORD build, bool missingOnly = false)
{
    const auto ids = ReadDeviceHardwareIds(missingOnly);
    std::vector<DriverMatch> candidates;
    if (ids.empty()) {
        return candidates;
    }
    for (const auto& directory : DriverDirectories(bundle, build)) {
        std::error_code error;
        if (!fs::exists(directory, error)) {
            continue;
        }
        for (fs::recursive_directory_iterator it(directory, fs::directory_options::skip_permission_denied, error), end;
            !error && it != end; it.increment(error)) {
            if (!it->is_regular_file(error) || _wcsicmp(it->path().extension().c_str(), L".inf") != 0) {
                continue;
            }
            std::wstring name;
            auto id = MatchNetworkInf(it->path(), build, ids, name);
            if (!id.empty() && VerifyNetworkDriver(it->path())) {
                candidates.push_back({ it->path(), std::move(id), std::move(name) });
            }
        }
    }
    return candidates;
}

#include "PeWizard.h"

#include "RescueCli.h"
#include "SharedHome.h"

int wmain(int argc, wchar_t** argv)
{
    wchar_t executable[MAX_PATH]{};
    const auto length = GetModuleFileNameW(nullptr, executable, MAX_PATH);
    if (!length || length >= MAX_PATH) return 3;
    const auto bundle = fs::path(executable).parent_path();
    if (argc == 2 && wcscmp(argv[1], L"--list-targets") == 0) {
        const auto targets = DiscoverTargets();
        for (const auto& target : targets) std::wcout << WindowsLabel(target.root, target.build) << L'\n';
        std::wcout << L"Offline Windows installations: " << targets.size() << L'\n';
        return 0;
    }
    HKEY miniNt{};
    const bool isPe = RegOpenKeyExW(HKEY_LOCAL_MACHINE, L"SYSTEM\\CurrentControlSet\\Control\\MiniNT",
        0, KEY_READ, &miniNt) == ERROR_SUCCESS;
    if (isPe) RegCloseKey(miniNt);
    if (argc == 2 && wcscmp(argv[1], L"--ui") == 0) return RunSharedHome(bundle, isPe);
    const bool keepOpen = argc == 2 && wcscmp(argv[1], L"--cli-window") == 0;
    return StartCli(bundle, isPe, keepOpen);
}
