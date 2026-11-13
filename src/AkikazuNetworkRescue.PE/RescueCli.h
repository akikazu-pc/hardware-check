static bool WaitForLanguageKey(HANDLE input)
{
    const auto deadline = GetTickCount64() + 3000;
    for (auto now = GetTickCount64(); now < deadline; now = GetTickCount64()) {
        if (WaitForSingleObject(input, static_cast<DWORD>(deadline - now)) != WAIT_OBJECT_0) return false;
        INPUT_RECORD record{};
        DWORD read = 0;
        if (!ReadConsoleInputW(input, &record, 1, &read) || read != 1) return false;
        if (record.EventType == KEY_EVENT && record.Event.KeyEvent.bKeyDown) {
            const auto key = record.Event.KeyEvent.wVirtualKeyCode;
            if (key != VK_SHIFT && key != VK_CONTROL && key != VK_MENU) return true;
        }
    }
    return false;
}

static size_t ReadCliChoice(const PeText& text, size_t maximum)
{
    for (;;) {
        std::wcout << text.cliChoice << std::flush;
        std::wstring line;
        if (!std::getline(std::wcin, line)) return 0;
        const auto begin = line.find_first_not_of(L" \t\r");
        const auto last = line.find_last_not_of(L" \t\r");
        if (begin == std::wstring::npos) continue;
        const auto choice = line.substr(begin, last - begin + 1);
        if (choice.find_first_not_of(L"0123456789") != std::wstring::npos) continue;
        wchar_t* end = nullptr;
        const auto value = wcstoul(choice.c_str(), &end, 10);
        if (*end == L'\0' && value <= maximum) return value;
    }
}

static size_t ChooseCli(const PeText& text, const wchar_t* prompt,
    const std::vector<std::wstring>& choices, bool allowSingle = true)
{
    if (choices.empty()) return 0;
    std::wcout << prompt << L'\n';
    for (size_t i = 0; i < choices.size(); ++i) std::wcout << i + 1 << L". " << choices[i] << L'\n';
    if (allowSingle && choices.size() == 1) return 1;
    std::wcout << L"0. " << text.cancel << L'\n';
    return ReadCliChoice(text, choices.size());
}

static DWORD CurrentWindowsBuild()
{
    SYSTEM_INFO system{};
    GetNativeSystemInfo(&system);
    if (system.wProcessorArchitecture != PROCESSOR_ARCHITECTURE_AMD64) return 0;
    wchar_t build[16]{};
    DWORD bytes = sizeof build;
    if (RegGetValueW(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
            L"CurrentBuildNumber", RRF_RT_REG_SZ, nullptr, build, &bytes) != ERROR_SUCCESS) return 0;
    return wcstoul(build, nullptr, 10);
}

static std::wstring InfHash(const fs::path& path)
{
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    const auto size = stream.tellg();
    constexpr auto maxInfSize = 16 * 1024 * 1024;
    if (size <= 0 || size > maxInfSize) return {};
    std::vector<UCHAR> data(static_cast<size_t>(size));
    if (!stream.seekg(0).read(reinterpret_cast<char*>(data.data()), static_cast<std::streamsize>(data.size()))) return {};
    BCRYPT_ALG_HANDLE sha{};
    if (BCryptOpenAlgorithmProvider(&sha, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0) return {};
    std::array<UCHAR, 32> digest{};
    const auto result = BCryptHash(sha, nullptr, 0, data.data(), static_cast<ULONG>(data.size()),
        digest.data(), static_cast<ULONG>(digest.size()));
    BCryptCloseAlgorithmProvider(sha, 0);
    if (result != 0) return {};
    constexpr wchar_t hex[] = L"0123456789ABCDEF";
    std::wstring output;
    for (const auto byte : digest) {
        output += hex[byte >> 4];
        output += hex[byte & 15];
    }
    return output;
}

static DWORD InstallCurrentDriver(const fs::path& bundle, const DriverMatch& driver)
{
    const auto hash = InfHash(driver.path);
    if (hash.empty()) return ERROR_INVALID_DATA;
    const auto executable = bundle / L"AkikazuHardwareCheck.exe";
    const auto args = L"--install-network-driver \"" + driver.path.wstring() +
        L"\" \"" + driver.id + L"\" " + hash;
    SHELLEXECUTEINFOW start{};
    start.cbSize = sizeof start;
    start.fMask = SEE_MASK_NOCLOSEPROCESS;
    start.lpVerb = L"runas";
    start.lpFile = executable.c_str();
    start.lpParameters = args.c_str();
    start.nShow = SW_HIDE;
    if (!ShellExecuteExW(&start) || !start.hProcess) return ERROR_ACCESS_DENIED;
    WaitForSingleObject(start.hProcess, INFINITE);
    DWORD result = ERROR_GEN_FAILURE;
    GetExitCodeProcess(start.hProcess, &result);
    CloseHandle(start.hProcess);
    return result;
}

static int RunCli(const fs::path& bundle, bool isPe, int language)
{
    const auto& text = peText[language];
    const auto targets = isPe ? DiscoverTargets() : std::vector<Target>{};
    const auto media = isPe && !IsSetupRunning() ? DiscoverSetupMedia() : std::vector<SetupMedia>{};
    bool setup = false;
    std::optional<DeploymentSelection> deployment;
    DWORD build = 0;
    size_t selected = 0;

    if (isPe) {
        if (targets.empty() && media.empty()) {
            std::wcout << text.noTarget << L'\n' << text.noMedia << L'\n';
            return 2;
        }
        if (!targets.empty() && !media.empty()) {
            const auto action = ChooseCli(text, text.action, { text.repair, text.setup });
            if (!action) return 0;
            setup = action == 2;
        } else {
            setup = targets.empty();
        }
        std::vector<std::wstring> choices;
        if (setup) {
            for (const auto& source : media) choices.push_back(WindowsLabel(source.root, source.build));
        } else {
            for (const auto& target : targets) choices.push_back(WindowsLabel(target.root, target.build));
        }
        selected = ChooseCli(text, setup ? text.media : text.target, choices);
        if (!selected) return 0;
        build = setup ? media[selected - 1].build : targets[selected - 1].build;
        if (setup && SupportsUnattended(media[selected - 1])) {
            const auto mode = ChooseCli(text, text.deployMode, { text.deploySetup, text.deployUnattended });
            if (!mode) return 0;
            if (mode == 2) {
                deployment = ChooseDeployment(media[selected - 1], text,
                    [&](const wchar_t* prompt, const std::vector<std::wstring>& entries) {
                        return static_cast<int>(ChooseCli(text, prompt, entries, false)) - 1;
                    },
                    [&](const wchar_t* message) { std::wcout << message << L'\n'; });
                if (!deployment) return 0;
            }
        }
    } else {
        std::wcout << text.cliCurrent << L'\n';
        build = CurrentWindowsBuild();
        if (build < 10240) {
            std::wcout << text.failed << L'\n';
            return 2;
        }
        if (ReadDeviceHardwareIds(true).empty()) {
            std::wcout << text.cliNoMissing << L'\n';
            return 0;
        }
    }

    std::wcout << text.scan << L'\n';
    auto matches = ScanDrivers(bundle, build, !isPe);
    std::vector<const DriverMatch*> chosen;
    if (matches.empty()) {
        if (!deployment && !setup) {
            std::wcout << text.noDriver << L'\n';
            return 4;
        }
        if (!ChooseCli(text, text.continueWithoutDriver, { text.confirm }, false)) return 0;
    } else {
        std::vector<std::wstring> labels;
        for (const auto& match : matches) {
            labels.push_back(match.name + L"  " + match.path.filename().wstring() + L" [" + match.id + L"]");
        }
        const bool installAll = (isPe || deployment || setup) && matches.size() > 1;
        if (installAll) {
            labels.push_back(std::wstring(text.installAll) + L" (" + std::to_wstring(matches.size()) + L")");
        }
        const auto driver = ChooseCli(text, text.driver, labels);
        if (!driver) return 0;
        if (installAll && driver == static_cast<int>(matches.size()) + 1) {
            for (const auto& match : matches) chosen.push_back(&match);
        } else {
            chosen.push_back(&matches[driver - 1]);
        }
    }
    const auto driverPaths = [&] {
        std::vector<fs::path> paths;
        for (const auto* match : chosen) paths.push_back(match->path);
        return paths;
    };
    if (deployment) {
        const auto& source = media[selected - 1];
        const auto paths = driverPaths();
        std::wcout << DeploymentDetails(source, *deployment, paths) << L'\n';
        if (!ChooseCli(text, text.deployConfirm, { text.confirm }, false)) return 0;
        const wchar_t* step = text.deployPreparing;
        const auto code = RunUnattended(source, *deployment, paths, text,
            [](const wchar_t* message) { std::wcout << message << L'\n' << std::flush; }, step);
        if (code == ERROR_SUCCESS) return 0;
        std::wcout << DeploymentFailure(text, step, code) << L'\n';
        return 6;
    }
    if (!chosen.empty()) {
        const auto* confirmation = setup ? text.confirmSetup : isPe ? text.confirmRepair : text.cliConfirmCurrent;
        if (!ChooseCli(text, confirmation, { text.confirm }, false)) return 0;
    }
    for (const auto* match : chosen) {
        if (!VerifyNetworkDriver(match->path)) {
            std::wcout << text.failed << L'\n';
            return 5;
        }
    }
    if (setup) {
        const auto result = StartSetup(media[selected - 1], driverPaths());
        if (result == SetupStart::Started) return 0;
        if (result == SetupStart::DriverPreparationFailed) {
            std::wcout << text.setupDriverPreparationFailed << L'\n';
            return 6;
        }
    } else if (isPe) {
        const auto& target = targets[selected - 1];
        if (ReadWindowsBuild(target.root) == target.build) {
            bool added = true;
            for (const auto* match : chosen) {
                const auto result = RunDism(target, L"/Add-Driver /Driver:\"" + match->path.wstring() + L"\"");
                if (result != ERROR_SUCCESS && result != ERROR_SUCCESS_REBOOT_REQUIRED) {
                    added = false;
                    break;
                }
            }
            if (added && RunDism(target, L"/Get-Drivers") == ERROR_SUCCESS) {
                std::wcout << text.repairDone << L'\n';
                return 0;
            }
        }
    } else {
        const auto result = InstallCurrentDriver(bundle, *chosen[0]);
        const wchar_t* messages[] = { text.cliBound, text.cliRestart, text.cliUnconfirmed };
        if (result < ARRAYSIZE(messages)) {
            std::wcout << messages[result] << L'\n';
            return static_cast<int>(result);
        }
    }
    std::wcout << text.failed << L'\n';
    return 6;
}

class UnicodeConsoleOutput final : public std::wstreambuf {
public:
    explicit UnicodeConsoleOutput(HANDLE output) : output_(output) {}

protected:
    std::streamsize xsputn(const wchar_t* text, std::streamsize size) override
    {
        if (size <= 0 || size > MAXDWORD) return 0;
        DWORD written = 0;
        return WriteConsoleW(output_, text, static_cast<DWORD>(size), &written, nullptr) ? written : 0;
    }

    int_type overflow(int_type value) override
    {
        if (traits_type::eq_int_type(value, traits_type::eof())) return traits_type::not_eof(value);
        const auto ch = traits_type::to_char_type(value);
        return xsputn(&ch, 1) == 1 ? value : traits_type::eof();
    }

private:
    HANDLE output_;
};

static int StartCli(const fs::path& bundle, bool isPe, bool keepOpen)
{
    DWORD mode = 0;
    const auto output = GetStdHandle(STD_OUTPUT_HANDLE);
    const bool consoleOutput = GetConsoleMode(output, &mode) != FALSE;
    UnicodeConsoleOutput unicode(output);
    auto* previous = std::wcout.rdbuf();
    if (consoleOutput) {
        std::wcout.rdbuf(&unicode);
    } else {
        _setmode(_fileno(stdout), _O_U8TEXT);
    }
    int language = PreferredLanguage();
    const auto input = GetStdHandle(STD_INPUT_HANDLE);
    if (GetConsoleMode(input, &mode)) {
        std::wcout << peText[language].cliLanguage << L'\n' << std::flush;
        if (WaitForLanguageKey(input)) {
            const auto selection = ChooseCli(peText[language], peText[language].language,
                { L"English", L"Japanese", L"Simplified Chinese", L"Traditional Chinese" });
            if (selection) language = static_cast<int>(selection - 1);
        }
    }
    const auto result = RunCli(bundle, isPe, language);
    if (keepOpen) {
        std::wcout << peText[language].cliKeepOpen << L'\n';
        std::wstring ignored;
        std::getline(std::wcin, ignored);
    }
    std::wcout.flush();
    if (consoleOutput) std::wcout.rdbuf(previous);
    return result;
}
