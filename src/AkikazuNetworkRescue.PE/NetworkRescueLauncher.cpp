#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <filesystem>
#include <string>
#include <string_view>

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR arguments, int)
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

    const std::wstring_view argument(arguments);
    bool cli = argument == L"--cli";
    if (!cli && argument != L"--gui" && AttachConsole(ATTACH_PARENT_PROCESS)) {
        DWORD mode = 0;
        cli = GetConsoleMode(GetStdHandle(STD_INPUT_HANDLE), &mode) != FALSE;
        FreeConsole();
    }
    const auto directory = std::filesystem::path(executable).parent_path();
    const auto target = directory / (isPe || cli ? L"PeNetworkRescue.exe" : L"AkikazuHardwareCheck.exe");
    const auto mode = cli ? L"--cli-window" : isPe ? L"--ui" : L"--portable-rescue";
    auto command = L"\"" + target.wstring() + L"\" " + mode;
    // An interactive shell does not wait for a GUI-subsystem launcher. Give the CLI its
    // own console so both programs cannot compete for the same keyboard input.
    const DWORD flags = cli ? CREATE_NEW_CONSOLE : isPe ? CREATE_NO_WINDOW : 0;
    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(target.c_str(), command.data(), nullptr, nullptr, FALSE, flags,
            nullptr, directory.c_str(), &startup, &process)) {
        MessageBoxW(nullptr, L"Extract the complete offline package and run NetworkRescue.exe again.",
            L"Network Rescue", MB_OK | MB_ICONERROR);
        return 2;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
