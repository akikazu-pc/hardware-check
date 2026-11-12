# 共享桌面首轮原型：断网急救与硬件测试

**状态**：可运行原型，不是发行版。只验证官网/Portable 能力；MSI、Store 提审、真实驱动安装和回退不在本轮范围。

## 已实现

- 硬件测试和断网急救各有一个独立安装身份、开始菜单入口和“已安装的应用”卸载入口。
- 单装任一应用都只显示自己的页面；双装共用一个 WinForms 主窗口和导航条，入口参数决定初始页面。
- 每用户会话单实例。第二次启动写一个请求文件后退出，已运行窗口按请求切换到对应模块并恢复前台。
- 托盘由唯一主窗口创建，启用时一个进程只有一个 `NotifyIcon`；关闭、隐藏和恢复沿用原有设置。
- 共享组件按版本目录保存，卸载或升级时保留另一款仍需使用的宿主版本。
- 断网急救页只读取本机网络接口和模块注册，不发送数据包；没有驱动安装按钮。
- Store 构建只允许硬件测试模块，断网急救模块在 Store 构建中不可见。

## 安装身份

身份清单：`packaging/shared-desktop/app-identities.json`。

| 应用 | 模块 ID | 安装身份 | UpgradeCode | 默认模块版本 |
| --- | --- | --- | --- | --- |
| 秋和PC 硬件测试工具 | `hardware-check` | `Akikazu.HardwareCheck` | `{D54F7C1E-7906-4A86-98CC-4494BD398F5B}` | 产品版本 |
| 断网急救 | `network-rescue` | `Akikazu.NetworkRescue` | `{66B08D82-E82C-423C-9252-2B2A73E9AB01}` | `0.1.0` |

UpgradeCode 已按稳定身份写入清单，供后续 MSI 项目使用；本轮的 PowerShell 安装器只做 per-user 原型安装，不改动现有 MSI 脚本。

### 目录

```text
%LOCALAPPDATA%\Akikazu\SharedDesktop\
  host\<宿主版本>\AkikazuHardwareCheck.exe + 依赖
  modules\hardware-check\module.json + uninstall.ps1 + SharedDesktopPrototype.psm1
  modules\network-rescue\module.json + uninstall.ps1 + SharedDesktopPrototype.psm1
```

两个模块可以指向同一宿主版本，也可以各自指向不同版本。安装器只复制缺失的宿主版本；卸载时扫描剩余模块的 `HostVersion`，删除不再被引用的宿主目录。

### 注册表

```text
HKCU\Software\Akikazu\SharedDesktop
  SchemaVersion = 1
  HostInterfaceVersion = 1
  Modules\hardware-check
    SchemaVersion = 1
    Id, Version, MinHostInterface, HostVersion
    InstallRoot, HostPath, EntryArguments
    InstallIdentity, UninstallKey
  Modules\network-rescue
    ...同上...
```

卸载入口：

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Akikazu.HardwareCheck
HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Akikazu.NetworkRescue
```

开始菜单入口位于 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\秋和PC\`，分别传 `--module hardware-check` 和 `--module network-rescue`。

## 版本化接口

- `SharedDesktopContract` 固定 `SCHEMA_VERSION = 1` 和 `HOST_INTERFACE_VERSION = 1`。
- 模块声明 `MinHostInterface`；宿主只加载能理解的版本，未来版本、缺字段、宿主文件缺失或接口不兼容的注册会被跳过，不影响另一个模块。
- 注册读取失败时启动回退到硬件测试（Portable/未安装运行的默认模块）。
- Store 构建在发现和窗口两层都过滤 `network-rescue`，避免网站安装的模块泄漏到商店版。

## 启动、导航与单实例

命令行：

| 参数 | 作用 |
| --- | --- |
| `--module hardware-check` / `--module network-rescue` | 请求的初始页面；未安装时回退到已安装主模块 |
| `--module=network-rescue` | 同上，等号形式 |
| `--tray` | 静默后台启动；有注册表时按主模块启动 |
| `--no-elevate` | 测试和普通权限运行 |

启动流程：

1. 读取模块注册并解析入口；只有硬件测试模块沿用原有自动提权策略，断网急救入口不提权。
2. 用 `Local\AkikazuHardwareCheck.SingleInstance` 命名互斥锁保证每个 Windows 登录会话一个主窗口。
3. 第一个实例清理本进程启动前遗留的请求，创建主窗口；第二个实例把 `{Module, RequestedAt}` 写入 `%LOCALAPPDATA%\AkikazuHardwareCheck\launch-requests\session-<会话ID>\` 后立即退出。
4. 主窗口每 300 ms 读取请求；文件方式可跨越 Windows 完整性级别（提权的硬件窗口和非提权的急救入口可以互相唤回），不依赖托盘事件。
5. 请求的模块已安装时切换页面，否则只恢复当前窗口。
6. 托盘、语言、关闭到后台和自启动仍由主窗口统一管理；不新增第二个常驻进程或第二个图标。

### 自启动入口

- `StartupRegistration.Set(true)` 不再固定写当前运行副本，而是写主模块已安装宿主的 `HostPath`；没有安装记录时才回退到当前进程路径（Portable）。
- 安装器在安装、升级和卸载后调用 `Update-StartupRegistration`：
  - 只处理指向本共享根目录的 Run 值，指向其他位置的 Portable/其他应用值不动；
  - 还有模块时，改写到主模块（硬件优先）存在且可启动的宿主；
  - 最后一个模块卸载后删除 Run 值；
  - 原本禁用（没有 Run 值）时不做任何写入。
- 采用“安装迁移时可靠重写”的方案，不引入额外常驻启动器。实际 Windows 登录触发未在本轮验证。

## 页面

- **硬件测试**：保留原有主界面、菜单、测试、监控和设置；首次进入该页才启动 WMI/传感器驱动，急救单装不会因为共享宿主启动而安装 PawnIO。
- **断网急救**：只读显示活动物理网卡、类型、连接状态、链路速率、是否有默认网关，以及已安装模块的模块版本和接口版本。不读取 SSID、主机名、用户名或序列号，不访问互联网。
- 双装时窗口顶部显示“硬件测试/断网急救”原生按钮导航；单装时不显示导航条。
- 急救页面的菜单收窄为文件（退出）、设置、语言和帮助；硬件菜单只在硬件页面出现。

## 运行原型

先构建 Release，再安装：

```powershell
dotnet build AkikazuHardwareCheck.slnx -c Release

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/install-app.ps1 -App hardware-check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/install-app.ps1 -App network-rescue

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/uninstall-app.ps1 -App network-rescue
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/uninstall-app.ps1 -App hardware-check
```

验证脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/test-shared-desktop.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/test-shared-desktop-upgrade.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/test-shared-desktop-elevation.ps1
```

脚本会：

- 拒绝在已有共享桌面注册的电脑上运行，避免覆盖用户安装；
- 备份、写入并恢复 `settings.json` 和 `HKCU\...\Run\AkikazuHardwareCheck`；
- 在 `%TEMP%\AkikazuSharedDesktopTest-<随机>` 下安装，结束后清理测试根目录、注册表、快捷方式和进程；
- 覆盖单装、两种安装顺序、双装导航、并发启动、托盘隐藏恢复、各自升级、两种卸载方向、注册卸载命令和断网模拟启动；
- 主脚本补测自启动 Run 迁移、禁用后无残留、`Shell_NotifyIconGetRect` 实际托盘注册；
- `test-shared-desktop-upgrade.ps1` 构建 0.2.0 和 0.2.1 两个不同二进制，验证真实文件版本升级和 Run 迁移；
- `test-shared-desktop-elevation.ps1` 验证硬件入口提权、急救入口不提权和混合入口单窗口；该脚本要求本机已安装 PawnIO，避免测试触发驱动安装。

指定构建产物：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/test-shared-desktop.ps1 -SkipBuild -PayloadPath <构建输出目录>
```

## 本轮实际验证

环境：Windows 11 26H2（Build 26300），150% 缩放，3840×2160，普通用户权限；隔离工作树 `proto/shared-desktop`，基线 `dcabefe`。

| 项目 | 结果 |
| --- | --- |
| Release 构建 | 0 警告、0 错误 |
| 单元测试 | 482 个全部通过（含新增 `SharedDesktopTests` 和 `SharedDesktopPackagingTests`） |
| Website 窗口冒烟 | 四语言全部窗口构造通过；双装初始页、导航切换、急救单装隐藏硬件页通过 |
| Store 窗口冒烟 | 通过；Store 构建不出现急救模块和导航 |
| 共享窗口截图 | 双装断网急救页：标题“断网急救 v0.1.0”，顶部两个原生导航按钮，本机网卡与已安装模块列表正常 |
| 单装硬件 | 入口打开硬件窗口；快捷方式和卸载项版本正确；注册卸载命令退出码 0，清理模块、卸载项和共享根目录 |
| 单装急救 | 通过开始菜单快捷方式实际启动，标题“断网急救 v0.1.0” |
| 安装顺序 | 先硬件后急救、先急救后硬件均成功；双装窗口共享 |
| 双装导航 | 第二入口写入请求后立即退出，原窗口在 300 ms 轮询周期内切换到请求页面；进程数始终为 1 |
| 并发启动 | 同时启动两个入口后只保留一个共享宿主进程和一个窗口，随后导航正常 |
| 托盘隐藏 | `--tray` 启动无可见主窗口；第二入口唤回并显示急救页；进程数 1 |
| 独立升级 | 急救升级到 0.1.1/宿主 0.2.1 时硬件保持 0.2.0/0.2.0；硬件升级到 0.2.1/宿主 0.2.2 时急救保持 0.1.1/0.2.1；旧宿主按引用清理 |
| 真实版本升级 | 0.2.0 与 0.2.1 是不同二进制（FileVersion 0.2.0.0 / 0.2.1.0）；升级后新宿主可启动，急救保留 0.2.0 宿主；Run 指向新宿主 |
| 独立卸载 | 卸载硬件后急救仍可启动；卸载急救后硬件及其宿主仍可启动；最后卸载清理共享根目录和注册表 |
| 自启动迁移 | 双装、单装急救、急救/硬件各自升级和任一卸载后，Run 都指向存在的主模块宿主；最后一款卸载后 Run 被删除 |
| 禁用自启动 | `--autostart-check` 启用后写入 `--tray`，禁用后无 Run 值；安装/升级/卸载不会重新创建已禁用的值 |
| 实际托盘 | 双装窗口的 `NotifyIcon` 通过 `Shell_NotifyIconGetRect` 返回真实通知区域矩形；提权硬件宿主启动后切换急救页，切换前后是同一个图标 identity/rect |
| 提权入口 | 硬件入口自动提权；运行窗口令牌为 elevated；原非提权启动器退出，只保留一个宿主进程 |
| 非提权入口 | 急救入口运行窗口令牌为 non-elevated；只保留一个宿主进程 |
| 混合入口：急救先 | 先急救后硬件只有一个非提权窗口，窗口切到硬件页但不会变成提权进程（已知首轮限制） |
| 混合入口：硬件先 | 管理员硬件宿主先启动，再由普通权限急救入口切到急救页；同一 PID、同一主窗口句柄、一个进程、一个托盘图标；窗口保持 elevated |
| 实际登录自启 | **阻塞**：当前机器只有 console 会话 1，没有可用的 Hyper-V/VMware/VirtualBox VM、Windows Sandbox 或第二 Windows 会话；未注销/重启当前桌面，也未新建 VM。Run 值迁移已验证，登录触发未验证 |
| 断网模拟 | 把 `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` 指向死端点后急救页仍在 15 秒内打开 |

提权测试在 PawnIO 已安装且运行的开发机上执行，未触发驱动安装或卸载；不能代表干净机器上的驱动生命周期。

**未验证**：

- 真实拔网/断网环境；本轮只验证急救页启动路径没有互联网依赖，并用死代理模拟。
- MSI 交互/静默安装、升级、降级阻止和签名；本机没有 Advanced Installer，未生成 MSI。本轮安装器是 per-user PowerShell 原型，不是 per-machine MSI。
- Store MSIX、WACK、Partner Center 身份和提审。
- 真实驱动安装、驱动备份和回退；急救页本轮没有驱动操作；提权测试借用已安装的 PawnIO。
- 不同二进制版本之间的长期接口兼容性；本轮只验证了 0.2.0→0.2.1 的一次真实硬件宿主升级。
- 通过硬件测试快捷方式实际点击启动（快捷方式参数和直接启动已验证；硬件入口自动提权已验证，但未从 `.lnk` 点击触发）。
- 运行中的窗口热切换升级；本轮真实版本升级在停止窗口后进行。
- 通知区域图标数量的跨 Explorer 重启、图标溢出区和多用户会话计数；本轮验证了双装窗口实际注册的一个 `NotifyIcon`，但没有枚举整个通知区域计数。
- Explorer 重启、多个 Windows 用户会话、实际登录触发自启动。Run 值迁移已验证，但登录时实际启动因无隔离环境而阻塞。

## 本轮阻塞

实际登录自启未执行。检查结果：

- 当前只有 `console` 会话 ID 1，使用中的桌面不能被注销或重启；
- `Get-VM` 没有可用 VM，未发现 VirtualBox/VMware 安装；
- 未找到 `WindowsSandbox.exe`，WSL 也没有已安装发行版。

因此没有可用的隔离 Windows 会话或 VM。没有为了这次验证新建 VM、切换用户会话或重启当前桌面。Run 值在安装/升级/卸载后的迁移已由脚本验证；实际登录触发需要后续在隔离 VM 或独立测试账号会话中补测。

## 后续工作

1. 用身份清单和稳定 UpgradeCode 生成两个 per-machine MSI 项目；安装器把共享宿主放到受控目录，并用 HKLM 或安装上下文解析模块。
2. 评估把自启动迁移改成稳定启动器，减少对安装器重写的依赖，并验证实际登录触发。
3. 把断网急救的驱动安装、离线包索引和回退做成独立模块，驱动操作单独提权并保持主窗口权限不变。
4. 为 Store 配置工具做最小 MSIX 原型，验证相互打开、状态访问、双装/卸载和商店政策边界。
5. 运行中的共享窗口增加版本刷新或安全重启协议，处理“旧窗口收到新模块导航”的升级场景。
6. 用真实断网、Explorer 重启、不同 Windows 用户和混合提权场景补全验证记录。

## 只读网卡扫描

断网急救页可按需扫描当前枚举的 PCI 网络控制器候选，并导出 Windows 构建、系统架构、有序硬件 ID、SUBSYS 和设备问题码。PCI 0280 是候选类别。问题码 28 表示没有安装驱动。导出保存在用户选择的位置，只包含诊断字段。此流程不联网，也不会安装驱动。

[四平台驱动索引样例](wifi-driver-index.sample.json)保留出厂模块和驱动来源证据，分别记录 Windows 10/11 的 INF 核验与实机测试状态。当前样例没有经过 INF 匹配验证的包记录，不参与自动匹配。

扫描到候选设备后，可以选择解包后的本地网络驱动 INF 预览匹配。通过 Windows SetupAPI 读取适用于当前系统的 Models 段，并按已扫描设备的有序硬件 ID 显示匹配依据。该操作只读取选中的 INF 文件。包签名、依赖、正式 Windows 驱动排名和安装另行处理。

官网渠道可对单个问题码为 28 的匹配设备确认安装。预览使用 Windows catalog 验证 INF 并显示签名者。短时管理员进程重新检查 INF 指纹、catalog、当前系统匹配与设备状态。若同一硬件 ID 对应多台设备，退出安装。Windows 负责驱动包依赖、安装策略与排名。结束后核对原设备实例、问题码、驱动服务、实际绑定版本以及驱动库中 INF 的 SHA-256，再报告绑定状态，需重启时由用户决定重启。联网状态需另行检查。商店渠道仅提供预览。

## 从离线驱动目录查找候选

把已解包的驱动目录带到断网电脑。扫描设备后选择「搜索驱动目录」。工具遍历目录下的 INF，列出当前 Windows 上有硬件 ID 匹配的候选，并提示不可读取的 INF 数量。排序优先显示较具体的硬件 ID。选中后使用原有的预览、签名校验和安装确认。保留厂商包的目录结构和依赖文件。压缩包和厂商安装程序需要事先解包。

首批候选之一是[技嘉 B650 AORUS ELITE AX rev. 1.2 Realtek 8852 Wi-Fi 6001.16.172.0](https://www.gigabyte.com/Motherboard/B650-AORUS-ELITE-AX-rev-12/Support/sp)，厂商标注支持 Windows 10/11 x64。实测官方下载 ZIP 的 SHA-256 为 A6CD81E7792678D6BCB7A9F791C2CBD1972BC653B7A3A4102D0AF342F8038725。已通过 Windows tar 解包厂商自解压文件，未执行厂商 EXE。包内 netrtwlane602.inf 版本为 6001.16.172.0，包含 RTL8852CE 的多个 SUBSYS 项。Windows 在开发机上将 catalog 签名判为有效，签名者为 Microsoft Windows Hardware Compatibility Publisher。包内 Realtek 版权声明列明附条件的二进制再分发许可，准备脚本会保留原声明。具体主板实机 SUBSYS 与安装结果仍待确认。

用官方下载 ZIP 生成可搜索的本地目录：

```powershell
powershell -NoProfile -File scripts/prototype/prepare-realtek-wifi-pack.ps1 -VendorZip <下载的ZIP> -OutputDirectory <新的目录>
```

准备脚本固定 ZIP 和 INF 的 SHA-256，保留完整的驱动子目录和版权声明。它不执行安装，也不生成正式离线安装器。

## 可安装的 ZIP 预览

在安装了 .NET 10 SDK 的构建机上，使用运行于 .NET 10 的 PowerShell 运行：

```powershell
pwsh -NoProfile -File scripts/publish-network-rescue-bundles.ps1 -RealtekVendorZip <官方下载ZIP>
```

输出位于 `artifacts/network-rescue`。不传入厂商 ZIP 时仅生成精简版。离线预览版随附已准备好的 Realtek 包。两个 ZIP 都包含自包含 x64 主程序、安装入口和独立卸载注册所需文件。目标电脑解压后运行 `Install.cmd`。离线包安装到断网急救模块目录，驱动目录选择器默认打开该位置。精简版再次安装时保留已有驱动目录。安装入口使用按用户安装脚本，MSI 签名、正式完整版和安装实机验收仍在发布阶段处理。

### 汇总现有驱动目录

```powershell
pwsh -NoProfile -File scripts/publish-network-rescue-bundles.ps1 -IncludeCatalog
```

可使用 `-VendorSourceDirectory <缓存目录>` 从本地构建。目录按清单的包 ID 分组，每组包含原始厂商 ZIP。离线目录版保留原始安装包在 ZIP 的 `vendor-installers`，另将 INF 及依赖预解包到 `driver-packs`。安装时只复制后者到断网急救模块，原始安装包可从 U 盘另行查看。脚本只解包，不运行厂商 EXE。厂商归档按 [包清单](../packaging/shared-desktop/wifi-preview-packages.json)逐一校验 SHA-256，能取得的版权声明随驱动保留。

此版本用于本地测试和离线救援准备。各包的再分发条款仍须逐包确认，四平台逐板覆盖仍以证据目录验收。LGA1700 华擎样例的出厂模块仍待核实。LGA1851 的两个 Wi-Fi 7 包由厂商标注为 Windows 11 x64。

### USB 无线网卡候选

扫描继续收录 PCI 无线候选，同时收录 USB 网络设备和缺驱动且设备类未识别的 USB VID/PID。后者在界面和诊断 JSON（schema 2）标记为未识别的 USB 设备，需要由网络类 INF 的明确硬件 ID 给出候选。已识别的 HID 等 USB 类不会列入。安装沿用签名、单设备和缺驱动检查。

离线目录增加 TP-Link Archer T3U Plus V1/V1.6 的官方 Windows 10/11 x64 包。使用包内 `USB\VID_2357&PID_0138` 样例，在当前 Windows 上通过程序的候选匹配及 INF 签名检查。尚无缺驱动 USB 实机安装结果。

### 扩展 WLAN 驱动库和主板目录

从 [SDIO 官方种子](https://www.glenn.delahoy.com/snappy-driver-installer-origin/)仅下载 WLAN/Wi-Fi 压缩包。固定快照 `DP_WLAN-WiFi_26082.7z` 含 1,634 个 INF。构建校验归档 SHA-256，并将驱动文件解包到驱动搜索目录。完整版输出 ZIP，逐文件核对相对路径和 SHA-256，原始下载包的链接和哈希可从索引查询。

```powershell
pwsh -NoProfile -File scripts/publish-network-rescue-bundles.ps1 -IncludeCatalog -WlanArchive <本地WLAN归档> -PeEthernetPackDirectory <有线驱动ZIP及其SHA-256所在目录> -SevenZipExecutable <完整版7z.exe>
```

可用 `scripts/audit-network-rescue-library.ps1 -DriverDirectory <已解包的driver-packs>` 检查当前 Windows 构建能解析的网络类 INF 和通过签名验证的硬件 ID。该脚本从文件提取字面 ID，再通过应用的 SetupAPI 匹配检查。结果是一份当前构建上的证据下界。它不会安装驱动，不能替代板载模块映射或缺驱动实机测试。

[华硕型号发现快照](asus-motherboard-discovery.csv)采集于 2026-11-12，来自[华硕全球产品目录](https://www.asus.com/motherboards-components/motherboards/all-series/filter?Series=All-series)的四个插槽过滤结果。AM4 35 条、AM5 140 条、LGA1700 176 条、LGA1851 56 条。174 条目录卡片提及 Wi-Fi。未提及的条目保持 unknown，下一步需查产品规格、区域修订、出厂模块和实际硬件 ID。该目录未覆盖其他品牌、所有历史型号或区域变体。

本次在 Windows 构建 26300 检查 1,651 个 INF，其中 669 个匹配当前系统的网络设备 ID，582 个 INF 通过签名检查。签名有效的 ID 去重后有 4,566 个 PCI ID、1,228 个 USB ID。一个网卡可能有多个 ID，同一芯片也可能有多个 SUBSYS。该数字不代表网卡或主板型号数。实际安装及联网、Windows 10 审计和其余品牌目录仍待核对。大型 ZIP 超过 FAT32 单文件大小限制，U 盘可使用 exFAT 或 NTFS。

## 当前交付方式

- 在线安装版 `NetworkRescue-<version>-online-install-win-x64.zip` 解包后运行 `Install.cmd`。包内不含驱动本体。扫描到缺驱动设备后，可从内置目录查询官方来源，选择并确认下载。ZIP 通过 SHA-256 校验后解包，随后用本机 Windows 的硬件 ID 和签名流程确认安装。目录是随程序发布的固定快照，暂不提供全量联网索引、驱动升级或回退。
- 离线完整版 `NetworkRescue-<version>-offline-full-portable-win-x64.zip` 解包后双击 `NetworkRescue.exe`。主程序直接使用随附运行时与同目录 `driver-packs`。关闭窗口即退出。安装 Wi-Fi 驱动需要管理员确认。
- 完整版为未加密 ZIP，可用 Windows 文件资源管理器的「全部解压缩」。打包脚本检查 SDIO 和原厂 INF 都已进入暂存目录，逐项比对 ZIP 与暂存文件的路径、长度和 SHA-256。验证通过后才替换成品并记录 SHA-256。更新主程序时重新运行打包脚本。

两版均包含[原厂驱动下载索引](network-rescue-driver-index.csv)，可按型号查找官网支持页、下载直链、版本和 SHA-256。在驱动候选列表选中一项后，点击「导出驱动 ZIP」可带走该 INF 所在的签名驱动目录及子目录，保留相对路径供另一台电脑解压使用。

当芯片 ID 一致且子系统匹配待确认时，在线目录和离线文件夹扫描会显示「可能的驱动」，供用户比对本机 ID 和候选 ID。用户可以手动选择在线下载或导出已验证签名的候选文件。安装仍要求当前设备的实际 ID 与适用的签名 INF 匹配。

在「型号搜索」页输入型号或选择设备分类，即可查看已知网卡和 Windows 10／11 x64 的驱动证据。一级分类为 DIY 台式电脑、笔记本电脑和其他设备。选中「其他设备」后可按二级标签筛选。详情提供已知的官网驱动页和资料来源，断网时也可搜索。

用 Ctrl+F 打开型号搜索并聚焦输入框。Alt+D 聚焦设备分类，Alt+T 聚焦可用的设备标签。用 Enter 选中首条搜索结果，用方向键浏览。Tab 和 Shift+Tab 可在筛选、结果及链接之间移动。

断网急救打开后读取本机主板或笔记本型号。型号链接优先使用原厂包索引的已核对页面，华硕主板另可用型号目录定位其下载页。已识别的网卡名称可点击保存本地驱动 ZIP，离线版优先使用随附驱动。「安装网络驱动」入口涵盖有线和无线网卡，优先扫描本地驱动目录，也可按已识别的设备下载驱动。安装继续使用 INF 匹配、签名核验及管理员确认。

「检测网络故障」区分缺驱动、设备错误和未确认用途的 USB 设备。「本机网络」显示断开连接的网卡，并提示链路、可用 IP 和默认网关的状态。Windows 10 2004 及更新版本同时读取 Windows 的互联网连接提示。程序不主动访问外网，系统提示按整台电脑显示。安装后分别显示驱动绑定与连接状态，也可手动「复测连接」或打开 Windows 网络设置。

从「安装网络驱动」进入时，只搜索缺驱动的设备。随附目录读不到或查无候选时，可改选 U 盘里的已解压驱动目录；内置在线目录有候选时，也可切换到在线候选并另行确认下载。离线完整版在桌面模式下也可从「工具」菜单直接进入在线候选。

同一个 INF 匹配多块缺驱动的网卡时，用户按网卡名和硬件 ID 选择本次修复的目标。提权后重新检查指定 ID 和当前设备状态。同一硬件 ID 对应多个在场设备时，自动安装会停止。

两版都覆盖桌面和笔记本。在线安装版沿用与硬件测试的双装联动。旧的 `offline-wlan-library` 安装 ZIP 记录保留供追踪，当前离线交付以免安装完整版为准。

## 离线完整版在 Windows 与 WinPE 中使用

将同一个离线完整版 ZIP 解压到 U 盘，两种环境都双击 `NetworkRescue.exe`。普通 Windows 默认打开完整急救窗口，包括型号搜索、在线下载和导出。x64 WinPE 打开原生窗口，顶部保留工具、语言和帮助。上方显示本机网络设备状态，下方显示驱动准备入口和可修复的离线 Windows。运行时不依赖 WMI、PowerShell 或 .NET。普通 Windows 和 PE 的顶部工具栏都支持日语、简体中文、繁体中文和英语。从终端运行 EXE 时打开命令行界面。使用 `NetworkRescue.exe --gui` 可显式打开图形窗口，使用 `Run-Network-Rescue.cmd --cli` 可在当前控制台运行。两种界面默认跟随 Windows 显示语言，无法匹配时使用英语。交互式命令行等待 3 秒，按键后持续等待语言编号，超时则继续。唯一目标和唯一签名驱动自动选中，写入前仍需确认。控制台以 Unicode 输出，精简 PE 的中日文显示取决于控制台可用字体；图形向导使用离线包内置字体。

在 PE 的「工具」中选择「修复已有 Windows」，工具列出可访问的固定磁盘分区中的 Windows 10/11 x64 系统。它用内核版本区分系统和匹配 INF 最低构建号，启用包更新的 Windows 可能显示较早的基线内核构建号。若找不到预期分区，先检查 PE 是否能读取磁盘，或在具备相应组件的 PE 中解锁 BitLocker。

PE 首页按网络设备类或 PCI 网络控制器 ID 识别网卡，可显示尚未归入网络设备类的 PCI 网卡。状态区分驱动运行、驱动未启动、缺驱动、设备错误和未知状态，所显示的是 PE 内的设备状态。

选择目标后，程序自动读取本机 PCI/USB 硬件 ID，共用完整版的 SDIO WLAN 库和原厂驱动目录。按目标系统构建号筛选原厂包，按目标系统选择随包提供的有线补充目录。只列出目标系统适用的网络类签名 INF 精确匹配项。按 Y 确认后调用系统 DISM 写入选中的离线 Windows，并列出目标驱动存储。重启进入该 Windows 后验证驱动绑定和联网。

生成完整版需要 MSVC x64 和 Windows SDK，打包脚本自动构建 PE 入口。完整版需要 `-PeEthernetPackDirectory` 提供的两份 Windows 10/11 Realtek PCIe 有线 ZIP 及对应 SHA-256 文件，以及 `-SevenZipExecutable` 指定的完整版 `7z.exe`，用于静态解包原厂 NSIS 驱动。原厂包清单中按 Windows 版本指定的驱动会放到对应的有线目录。完整版输出 ZIP。Windows 11 的 PE 离线写入已在隔离虚拟机验收。Windows 10 目标和实体网卡重启联网仍待验收。


### 全新安装时准备联网驱动

从独立 x64 WinPE 启动离线完整版，选择「安装 Windows 并准备联网驱动」。工具检查本机网卡及所连接的 Windows 安装介质，根据安装映像中的版本与架构筛选签名驱动。用户选中的 INF 如果与其他独立 INF 共用目录，工具会保留文件相对路径，在 PE 临时目录准备只含所选 INF 的驱动目录，并重新校验签名。所选 INF 如果需要同目录的其他 INF，则提示用户改用独立驱动包或在首次联网时补装。

Windows 11 24H2 及更新的安装程序使用 `/InstallDrivers`。较早的安装程序使用仅含驱动路径的应答文件。用户在微软安装器中选择目标磁盘，安装期间保留介质连接。驱动供新系统使用。

### 无人值守安装验证

隔离实验中，Windows 11 24H2 安装器可以同时使用 `/unattend` 和 `/InstallDrivers`。应答文件预先指定映像索引、唯一的空白虚拟磁盘、UEFI 分区和许可选择。从启动命令到首次设置可无人值守。预先配置地区和实验室临时账户后，另一次实验自动完成首次设置并到达锁屏。实际驱动入库见 [验证记录](validation-record.md)。

从独立 x64 UEFI WinPE 打开离线完整版。图形界面点「安装 Windows 并准备联网驱动」，命令行按编号选择安装。选择 Windows 安装介质后，可选择标准 Windows 安装程序，或使用「无人值守安装到空白磁盘」。后者确认映像版本、目标盘和签名网卡驱动后直接应用 Windows 映像，跳过 Windows Setup 的硬件检查流程。

无人值守方式只列出符合条件的在线、可写空白内置盘，开始写入前复核磁盘身份和空白状态。C 盘目标为 300 GiB，空间不足则使用扣除 EFI、MSR、1 GiB 恢复分区及对齐预留后的空间。大盘剩余空间不分配。默认创建本地管理员 `user`，密码留空。所选驱动写入新系统后配置 UEFI 引导和 Windows 恢复环境，成功后自动重启。若 Windows 在首次启动显示许可页面，按页面操作。部署遇错显示失败步骤及代码，并停止自动流程。映像应用和驱动写入日志保存在新系统的 `C:\NetworkRescueDeployment`。

此入口要求 UEFI 和至少 64 GiB 的合格空盘。存储控制器须已能在 PE 中识别。部署期间保持磁盘连接。若从 U 盘启动 PE，可用固件的一次性启动菜单，确保重启时从新系统盘启动。检测到 Microsoft 安装程序正在运行时，先使用独立 WinPE 环境。中断后磁盘若已有分区，将不再作为空盘提供。Windows 10、Windows 11 Home／Pro 和实体 Wi-Fi／有线网卡仍待实测。见 [验证记录](validation-record.md#离线完整版的无人值守入口)。

便携 Windows 窗口顶部的「工具」收纳刷新、诊断导出、INF 预览和手动选择目录。「帮助」沿用 Hardware Check 的指南链接和关于窗口。PE 离线包内置 Noto Sans CJK 字体，英文 PE 也能显示日语、简体中文和繁体中文。
