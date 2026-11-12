# 统一离线安装包覆盖进度

[逐型号 Wi-Fi 缺口清单](network-rescue-model-gaps.csv)记录当前已发现的 1,237 条主板型号或修订、912 条笔记本系列或型号、1 条一体机型号，以及 167 条戴尔系统与 Windows 组合。同一台笔记本可出现在多个系统组合。

清单分别记录 `windows10X64Evidence` 和 `windows11X64Evidence`。`oem-package-indexed` 表示原厂包已入索引，`oem-wlan-listed` 表示原厂资料列出无线驱动，`oem-driver-pack-listed` 表示原厂列出该系统的整机部署包，仍需检查包内 WLAN 驱动。`oem-os-upgrade-tested` 表示原厂列出 Windows 11 升级测试，WLAN 驱动仍待核对。`pending` 表示该系统的证据待核。`oem-wlan-not-supported` 表示原厂明确说明该系统没有该出厂无线模块的驱动。仅预留接口和 ARM64 组合另有标记。原厂下载索引目前有 9 个包标注支持 Windows 10 x64，18 个包标注支持 Windows 11 x64，部分包另有最低构建号要求。[原厂下载索引](network-rescue-driver-index.csv)

| 主板范围 | 已发现的型号或修订 |
| --- | ---: |
| AM4 | 249 |
| AM5 | 367 |
| LGA1700 | 438 |
| LGA1851 | 183 |

上一轮统计中，主板有 1,112 条还需确认出厂无线状态、模块及驱动，118 条已有模块或驱动候选，仍需把所有出厂变体对应到精确 ID 和断网安装结果。B850M AYW GAMING WIFI-CSM 已确认板载 Wi-Fi，仍缺芯片证据。ROG STRIX B860-G GAMING WIFI 的本机 MT7925 子系统已匹配签名 INF，仍需核对其他出厂配置及断网安装。另有两款已确认仅预留接口。[华硕 B860-G 驱动页](https://www.asus.com/tw/supportonly/rog%20strix%20b860-g%20gaming%20wifi/helpdesk_download/)

笔记本记录包括华硕 82 条 ROG/TUF 系列和 3 条型号证据、联想拯救者 15 条型号证据、Alienware 5 条型号证据、惠普 309 条商用笔记本或二合一型号、宏碁 398 条系列或型号及微星 100 条系列或型号。戴尔的 167 条系统组合来自 52 个目录型号，含 Windows 11 x64 127 条、Windows 10 x64 39 条及 Windows 11 ARM64 1 条。完整的地区 SKU、出厂网卡组合和实机安装数据仍待采集。

华擎目录从六份原厂 CPU 支持列表提取 360 条主板型号或修订。另从映泰和 EVGA 原厂资料分别录入 14 条和 2 条。新增的 376 条主板记录都待核对出厂无线状态、模块及 Windows 10、11 驱动。[华擎型号清单](asrock-motherboard-discovery.csv) · [映泰与 EVGA 型号清单](additional-motherboard-discovery.csv)

惠普商务笔记本目录有 246 条 Windows 10 x64 部署包引用和 231 条 Windows 11 x64 部署包引用，其中 168 条列出两种系统。部署包的 WLAN 内容和消费级产品目录仍待核对。[惠普部署包矩阵](https://hpia.hpcloud.hp.com/downloads/driverpackcatalog/HP_Driverpack_Matrix_x64.html)

宏碁录入 101 条系列和 297 条型号。型号中 293 条见于原厂 Windows 11 升级测试清单，另有 4 条原厂支持页记录。微星从游戏和商务产品列表录入 24 条系列，从原厂第 12 代笔记本清单补录 76 条型号。两家目录的地区 SKU 及每个型号的 Windows 10、11 WLAN 驱动仍待核对。[笔记本补充目录](network-rescue-oem-laptops.csv) · [宏碁笔记本](https://www.acer.com/us-en/laptops) · [微星游戏笔记本](https://us.msi.com/Laptops/Products) · [微星商务笔记本](https://www.msi.com/Business-Productivity/Products)

更新补充目录后，在仓库根目录运行 `pwsh -File scripts/merge-network-rescue-model-gaps.ps1`。脚本按类型、品牌和型号合并新条目，并输出各品牌的 Windows 10、11 待核数量。

本轮复核确认 376 条新增主板记录的型号与插槽均与源表一致。抽查的 12 条华擎链接与原厂清单一致，其中 4 个旧型号页面未能提取内容。映泰目录及 EVGA 两条资料链接的实时访问仍待确认。

一体机从惠普 Presence 24 会议一体机开始录入。Windows 10 x64 已找到原厂整机部署包，包内 WLAN 驱动及 Windows 11 x64 驱动仍待核对。[一体机目录](network-rescue-oem-all-in-ones.csv) · [惠普产品规格](https://support.hp.com/gb-en/document/ish_5880723-5880767-16)

长期目录覆盖目标包括可安装 Windows 的设备。后续补录一体机、品牌台式机、迷你电脑、工作站和 Intel Mac。Intel Mac 按 Apple 型号标识收录，记录 Boot Camp 驱动包和网卡硬件 ID。覆盖记录注明 Windows 版本、x64 或 ARM64 架构，以及原生安装或虚拟机环境。[Apple Boot Camp 驱动说明](https://support.apple.com/en-gb/102465)

型号表用 `deviceCategory` 和 `deviceTag` 保存设备分类。旧记录按原类型补齐分类，Windows 驱动证据继续使用原字段。分类只用于检索。离线驱动库的范围限于恢复联网所需的 Wi-Fi 和有线网卡驱动。

日期为 2026-11-12。统一的断网急救离线包适用于桌面和笔记本，通用包与 OEM 补充包按设备 ID 和系统选取。两类设备分别验收。先核对 AM5、LGA1851 及 2025 年起出货的笔记本，完成后再系统扩展到 AM4、LGA1700 及更旧的笔记本。

| 统计范围 | 分母 | 已核对 | 比例 |
| --- | ---: | ---: | ---: |
| 华硕 AM5 / LGA1851 已知样本的板载 Wi-Fi 状态 | 101 | 99 条有板载 Wi-Fi，2 条仅有预留接口 | 100% |
| 华硕 AM5 / LGA1851 已发现的 Wi-Fi 主板样本 | 99 | 98 条有原厂手册或型号专属下载页的模块候选 | 98.99% |
| 戴尔近期笔记本，Windows 11 x64 系统 ID 组合 | 127 | 125 条有 OEM 元数据，2 条有该型号的原厂部署包公告 | 100% |
| 戴尔近期笔记本，Windows 10 x64 系统 ID 组合 | 39 | 39 条 OEM 元数据列出 WLAN INF | 100% |
| HP sp173191 文档的具体 PCI SUBSYS，在 Windows 11 构建 26300 | 23 | 23 条被离线库的签名 INF 匹配 | 100% |

华硕统计只包括已发现且明确提到 Wi-Fi 的型号。手册中有多个出厂模块的，仍待核对每种实卡硬件 ID。台式机证据见 [华硕样本](asus-recent-wireless-module-evidence.csv)和[目录](asus-motherboard-discovery.csv)。

戴尔统计以 2026-11-09 的 [Dell Driver Pack Catalog](https://downloads.dell.com/catalog/DriverPackCatalog.cab) 为分母，覆盖 52 个近期型号。不同系统 ID 和 Windows 组合分别统计。Windows 11 x64 中，P514265（0EFB）和 MB18250（0E87）的 XML 未列相同系统 ID，已分别用同一部署包编号 5D0VR A01、J0TYF A06 的型号专属公告确认 WLAN 驱动 5MPG4、KGD8K。另有一条 ARM64 记录。具体出厂 SUBSYS、签名 INF 和实机安装仍需核对。[逐条索引](dell-recent-laptop-wlan-discovery.csv)

HP 从[官方 SoftPaq](https://ftp.ext.hp.com/pub/softpaq/sp173001-173500/sp173191.html)提取了 23 个带 SUBSYS 的 PCI ID，再用应用的 SetupAPI 匹配和 INF 签名校验核对。硬件 ID 按缺驱动样例传给程序，未对本机安装驱动。一次 Windows 11 审计不能代表 Windows 10 或实机联网。

总体百分比分母尚未冻结。上述新型号缺少完整的断网实机安装与联网记录。继续补齐华硕和戴尔的出厂子系统 ID，以及技嘉、微星、华擎等新平台型号。后续按实际网卡变体分别验证 Windows 10/11。

## 优先系列覆盖

先完成近期型号，随后补齐这些系列的旧型号。100% 以各品牌冻结目录的全部机型、区域修订和有证据的出厂模块变体为分母。每条分别记录 Windows 10/11 适用性、精确硬件 ID、签名 INF 和断网实机结果。无板载 Wi-Fi 或厂商明确不支持某系统时也须有证据。厂商不支持的组合单列，不能记为可安装。

- 联想拯救者：收录 12 个近期 Legion 笔记本型号的原厂 WLAN 驱动系列证据。Intel、Realtek、MediaTek 可能同时出现在同一机型页面。后续从 PSREF 和各地区机器类型补齐完整分母。
- 华硕 ROG / TUF 笔记本：华硕全球目录接口收录 62 条 ROG、21 条 TUF 产品记录。TUF Gaming A16 的 FA608WM 和 FA608UH 已加入 OEM 驱动证据。产品记录和具体 SKU 使用不同粒度，不直接计算覆盖比例。ROG 独立站、区域 SKU、停产型号和具体模块待合并。
- 戴尔 Alienware：从其消费者支持目录逐系列核对。已有 16/18 Area-51 与 16/16X Aurora 四款的原厂手册模块证据。之前的 Dell 企业 Driver Pack 统计不代表 Alienware 覆盖。
- 华硕、微星、技嘉主板：优先覆盖四个平台的全系列与有差异的硬件修订。华硕已有 407 条全球目录记录；微星 CPU 支持目录新增 409 条可归类记录（AM4 98、AM5 113、LGA1700 146、LGA1851 52）；技嘉新增 14 条有官方来源的型号或修订发现记录。目录条目未出现 Wi-Fi 字样时继续待核。新加入微星 Z890 TOMAHAWK、技嘉 X870E AORUS MASTER 和 Z890 EAGLE 修订的无线证据。

证据文件为 [笔记本优先清单](priority-laptop-wlan-evidence.csv)、[华硕游戏本目录](asus-gaming-laptop-discovery.csv)、[微星主板目录](msi-motherboard-discovery.csv)、[技嘉主板目录](gigabyte-priority-motherboard-discovery.csv)和[主板无线证据](priority-motherboard-wlan-evidence.csv)。

本轮新增技嘉官网下载的 Qualcomm Wi-Fi 7 3.1.0.1571 包。厂商标注 Windows 11 x64。在构建 26300 上以包内 NCM865 样例 ID 通过应用 INF 匹配和签名检查。尚未测实际主板装卡和联网。

### 2026-11-12 第一批新型号资料核查

[华硕新平台手册审计](asus-recent-wlan-manual-audit.csv)对全球产品目录中 100 条提到 Wi-Fi 的记录读取英文手册，保存 PDF 和命中页码。96 条发现具体模块名，4 条最初未找到具体模块。对 4 条待查记录复核后，B860M-E 与 B860M-E-CSM 的规格明确标示无线模块另售，排除出厂 Wi-Fi。加上独立查到的 ROG MAXIMUS Z890 HERO，现有 101 条样本中 97 条有模块候选证据、2 条确认只预留接口、2 条仍待核对。按这批已知样本计算，模块资料为 97/99（97.98%），出厂无线状态资料为 99/101（98.02%）。两个剩余缺项是 PRIME B650M-A AX 与 B850M AYW GAMING WIFI-CSM。型号名称相近的 AX II 或 B850M-E 资料不代替原型号证据。

技嘉发现清单从 14 增至 24 条。新核对 5 个主板型号的 9 条模块配置，其中 B860 GAMING X WIFI6E、B860 DS3H WIFI6E、X870 GAMING X WIFI7、B860M A PRO WIFI7 各有两个模块修订。Dell 2026 年日本发布的 16X Aurora 与两款 Area-51 对应已有的 AC16251、AA16250、AA18250 型号代码。新增 Alienware 15 DA15260 及 MediaTek MT7920 模块证据。联想新增 3 款第 11 代 Legion 5 的 PSREF 资料，15IAX11 的 Wi-Fi 6E 配置列有 Killer AX1675i，Wi-Fi 7 配置模块仍待核对。另两款 PSREF 列出 Wi-Fi 世代，未确认芯片。

本批记录模块、厂商手册和目录证据。实际 SUBSYS、Windows 10/11 签名 INF 对应及实机联网尚待补验。

### 华硕与戴尔原厂包接入

华硕 TUF Gaming A16 FA608WM 新增 MediaTek 和 Realtek 两包。ROG Strix G16 G615LR 新增 Intel BE200 包。共 54 个精确 PCI/SUBSYS 条目通过 Windows 11 x64 构建 26300 的 INF 匹配和签名检查。在线目录按华硕支持范围从 Windows 11 24H2（26100）提供这些候选。来源为 [TUF FA608WM](https://www.asus.com/laptops/for-gaming/tuf-gaming/asus-tuf-gaming-a16-2025/helpdesk_download/?model2Name=FA608WM)和 [ROG G615LR](https://www.asus.com/supportonly/g615lr/helpdesk_download/)。

戴尔 7TY65 包加入在线目录和离线完整版。在线入口支持 Windows 11 x64 的 MT7925 参考子系统 PCI\VEN_14C3&DEV_7925&SUBSYS_792514C3 及下文的 AC16250 子系统。Alienware 16 Aurora AC16250 和 16X Aurora AC16251 的原厂手册列有 MT7925B22M。其他整机出厂批次的 SUBSYS 和实机联网结果仍待核验。[戴尔 7TY65 驱动及兼容列表](https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=7ty65)

打包和在线安装均先核对原包 SHA-256，再静态解出嵌入的 7z。离线文件夹扫描使用当前 Windows 的 INF 适用性和设备硬件 ID。上述结果仍需断网实机安装及联网验证。

DeepSeek Harness 为联想 DS575356 找到了 Inno Setup 静态解包路径，现已接入在线版和离线完整版。在线版按需下载并验证 InnoExtract 1.9 和联想原包的 SHA-256，离线版在打包时解出 INF 和对应文件。Windows 11 x64 构建 26300 的实际下载验证匹配了三个微软签名 INF 中的七个联想子系统 ID。MediaTek 为 DEV_7925 的 E02517AA、E0FF17AA 及 DEV_7927 的 E0E417AA。Realtek 为 DEV_B852 的 485317AA、B85317AA 及 DEV_8922 的 492217AA、492317AA。联想支持页列出 Legion 5 16IAX10、Legion Pro 5 16IAX10 和 16IAX10H，具体出厂配置对应关系仍待实机核对。[联想 DS575356](https://support.lenovo.com/ao/en/downloads/DS575356)

Alienware 16 Aurora AC16250（0D35）的三个 Ubuntu 认证配置均列出 MT7925 的子系统 `105B:E123`。戴尔 7TY65 的微软签名 INF 在 Windows 11 构建 26300 匹配 `PCI\VEN_14C3&DEV_7925&SUBSYS_E123105B`，该 ID 已加入在线目录。AC16251 的原厂资料确认 MT7925B22M，精确出厂 ID 仍待核验。[Canonical 认证记录](https://ubuntu.com/certified/platforms/15401) · [戴尔 7TY65](https://www.dell.com/support/home/en-us/drivers/driversdetails?driverid=7ty65)

### 离线归档审计与下一批型号

原 6.28 GiB ZIP 的 12,405 个文件均可完整读取并通过 CRC 校验。按内容 SHA-256 分组后有 7,170 份唯一内容，5,235 个重复副本。重复副本占原始文件约 2.94 GiB，在 ZIP 中约占 1.69 GiB。另有约 0.99 GiB 为已解包驱动对应的原始下载归档。固实 7z 成品为 1.95 GiB，减少 68.96%。全部 12,373 个驱动文件的路径、大小和 CRC 与原 ZIP 一致。这次历史归档审计时，索引记录 14 个已收录的原厂包。[驱动下载索引](network-rescue-driver-index.csv)

Windows 11 构建 26300 的最新库审计覆盖 1,666 个 INF。其中 682 个匹配当前系统的网络设备 ID，595 个通过签名检查。去重后签名有效的 ID 有 4,566 个 PCI ID 和 1,228 个 USB ID。其余 INF 仍需按系统、架构及驱动组件用途核对。

华硕 PRIME B650M-A AX 的型号专属驱动页列出 Realtek RTL8852BE，适用于 Windows 10/11 x64。原厂 ZIP 的 SHA-256、包内 INF 签名及 21 个 RTL8852BE 子系统 ID 的 Windows 11 匹配已核对，并纳入两版。整机出厂 ID 与实机安装仍待查。[PRIME B650M-A AX 下载页](https://www.asus.com/us/supportonly/prime%20b650m-a%20ax/helpdesk_download/) · [原厂 ZIP](https://dlcdnets.asus.com/pub/ASUS/mb/08WIRELESS/DRV_WiFi_RTK_8852BE_SZ-TSD1_W11_64_V6001151610_20251128R.zip)

华硕的 B850M AYW GAMING WIFI-CSM 官方规格明确列出板载 Wi-Fi 模块。已知样本的无线状态达到 101/101，其中 99 条有板载 Wi-Fi，两条仅预留接口。具体模块候选为 98/99，缺口是该 CSM 型号的芯片。普通版的 MediaTek 驱动和 -E CSM 版的 Realtek 驱动各对应自己的型号。[华硕 CSM 型号规格](https://www.asus.com/product-compare?LevelId=Motherboards-Components-Motherboards&ProductID=31128%2C28588)

复查 B850M AYW GAMING WIFI-CSM 的华硕全球、南非及沙特支持页。页面可打开，华硕型号查询接口返回空下载地址。用普通版的原厂 MediaTek 3.5.0.1349 ZIP 做候选比对，归档 SHA-256 与华硕公布值一致，`mtkwl6ex.inf` 通过签名校验。Windows 11 构建 26300 匹配了 75 个精确子系统 ID，涉及 MT7902、MT7920、MT7921、MT7922、RZ608 和 RZ616。普通版 INF 可用于核对实机硬件 ID，CSM 出厂模块仍需独立证据。[CSM 支持页](https://www.asus.com/motherboards-components/motherboards/csm/b850m-ayw-gaming-wifi-csm/helpdesk_download/?model2Name=B850M-AYW-GAMING-WIFI-CSM) · [普通版支持页](https://www.asus.com/motherboards-components/motherboards/others/b850m-ayw-gaming-wifi/helpdesk_download/?model2Name=B850M-AYW-GAMING-WIFI) · [华硕原厂 ZIP](https://dlcdnets.asus.com/pub/ASUS/mb/08WIRELESS/DRV_WiFi_MediaTek_SZ-TSD_W11_64_V3501349_20260305R.zip)


逐型号缺口清单已补入 6 条技嘉原厂包索引记录，覆盖 AM4、AM5、LGA1700 和 LGA1851。其中 5 条有 Windows 10/11 x64 的原厂包，Z890 AORUS ELITE WIFI7 的两种候选驱动包标注 Windows 11 x64。出厂网卡 SUBSYS 与断网安装仍待核对。

## 有线联网救援

设备扫描会识别缺驱动（Code 28）的 PCI 有线网卡，按实际硬件 ID 搜索本地网络类 INF。已具备驱动的 PCI 有线网卡仍显示在网络状态区。救援安装沿用硬件 ID 精确匹配和签名校验。

首批样本来自 [技嘉 B550M DS3H AC R2 Rev. 1.2 驱动页](https://www.gigabyte.com/Motherboard/B550M-DS3H-AC-R2-rev-12/Support)。两个系统的原厂压缩包独立校验。提取外层 ZIP 后，用完整版 7-Zip 解开其中的自解压包，再选取对应系统的 64 位驱动目录。用户可解压对应系统的本地驱动包，在「断网急救」中选择该文件夹扫描。

| 系统 | 原厂版本和下载 | 原厂 ZIP SHA-256 | 提取目录 | CAT 签名 |
| --- | --- | --- | --- | --- |
| Windows 10 x64 | [10.079.50.1003](https://download.gigabyte.com/FileList/Driver/mb_driver_542_w10_10.079.50.1003.zip) | `353AF723FD09FAC659341D5078B8B15D0534BE0DEF0249E411C27350AEC57821` | `mbdriver/WIN10/64` | 1 份有效 |
| Windows 11 x64 | [11.29.50.0202](https://download.gigabyte.com/FileList/Driver/mb_driver_654_w11_11.29.50.0202.zip) | `07013117E12AB44C0AFADC2D898ED4904121E56C3579DF33CE7E3F687F43AE1F` | `mbdriver/WIN11/64` | 8 份有效 |

当前离线完整版随包提供按系统分开的有线驱动目录。普通 Windows 的「安装驱动」入口和 WinPE 入口都按目标 Windows 10/11 x64 选择对应目录。对应主板的实机断网安装和联网恢复待验。上述样本单独计入有线驱动记录。

本地完整版 ZIP 已通过逐文件 SHA-256 校验，含 WinPE 入口和 1,676 个 INF，其中 Windows 10 有线目录 1 个、Windows 11 有线目录 8 个。


## 2026-11-12 开源型号与原厂驱动核查

读取 Linux Hardware Project 的 DMI Desktop 数据快照，涵盖华硕、技嘉、华擎、微星、映泰和 EVGA 六个厂商目录。以 DMI 型号中的芯片组标记推定四个平台，按品牌、平台和规范化型号与主表比对。去重后有 375 条未直接匹配的型号线索，其中技嘉 196 条、华硕 129 条、映泰 23 条、华擎 22 条、EVGA 3 条、微星 2 条。DMI 字符串可能包含别名、整机标识和已知型号的其他写法。逐条使用候选表中的固定快照链接回溯，资料来自按 CC BY 4.0 发布的 Linux Hardware Project DMI 数据。 [DMI 快照](https://github.com/linuxhw/DMI/tree/57b21bc6fdd863380e99c228c22aafcd1509528c) · [数据许可](https://github.com/linuxhw/DMI/blob/57b21bc6fdd863380e99c228c22aafcd1509528c/LICENSE) · [候选表](network-rescue-dmi-candidates.csv)

用原厂资料确认并补入 B650 AERO G rev. 1.0、B650 EAGLE AX rev. 1.0/1.1、B650 AORUS ELITE AX V2 rev. 1.0/1.1 三条新记录。技嘉 9 条主表记录已关联到 12 条 PCB 修订或修订组与原厂包的对应关系。B650 AORUS ELITE AX 的 rev. 1.0、1.1、1.2 分别对应 AMD RZ616、Intel AX210、Realtek RTL8852CE。B860 GAMING X WIFI6E 的 rev. 1.0、1.1 分别对应 Intel AX211、Realtek RTL8852CE。每条映射均附支持页和适用系统包 ID。 [逐修订包映射](network-rescue-motherboard-driver-matches.csv) · [原厂包索引](network-rescue-driver-index.csv)

本地保存了 5 个原厂 ZIP，合计约 64.4 MiB。全部静态解包，在 Windows 11 Build 26300 上通过应用的 INF 匹配与签名检查。各包的 ID 数独立统计，同一 ID 可以出现于多个包。原始文件位于 `artifacts/network-rescue-driver-research`，下载地址和 SHA-256 见原厂包索引。RTL8851BE 的两个包新增到索引，本轮未重建完整版 ZIP。

| 原厂包 | 原厂标注 | 通过签名的网络 INF | 匹配的 PCI ID |
| --- | --- | ---: | ---: |
| Intel 24.10.0.4 | Win10/11 x64 | 2 | 835 |
| Realtek 8852 6001.16.172.0 | Win10/11 x64 | 1 | 18 |
| AMD 3.3.0.496 | Win10/11 x64 | 1 | 26 |
| Realtek 8851 6001.19.119.0 | Win10 x64 | 2 | 18 |
| Realtek 8851 6101.19.134.1 | Win11 x64 | 2 | 20 |

Z790 D WIFI rev. 1.0 的下载页按系统列出 Realtek 8851 驱动。解包后在 INF 中确认 RTL8851BE（`PCI\VEN_10EC&DEV_B851`）是包内候选，主板实机 SUBSYS 尚未确认。Win10 包也在当前 Win11 开发机上做了静态匹配和签名检查，Win10 上的适用性以厂商标注为依据，仍待 Win10 实机验证。 [Z790 下载页](https://www.gigabyte.com/de/Motherboard/Z790-D-WIFI-rev-10/support)

B550 UD WIFI6E rev. 1.2 的支持页列出适用两个系统的 MediaTek Wi-Fi 6E 包。抓到的旧版 3.05.00.1349 下载链接返回 404，新版 3.5.0.1392 的直接链接未取得，因此只记录下载页证据。A520I AC rev. 1.5 的支持页把 Realtek WLAN 包标为仅适用于 rev. 1.4，保留待核。MSI MAG Z890 TOMAHAWK WIFI 的官方规格只列 Win11 x64，Win10 更新为厂商未列支持，Win11 驱动包匹配仍待核。 [B550 支持页](https://www.gigabyte.com/ca/Motherboard/B550-UD-WIFI6E-rev-12/support) · [A520I 支持页](https://www.gigabyte.com/Motherboard/A520I-AC-rev-15/support) · [微星规格](https://www.msi.com/Motherboard/MAG-Z890-TOMAHAWK-WIFI/Specification)

| 平台 | 主板记录 | Win10 x64 待核 | Win11 x64 待核 |
| --- | ---: | ---: | ---: |
| AM4 | 249 | 245 | 245 |
| AM5 | 367 | 359 | 358 |
| LGA1700 | 438 | 436 | 436 |
| LGA1851 | 183 | 178 | 177 |
| 合计 | 1,237 | 1,218 | 1,216 |

上述待核数字按主表中 `pending` 字段计数。只有厂商页面证据或原厂包索引的条目仍需完成实机验证。375 条开源型号线索中还有 372 条未完成原厂型号核对。下一批优先核查已有明确型号支持页的待核记录，再用已验证型号补充开源线索。所有新增映射仍需获取出厂网卡 SUBSYS，按目标 Windows 测试离线安装、重启后的驱动绑定和联网。


### 技嘉支持页与驱动复查

先保留原厂 URL 中的完整型号和 PCB 修订，例如 `B550-UD-WIFI6E-rev-12` 或 `A520I-AC-rev-15`。技嘉产品页采用 `/Motherboard/<型号及修订>/support` 查询下载，末尾替换为 `/sp` 可查询规格。全球页打不开或资料缺失时，可在 `/Motherboard/` 前试用已有的地区前缀，例如 `/us`、`/eu`、`/jp`。也可查 AORUS 的 `/motherboards/<型号及修订>/support/driver`。这些地址作为查询入口，打开后核对页面标题、PCB 修订、驱动下载项自身的限制和 Windows 版本。下载链接应从原厂页面提取，文件名不按模板推算。

- **B550 UD WIFI6E rev. 1.2**。技嘉规格确认 MediaTek MT7902。通过同修订的 AORUS 支持页取得原厂 3.5.0.1392 ZIP，原厂标注 Win10/11 x64。已保存到本地研究目录，静态解开 ZIP 里的 NSIS 安装包，未运行安装程序。Win11 Build 26300 的审计匹配 1 个有效签名 INF、78 个 PCI ID，其中 12 个是 MT7902 的精确子系统 ID。驱动已入索引，出厂实机 SUBSYS 和安装待验。 [原厂规格](https://www.gigabyte.com/us/Motherboard/B550-UD-WIFI6E-rev-12/sp) · [AORUS 下载页](https://www.aorus.com/pk/motherboards/B550-UD-WIFI6E-rev-12/support/driver)
- **A520I AC rev. 1.5**。技嘉规格和该修订手册确认 AzureWave AW-CB304NF（Realtek RTL8821CE）。复查了 2024.10.138.3 原厂 ZIP，SHA-256 与已有索引一致。Win11 Build 26300 匹配了 40 个 RTL8821CE 的精确子系统 ID，其中 11 个子系统厂商为 AzureWave。下载项仍明确标注仅适用于 rev. 1.4。两套系统的 rev. 1.5 驱动匹配仍待实机 ID 或原厂说明确认。 [原厂规格](https://www.gigabyte.com/eu/Motherboard/A520I-AC-rev-15/sp) · [原厂下载页](https://www.gigabyte.com/eu/Motherboard/A520I-AC-rev-15/support)

本次更新了原厂包索引与型号证据，B550 的系统状态从原厂列出提升为包已入索引。两条记录的 `pending` 计数因此维持 Win10 1,218 条、Win11 1,216 条。完整版 ZIP 尚未重建。


### 待核清单清理与完整版收录

主板表的 `pending` 表示该主板记录在对应 Windows 版本的原厂 WLAN 证据仍待核实。可能缺出厂无线状态、具体模块、适用包或修订限制。已有原厂包证据的记录仍可能缺实机 SUBSYS、驱动绑定和联网结果，这些缺口保留在 `gap` 和逐修订映射的字段中。

已核对 X870 GAMING X WIFI7 rev. 1.0／1.1 的原厂手册和支持页，两条关联现有 MT7925／RTL8922AE 包，Win10 标记为原厂下载页未列 WLAN 包。B860 DS3H WIFI6E rev. 1.0 的 AX211 已关联现有 Win10/11 Intel 包，rev. 1.1 仍待核对对应修订的下载项。Z790 D WIFI rev. 1.0 的原厂手册无线认证表确认 RTL8851BE，已补入模块证据。 [X870 支持页](https://www.gigabyte.com/eu/Motherboard/X870-GAMING-X-WIFI7-rev-1x/support) · [B860 支持页](https://www.gigabyte.com/us/Motherboard/B860-DS3H-WIFI6E-rev-10/support) · [Z790 手册](https://download.gigabyte.com/FileList/Manual/mb_manual_z790-d_series_1005_e.pdf?v=5374f4d5a8cf166aca24724729b39334)

待核计数降至 Win10 **1,215** 条、Win11 **1,213** 条。两套系统各有 **1,106** 条共用的主板记录仍需先核对出厂无线状态。型号及修订应按原厂目录批量取得支持页，再按下载地址和 SHA-256 去重，复用已解析的 INF 和签名证据。网页修订冲突、模块变体和出厂实机 ID 需要逐条核对。

完整版打包现从原厂索引取得 B550 MT7902 和 Z790 RTL8851BE 的三份原包，校验 SHA-256 后静态解包。MT7902 放入 Win10 和 Win11 目录，RTL8851BE 的两份包各取其对应系统的驱动目录。普通 Windows 与 WinPE 共用按目标系统选择的补充目录。


### 华硕规格批量重跑

先按品牌取得原厂型号清单，再批量查型号专属规格，最后处理缺页、同型号不同修订及冲突证据。每次合并保留已有原厂包和实机证据。核对系统和驱动时，按原厂下载链接和 SHA-256 复用包级结论，再关联型号及 PCB 修订。现有逐修订映射的 30 个系统与包关联只引用 8 个不同包。

本批处理华硕目录 407 条。采集器核对返回路径与页面内型号，要求有 CPU、芯片组和两类接口等规格字段。384 条取得可分类证据，包括 7 条列出具体模块、160 条列出无线规格、66 条明确只提供插槽或模块另售、151 条规格未列 WLAN。其余 23 条规格不完整或含糊。抽查了 H610M-AYW D4、PRIME B650-PLUS 和 TUF GAMING B550M-E WIFI。 [规格审计表](asus-wlan-spec-audit.csv) · [H610M-AYW D4](https://www.asus.com/motherboards-components/motherboards/others/h610m-ayw-d4/techspec/) · [PRIME B650-PLUS 原厂手册](https://dlcdnets.asus.com/pub/ASUS/mb/Socket%20AM5/PRIME_B650-PLUS/E20333_PRIME_B650-PLUS_UM_WEB.pdf?model=PRIME+B650-PLUS) · [TUF GAMING B550M-E WIFI](https://www.asus.com/uk/motherboards-components/motherboards/all-series/tuf-gaming-b550m-e-wifi/techspec/)

合并更新 285 条原来仅有目录证据的主板记录。64 条确认未随板提供 WLAN 模块，从两个系统的待核数中移出。70 条补上出厂无线规格或模块证据，151 条规格未列无线并继续待核。型号总数保持 1,237 条，Win10／Win11 待核分别为 **1,151／1,149** 条。本批没有新增驱动包。

在仓库根目录运行以下命令。默认复用已成功分类的同型号规格，重查未验证的记录；全量刷新时加 `--refresh`。首次执行 407 条，第二次只请求 26 条，并从中补回 3 条。微星抽样请求返回 403，华擎抽样返回验证页，两个品牌需要单独验证可读取的原厂入口。

```powershell
python scripts/collect-asus-wlan-specs.py docs/asus-motherboard-discovery.csv docs/asus-wlan-spec-audit.csv
pwsh -File scripts/merge-network-rescue-model-gaps.ps1
```


### 微星规格书与华擎手册补查

微星地区规格页直连仍返回 403，改用官方静态规格书，核对 PDF 内的型号后解析无线栏。批量处理 409 条，34 条规格书给出具体模块，216 条给出无线规格，132 条未列无线，27 条未取到可分类证据。主表回填微星 381 条，其中 33 条新增模块字段。规格书未列无线的条目仍待核。 [微星规格书审计](msi-wlan-datasheet-audit.csv) · [微星 AX200 样例](https://storage-asset.msi.com/datasheet/mb/global/MPG-B550-GAMING-CARBON-WIFI.pdf)

华擎手册直连初轮可用，扩大批次后连续返回 403。初轮结果未在刷新时保留。本轮只合并能独立复核的型号证据，采集器已修正为下载失败时保留已有成功记录。共补齐 9 条华擎无线证据。其中 X870E Taichi、X870E Taichi Lite、X870E Nova WiFi、B650 Rock WiFi 7、B850 Steel Legend WiFi 的原厂规格明确说明随板无线模块无 Win10 驱动，Win11 驱动包和实机 SUBSYS 仍待核。 [华擎手册审计](asrock-wlan-manual-audit.csv) · [X870E Taichi](https://www.asrock.com/mb/AMD/X870E%20Taichi/index.asp) · [B850 Steel Legend WiFi](https://asrock.com/mb/AMD/B850%20Steel%20Legend%20WiFi/index.asp)

主表共回填 390 条。主板总数为 1,237，Win10 待核降至 **1,146**，Win11 待核仍为 **1,149**。未新增驱动包或重建完整版 ZIP。华硕剩余 23 条以美国、英国地区规格页重查，仍缺足够证据。

```powershell
python scripts/collect-oem-wlan-documents.py --brand MSI docs/msi-motherboard-discovery.csv docs/msi-wlan-datasheet-audit.csv
python scripts/collect-oem-wlan-documents.py --brand ASRock --workers 2 --limit 137 docs/asrock-motherboard-discovery.csv docs/asrock-wlan-manual-audit.csv
pwsh -File scripts/merge-network-rescue-model-gaps.ps1
```
