#include <commctrl.h>

enum HomeControl {
    HomeTools = 201, HomeLanguage, HomeHelp, HomeHeading, HomeIntro, HomeList, HomeRefresh, HomePrimary,
    HomeSummary, HomeNetworkHeading, HomeDriverHeading, HomeNetworkList
};

struct HomeState {
    const fs::path& bundle;
    bool isPe;
    int language;
    HFONT font = nullptr;
    HFONT headingFont = nullptr;
    HFONT sectionFont = nullptr;
};

static void AddHomeRow(HWND list, const std::wstring& name, const wchar_t* status)
{
    LVITEMW item{};
    item.mask = LVIF_TEXT;
    item.iItem = ListView_GetItemCount(list);
    item.pszText = const_cast<wchar_t*>(name.c_str());
    const auto index = ListView_InsertItem(list, &item);
    if (index >= 0) ListView_SetItemText(list, index, 1, const_cast<wchar_t*>(status));
}

static void FillNetworkDevices(HWND list, const PeText& text)
{
    const GUID network = { 0x4d36e972, 0xe325, 0x11ce, { 0xbf, 0xc1, 0x08, 0x00, 0x2b, 0xe1, 0x03, 0x18 } };
    const auto devices = SetupDiGetClassDevsW(&network, nullptr, nullptr, DIGCF_PRESENT);
    if (devices == INVALID_HANDLE_VALUE) return;
    for (DWORD index = 0;; ++index) {
        SP_DEVINFO_DATA device{};
        device.cbSize = sizeof device;
        if (!SetupDiEnumDeviceInfo(devices, index, &device)) break;
        wchar_t name[256]{};
        if (!SetupDiGetDeviceRegistryPropertyW(devices, &device, SPDRP_FRIENDLYNAME, nullptr,
                reinterpret_cast<PBYTE>(name), sizeof name, nullptr) &&
            !SetupDiGetDeviceRegistryPropertyW(devices, &device, SPDRP_DEVICEDESC, nullptr,
                reinterpret_cast<PBYTE>(name), sizeof name, nullptr)) {
            continue;
        }
        ULONG status = 0;
        ULONG problem = 0;
        const auto state = CM_Get_DevNode_Status(&status, &problem, device.DevInst, 0);
        const auto* label = state != CR_SUCCESS ? L"" : problem == CM_PROB_FAILED_INSTALL ? text.homeMissing :
            problem == 0 ? text.homeReady : L"";
        AddHomeRow(list, name, label);
    }
    SetupDiDestroyDeviceInfoList(devices);
}

static void FillHomeList(HWND window, const HomeState& state)
{
    const auto& text = peText[state.language];
    const auto list = GetDlgItem(window, HomeList);
    ListView_DeleteAllItems(list);
    if (state.isPe) {
        const auto adapters = GetDlgItem(window, HomeNetworkList);
        ListView_DeleteAllItems(adapters);
        FillNetworkDevices(adapters, text);
        if (ListView_GetItemCount(adapters) == 0) AddHomeRow(adapters, text.homeNoNetwork, L"");

        const auto targets = DiscoverTargets();
        for (const auto& target : targets) AddHomeRow(list, WindowsLabel(target.root, target.build), text.homeFound);
        SetDlgItemTextW(window, HomeSummary, targets.empty() ? text.noTarget : L"");
    } else {
        FillNetworkDevices(list, text);
        SetDlgItemTextW(window, HomeSummary, ReadDeviceHardwareIds(true).empty() ? text.cliNoMissing : L"");
    }
}

static void LocalizeList(HWND list, const wchar_t* first, const wchar_t* second)
{
    if (!list) return;
    LVCOLUMNW column{};
    column.mask = LVCF_TEXT;
    column.pszText = const_cast<wchar_t*>(first);
    ListView_SetColumn(list, 0, &column);
    column.pszText = const_cast<wchar_t*>(second);
    ListView_SetColumn(list, 1, &column);
}

static void SetHomeCombo(HWND window, int id, const std::vector<const wchar_t*>& items, int selected)
{
    const auto combo = GetDlgItem(window, id);
    SendMessageW(combo, CB_RESETCONTENT, 0, 0);
    for (const auto* item : items) SendMessageW(combo, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(item));
    SendMessageW(combo, CB_SETCURSEL, selected, 0);
}

static void LocalizeHome(HWND window, HomeState& state)
{
    const auto& text = peText[state.language];
    if (!state.isPe) SetWindowTextW(window, text.homeTitle);
    SetDlgItemTextW(window, HomeHeading, text.homeTitle);
    SetDlgItemTextW(window, HomeIntro, state.isPe ? text.homePe : text.homeWindows);
    SetDlgItemTextW(window, HomeNetworkHeading, text.homeNetwork);
    SetDlgItemTextW(window, HomeDriverHeading, text.homePreparation);
    SetDlgItemTextW(window, HomeRefresh, text.homeScan);
    SetDlgItemTextW(window, HomePrimary, state.isPe ? text.setup : text.homeInstall);
    SetDlgItemTextW(window, IDCANCEL, text.close);
    SetHomeCombo(window, HomeTools, { text.tools, state.isPe ? text.repair : text.homeAdvanced }, 0);
    SetHomeCombo(window, HomeLanguage, { L"English", L"日本語", L"简体中文", L"繁體中文" }, state.language);
    SetHomeCombo(window, HomeHelp, { text.homeHelp, text.homeGuide, text.homeAbout }, 0);
    const auto font = WizardFont(text);
    LOGFONTW heading{};
    const bool haveHeadingFont = font && GetObjectW(font, sizeof heading, &heading) == sizeof heading;
    heading.lfWeight = FW_BOLD;
    const auto section = haveHeadingFont ? CreateFontIndirectW(&heading) : nullptr;
    heading.lfHeight = MulDiv(heading.lfHeight, 3, 2);
    const auto large = haveHeadingFont ? CreateFontIndirectW(&heading) : nullptr;
    for (const auto id : { HomeTools, HomeLanguage, HomeHelp, HomeHeading, HomeIntro, HomeList,
            HomeNetworkHeading, HomeDriverHeading, HomeNetworkList, HomeRefresh, HomePrimary,
            HomeSummary, static_cast<HomeControl>(IDCANCEL) }) {
        auto selected = font;
        if (id == HomeHeading && large) selected = large;
        if ((id == HomeNetworkHeading || id == HomeDriverHeading) && section) selected = section;
        if (selected) SendDlgItemMessageW(window, id, WM_SETFONT, reinterpret_cast<WPARAM>(selected), TRUE);
    }
    if (state.font) DeleteObject(state.font);
    if (state.headingFont) DeleteObject(state.headingFont);
    if (state.sectionFont) DeleteObject(state.sectionFont);
    state.font = font;
    state.headingFont = large;
    state.sectionFont = section;
    LocalizeList(GetDlgItem(window, HomeList), state.isPe ? text.homeOffline : text.homeDevice, text.homeStatus);
    LocalizeList(GetDlgItem(window, HomeNetworkList), text.homeDevice, text.homeStatus);
    FillHomeList(window, state);
}

static bool OpenFullWindowsTools(const fs::path& bundle, int language)
{
    const auto program = bundle / L"AkikazuHardwareCheck.exe";
    constexpr const wchar_t* languages[] = { L"en-US", L"ja-JP", L"zh-CN", L"zh-TW" };
    auto command = L"\"" + program.wstring() + L"\" --portable-rescue " + languages[language];
    STARTUPINFOW startup{};
    startup.cb = sizeof startup;
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(program.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr,
            bundle.c_str(), &startup, &process)) return false;
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return true;
}

static void RepairCurrentFromHome(const HomeState& state)
{
    const auto& text = peText[state.language];
    const auto build = CurrentWindowsBuild();
    if (build < 10240) {
        Notice(text, text.failed);
        return;
    }
    if (ReadDeviceHardwareIds(true).empty()) {
        Notice(text, text.cliNoMissing);
        return;
    }
    const auto matches = ScanWithProgress(state.bundle, build, text, true);
    if (matches.empty()) {
        Notice(text, text.noDriver);
        return;
    }
    std::vector<std::wstring> choices;
    for (const auto& match : matches) choices.push_back(match.name + L"  [" + match.id + L"]");
    const auto selected = Choose(text, text.driver, choices);
    if (selected < 0) return;
    const auto& match = matches[selected];
    if (!Confirm(text, text.cliConfirmCurrent, match.path.wstring())) return;
    const auto result = InstallCurrentDriver(state.bundle, match);
    const wchar_t* messages[] = { text.cliBound, text.cliRestart, text.cliUnconfirmed };
    Notice(text, result < ARRAYSIZE(messages) ? messages[result] : text.failed);
}

static HWND CreateHomeList(HWND window, int id, RECT bounds, const wchar_t* first, const wchar_t* second)
{
    const auto list = ChoiceControl(window, WC_LISTVIEWW, L"", WS_TABSTOP | WS_BORDER |
        LVS_REPORT | LVS_SINGLESEL | LVS_SHOWSELALWAYS | LVS_NOSORTHEADER, id, bounds);
    if (!list) return nullptr;
    ListView_SetExtendedListViewStyle(list, LVS_EX_FULLROWSELECT | LVS_EX_DOUBLEBUFFER);
    const auto span = bounds.right - bounds.left;
    RECT width{ 0, 0, MulDiv(span, 68, 100), 0 };
    MapDialogRect(window, &width);
    LVCOLUMNW column{};
    column.mask = LVCF_WIDTH | LVCF_TEXT | LVCF_FMT;
    column.fmt = LVCFMT_LEFT;
    column.cx = width.right;
    column.pszText = const_cast<wchar_t*>(first);
    ListView_InsertColumn(list, 0, &column);
    width.right = MulDiv(span, 28, 100);
    MapDialogRect(window, &width);
    column.cx = width.right;
    column.pszText = const_cast<wchar_t*>(second);
    ListView_InsertColumn(list, 1, &column);
    return list;
}

static INT_PTR CALLBACK SharedHomeDialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    if (message == WM_INITDIALOG) {
        auto& state = *reinterpret_cast<HomeState*>(lparam);
        SetWindowLongPtrW(window, GWLP_USERDATA, lparam);
        SetWindowTextW(window, L"Network Rescue");
        const auto icon = LoadIconW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(1));
        SendMessageW(window, WM_SETICON, ICON_SMALL, reinterpret_cast<LPARAM>(icon));
        SendMessageW(window, WM_SETICON, ICON_BIG, reinterpret_cast<LPARAM>(icon));

        constexpr auto dropdown = WS_TABSTOP | WS_VSCROLL | CBS_DROPDOWNLIST | CBS_HASSTRINGS;
        const auto tools = ChoiceControl(window, L"COMBOBOX", L"", dropdown, HomeTools, { 10, 8, 94, 75 });
        SendMessageW(tools, CB_SETDROPPEDWIDTH, 330, 0);
        ChoiceControl(window, L"COMBOBOX", L"", dropdown, HomeLanguage, { 99, 8, 190, 88 });
        ChoiceControl(window, L"COMBOBOX", L"", dropdown, HomeHelp, { 195, 8, 268, 75 });
        const int right = state.isPe ? 404 : 362;
        ChoiceControl(window, L"STATIC", L"", SS_ETCHEDHORZ, -1, { 10, 28, right, 30 });
        ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeHeading, { 10, 37, right, 57 });
        ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeIntro, { 10, 59, right, 75 });

        const auto& text = peText[state.language];
        HWND list = nullptr;
        HWND primary = nullptr;
        if (state.isPe) {
            ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeNetworkHeading, { 10, 78, right, 91 });
            if (!CreateHomeList(window, HomeNetworkList, { 10, 93, right, 144 }, text.homeDevice, text.homeStatus)) {
                EndDialog(window, 1);
                return TRUE;
            }
            ChoiceControl(window, L"STATIC", L"", SS_ETCHEDHORZ, -1, { 10, 152, right, 154 });
            ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeDriverHeading, { 10, 160, right, 174 });
            primary = ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP | BS_DEFPUSHBUTTON,
                HomePrimary, { 10, 178, 220, 200 });
            ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP, HomeRefresh, { 226, 178, 294, 200 });
            list = CreateHomeList(window, HomeList, { 10, 206, right, 263 }, text.homeOffline, text.homeStatus);
            ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeSummary, { 10, 267, 324, 288 });
            ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP, IDCANCEL, { 334, 270, right, 291 });
        } else {
            list = CreateHomeList(window, HomeList, { 10, 83, right, 166 }, text.homeDevice, text.homeStatus);
            ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeSummary, { 10, 170, right, 189 });
            ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP, HomeRefresh, { 10, 195, 76, 216 });
            primary = ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP | BS_DEFPUSHBUTTON,
                HomePrimary, { 81, 195, 287, 216 });
            ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP, IDCANCEL, { 292, 195, right, 216 });
        }
        if (!list || !primary) {
            EndDialog(window, 1);
            return TRUE;
        }
        LocalizeHome(window, state);
        SendMessageW(window, DM_SETDEFID, HomePrimary, 0);
        SetFocus(primary);
        return FALSE;
    }
    if (message == WM_CLOSE || (message == WM_COMMAND && LOWORD(wparam) == IDCANCEL)) {
        EndDialog(window, 0);
        return TRUE;
    }
    constexpr UINT selectedMenu = WM_APP + 1;
    if (message != WM_COMMAND && message != selectedMenu) return FALSE;
    auto* state = reinterpret_cast<HomeState*>(GetWindowLongPtrW(window, GWLP_USERDATA));
    if (!state) return FALSE;
    const auto control = LOWORD(wparam);
    if (message == WM_COMMAND && (control == HomeLanguage || control == HomeTools || control == HomeHelp) &&
        HIWORD(wparam) == CBN_SELENDOK) {
        const auto selection = SendDlgItemMessageW(window, control, CB_GETCURSEL, 0, 0);
        if (selection != CB_ERR) PostMessageW(window, selectedMenu, control, selection);
        return TRUE;
    }
    if (control == HomeLanguage && message == selectedMenu) {
        if (lparam >= 0 && lparam < ARRAYSIZE(peText)) {
            state->language = static_cast<int>(lparam);
            LocalizeHome(window, *state);
        }
        return TRUE;
    }
    if (control == HomeRefresh) {
        FillHomeList(window, *state);
        return TRUE;
    }
    const auto& text = peText[state->language];
    if (control == HomePrimary || ((control == HomeTools || control == HomeHelp) && message == selectedMenu)) {
        const auto selection = lparam;
        if (control != HomePrimary) {
            SendDlgItemMessageW(window, control, CB_SETCURSEL, 0, 0);
            if (selection <= 0) return TRUE;
        }
        wizardOwner = window;
        if (control == HomePrimary) {
            if (state->isPe) RunPeAction(state->bundle, text, true);
            else RepairCurrentFromHome(*state);
        } else if (control == HomeTools) {
            if (state->isPe) RunPeAction(state->bundle, text, false);
            else if (!OpenFullWindowsTools(state->bundle, state->language)) Notice(text, text.failed);
        } else if (selection == 1) {
            Notice(text, state->isPe ? text.homePeGuide : text.homeWindowsGuide);
        } else {
            Notice(text, (std::wstring(text.homeTitle) + L"  " + peVersion + L"\nhttps://github.com/akikazu-pc/hardware-check").c_str());
        }
        wizardOwner = nullptr;
        FillHomeList(window, *state);
        return TRUE;
    }
    return FALSE;
}

static int RunSharedHome(const fs::path& bundle, bool isPe)
{
    const INITCOMMONCONTROLSEX controls{ sizeof controls, ICC_LISTVIEW_CLASSES };
    if (!InitCommonControlsEx(&controls)) return 1;
    const auto font = bundle / L"pe-fonts/NotoSansCJK-Regular.ttc";
    AddFontResourceExW(font.c_str(), FR_PRIVATE, nullptr);
    struct alignas(DWORD) EmptyDialog {
        DLGTEMPLATE base;
        WORD menu;
        WORD windowClass;
        WORD title;
    };
    const EmptyDialog layout{
        { WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | DS_CENTER, 0, 0, 0, 0, static_cast<short>(isPe ? 414 : 372), static_cast<short>(isPe ? 301 : 226) },
        0, 0, 0
    };
    HomeState state{ bundle, isPe, PreferredLanguage() };
    const auto result = DialogBoxIndirectParamW(GetModuleHandleW(nullptr), &layout.base, nullptr,
        SharedHomeDialog, reinterpret_cast<LPARAM>(&state));
    if (state.font) DeleteObject(state.font);
    if (state.headingFont) DeleteObject(state.headingFont);
    if (state.sectionFont) DeleteObject(state.sectionFont);
    return result < 0 ? 1 : static_cast<int>(result);
}
