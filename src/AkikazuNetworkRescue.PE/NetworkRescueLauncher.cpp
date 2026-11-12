#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <filesystem>
#include <string>

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int)
{
    constexpr wchar_t miniNt[] = L"SYSTEM\\CurrentControlSet\\Control\\MiniNT";
    HKEY key{};
    const auto status = RegOpenKeyExW(HKEY_LOCAL_MACHINE, miniNt, 0, KEY_QUERY_VALUE, &key);
    const bool isPe = status == ERROR_SUCCESS;
    if (isPe) RegCloseKey(key);

    wchar_t executable[MAX_PATH]{};
    const auto length = GetModuleFileNameW(nullptr, executable, ARRAYSIZE(executable));
    if ((!isPe && status != ERROR_FILE_NOT_FOUND && status != ERROR_PATH_NOT_FOUND) ||
        !length || length >= ARRAYSIZE(executable)) {
        MessageBoxW(nullptr, L"Unable to identify the Windows environment.", L"Network Rescue", MB_OK | MB_ICONERROR);
        return 1;
    }

    const auto directory = std::filesystem::path(executable).parent_path();
    const auto target = directory / (isPe ? L"PeNetworkRescue.exe" : L"AkikazuHardwareCheck.exe");
    auto command = L"\"" + target.wstring() + (isPe ? L"\" --ui" : L"\" --portable-rescue");
    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(target.c_str(), command.data(), nullptr, nullptr, FALSE, isPe ? CREATE_NO_WINDOW : 0,
            nullptr, directory.c_str(), &startup, &process)) {
        MessageBoxW(nullptr, L"Extract the complete offline package and run NetworkRescue.exe again.",
            L"Network Rescue", MB_OK | MB_ICONERROR);
        return 2;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
