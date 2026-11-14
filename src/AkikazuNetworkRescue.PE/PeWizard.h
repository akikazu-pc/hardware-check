#include <windows.h>
#include <tlhelp32.h>
#include <cstring>
#include <fstream>
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
        }
        if (list || choice.safeDefault) {
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

struct SetupImage {
    unsigned long index;
    std::wstring name;
    std::wstring locale;
};

struct SetupMedia {
    fs::path root;
    fs::path image;
    DWORD build;
    std::vector<SetupImage> editions;
};

static std::wstring ImageValue(std::wstring_view entry, const std::wstring& name)
{
    const auto begin = entry.find(L"<" + name + L">");
    if (begin == std::wstring_view::npos) return {};
    const auto value = begin + name.size() + 2;
    const auto end = entry.find(L"</" + name + L">", value);
    return end == std::wstring_view::npos ? std::wstring{} : std::wstring(entry.substr(value, end - value));
}

template<class Function> static Function WimApi(HMODULE library, const char* name)
{
    const auto address = GetProcAddress(library, name);
    Function result{};
    static_assert(sizeof result == sizeof address);
    std::memcpy(&result, &address, sizeof result);
    return result;
}

static DWORD ReadImageBuild(const fs::path& path, std::vector<SetupImage>& editions)
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
                    const auto indexTag = entry.find(L" INDEX=\"");
                    if (indexTag == std::wstring_view::npos) {
                        result = 0;
                        break;
                    }
                    const auto indexText = std::wstring(entry.substr(indexTag + 8));
                    wchar_t* indexEnd = nullptr;
                    const auto index = wcstoul(indexText.c_str(), &indexEnd, 10);
                    if (!index || *indexEnd != L'"') {
                        result = 0;
                        break;
                    }
                    auto name = ImageValue(entry, L"DISPLAYNAME");
                    if (name.empty()) name = ImageValue(entry, L"NAME");
                    auto locale = ImageValue(entry, L"DEFAULT");
                    if (!IsValidLocaleName(locale.c_str()) || locale.empty()) locale.clear();
                    editions.push_back({ index, std::move(name), std::move(locale) });
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
                std::vector<SetupImage> editions;
                const auto build = ReadImageBuild(image, editions);
                if (build) {
                    result.push_back({ root, image, build, std::move(editions) });
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

static bool CanIsolateSetupInf(const fs::path& path, const std::vector<fs::path>& otherInfs)
{
    const auto inf = SetupOpenInfFileW(path.c_str(), nullptr, INF_STYLE_WIN4, nullptr);
    if (inf == INVALID_HANDLE_VALUE) return false;
    bool isolated = true;
    for (UINT index = 0; isolated; ++index) {
        wchar_t section[1024]{};
        if (!SetupEnumInfSectionsW(inf, index, section, ARRAYSIZE(section), nullptr)) {
            isolated = GetLastError() == ERROR_NO_MORE_ITEMS;
            break;
        }
        INFCONTEXT line{};
        if (SetupFindFirstLineW(inf, section, L"CopyINF", &line)) {
            isolated = false;
            break;
        }
        if (!SetupFindFirstLineW(inf, section, L"Include", &line)) continue;
        do {
            for (DWORD field = 1; field <= SetupGetFieldCount(&line); ++field) {
                const auto include = fs::path(InfField(line, field)).filename();
                if (include.empty() || std::any_of(otherInfs.begin(), otherInfs.end(), [&include](const auto& other) {
                    return _wcsicmp(include.c_str(), other.filename().c_str()) == 0;
                })) {
                    isolated = false;
                    break;
                }
            }
        } while (isolated && SetupFindNextMatchLineW(&line, L"Include", &line));
    }
    SetupCloseInfFile(inf);
    return isolated;
}

static fs::path PrepareSetupDriver(const fs::path& inf, const fs::path& workspace)
{
    const auto source = inf.parent_path();
    std::vector<fs::path> files;
    std::vector<fs::path> otherInfs;
    bool foundSelected = false;
    std::error_code error;
    for (fs::recursive_directory_iterator it(source, error), end; !error && it != end; it.increment(error)) {
        const auto attributes = GetFileAttributesW(it->path().c_str());
        if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT)) return {};
        if (attributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        const auto& path = it->path();
        if (_wcsicmp(path.extension().c_str(), L".inf") == 0) {
            if (_wcsicmp(path.c_str(), inf.c_str()) != 0) {
                otherInfs.push_back(path);
                continue;
            }
            foundSelected = true;
        }
        files.push_back(path);
    }
    if (error || !foundSelected) return {};
    if (otherInfs.empty()) return source;
    if (!CanIsolateSetupInf(inf, otherInfs)) return {};

    const auto stage = workspace / L"driver";
    for (const auto& path : files) {
        const auto destination = stage / path.lexically_relative(source);
        fs::create_directories(destination.parent_path(), error);
        if (error || !fs::copy_file(path, destination, fs::copy_options::none, error)) {
            return {};
        }
    }
    return VerifyNetworkDriver(stage / inf.filename()) ? stage : fs::path{};
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

static bool WriteSetupAnswer(const fs::path& answer, const std::vector<fs::path>& drivers)
{
    std::wstring paths;
    for (size_t index = 0; index < drivers.size(); ++index) {
        paths += L"<PathAndCredentials wcm:action=\"add\" wcm:keyValue=\"" + std::to_wstring(index + 1) +
            L"\"><Path>" + XmlEscape(drivers[index].wstring()) + L"</Path></PathAndCredentials>";
    }
    const auto xml = std::wstring(
        L"\uFEFF<?xml version=\"1.0\" encoding=\"utf-16\"?>"
        L"<unattend xmlns=\"urn:schemas-microsoft-com:unattend\" xmlns:wcm=\"http://schemas.microsoft.com/WMIConfig/2002/State\">"
        L"<settings pass=\"offlineServicing\">"
        L"<component name=\"Microsoft-Windows-PnpCustomizationsNonWinPE\" processorArchitecture=\"amd64\" "
        L"publicKeyToken=\"31bf3856ad364e35\" language=\"neutral\" versionScope=\"nonSxS\">"
        L"<DriverPaths>") + paths + L"</DriverPaths></component></settings></unattend>";
    const auto file = CreateFileW(answer.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return false;
    }
    const auto bytes = static_cast<DWORD>(xml.size() * sizeof(wchar_t));
    DWORD written = 0;
    const bool saved = WriteFile(file, xml.data(), bytes, &written, nullptr) && written == bytes;
    CloseHandle(file);
    return saved;
}

enum class SetupStart { Started, DriverPreparationFailed, LaunchFailed };

static SetupStart StartSetup(const SetupMedia& media, const std::vector<fs::path>& infs)
{
    if (IsSetupRunning()) return SetupStart::LaunchFailed;
    wchar_t temp[MAX_PATH]{};
    const auto length = GetTempPathW(MAX_PATH, temp);
    if (!length || length >= MAX_PATH) {
        return SetupStart::LaunchFailed;
    }
    const auto workspace = fs::path(temp) / (L"NetworkRescue-" + std::to_wstring(GetCurrentProcessId()) +
        L"-" + std::to_wstring(GetTickCount64()));
    std::error_code error;
    if (!fs::create_directory(workspace, error)) return SetupStart::LaunchFailed;
    // No INFs means the user chose to continue without adding a driver.
    std::vector<fs::path> drivers;
    for (size_t index = 0; index < infs.size(); ++index) {
        const auto stage = workspace / (L"driver-" + std::to_wstring(index));
        std::error_code stageError;
        fs::create_directory(stage, stageError);
        if (stageError) {
            fs::remove_all(workspace, error);
            return SetupStart::LaunchFailed;
        }
        const auto driver = PrepareSetupDriver(infs[index], stage);
        if (driver.empty()) {
            fs::remove_all(workspace, error);
            return SetupStart::DriverPreparationFailed;
        }
        drivers.push_back(driver);
    }
    const auto setup = media.root / L"setup.exe";
    const auto hostBuild = ReadWindowsFileBuild(media.root / L"sources/setuphost.exe");
    const auto setupBuild = hostBuild ? hostBuild : ReadWindowsFileBuild(setup);
    auto command = L"\"" + setup.wstring() + L"\"";
    if (drivers.empty()) {
        // Launch Windows Setup without a driver answer.
    } else if (setupBuild >= 26100) {
        // Setup 24H2 takes one folder; put the isolated drivers under it when they differ.
        auto root = drivers[0];
        const bool sameRoot = std::all_of(drivers.begin(), drivers.end(), [&](const fs::path& driver) {
            return driver == drivers[0];
        });
        if (!sameRoot) {
            root = workspace / L"drivers";
            std::error_code copyError;
            fs::create_directory(root, copyError);
            for (size_t index = 0; index < drivers.size() && !copyError; ++index) {
                fs::copy(drivers[index], root / std::to_wstring(index), fs::copy_options::recursive, copyError);
            }
            if (copyError) {
                fs::remove_all(workspace, error);
                return SetupStart::LaunchFailed;
            }
        }
        command += L" /InstallDrivers \"" + root.wstring() + L"\"";
    } else {
        const auto answer = workspace / L"unattend.xml";
        if (!WriteSetupAnswer(answer, drivers)) {
            fs::remove_all(workspace, error);
            return SetupStart::LaunchFailed;
        }
        command += L" /unattend:\"" + answer.wstring() + L"\"";
    }
    // Record the staged drivers and the Setup command line for field diagnosis.
    wchar_t logPath[MAX_PATH]{};
    const auto logLength = GetTempPathW(MAX_PATH, logPath);
    if (logLength && logLength < MAX_PATH) {
        std::ofstream log(fs::path(logPath) / L"NetworkRescue-setup.log", std::ios::binary | std::ios::trunc);
        for (const auto& driver : drivers) {
            const auto driverLine = L"driver " + driver.wstring() + L"\r\n";
            log.write(reinterpret_cast<const char*>(driverLine.data()),
                static_cast<std::streamsize>(driverLine.size() * sizeof(wchar_t)));
        }
        const auto commandLine = L"command " + command + L"\r\n";
        log.write(reinterpret_cast<const char*>(commandLine.data()),
            static_cast<std::streamsize>(commandLine.size() * sizeof(wchar_t)));
    }
    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(setup.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr,
            media.root.c_str(), &startup, &process)) {
        fs::remove_all(workspace, error);
        return SetupStart::LaunchFailed;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return SetupStart::Started;
}

#include "PeUnattended.h"

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
    std::optional<DeploymentSelection> deployment;
    if (setup && SupportsUnattended(media[target])) {
        const auto mode = Choose(text, text.deployMode, { text.deploySetup, text.deployUnattended });
        if (mode < 0) return 0;
        if (mode == 1) {
            deployment = ChooseDeployment(media[target], text,
                [&](const wchar_t* prompt, const std::vector<std::wstring>& entries) { return Choose(text, prompt, entries); },
                [&](const wchar_t* message) { Notice(text, message); });
            if (!deployment) return 0;
        }
    }
    const auto build = setup ? media[target].build : targets[target].build;
    auto matches = ScanWithProgress(bundle, build, text);
    std::vector<fs::path> selected;
    if (matches.empty()) {
        if (!setup && !deployment) {
            Notice(text, text.noDriver);
            return 0;
        }
        // Setup and unattended deployment can continue; the image may carry its own network driver.
        if (!Confirm(text, text.continueWithoutDriver, choices[target])) return 0;
    } else {
        std::vector<std::wstring> labels;
        for (const auto& match : matches) {
            labels.push_back(match.name + L"  " + match.path.filename().wstring() + L"  [" + match.id + L"]");
        }
        // Multiple missing NICs can need different INFs; offer one action that installs all of them.
        const bool installAllOffered = CanInstallAll(matches);
        if (installAllOffered) {
            labels.push_back(std::wstring(text.installAll) + L" (" + std::to_wstring(matches.size()) + L")");
        }
        const auto driver = deployment && labels.size() == 1 ? 0 : Choose(text, text.driver, labels);
        if (driver < 0) return 0;
        if (installAllOffered && driver == static_cast<int>(matches.size())) {
            for (const auto& match : matches) selected.push_back(match.path);
        } else {
            selected.push_back(matches[driver].path);
        }
    }
    std::wstring selectedNames;
    for (const auto& path : selected) {
        if (!selectedNames.empty()) selectedNames += L"\n";
        selectedNames += path.filename().wstring();
    }
    if (deployment) {
        const auto confirmation = std::wstring(text.deployConfirm) + L"\n\n" +
            DeploymentDetails(media[target], *deployment, selected, text);
        if (Choose(text, confirmation.c_str(), {}, 0, text.confirm, true) < 0) return 0;
        return DeployWithUi(media[target], *deployment, selected, text);
    }
    if (!selected.empty() &&
        !Confirm(text, setup ? text.confirmSetup : text.confirmRepair, choices[target] + L"  " + selectedNames)) {
        return 0;
    }
    for (const auto& path : selected) {
        if (!VerifyNetworkDriver(path)) {
            Notice(text, text.failed);
            return 0;
        }
    }
    if (setup) {
        const auto result = StartSetup(media[target], selected);
        if (result == SetupStart::Started) return 0;
        Notice(text, result == SetupStart::DriverPreparationFailed ? text.setupDriverPreparationFailed : text.failed);
        return 6;
    }
    const auto& offline = targets[target];
    if (ReadWindowsBuild(offline.root) != offline.build) {
        Notice(text, text.failed);
        return 0;
    }
    bool added = true;
    for (const auto& path : selected) {
        const auto result = RunDism(offline, L"/Add-Driver /Driver:\"" + path.wstring() + L"\"");
        if (result != ERROR_SUCCESS && result != ERROR_SUCCESS_REBOOT_REQUIRED) {
            added = false;
            break;
        }
    }
    const bool checked = added && RunDism(offline, L"/Get-Drivers") == ERROR_SUCCESS;
    Notice(text, checked ? text.repairDone : text.failed);
    return checked ? 0 : 6;
}
