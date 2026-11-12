#include <commctrl.h>

enum HomeControl {
    HomeHeading = 201, HomeIntro, HomeList, HomeRefresh, HomePrimary,
    HomeSummary, HomeNetworkHeading, HomeDriverHeading, HomeNetworkList,
    HomeRepair, HomeGuide, HomeAbout, HomeTools, HomeLanguage, HomeHelp, HomeToolbar
};

struct HomeState {
    const fs::path& bundle;
    bool isPe;
    int language;
    HFONT font = nullptr;
    HFONT headingFont = nullptr;
    HFONT sectionFont = nullptr;
};

static HICON LoadHomeIcon(int width, int height)
{
    return static_cast<HICON>(LoadImageW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(1),
        IMAGE_ICON, width, height, LR_SHARED));
}

static void AddHomeRow(HWND list, const std::wstring& name, const wchar_t* status)
{
    LVITEMW item{};
    item.mask = LVIF_TEXT;
    item.iItem = ListView_GetItemCount(list);
    item.pszText = const_cast<wchar_t*>(name.c_str());
    const auto index = ListView_InsertItem(list, &item);
    if (index >= 0) ListView_SetItemText(list, index, 1, const_cast<wchar_t*>(status));
}

static bool IsPciNetworkDevice(HDEVINFO devices, SP_DEVINFO_DATA& device)
{
    for (const auto property : { SPDRP_COMPATIBLEIDS, SPDRP_HARDWAREID }) {
        const auto values = ReadDeviceIdProperty(devices, device, property);
        if (values.empty()) continue;
        for (const auto* id = values.data(); *id; id += wcslen(id) + 1) {
            if (_wcsnicmp(id, L"PCI\\", 4) != 0) continue;
            for (const auto* part = id + 4; part; ) {
                if (_wcsnicmp(part, L"CC_0200", 7) == 0 || _wcsnicmp(part, L"CC_0280", 7) == 0) return true;
                const auto next = wcschr(part, L'&');
                part = next ? next + 1 : nullptr;
            }
        }
    }
    return false;
}

static void FillNetworkDevices(HWND list, const PeText& text)
{
    const GUID network = { 0x4d36e972, 0xe325, 0x11ce, { 0xbf, 0xc1, 0x08, 0x00, 0x2b, 0xe1, 0x03, 0x18 } };
    const auto devices = SetupDiGetClassDevsW(nullptr, nullptr, nullptr, DIGCF_ALLCLASSES | DIGCF_PRESENT);
    if (devices == INVALID_HANDLE_VALUE) return;
    for (DWORD index = 0;; ++index) {
        SP_DEVINFO_DATA device{};
        device.cbSize = sizeof device;
        if (!SetupDiEnumDeviceInfo(devices, index, &device)) break;
        if (!IsEqualGUID(device.ClassGuid, network) && !IsPciNetworkDevice(devices, device)) continue;
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
        std::wstring label = text.homeUnknown;
        if (state == CR_SUCCESS) {
            if (problem == CM_PROB_FAILED_INSTALL) label = text.homeMissing;
            else if (problem != 0) label = std::wstring(text.homeProblem) + L" (" + std::to_wstring(problem) + L")";
            else if ((status & DN_STARTED) && (status & DN_DRIVER_LOADED)) label = text.homeReady;
            else label = text.homeNotStarted;
        }
        AddHomeRow(list, name, label.c_str());
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

static LRESULT CALLBACK HomeToolbarKeys(HWND toolbar, UINT message, WPARAM wparam, LPARAM lparam,
    UINT_PTR, DWORD_PTR)
{
    if (message == WM_GETDLGCODE) {
        return DLGC_WANTARROWS | (wparam == VK_RETURN ? DLGC_WANTMESSAGE : 0);
    }
    if (message == WM_SETFOCUS && SendMessageW(toolbar, TB_GETHOTITEM, 0, 0) < 0) {
        SendMessageW(toolbar, TB_SETHOTITEM, 0, 0);
    }
    if (message == WM_KEYDOWN) {
        const auto index = std::max<LRESULT>(0, SendMessageW(toolbar, TB_GETHOTITEM, 0, 0));
        if (wparam == VK_LEFT || wparam == VK_RIGHT) {
            const auto count = SendMessageW(toolbar, TB_BUTTONCOUNT, 0, 0);
            if (count > 0) SendMessageW(toolbar, TB_SETHOTITEM, (index + count + (wparam == VK_LEFT ? -1 : 1)) % count, 0);
            return 0;
        }
        if (wparam == VK_RETURN || wparam == VK_SPACE || wparam == VK_DOWN || wparam == VK_F4) {
            TBBUTTON button{};
            if (SendMessageW(toolbar, TB_GETBUTTON, index, reinterpret_cast<LPARAM>(&button))) {
                PostMessageW(GetParent(toolbar), WM_COMMAND, button.idCommand, reinterpret_cast<LPARAM>(toolbar));
            }
            return 0;
        }
    }
    return DefSubclassProc(toolbar, message, wparam, lparam);
}

static void LocalizeHomeToolbar(HWND toolbar, const PeText& text, HFONT font)
{
    std::wstring help = text.homeHelp;
    if (const auto suffix = help.find(L"(&"); suffix != std::wstring::npos) help.resize(suffix);
    else if (!help.empty() && help.front() == L'&') help.erase(0, 1);

    const auto hot = SendMessageW(toolbar, TB_GETHOTITEM, 0, 0);
    while (SendMessageW(toolbar, TB_BUTTONCOUNT, 0, 0) > 0) {
        if (!SendMessageW(toolbar, TB_DELETEBUTTON, 0, 0)) break;
    }
    SendMessageW(toolbar, WM_SETFONT, reinterpret_cast<WPARAM>(font), FALSE);
    const TBBUTTON buttons[] = {
        { I_IMAGENONE, HomeTools, TBSTATE_ENABLED, BTNS_AUTOSIZE | BTNS_WHOLEDROPDOWN, {}, 0, reinterpret_cast<INT_PTR>(text.tools) },
        { I_IMAGENONE, HomeLanguage, TBSTATE_ENABLED, BTNS_AUTOSIZE | BTNS_WHOLEDROPDOWN, {}, 0, reinterpret_cast<INT_PTR>(text.language) },
        { I_IMAGENONE, HomeHelp, TBSTATE_ENABLED, BTNS_AUTOSIZE | BTNS_WHOLEDROPDOWN, {}, 0, reinterpret_cast<INT_PTR>(help.c_str()) }
    };
    SendMessageW(toolbar, TB_ADDBUTTONSW, ARRAYSIZE(buttons), reinterpret_cast<LPARAM>(buttons));
    SendMessageW(toolbar, TB_AUTOSIZE, 0, 0);
    if (hot >= 0) SendMessageW(toolbar, TB_SETHOTITEM, hot, 0);
    InvalidateRect(toolbar, nullptr, TRUE);
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
    const auto font = WizardFont(text);
    LocalizeHomeToolbar(GetDlgItem(window, HomeToolbar), text, font);
    LOGFONTW heading{};
    const bool haveHeadingFont = font && GetObjectW(font, sizeof heading, &heading) == sizeof heading;
    heading.lfWeight = FW_BOLD;
    const auto section = haveHeadingFont ? CreateFontIndirectW(&heading) : nullptr;
    heading.lfHeight = MulDiv(heading.lfHeight, 3, 2);
    const auto large = haveHeadingFont ? CreateFontIndirectW(&heading) : nullptr;
    for (const auto id : { HomeHeading, HomeIntro, HomeList,
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
        const auto smallIcon = LoadHomeIcon(GetSystemMetrics(SM_CXSMICON), GetSystemMetrics(SM_CYSMICON));
        const auto largeIcon = LoadHomeIcon(GetSystemMetrics(SM_CXICON), GetSystemMetrics(SM_CYICON));
        SendMessageW(window, WM_SETICON, ICON_SMALL, reinterpret_cast<LPARAM>(smallIcon));
        SendMessageW(window, WM_SETICON, ICON_BIG, reinterpret_cast<LPARAM>(largeIcon));

        const int right = state.isPe ? 404 : 362;
        const auto toolbar = ChoiceControl(window, TOOLBARCLASSNAMEW, L"",
            WS_TABSTOP | TBSTYLE_FLAT | TBSTYLE_LIST | CCS_NOPARENTALIGN | CCS_NOMOVEY | CCS_NODIVIDER,
            HomeToolbar, { 10, 5, right, 25 });
        if (!toolbar || !SetWindowSubclass(toolbar, HomeToolbarKeys, 1, 0)) {
            EndDialog(window, 1);
            return TRUE;
        }
        SendMessageW(toolbar, TB_BUTTONSTRUCTSIZE, sizeof(TBBUTTON), 0);
        ChoiceControl(window, L"STATIC", L"", SS_ETCHEDHORZ, -1, { 10, 26, right, 28 });
        ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeHeading, { 10, 36, right, 56 });
        ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeIntro, { 10, 57, right, 74 });

        const auto& text = peText[state.language];
        HWND list = nullptr;
        HWND primary = nullptr;
        if (state.isPe) {
            ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeNetworkHeading, { 10, 77, right, 91 });
            if (!CreateHomeList(window, HomeNetworkList, { 10, 93, right, 156 }, text.homeDevice, text.homeStatus)) {
                EndDialog(window, 1);
                return TRUE;
            }
            ChoiceControl(window, L"BUTTON", L"", BS_GROUPBOX, HomeDriverHeading, { 10, 163, right, 279 });
            primary = ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP | BS_DEFPUSHBUTTON,
                HomePrimary, { 19, 179, 229, 201 });
            list = CreateHomeList(window, HomeList, { 19, 207, right - 9, 254 }, text.homeOffline, text.homeStatus);
            ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeSummary, { 19, 258, right - 9, 274 });
            ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP, IDCANCEL, { 334, 285, right, 306 });
        } else {
            list = CreateHomeList(window, HomeList, { 10, 82, right, 165 }, text.homeDevice, text.homeStatus);
            ChoiceControl(window, L"STATIC", L"", SS_NOPREFIX, HomeSummary, { 10, 169, right, 188 });
            ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP, HomeRefresh, { 10, 194, 76, 215 });
            primary = ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP | BS_DEFPUSHBUTTON,
                HomePrimary, { 81, 194, 287, 215 });
            ChoiceControl(window, L"BUTTON", L"", WS_TABSTOP, IDCANCEL, { 292, 194, right, 215 });
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
    if (message == WM_NOTIFY) {
        const auto* notification = reinterpret_cast<const NMTOOLBARW*>(lparam);
        if (notification->hdr.idFrom == HomeToolbar && notification->hdr.code == TBN_DROPDOWN) {
            PostMessageW(window, WM_COMMAND, notification->iItem, reinterpret_cast<LPARAM>(notification->hdr.hwndFrom));
            SetWindowLongPtrW(window, DWLP_MSGRESULT, TBDDRET_DEFAULT);
            return TRUE;
        }
    }
    if (message != WM_COMMAND) return FALSE;
    auto* state = reinterpret_cast<HomeState*>(GetWindowLongPtrW(window, GWLP_USERDATA));
    if (!state) return FALSE;
    int control = LOWORD(wparam);
    const auto& text = peText[state->language];
    if (control == HomeTools || control == HomeLanguage || control == HomeHelp) {
        wizardOwner = window;
        if (control == HomeLanguage) {
            constexpr int languages[] = { 1, 2, 3, 0 };
            const auto current = std::find(std::begin(languages), std::end(languages), state->language) - std::begin(languages);
            const auto selection = Choose(text, text.language, { L"日本語", L"简体中文", L"繁體中文", L"English" }, static_cast<int>(current));
            wizardOwner = nullptr;
            if (selection >= 0 && selection < static_cast<int>(ARRAYSIZE(languages))) {
                state->language = languages[selection];
                LocalizeHome(window, *state);
            }
            return TRUE;
        }
        const bool tools = control == HomeTools;
        const auto selection = tools
            ? Choose(text, text.tools, { text.homeScan, state->isPe ? text.repair : text.homeAdvanced })
            : Choose(text, text.homeGuide, { text.homeGuide, text.homeAbout });
        wizardOwner = nullptr;
        if (selection < 0) return TRUE;
        if (tools) control = selection == 0 ? HomeRefresh : HomeRepair;
        else control = selection == 0 ? HomeGuide : HomeAbout;
    }
    if (control == HomeRefresh) {
        FillHomeList(window, *state);
        return TRUE;
    }
    if (control == HomePrimary || control == HomeRepair || control == HomeGuide || control == HomeAbout) {
        wizardOwner = window;
        if (control == HomePrimary) {
            if (state->isPe) RunPeAction(state->bundle, text, true);
            else RepairCurrentFromHome(*state);
        } else if (control == HomeRepair) {
            if (state->isPe) RunPeAction(state->bundle, text, false);
            else if (!OpenFullWindowsTools(state->bundle, state->language)) Notice(text, text.failed);
        } else if (control == HomeGuide) {
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
    const INITCOMMONCONTROLSEX controls{ sizeof controls, ICC_LISTVIEW_CLASSES | ICC_BAR_CLASSES };
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
        { WS_POPUP | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | DS_CENTER, 0, 0, 0, 0, static_cast<short>(isPe ? 414 : 372), static_cast<short>(isPe ? 314 : 225) },
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
