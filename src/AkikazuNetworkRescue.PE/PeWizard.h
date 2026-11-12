#include <windows.h>
#include <tlhelp32.h>
#include <cstring>
#include <string_view>

#include "PeStrings.generated.h"

static HWND wizardOwner = nullptr;

struct PeChoice {
    const PeText& text;
    const wchar_t* prompt;
    const std::vector<std::wstring>& entries;
    int initial;
    HFONT font;
    const wchar_t* button;
    bool safeDefault;
};

static HWND ChoiceControl(HWND dialog, const wchar_t* type, const wchar_t* title, DWORD style, int id, RECT bounds)
{
    MapDialogRect(dialog, &bounds);
    return CreateWindowExW(0, type, title, WS_CHILD | WS_VISIBLE | style, bounds.left, bounds.top,
        bounds.right - bounds.left, bounds.bottom - bounds.top, dialog,
        reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)), GetModuleHandleW(nullptr), nullptr);
}

static INT_PTR CALLBACK PeChoiceDialog(HWND dialog, UINT message, WPARAM wparam, LPARAM lparam)
{
    constexpr int listId = 100;
    if (message == WM_INITDIALOG) {
        const auto& choice = *reinterpret_cast<const PeChoice*>(lparam);
        SetWindowLongPtrW(dialog, GWLP_USERDATA, choice.safeDefault ? 1 : 0);
        // The window frame uses the PE system font, which may lack CJK glyphs.
        SetWindowTextW(dialog, L"Network Rescue");
        const auto icon = LoadIconW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(1));
        if (icon) {
            SendMessageW(dialog, WM_SETICON, ICON_SMALL, reinterpret_cast<LPARAM>(icon));
            SendMessageW(dialog, WM_SETICON, ICON_BIG, reinterpret_cast<LPARAM>(icon));
        }
        const auto prompt = ChoiceControl(dialog, L"STATIC", choice.prompt, 0, -1,
            choice.entries.empty() ? RECT{ 8, 8, 410, 126 } : RECT{ 8, 8, 410, 30 });
        const auto primary = ChoiceControl(dialog, L"BUTTON", choice.button,
            WS_TABSTOP | (choice.safeDefault ? BS_PUSHBUTTON : BS_DEFPUSHBUTTON), IDOK, { 294, 134, 348, 151 });
        HWND list = nullptr;
        HWND cancel = nullptr;
        if (!choice.entries.empty()) {
            list = ChoiceControl(dialog, L"LISTBOX", L"", WS_TABSTOP | WS_BORDER | WS_VSCROLL |
                WS_HSCROLL | LBS_NOTIFY | LBS_NOINTEGRALHEIGHT, listId, { 8, 32, 410, 126 });
            cancel = ChoiceControl(dialog, L"BUTTON", choice.text.cancel,
                WS_TABSTOP | (choice.safeDefault ? BS_DEFPUSHBUTTON : BS_PUSHBUTTON), IDCANCEL, { 354, 134, 410, 151 });
        }
        for (const auto control : { prompt, primary, list, cancel }) {
            if (control && choice.font) SendMessageW(control, WM_SETFONT, reinterpret_cast<WPARAM>(choice.font), TRUE);
        }
        size_t width = 0;
        for (const auto& entry : choice.entries) {
            SendMessageW(list, LB_ADDSTRING, 0, reinterpret_cast<LPARAM>(entry.c_str()));
            width = std::max(width, entry.size());
        }
        if (list) {
            SendMessageW(list, LB_SETHORIZONTALEXTENT, width * 15, 0);
            SendMessageW(list, LB_SETCURSEL, choice.initial, 0);
        }
        SendMessageW(dialog, DM_SETDEFID, choice.safeDefault ? IDCANCEL : IDOK, 0);
        SetFocus(choice.safeDefault ? cancel : list ? list : primary);
        return FALSE;
    }
    if (message == WM_CLOSE || (message == WM_COMMAND && LOWORD(wparam) == IDCANCEL)) {
        EndDialog(dialog, 0);
        return TRUE;
    }
    if (message == WM_COMMAND && (LOWORD(wparam) == IDOK ||
            (LOWORD(wparam) == listId && HIWORD(wparam) == LBN_DBLCLK &&
                GetWindowLongPtrW(dialog, GWLP_USERDATA) == 0))) {
        const auto index = SendDlgItemMessageW(dialog, listId, LB_GETCURSEL, 0, 0);
        if (!GetDlgItem(dialog, listId) || index != LB_ERR) {
            EndDialog(dialog, index == LB_ERR ? 1 : index + 1);
        }
        return TRUE;
    }
    return FALSE;
}

static HFONT WizardFont(const PeText& text)
{
    const wchar_t* faces[] = { L"Noto Sans CJK JP", L"Noto Sans CJK JP", L"Noto Sans CJK SC", L"Noto Sans CJK TC" };
    const auto screen = GetDC(nullptr);
    const int dpi = screen ? GetDeviceCaps(screen, LOGPIXELSY) : 96;
    if (screen) ReleaseDC(nullptr, screen);
    return CreateFontW(-MulDiv(10, dpi, 72), 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE, faces[&text - peText]);
}

static int Choose(const PeText& text, const wchar_t* prompt, const std::vector<std::wstring>& entries, int initial = 0,
    const wchar_t* button = nullptr, bool safeDefault = false)
{
    struct alignas(DWORD) EmptyDialog {
        DLGTEMPLATE base;
        WORD menu;
        WORD windowClass;
        WORD title;
    };
    const EmptyDialog layout{
        { WS_POPUP | WS_CAPTION | WS_SYSMENU | DS_MODALFRAME | DS_CENTER, 0, 0, 0, 0, 418, 158 },
        0, 0, 0
    };
    const auto font = WizardFont(text);
    const PeChoice choice{ text, prompt, entries, initial, font, button ? button : text.next, safeDefault };
    const auto result = DialogBoxIndirectParamW(GetModuleHandleW(nullptr), &layout.base, wizardOwner,
        PeChoiceDialog, reinterpret_cast<LPARAM>(&choice));
    if (font) DeleteObject(font);
    return result > 0 ? static_cast<int>(result - 1) : -1;
}

static void Notice(const PeText& text, const wchar_t* message)
{
    Choose(text, message, {}, 0, text.close);
}

static bool Confirm(const PeText& text, const wchar_t* prompt, const std::wstring& details)
{
    return Choose(text, prompt, { details }, 0, text.confirm, true) == 0;
}

static std::wstring WindowsLabel(const fs::path& root, DWORD build)
{
    return root.wstring() + L"  Windows " + (build < 22000 ? L"10" : L"11") +
        L" x64  (" + std::to_wstring(build) + L")";
}

struct SetupMedia {
    fs::path root;
    DWORD build;
};

template<class Function> static Function WimApi(HMODULE library, const char* name)
{
    const auto address = GetProcAddress(library, name);
    Function result{};
    static_assert(sizeof result == sizeof address);
    std::memcpy(&result, &address, sizeof result);
    return result;
}

static DWORD ReadImageBuild(const fs::path& path)
{
    const auto library = LoadLibraryExW(L"wimgapi.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!library) {
        return 0;
    }
    const auto open = WimApi<HANDLE (WINAPI*)(PWSTR, DWORD, DWORD, DWORD, DWORD, PDWORD)>(library, "WIMCreateFile");
    const auto info = WimApi<BOOL (WINAPI*)(HANDLE, PVOID*, PDWORD)>(library, "WIMGetImageInformation");
    const auto close = WimApi<BOOL (WINAPI*)(HANDLE)>(library, "WIMCloseHandle");
    DWORD result = 0;
    if (open && info && close) {
        auto filename = path.wstring();
        constexpr DWORD wimOpenExisting = 3;
        const auto handle = open(filename.data(), 0, wimOpenExisting, 0, 0, nullptr);
        if (handle && handle != INVALID_HANDLE_VALUE) {
            void* buffer = nullptr;
            DWORD size = 0;
            if (info(handle, &buffer, &size) && buffer) {
                const std::wstring_view xml(static_cast<const wchar_t*>(buffer), size / sizeof(wchar_t));
                size_t start = 0;
                while ((start = xml.find(L"<IMAGE ", start)) != std::wstring_view::npos) {
                    const auto end = xml.find(L"</IMAGE>", start);
                    if (end == std::wstring_view::npos) {
                        result = 0;
                        break;
                    }
                    const auto entry = xml.substr(start, end - start);
                    const auto tag = entry.find(L"<BUILD>");
                    if (tag == std::wstring_view::npos || entry.find(L"<ARCH>9</ARCH>") == std::wstring_view::npos ||
                        entry.find(L"<MAJOR>10</MAJOR>") == std::wstring_view::npos) {
                        result = 0;
                        break;
                    }
                    const auto value = std::wstring(entry.substr(tag + 7));
                    const auto build = wcstoul(value.c_str(), nullptr, 10);
                    if (build < 10240 || (result && result != build)) {
                        result = 0;
                        break;
                    }
                    result = build;
                    start = end + 8;
                }
                LocalFree(buffer);
            }
            close(handle);
        }
    }
    FreeLibrary(library);
    return result;
}

static std::vector<SetupMedia> DiscoverSetupMedia()
{
    wchar_t windows[MAX_PATH]{};
    if (!GetWindowsDirectoryW(windows, MAX_PATH)) {
        return {};
    }
    std::vector<SetupMedia> result;
    const auto drives = GetLogicalDrives();
    for (int i = 0; i < 26; ++i) {
        if (!(drives & (1u << i)) || L'A' + i == towupper(windows[0])) {
            continue;
        }
        const wchar_t drive[] = { static_cast<wchar_t>(L'A' + i), L':', L'\\', L'\0' };
        const auto type = GetDriveTypeW(drive);
        if (type != DRIVE_FIXED && type != DRIVE_REMOVABLE && type != DRIVE_CDROM) {
            continue;
        }
        const fs::path root(drive);
        std::error_code error;
        if (!fs::is_regular_file(root / L"setup.exe", error)) {
            continue;
        }
        for (const auto* file : { L"install.wim", L"install.esd", L"install.swm" }) {
            const auto image = root / L"sources" / file;
            if (fs::is_regular_file(image, error)) {
                const auto build = ReadImageBuild(image);
                if (build) {
                    result.push_back({ root, build });
                }
                break;
            }
        }
    }
    return result;
}

static bool IsSetupRunning()
{
    const auto snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return true;
    }
    PROCESSENTRY32W process{};
    process.dwSize = sizeof process;
    bool running = false;
    if (Process32FirstW(snapshot, &process)) {
        do {
            if (_wcsicmp(process.szExeFile, L"setup.exe") == 0 ||
                _wcsicmp(process.szExeFile, L"setuphost.exe") == 0) {
                running = true;
                break;
            }
        } while (Process32NextW(snapshot, &process));
    }
    CloseHandle(snapshot);
    return running;
}

static bool IsStandaloneDriver(const fs::path& inf)
{
    size_t count = 0;
    std::error_code error;
    for (fs::recursive_directory_iterator it(inf.parent_path(), error), end;
        !error && it != end; it.increment(error)) {
        if (it->is_symlink(error)) {
            return false;
        }
        if (it->is_regular_file(error) && _wcsicmp(it->path().extension().c_str(), L".inf") == 0 && ++count > 1) {
            return false;
        }
    }
    return !error && count == 1;
}

static std::wstring XmlEscape(std::wstring_view value)
{
    std::wstring result;
    for (const wchar_t ch : value) {
        switch (ch) {
        case L'&': result += L"&amp;"; break;
        case L'<': result += L"&lt;"; break;
        case L'>': result += L"&gt;"; break;
        default: result += ch;
        }
    }
    return result;
}

static bool StartSetup(const SetupMedia& media, const fs::path& inf)
{
    wchar_t temp[MAX_PATH]{};
    const auto length = GetTempPathW(MAX_PATH, temp);
    if (!length || length >= MAX_PATH) {
        return false;
    }
    const auto answer = fs::path(temp) / (L"NetworkRescue-" + std::to_wstring(GetCurrentProcessId()) +
        L"-" + std::to_wstring(GetTickCount64()) + L".xml");
    const auto xml = std::wstring(
        L"\uFEFF<?xml version=\"1.0\" encoding=\"utf-16\"?>"
        L"<unattend xmlns=\"urn:schemas-microsoft-com:unattend\" xmlns:wcm=\"http://schemas.microsoft.com/WMIConfig/2002/State\">"
        L"<settings pass=\"offlineServicing\">"
        L"<component name=\"Microsoft-Windows-PnpCustomizationsNonWinPE\" processorArchitecture=\"amd64\" "
        L"publicKeyToken=\"31bf3856ad364e35\" language=\"neutral\" versionScope=\"nonSxS\">"
        L"<DriverPaths><PathAndCredentials wcm:action=\"add\" wcm:keyValue=\"1\"><Path>") +
        XmlEscape(inf.parent_path().wstring()) +
        L"</Path></PathAndCredentials></DriverPaths></component></settings></unattend>";
    const auto file = CreateFileW(answer.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return false;
    }
    const auto bytes = static_cast<DWORD>(xml.size() * sizeof(wchar_t));
    DWORD written = 0;
    const bool saved = WriteFile(file, xml.data(), bytes, &written, nullptr) && written == bytes;
    CloseHandle(file);

    const auto setup = media.root / L"setup.exe";
    auto command = L"\"" + setup.wstring() + L"\" /unattend:\"" + answer.wstring() + L"\"";
    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process{};
    if (!saved || !CreateProcessW(setup.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr,
            media.root.c_str(), &startup, &process)) {
        DeleteFileW(answer.c_str());
        return false;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return true;
}

static int PreferredLanguage()
{
    const LANGID uiLanguage = GetUserDefaultUILanguage();
    int preferred = 0;
    if (PRIMARYLANGID(uiLanguage) == LANG_JAPANESE) preferred = 1;
    if (PRIMARYLANGID(uiLanguage) == LANG_CHINESE) {
        const auto sublanguage = SUBLANGID(uiLanguage);
        preferred = sublanguage == SUBLANG_CHINESE_SIMPLIFIED || sublanguage == SUBLANG_CHINESE_SINGAPORE ? 2 : 3;
    }
    return preferred;
}

static std::vector<DriverMatch> ScanWithProgress(const fs::path& bundle, DWORD build, const PeText& text,
    bool missingOnly = false)
{
    const auto progress = CreateWindowExW(WS_EX_TOOLWINDOW, L"STATIC", text.scan,
        WS_POPUP | WS_CAPTION | WS_VISIBLE | SS_CENTER | SS_CENTERIMAGE,
        (GetSystemMetrics(SM_CXSCREEN) - 520) / 2, (GetSystemMetrics(SM_CYSCREEN) - 100) / 2,
        520, 100, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    const auto font = WizardFont(text);
    if (progress) {
        SetWindowTextW(progress, L"Network Rescue");
        const auto message = CreateWindowExW(0, L"STATIC", text.scan, WS_CHILD | WS_VISIBLE | SS_CENTER,
            12, 16, 492, 32, progress, nullptr, GetModuleHandleW(nullptr), nullptr);
        UpdateWindow(progress);
        if (message) {
            if (font) SendMessageW(message, WM_SETFONT, reinterpret_cast<WPARAM>(font), TRUE);
            UpdateWindow(message);
        }
    }
    auto matches = ScanDrivers(bundle, build, missingOnly);
    if (progress) DestroyWindow(progress);
    if (font) DeleteObject(font);
    return matches;
}

static int RunPeAction(const fs::path& bundle, const PeText& text, bool setup)
{
    if (setup && IsSetupRunning()) {
        Notice(text, text.setupRunning);
        return 0;
    }

    const auto targets = setup ? std::vector<Target>{} : DiscoverTargets();
    const auto media = setup ? DiscoverSetupMedia() : std::vector<SetupMedia>{};
    std::vector<std::wstring> choices;
    for (const auto& target : targets) choices.push_back(WindowsLabel(target.root, target.build));
    for (const auto& source : media) choices.push_back(WindowsLabel(source.root, source.build));
    if (choices.empty()) {
        Notice(text, setup ? text.noMedia : text.noTarget);
        return 0;
    }
    const auto target = Choose(text, setup ? text.media : text.target, choices);
    if (target < 0) return 0;
    const auto build = setup ? media[target].build : targets[target].build;
    auto matches = ScanWithProgress(bundle, build, text);
    if (matches.empty()) {
        Notice(text, text.noDriver);
        return 0;
    }
    if (setup) {
        matches.erase(std::remove_if(matches.begin(), matches.end(), [](const DriverMatch& match) {
            return !IsStandaloneDriver(match.path);
        }), matches.end());
        if (matches.empty()) {
            Notice(text, text.noStandalone);
            return 0;
        }
    }
    std::vector<std::wstring> labels;
    for (const auto& match : matches) {
        labels.push_back(match.name + L"  " + match.path.filename().wstring() + L"  [" + match.id + L"]");
    }
    const auto driver = Choose(text, text.driver, labels);
    if (driver < 0) return 0;
    const auto& inf = matches[driver].path;
    if (!Confirm(text, setup ? text.confirmSetup : text.confirmRepair, choices[target] + L"  " + inf.wstring())) {
        return 0;
    }
    if (!VerifyNetworkDriver(inf)) {
        Notice(text, text.failed);
        return 0;
    }
    if (setup) {
        if (!IsSetupRunning() && IsStandaloneDriver(inf) && StartSetup(media[target], inf)) return 0;
        Notice(text, text.failed);
        return 0;
    }
    const auto& offline = targets[target];
    if (ReadWindowsBuild(offline.root) != offline.build) {
        Notice(text, text.failed);
        return 0;
    }
    const auto result = RunDism(offline, L"/Add-Driver /Driver:\"" + inf.wstring() + L"\"");
    const bool added = result == ERROR_SUCCESS || result == ERROR_SUCCESS_REBOOT_REQUIRED;
    const bool checked = added && RunDism(offline, L"/Get-Drivers") == ERROR_SUCCESS;
    Notice(text, checked ? text.repairDone : text.failed);
    return checked ? 0 : 6;
}
