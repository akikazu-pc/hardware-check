# 断网急救开发交接

记录日期 2026-11-13（JST）。范围为断网急救及其与 Hardware Check 共享的 Windows 桌面入口。

## 接手基线

- GitHub 仓库为 [akikazu-pc/hardware-check](https://github.com/akikazu-pc/hardware-check)。远端 `main` 为 [`1347ce8`](https://github.com/akikazu-pc/hardware-check/commit/1347ce8101c69193727e133f84e8732458d57690)，其中包含合并 [`ee26ee4`](https://github.com/akikazu-pc/hardware-check/commit/ee26ee4ddf2cb887c9a20c04bb4af472de6b8b42)，`proto/shared-desktop` 已删除。合并后相对该分支最后提交 `2f446fd` 的树差异只有 `AGENTS.md`。
- `1fb8dcc` 接入 PE 空盘部署，`9c55511` 收录 B850M 普通版无线驱动，`2f446fd` 修复 I226-V 兼容 ID 漏匹配。本地 `main` 的补库提交已与远端 `1347ce8` 合并到 `eebb252`，按包 ID 和行键合并索引，重复的华硕 MediaTek 3.5.0.1349 包统一为 `asus-mb-mtk-3501349`。补库流程见[采集与核验交接](network-rescue-catalog-handoff.md)。之后直接在 `main` 上开发。
- [`ee26ee4` 的 GitHub Actions](https://github.com/akikazu-pc/hardware-check/actions/runs/43266106438)和 [`1347ce8` 的运行](https://github.com/akikazu-pc/hardware-check/actions/runs/43266826000)均已通过。以下安装包是本地产物。本次合并尚未制作新 GitHub Release、提交商店或部署网站。
- 截至 `faf66de`（2026-11-13 09:13 JST），本地 `main` 比远端 `1347ce8` 多 47 个提交，均未 push，远端 CI 为 Unverified。其中 `38d4e71` 修复运行中 Windows 无法为 I226-V 安装驱动，`62ab531` 修正 PE 命令行版本列表重复编号，`e692526`、`bfed381`、`62ccca5` 记录虚拟机验收，`faf66de` 拆分华硕笔记本 SKU；其余为补库会话的提交。

## 使用方式和交付包

| 包 | 入口 | 用途 |
| --- | --- | --- |
| 离线完整版便携 ZIP | 全部解压后运行 `NetworkRescue.exe`。明确用图形界面时加 `--gui`，命令行可用 `Run-Network-Rescue.cmd --cli`。 | 同一包适用于 Windows 和 x64 WinPE。包含 WLAN、OEM 和分系统的有线驱动。复制大文件到 U 盘时使用 exFAT 或 NTFS。 |
| 在线安装版 ZIP | 解压后运行 `Install.cmd`。 | 用已有的网络连接下载和校验原厂驱动。索引随程序发布。 |

- Windows 桌面可扫描有线／无线设备、按型号或设备类型搜索、打开官网驱动页、导出驱动 ZIP 和确认安装。存在候选分歧时，按硬件 ID 比对后选择。最终安装仍校验 INF 匹配及签名。两个应用可各自安装，也可在双装时共享窗口和托盘。日语、简体中文、繁体中文和英语可从菜单切换。
- PE 可发现已有离线 Windows 并写入网络驱动，也可为微软安装器准备选定驱动。无人值守新装从独立 x64 UEFI WinPE 启动，确认版本和空盘后直接应用映像，绕过 Windows Setup 硬件检查。要求 PE 能看到至少 64 GiB 的空盘。C 盘最多 300 GiB，较小的盘扣除启动和恢复分区后使用剩余空间。默认创建空密码本地管理员 `user`。首次出现微软许可页时由用户确认。
- 操作细节见[产品原型说明](shared-desktop-prototype.md#当前交付方式)和 [PE 安装流程](shared-desktop-prototype.md#无人值守安装验证)。

本机原开发工作树 `hardware-check-shared-desktop` 的 `artifacts/network-rescue/` 仍保留旧版 ZIP（早于合并和 `38d4e71`，大小 5,764,476,552 和 53,719,554）。当前 `main` 工作树的 `artifacts/network-rescue/` 已从本轮代码重建两版，包含补库驱动、`38d4e71` 的运行中安装修复和新增的 4 个华硕笔记本 WLAN 包；实体验收前以这一版为准。构建使用便携 PowerShell 7.6.0（`artifacts/tools/pwsh-7.6.0`）和完整版 `7z.exe`；7za 无法解开 Gigabyte 的 NSIS 安装包。

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `NetworkRescue-0.2.0-offline-full-portable-win-x64.zip` | 6,220,413,183 | `67AC9FEBD96D667D5F51E6A3A3D329731E2561F81D4382558AC8CFA4049D3324` |
| `NetworkRescue-0.2.0-online-install-win-x64.zip` | 53,838,958 | `7DD2B13985725CCE733F84049CE967718D283B21FEF82EA2543C1ECA1352BF48` |

## 已有验证

| 场景 | 实际结果 |
| --- | --- |
| 本地构建和测试 | `2f446fd` 原生 PE 构建、540 项核心测试、四语言窗口冒烟、Website 和 Store 负载构建通过。两个 ZIP 的 SHA-256 已复核。 |
| WinPE 空盘部署 | Hyper-V 第 2 代、无虚拟 TPM、Secure Boot 开启。Windows 11 Enterprise LTSC Evaluation 24H2 x64 在 80 GiB 空盘上经 GUI 部署，C 盘 78.73 GiB，Windows RE 已实际启动。400 GiB 空盘经 CLI 部署，C 盘 300 GiB。两个来宾确认许可后自动进桌面，均可用空密码登录。 |
| 有分区磁盘保护 | 差分盘包含已有 Windows，GUI 和 CLI 均未将其列为无人值守目标。该 Windows 仍可由离线修复功能发现。 |
| 驱动与实体联网基线 | 虚拟机用合成 RTL8156 ID 验证签名驱动入库。ROG STRIX B860-G GAMING WIFI 实卡的 MT7925 和 I226-V 均匹配签名 INF，现有 Wi-Fi 访问 HTTPS 成功。I226-V 当时未接网线。宿主驱动未重装或停用。 |
| 型号与索引 | B850M AYW GAMING WIFI 普通版包已进入两版，核验 75 个精确 PCI 子系统 ID，其中 47 个首次进入在线索引。B850M AYW GAMING WIFI-CSM 已确认板载 Wi-Fi，仍缺实际芯片和精确 INF 对应。 |
| 华硕笔记本系列拆分 | 82 个 ROG／TUF 系列拆出 333 个精确 SKU、337 条系列×SKU 记录；逐 SKU 核对 Windows 10／11 原厂下载，75 个 Win10 格和 75 个 Win11 格关闭。7 个系列仍有待核格，3 个系列未取到型号列表。 |
| 消费版断网新装 | 微软官网 Windows 11 26300 与 Windows 10 22H2 日语 ISO，四台无网卡来宾分别部署 Home、Pro，合成 I226-V 或 RTL8168 缺驱动设备。自动选择分系统的签名 INF 并入库，用户确认许可后均离线进入 `user` 桌面。 |
| PE 修复已有 Windows 10 | DISM 写入 `rt640x64.inf` 10.79.50.1003，驱动库可见。 |
| 运行中 Windows 安装 | Windows 11 LTSC 24H2 来宾中，合成 I226-V 问题码 28 被识别并匹配 `e2fn.inf`。修复前返回 `NoEligibleDevice`，修复后驱动装到设备并启用 `e2fnexpress`，因无真实硬件报告「绑定未确认」。 |
| 当前构建 | `62ab531` 的 565 项核心测试和原生 PE 构建通过。 |

详细结果见[验证记录](validation-record.md#2026-11-13-hyper-v-消费版断网部署与修复)、[型号覆盖进度](network-rescue-coverage-progress.md)和[原厂下载索引](network-rescue-driver-index.csv)。截至本次记录，`NetworkRescue-PE-Validation` 仍在运行，其余虚拟机已关机；清理 `hardware-check-shared-desktop` 前先确认没有运行中的来宾。

## 下一阶段验收

1. **实机断网恢复。** 虚拟机已覆盖流程、驱动选择、入库和离线首次设置，剩下必须用实体网卡验证的部分：驱动加载后问题码为 0、`adapter.status` 为 `Up`、取得地址和网关、DNS 与 HTTPS 成功。在可隔离的实体机器上分别测试 Wi-Fi 和有线，覆盖 Windows 10 x64 与 Windows 11 Home／Pro x64 的正在运行的 Windows、PE 修复已有系统和全新安装后首次联网。Wi-Fi 绑定后还要手动连接无线网络。先用当前 `main` 重建 ZIP，实体 I226-V 在运行中 Windows 的安装依赖 `38d4e71`。步骤、场景矩阵和只读采集脚本见[实机验收](network-rescue-field-test.md)。
2. **重点型号补库。** 先完成 AM5、LGA1851 以及较新的 Legion／ROG／TUF／Alienware，再扩到 AM4、LGA1700 和旧设备。按型号、修订和地区 SKU 对照原厂页面、硬件 ID、适用系统及签名 INF。B850M CSM 需要从该型号实卡取得 `VEN/DEV/SUBSYS` 或清晰模块标签。型号发现、候选包、精确 INF、实机安装和联网应分别计数。
3. **PE 兜底。** 当前一次注入一个签名 INF，无匹配时停止。待补多网卡驱动、确认使用系统自带驱动继续、缺存储驱动时加载，以及中断后续装。验证多盘、不同存储控制器和固件启动顺序。保留对目标盘身份和空白状态的确认。
4. **后续交付。** 在线版待做驱动升级检查与回退。Microsoft Store 当前只有 Hardware Check 负载，断网急救配置工具及跨版本联动仍待实现。GitHub Release、商店和网站各按对应交付流程处理，push 与发布须分别获得授权。
5. **已知小问题。** PE 列出 Windows 10 22H2 介质时显示 WIM 头中的构建号 19041，映像实际为 19045。Windows 11 26300 与 Windows 10 22H2 映像自带 Realtek `rt640x64.inf`，常见 RTL8168 可能无需额外驱动；实机记录时注明是否由系统自带驱动联网。

## 虚拟机实验环境

- 本机只有 Hyper-V。Windows 客户端不支持 DDA 或 USB 直通，虚拟机无法验证真实网卡加载与联网。
- 实验目录在 `hardware-check-shared-desktop/artifacts/pe-hyperv-validation/`：`consumer-media/` 有官网 ISO 和实验数据 ISO（`lab-bin3.iso` 为最新），`consumer-lab/` 有 `NR-*` 来宾，`consumer-lab/tools/` 有脚本和结果。
- `tools/Lab.psm1` 负责建来宾、建 LABOUT 日志盘、经 Hyper-V 键盘输入和截图。来宾从 `matched-setup-pe.iso` 启动后，键入 `for %d in (D E F G H I J K) do @if exist %d:\lab.cmd call %d:\lab.cmd`。`lab.cmd` 读取 LABOUT 盘的 `case.cmd` 和 `fixture-ids.txt`，把选项编号经管道交给 `PeNetworkRescue.exe`，日志写回 LABOUT。
- `tools/fixture/MissingNicFixture.exe` 创建根枚举的缺驱动网卡（问题码 28），仅用于实验来宾。`Inspect-OsDisk.ps1` 只读挂载系统盘核对分区、驱动库和首次设置日志。挂载 VHDX 需要管理员权限，本机经 `Invoke-Elevated.ps1` 执行。
- 来宾 `user` 为空密码，PowerShell Direct 不接受。`NR-W11LTSC-OS` 是旧 LTSC 盘的副本，实验账户已临时设密码，仅用于运行中安装测试。微软许可页须由用户本人确认。
- 本机默认只有 Windows PowerShell 5.1。已在 `artifacts/tools/pwsh-7.6.0` 放置便携 PowerShell 7.6.0（.NET 10）；构建前把该目录加入 `PATH`，`build-network-rescue-pe.cmd` 的文本/图标生成和 `assert-distribution.ps1` 的 .NET 10 程序集断言都依赖它。此前用 Python 生成 `PeStrings.generated.h` 的替代做法不再需要。

## 代码和构建入口

- Windows 界面为 [NetworkRescueView.cs](../src/AkikazuHardwareCheck.App/NetworkRescueView.cs)，扫描、目录、签名校验和安装逻辑在 [Core/SharedDesktop](../src/AkikazuHardwareCheck.Core/SharedDesktop/)。
- 原生 PE 代码在 [AkikazuNetworkRescue.PE](../src/AkikazuNetworkRescue.PE/)，`PeWizard.h`、`PeUnattended.h` 和 `RescueCli.h` 分别覆盖图形流程、直接部署和命令行。四语言文本来自 Core 的 Localization JSON。
- 可下载驱动定义在 [wifi-preview-packages.json](../packaging/shared-desktop/wifi-preview-packages.json)。型号和原厂链接见 [型号缺口 CSV](network-rescue-model-gaps.csv)及[原厂下载索引](network-rescue-driver-index.csv)。
- 本地验证入口为 `scripts/test.ps1`、`scripts/build-network-rescue-pe.cmd` 和 `scripts/publish-store-payload.ps1`。重建两版使用 [publish-network-rescue-bundles.ps1](../scripts/publish-network-rescue-bundles.ps1)，传入 `-IncludeCatalog`、`-VendorSourceDirectory`、`-WlanArchive`、`-PeEthernetPackDirectory` 和 `-SevenZipExecutable`。本地缓存分别在 `artifacts/vendor-wifi`、`artifacts/wlan-library/SDIO_Update/drivers/DP_WLAN-WiFi_26082.7z` 和 `artifacts/network-rescue`。产物覆盖后重新核对 ZIP 与 `.sha256`。

## 2026-11-13 原厂列表批量取证

MSI、Acer、华擎的原厂下载接口拒绝脚本直连。本轮先在浏览器里正常打开原厂页面，在同源下低速调用接口，结果压缩成 JSON 快照，并用浏览器端和本地两边的 SHA-256 核对一致后才落盘（`artifacts/network-rescue-*-api*`，不入库）。下面的脚本只读这些快照，不联网，加 `--apply-oem-evidence` 才回填主表。重复运行均为 0 项变化。

| 脚本 | 证据表 | 回填 |
| --- | --- | --- |
| `collect-msi-wlan-downloads.py` | `network-rescue-msi-oem-listing-proof.csv`、`network-rescue-msi-laptop-listing-proof.csv` | 主板 751 格，笔记本 38 格。笔记本须产品族规格页逐字列出精确型号 |
| `collect-acer-wlan-downloads.py` | `network-rescue-acer-oem-listing-proof.csv` | 263 格，另把 129 个 Win11 升级测试格加强为 WLAN 列出。按文件 `oss` 分系统，`Step3` 须等于精确型号，排除 LED 工具 |
| `collect-asrock-wlan-downloads.py` | `network-rescue-asrock-oem-listing-proof.csv` | 455 格，另补 146 款产品页规格。读 `Download.html`，PG 型号从 pg.asrock.com 单独采集 |

判定口径与华硕一致：“列出”要求已有出厂无线证据；“未列出”要求该系统有有效的 LAN 列表和音频或芯片组列表，且有出厂无线证据或规格未列 WLAN。Killer 通用包、近似型号、组合系统文件、空列表都保持待核。提交 `e22e373` 的说明写成关闭 300 格，实际是 301 格。

最新待核：主板 Win10 75、Win11 75，笔记本 Win10 296、Win11 221，合计 **667**（起点 2,570）。另有戴尔系统 ID 组合 127 个 Win10、39 个 Win11 待核，单独计数。

剩余与下一步：
- Acer：仍有 130／102 格待核。37 款接口返回空，后来被限流（Failed to fetch），冷却后重查；101 条系列行还要拆成精确 SKU。本机 `www.acer.com` 卡在 TLS 重协商，`curl`、Python 和 headless Edge 都超时，只有 `global-download.acer.com` 可读，需换网络或浏览器会话再采。
- 惠普：84 格。`hpia.hpcloud.hp.com` 的驱动包矩阵和 `ftp.hp.com` 的 SoftPaq 说明可读，但待核型号在矩阵中没有对应系统的包（2025 AI PC 无 Win10 包，2017–2019 机型无 Win11 包），HPIA 范围本身不作为结案证据。
- MSI、技嘉、映泰、联想：`www.msi.com`、`www.gigabyte.com`、`www.biostar.com.tw`、`support.lenovo.com` 均返回 403 或拒绝 headless 浏览器；`storage-asset.msi.com` 数据表和 `pcsupport.lenovo.com` 可读，但拿不到逐型号下载列表。
- 华硕主板：余 20／19 格。已用原厂手册补足 14 款「无出厂无线」证据（[手册证据](network-rescue-asus-mb-spec-proof.csv)）；另有 5 款手册明写「Notices for non Wi-Fi model」，但原厂下载页仍列 Wi-Fi 驱动，按来源冲突保留待核；12 款没有精确型号手册（CSM 变体和 TUF 系列手册）；ROG MAXIMUS Z890 HERO、B850M AYW、ROG STRIX B860-G、ProArt B850-CREATOR 只有模块候选。
- 华擎：余 19／22 格。规格页标题不匹配的 36 格，另有 5 格规格未列 WLAN 但下载列表却列出；`www.asrock.com` 现在整站返回 Incapsula 质询页，只有 `download.asrock.com` 的文件可读，需浏览器会话。
- 华硕笔记本：82 个系列已拆分 333 个精确 SKU，余 7 个系列待核格、3 个系列缺型号列表。复跑同一批证据为 0 项变化。下一步按 SKU 的原厂下载链接补包入库和实机硬件 ID。
- 联想：余 Win10 3、Win11 4 格。PSREF 规格表对 14 款在待核 Legion 全部只列 Windows 11；其中 8 款的 WLAN 驱动包元数据也只列 `Windows 11 (64-bit)`，两处一致后关闭 8 个 Win10 格。余项缺独立的整机驱动列表（`support.lenovo.com` 403，只有 `pcsupport.lenovo.com` 的单个包页面可读）。[PSREF 证据](network-rescue-lenovo-psref-proof.csv)
- MSI：主板余 10／10 格。原厂规格页明确写「WIRELESS LAN & BLUETOOTH Wi-Fi 7，模块预装于 M.2 Key-E」，逐型号驱动面板只给 Windows 11 的 MediaTek／Qualcomm Wi-Fi 驱动、Windows 10 面板有 LAN 和音频而没有 Wi-Fi 项，据此关闭 4 款 Wi-Fi 板的两个系统格。[MSI 规格证据](network-rescue-msi-spec-proof.csv) 其余型号是通用 Wi-Fi 驱动包与规格未列 WLAN 的冲突，保持待核。
- 华硕笔记本：逐 SKU 复核 `GetPDOS` 后，11 个 SKU 自身的 OS 列表不含 Windows 10，另有 2 个系列因全部 SKU 一致而关闭，共补结 13 格；余 10 格是空 OS 列表或只有非网络类目。证据见[逐 SKU OS 证据](network-rescue-asus-sku-os-proof.csv)。
- 戴尔、EVGA、技嘉、映泰：见上条与[采集交接](network-rescue-catalog-handoff.md)；戴尔的 127 个 Win10 组合是只发 Win11 的新机型没有 Win10 驱动包，缺原厂系统支持声明。
