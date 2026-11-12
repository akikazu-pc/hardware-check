# 断网急救开发交接

记录日期 2026-11-13（JST）。范围为断网急救及其与 Hardware Check 共享的 Windows 桌面入口。

## 接手基线

- GitHub 仓库为 [akikazu-pc/hardware-check](https://github.com/akikazu-pc/hardware-check)。远端 `main` 已合并至 [`ee26ee4`](https://github.com/akikazu-pc/hardware-check/commit/ee26ee4ddf2cb887c9a20c04bb4af472de6b8b42)，`proto/shared-desktop` 已删除。合并后相对该分支最后提交 `2f446fd` 的树差异只有 `AGENTS.md`。
- `1fb8dcc` 接入 PE 空盘部署，`9c55511` 收录 B850M 普通版无线驱动，`2f446fd` 修复 I226-V 兼容 ID 漏匹配。本地 `main` 的补库提交已与远端 `1347ce8` 合并到 `eebb252`，按包 ID 和行键合并索引，重复的华硕 MediaTek 3.5.0.1349 包统一为 `asus-mb-mtk-3501349`。补库流程见[采集与核验交接](network-rescue-catalog-handoff.md)。之后直接在 `main` 上开发。
- [合并后 GitHub Actions](https://github.com/akikazu-pc/hardware-check/actions/runs/43266106438)已通过。以下安装包是本地产物。本次合并尚未制作新 GitHub Release、提交商店或部署网站。

## 使用方式和交付包

| 包 | 入口 | 用途 |
| --- | --- | --- |
| 离线完整版便携 ZIP | 全部解压后运行 `NetworkRescue.exe`。明确用图形界面时加 `--gui`，命令行可用 `Run-Network-Rescue.cmd --cli`。 | 同一包适用于 Windows 和 x64 WinPE。包含 WLAN、OEM 和分系统的有线驱动。复制大文件到 U 盘时使用 exFAT 或 NTFS。 |
| 在线安装版 ZIP | 解压后运行 `Install.cmd`。 | 用已有的网络连接下载和校验原厂驱动。索引随程序发布。 |

- Windows 桌面可扫描有线／无线设备、按型号或设备类型搜索、打开官网驱动页、导出驱动 ZIP 和确认安装。存在候选分歧时，按硬件 ID 比对后选择。最终安装仍校验 INF 匹配及签名。两个应用可各自安装，也可在双装时共享窗口和托盘。日语、简体中文、繁体中文和英语可从菜单切换。
- PE 可发现已有离线 Windows 并写入网络驱动，也可为微软安装器准备选定驱动。无人值守新装从独立 x64 UEFI WinPE 启动，确认版本和空盘后直接应用映像，绕过 Windows Setup 硬件检查。要求 PE 能看到至少 64 GiB 的空盘。C 盘最多 300 GiB，较小的盘扣除启动和恢复分区后使用剩余空间。默认创建空密码本地管理员 `user`。首次出现微软许可页时由用户确认。
- 操作细节见[产品原型说明](shared-desktop-prototype.md#当前交付方式)和 [PE 安装流程](shared-desktop-prototype.md#无人值守安装验证)。

本机原开发工作树 `hardware-check-shared-desktop` 的 `artifacts/network-rescue/` 下保留以下 ZIP 及同名 `.sha256`。工作树处于分离 HEAD `2f446fd`。

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `NetworkRescue-0.2.0-offline-full-portable-win-x64.zip` | 5,764,476,552 | `0F3F43E90BFED9C5BD54D1D6F45F620C806441A6427E8E970CAAD3BD2D8FAF0B` |
| `NetworkRescue-0.2.0-online-install-win-x64.zip` | 53,719,554 | `37C138DFD894838B25954D5B5385BE4AA5FBCC9753D5B39809F01A048F6FBB72` |

## 已有验证

| 场景 | 实际结果 |
| --- | --- |
| 本地构建和测试 | `2f446fd` 原生 PE 构建、540 项核心测试、四语言窗口冒烟、Website 和 Store 负载构建通过。两个 ZIP 的 SHA-256 已复核。 |
| WinPE 空盘部署 | Hyper-V 第 2 代、无虚拟 TPM、Secure Boot 开启。Windows 11 Enterprise LTSC Evaluation 24H2 x64 在 80 GiB 空盘上经 GUI 部署，C 盘 78.73 GiB，Windows RE 已实际启动。400 GiB 空盘经 CLI 部署，C 盘 300 GiB。两个来宾确认许可后自动进桌面，均可用空密码登录。 |
| 有分区磁盘保护 | 差分盘包含已有 Windows，GUI 和 CLI 均未将其列为无人值守目标。该 Windows 仍可由离线修复功能发现。 |
| 驱动与实体联网基线 | 虚拟机用合成 RTL8156 ID 验证签名驱动入库。ROG STRIX B860-G GAMING WIFI 实卡的 MT7925 和 I226-V 均匹配签名 INF，现有 Wi-Fi 访问 HTTPS 成功。I226-V 当时未接网线。宿主驱动未重装或停用。 |
| 型号与索引 | B850M AYW GAMING WIFI 普通版包已进入两版，核验 75 个精确 PCI 子系统 ID，其中 47 个首次进入在线索引。B850M AYW GAMING WIFI-CSM 已确认板载 Wi-Fi，仍缺实际芯片和精确 INF 对应。 |

详细结果见[验证记录](validation-record.md#离线完整版的无人值守入口)、[型号覆盖进度](network-rescue-coverage-progress.md)和[原厂下载索引](network-rescue-driver-index.csv)。三台部署测试虚拟机均已关机。

## 下一阶段验收

1. **实机断网恢复。** 在可隔离的实体机器上分别测试 Wi-Fi 和有线。以缺驱动、无法联网为起点，依次记录硬件 ID、INF 签名、安装结果、驱动绑定、地址和网关、DNS 与 HTTPS。记录系统构建、INF 版本和重启要求。补测 Windows 10 x64 与 Windows 11 Home／Pro x64，分别覆盖正在运行的 Windows、PE 修复已有系统、全新安装后首次联网。步骤、场景矩阵和只读采集脚本见[实机验收](network-rescue-field-test.md)。
2. **重点型号补库。** 先完成 AM5、LGA1851 以及较新的 Legion／ROG／TUF／Alienware，再扩到 AM4、LGA1700 和旧设备。按型号、修订和地区 SKU 对照原厂页面、硬件 ID、适用系统及签名 INF。B850M CSM 需要从该型号实卡取得 `VEN/DEV/SUBSYS` 或清晰模块标签。型号发现、候选包、精确 INF、实机安装和联网应分别计数。
3. **PE 兜底。** 当前一次注入一个签名 INF，无匹配时停止。待补多网卡驱动、确认使用系统自带驱动继续、缺存储驱动时加载，以及中断后续装。验证多盘、不同存储控制器和固件启动顺序。保留对目标盘身份和空白状态的确认。
4. **后续交付。** 在线版待做驱动升级检查与回退。Microsoft Store 当前只有 Hardware Check 负载，断网急救配置工具及跨版本联动仍待实现。GitHub Release、商店和网站各按对应交付流程处理。

## 代码和构建入口

- Windows 界面为 [NetworkRescueView.cs](../src/AkikazuHardwareCheck.App/NetworkRescueView.cs)，扫描、目录、签名校验和安装逻辑在 [Core/SharedDesktop](../src/AkikazuHardwareCheck.Core/SharedDesktop/)。
- 原生 PE 代码在 [AkikazuNetworkRescue.PE](../src/AkikazuNetworkRescue.PE/)，`PeWizard.h`、`PeUnattended.h` 和 `RescueCli.h` 分别覆盖图形流程、直接部署和命令行。四语言文本来自 Core 的 Localization JSON。
- 可下载驱动定义在 [wifi-preview-packages.json](../packaging/shared-desktop/wifi-preview-packages.json)。型号和原厂链接见 [型号缺口 CSV](network-rescue-model-gaps.csv)及[原厂下载索引](network-rescue-driver-index.csv)。
- 本地验证入口为 `scripts/test.ps1`、`scripts/build-network-rescue-pe.cmd` 和 `scripts/publish-store-payload.ps1`。重建两版使用 [publish-network-rescue-bundles.ps1](../scripts/publish-network-rescue-bundles.ps1)，传入 `-IncludeCatalog`、`-VendorSourceDirectory`、`-WlanArchive`、`-PeEthernetPackDirectory` 和 `-SevenZipExecutable`。本地缓存分别在 `artifacts/vendor-wifi`、`artifacts/wlan-library/SDIO_Update/drivers/DP_WLAN-WiFi_26082.7z` 和 `artifacts/network-rescue`。产物覆盖后重新核对 ZIP 与 `.sha256`。
