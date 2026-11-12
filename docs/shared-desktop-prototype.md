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

官网渠道可对单个问题码为 28 的匹配设备确认安装。预览使用 Windows catalog 验证 INF 并显示签名者。短时管理员进程重新检查 INF 指纹、catalog、当前系统匹配与设备状态。若同一硬件 ID 对应多台设备，退出安装。Windows 负责驱动包依赖、安装策略与排名。结束后按设备问题码和驱动服务报告绑定状态，需重启时由用户决定重启。联网状态需另行检查。商店渠道仅提供预览。

## 从离线驱动目录查找候选

把已解包的驱动目录带到断网电脑。扫描设备后选择「搜索驱动目录」。工具遍历目录下的 INF，列出当前 Windows 上有硬件 ID 匹配的候选，并提示不可读取的 INF 数量。排序优先显示较具体的硬件 ID。选中后使用原有的预览、签名校验和安装确认。保留厂商包的目录结构和依赖文件。压缩包和厂商安装程序需要事先解包。

首批候选之一是[技嘉 B650 AORUS ELITE AX rev. 1.2 Realtek 8852 Wi-Fi 6001.16.172.0](https://www.gigabyte.com/Motherboard/B650-AORUS-ELITE-AX-rev-12/Support/sp)，厂商标注支持 Windows 10/11 x64。实测官方下载 ZIP 的 SHA-256 为 A6CD81E7792678D6BCB7A9F791C2CBD1972BC653B7A3A4102D0AF342F8038725。该 ZIP 内是厂商 EXE，尚未核对其内部 INF，也未确认再分发授权。
