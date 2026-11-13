# 统一离线安装包覆盖进度

继续维护时参见[采集与核验交接](network-rescue-catalog-handoff.md)和[断网急救开发交接](network-rescue-handoff.md)。

[逐型号 Wi-Fi 缺口清单](network-rescue-model-gaps.csv)记录当前已发现的 1,237 条主板型号或修订、1,253 条笔记本型号或系列记录、1 条一体机型号，以及 167 条戴尔系统与 Windows 组合。华硕 ROG／TUF 的 82 个系列已拆成 333 个精确 SKU。

清单分别记录 `windows10X64Evidence` 和 `windows11X64Evidence`。`oem-package-indexed` 表示原厂包已入索引，`oem-wlan-listed` 表示原厂资料列出无线驱动，`oem-driver-pack-listed` 表示原厂列出该系统的整机部署包，仍需检查包内 WLAN 驱动。`oem-os-upgrade-tested` 表示原厂列出 Windows 11 升级测试，WLAN 驱动仍待核对。`pending` 表示该系统的证据待核。`oem-wlan-not-supported` 表示原厂明确说明该系统没有该出厂无线模块的驱动。仅预留接口和 ARM64 组合另有标记。原厂下载索引目前有 23 个包标注支持 Windows 10 x64，38 个包标注支持 Windows 11 x64，部分包另有最低构建号要求。[原厂下载索引](network-rescue-driver-index.csv)

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

### B850M AYW GAMING WIFI 普通版驱动入库

华硕普通版支持页将 MediaTek 3.5.0.1349 标注为 Windows 10/11 x64。已核对原厂 ZIP 的 SHA-256 和 mtkwl6ex.inf 的签名。INF 使用 16299 构建起的 x64 型号节。Windows 11 构建 26300 的 SetupAPI 验证了 75 个精确 PCI 子系统 ID，其中 47 个此前未在在线包目录中出现，5 个属于 MT7902。两种发行包使用同一索引。已用应用实际下载并重新校验 ZIP 与签名 INF，目录测试覆盖构建 19045、26100 及低于门槛的 16298。Windows 10 实际安装待验。[华硕普通版驱动页](https://www.asus.com/motherboards-components/motherboards/others/b850m-ayw-gaming-wifi/helpdesk_download?model2Name=B850M-AYW-GAMING-WIFI)

精确 CSM SKU 的华硕支持 ID 为 32852，普通版与 -E CSM 的 ID 分别为 32839 和 38840。CSM 规格列出 1×1 Wi-Fi 6 和 Realtek 2.5GbE，未标明无线芯片。跨地区查询的 CSM 下载入口仍无驱动数据。逐型号索引只为普通版列出上述包，CSM 记录仍待实机硬件 ID 确认。[CSM 规格](https://www.asus.com/motherboards-components/motherboards/csm/b850m-ayw-gaming-wifi-csm/techspec/) · [华硕型号映射](https://odinapi.asus.com/recent-data/apiv2/ModelMapping?SystemCode=asus&WebsiteCode=global&Model1WebPath=b850m-ayw-gaming-wifi-csm&Model2WebPath=B850M-AYW-GAMING-WIFI-CSM&siteID=www&sitelang=)

## 有线联网救援

设备扫描会识别缺驱动（Code 28）的 PCI 有线网卡，按实际硬件 ID 搜索本地网络类 INF。已具备驱动的 PCI 有线网卡仍显示在网络状态区。救援安装沿用硬件 ID 精确匹配和签名校验。

首批样本来自 [技嘉 B550M DS3H AC R2 Rev. 1.2 驱动页](https://www.gigabyte.com/Motherboard/B550M-DS3H-AC-R2-rev-12/Support)。两个系统的原厂压缩包独立校验。提取外层 ZIP 后，用完整版 7-Zip 解开其中的自解压包，再选取对应系统的 64 位驱动目录。用户可解压对应系统的本地驱动包，在「断网急救」中选择该文件夹扫描。

| 系统 | 原厂版本和下载 | 原厂 ZIP SHA-256 | 提取目录 | CAT 签名 |
| --- | --- | --- | --- | --- |
| Windows 10 x64 | [10.079.50.1003](https://download.gigabyte.com/FileList/Driver/mb_driver_542_w10_10.079.50.1003.zip) | `353AF723FD09FAC659341D5078B8B15D0534BE0DEF0249E411C27350AEC57821` | `mbdriver/WIN10/64` | 1 份有效 |
| Windows 11 x64 | [11.29.50.0202](https://download.gigabyte.com/FileList/Driver/mb_driver_654_w11_11.29.50.0202.zip) | `07013117E12AB44C0AFADC2D898ED4904121E56C3579DF33CE7E3F687F43AE1F` | `mbdriver/WIN11/64` | 8 份有效 |

当前离线完整版随包提供按系统分开的有线驱动目录。普通 Windows 的「安装驱动」入口和 WinPE 入口都按目标 Windows 10/11 x64 选择对应目录。对应主板的实机断网安装和联网恢复待验。上述样本单独计入有线驱动记录。

本地完整版 ZIP 已通过逐文件 SHA-256 校验，含 WinPE 入口和 1,676 个 INF，其中 Windows 10 有线目录 1 个、Windows 11 有线目录 8 个。

### Intel PCIe 与 Realtek USB 有线补充

| 来源 | 系统 | 已核对的签名 INF |
| --- | --- | --- |
| [技嘉 B760M D3H Rev. 1.x 驱动页](https://www.gigabyte.com/eu/Motherboard/B760M-D3H-rev-1x/support)的 Intel I225/I226 有线包 | Windows 10 x64，构建 17763 起；Windows 11 x64 | `e2f.inf` 1.1.4.38、`e2fn.inf` 2.1.5.7 |
| 同一技嘉页面的 Intel Gigabit Ethernet 包 | Windows 10 x64，构建 17763 起；Windows 11 x64 | `e1d.inf` 12.19.2.61、`e1dn.inf` 20.0.3.9 |
| [华硕 USB-C2500 V2 驱动页](https://www.asus.com/networking-iot-servers/wired-solutions/wired-adapters/usb-c2500-v2/helpdesk_download?model2Name=USB-C2500-V2)的 1001 版 USB 有线包 | Windows 10 x64、Windows 11 x64 | Windows 10 的 `rtump64x64sta.INF`，Windows 11 的六份 `rtu*cx22x64sta.INF` |

四份原厂 ZIP 形成六条按系统区分的候选记录。下载直链、SHA-256、版本及系统范围见 [驱动索引](network-rescue-driver-index.csv)。型号列记录原厂页面及对应驱动系列。设备实际适用性以安装时读取的硬件 ID、系统构建和签名 INF 为准。

Windows 11 已通过应用实际下载、校验并匹配 Intel I226、I219 与 RTL8156 三个硬件 ID 样本。Windows 10 核对了 INF、CAT 签名和目录选择规则，实体网卡安装与联网待验证。Intel 通用下载页要求接受许可，本轮使用技嘉提供的 OEM 来源。本轮生成本地测试包。

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


### 已知无线模块的批量驱动映射

本批核对 141 条有网卡型号候选的主板记录，涵盖华硕 98 条、技嘉 9 条和微星 34 条。按已记录的模块或芯片族建立 157 条映射，均能在当前完整版 ZIP 中找到 Win11 Build 26300 上通过签名检查的 PCI INF 候选。表中示例硬件 ID 来自 INF。具体主板的出厂 SUBSYS 和断网联网仍待实机验证。 [主板与 INF 候选表](network-rescue-motherboard-inf-candidates.csv)

华硕原厂下载接口按型号和 Win10/Win11 分别查询，返回 181 个型号与系统组合的 WLAN 下载证据，涉及 93 个不同 URL。其中 MediaTek 3.5.0.1349 在 92 个组合重复出现。新增 MediaTek 两包、Realtek RTL8851BE 两包、Intel 一包，均在本地保存原档并静态解包，新增原厂包已进入本地 ZIP。对成品重新提取审计，共 1,688 个 INF，其中 617 个通过当前构建的匹配与签名检查，签名有效的 PCI 和 USB ID 去重后分别为 17,555 和 1,228。新增包让更多型号能关联到原厂指定下载，去重后的 ID 数在这次 Win11 审计中保持一致。 [华硕下载审计](asus-wlan-download-audit.csv) · [原厂下载索引](network-rescue-driver-index.csv)

仅在当前记录的所有已知模块都能同时对应到原厂列出的适用包和 ZIP 内签名 INF 时，更新该系统的主表状态。Win10 回填 65 条、Win11 回填 73 条，共涉及 73 条主板记录。待核降至 Win10 **1,081**、Win11 **1,076**。Win10 的原厂支持状态根据原厂接口及包索引填写，仍未在 Win10 环境实测签名匹配或联网。微星和技嘉本轮的 43 条已有模块记录补到 INF 候选阶段，其型号专属包证据仍待补齐。

采集器 `scripts/collect-asus-wlan-downloads.py` 复用成功的查询。解压完整版 ZIP 的 `driver-packs` 和 `pe-drivers` 后，用 `scripts/audit-network-rescue-library.ps1 -EvidenceCsv` 导出签名 INF 证据。再用 `scripts/map-network-rescue-wlan.py` 生成本批候选表。核对结果后加 `--apply` 可回填主表，后续批次使用新的输出路径保存快照。


### 跨厂商快照、驱动复用与第二轮验证

本轮验证了微星支持 JSON、技嘉下载中心 JSON 和华擎静态下载表。前两个接口在本机返回 403，华擎下载表返回验证页。改用 WinDriverIndex 的静态数据先建立队列。校验板型目录、驱动族和原厂包表的快照 SHA-256，再按品牌、插槽、完整型号及修订关联逐板记录。原厂包候选同时要求厂商、驱动族、版本和发布日期一致，且只能匹配到一个归档。相同 SHA-256 只下载和验证一次。同版快照用本地缓存重新计算 1,071 条候选记录耗时约 0.37 秒，输出 SHA-256 一致。 [WinDriverIndex 设计](https://github.com/dtucny/WinDriverIndex/blob/main/doc/spec.md) · [快照清单](https://windriverindex.tucny.com/v1/latest/manifest.json)

该批为 426 条主板找到 485 条唯一包线索，涉及 66 个不同下载地址。58 条主板已有线索与原 ZIP 中原厂归档的 SHA-256 一致。本轮按复用数选择 6 个微星归档，全部从微星 CDN 下载并匹配快照 SHA-256。六包在本地 ZIP 内的驱动目录通过 Win11 Build 26300 匹配及签名检查，共 9 个签名 INF，关联 222 条主板的 239 条第三方候选线索。第三方快照未提供 PCB 和出厂 SUBSYS 对应，主表不会据此认定单板原厂包或实机覆盖。候选表改编自 [WinDriverIndex by dtucny](https://windriverindex.tucny.com)，按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 使用。 [快照关联审计](network-rescue-windriverindex-audit.csv) · [原厂包索引](network-rescue-driver-index.csv)

华擎手册改用 curl 读取官方 PDF，恢复 97 条先前缺少的无线规格证据。另回查技嘉原厂下载项及原厂手册，把 B860M C、B850M AORUS ELITE WIFI7 ICE-P、Z890 EAGLE WIFI7 rev. 1.0 与 rev. 1.1 共四条关联到 ZIP 中已有的 Win11 签名驱动。原厂无线下载栏未列 Win10 WLAN 包。主板待核降至 Win10 **1,077**、Win11 **1,072**。 [技嘉修订映射](network-rescue-motherboard-driver-matches.csv) · [华擎手册审计](asrock-wlan-manual-audit.csv)

普通 Windows 便携版与 WinPE 现在共用完整版的最低构建号列表。只标注 Win11 的 OEM 包从 Windows 10 自动扫描入口排除。旧版无列表的便携包继续使用原目录扫描。已通过 Windows 10、Windows 11 及 Win11 24H2 最低构建号的目录选择回归测试。仍需实机验证出厂网卡 ID、驱动绑定和断网恢复。


### 按新增主板候选选择下载

先读取现有 ZIP 中实际包含 INF 的原厂包目录，再按索引的原包 SHA-256 排除已收录的驱动。候选范围取 Win11 待核主板。每选一个包，就从其他包的得分中扣掉已经获得候选的型号。试跑前有 270 条待核主板已有同一快照的包候选。用同样的三包预算，按原始出现次数和原表顺序选包新增 52 条候选，按去重后的新增数选择则新增 **60 条**。原始排名第三、第四的两个包各出现 13 次，扣除已收录和当轮已选覆盖后，分别贡献 5 条和 13 条。 [优先顺序与原包 SHA-256](network-rescue-wlan-priority-round.csv) · [WinDriverIndex 快照来源](https://windriverindex.tucny.com/)

| 优先包 | 新增主板候选 | Win11 26300 签名 INF |
| --- | ---: | ---: |
| 华硕 Intel 24.20.0.4 | 26 | 2 |
| 华擎 AzureWave RTL8922AE EB601NF | 21 | 1 |
| 华擎 Intel 23.170.0.1G | 13 | 2 |

三份驱动均从厂商 CDN 下载，与快照 SHA-256 一致，已静态解包并收录到完整版 ZIP。华硕以精确型号重新请求原厂接口，在 26 条主板的 Win10 和 Win11 下载栏均核对到同一 SHA-256，因此两套系统各将 26 条回填为 `oem-wlan-listed`。仍需确认这些主板具体出厂模块和 SUBSYS。两份华擎包保留 Win11 候选范围，华擎型号专属下载页仍未能稳定读取。Win10 待核降至 **1,051**，Win11 待核降至 **1,046**。 [华硕原厂下载审计](asus-wlan-download-audit.csv) · [华硕原厂样例](https://www.asus.com/us/motherboards-components/motherboards/prime/prime-z690-p-wifi/helpdesk_download?model2Name=PRIME-Z690-P-WIFI)

后续以当前主表、原厂包索引、快照审计和完整版 ZIP 为输入运行 `scripts/rank-network-rescue-wlan-packages.py`。华硕下载采集器支持 `--model-list`，可针对入选包涉及的型号补查原厂系统和下载证据。

成品验收发现 AzureWave 原厂版本名含下划线，原有目录筛选跳过了该包。普通 Windows 与 WinPE 的包名检查已允许下划线。对新版 ZIP 的系统清单复查，本轮新增包在 Win10 扫描中可见 1 个，在 Win11 可见 3 个。


### 优先回填 ZIP 已收录的原厂包

复算上轮的三包预算，按出现次数选包可为 52 条主板增加候选，按新增主板去重选择可增加 60 条，增加 8 条约 15.4%。该排序作为新增驱动包的选择方法。开始选新包前，先用现有 ZIP 的包回查原厂型号下载栏，减少重复下载与重打包。

本轮选择 78 条已有原厂无线规格或模块证据的华硕主板，共 147 条待核系统记录。先按公开快照分组，再用型号专属原厂接口对照 SHA-256、原厂系统、ZIP 实际 INF 路径及最低构建号。重用组 46 条主板中，38 条取得包与型号一致的原厂证据。另 32 条对照组未取得一致的现有包证据。本样本如果先处理重用组，可用 46 条主板查询范围取得同样的结果，范围缩小约 41%。这项比例只适用于本轮样本。 [华硕原厂下载审计](asus-wlan-download-audit.csv) · [已收录包复用审计](network-rescue-bundled-wlan-reuse-audit.csv)

从现有 ZIP 提取华硕原厂驱动目录，在 Win11 Build 26300 上确认 16 个签名 PCI INF。Win10 回填 28 条、Win11 回填 38 条，待核分别降至 **1,023／1,008**。回填使用 `oem-wlan-listed`，后续仍需确认各出厂模块变体。原先记录了多模块的型号，本轮尚无一条能把所有已知模块同时关联到适用原厂包。未下载新驱动或重建 ZIP。

用 `scripts/audit-network-rescue-library.ps1 -EvidenceCsv` 导出成品内签名 INF，再用 `scripts/reconcile-asus-bundled-wlan.py` 输出待核条目的原厂包证据。审阅后用 `--apply` 回填。本轮只将具备出厂无线规格或模块证据、原厂下载 SHA-256 一致、且包内有签名 PCI INF 的条目提升为原厂列出。


### 先复用原厂包，再按缺失网卡变体选包

上一轮的复用优先法已纳入流程。该对照样本的 66 条原厂证据全来自 46 条有复用线索的主板，另外 32 条未命中。先查复用线索在这一样本中可以少查约 41% 的主板，而且无需新增归档或重打包。该比例作为本轮样本结果保留，其他厂商与平台仍需单独测量。

本轮先用当前 ZIP 的签名 INF 计算每个主板与系统组合尚缺哪些已知出厂模块，再根据原厂下载项名称中明确写出的网卡型号安排下载。原厂标题只用于排队，最终使用同型号的下载证据和成品签名 INF 确认。两包预算下，按原厂下载项出现次数选出的两包均面向 Win11，合计只涉及 13 条不同记录。按缺失模块选出的 Win11、Win10 RTL8922AE 包共出现在 22 条不同原厂记录中，验签后补齐全部已知模块的有 **17 条**。另外 5 条 Win10 记录仍缺随板 MediaTek 变体的适用包。 [变体选包结果](network-rescue-wlan-variant-priority.csv) · [逐型号模块验收](network-rescue-wlan-variant-audit.csv)

成品使用 Win10 对应的 `netrtwlane701.inf` 和 Win11 对应的 `netrtwlane711.inf`。两包原档与华硕发布的 SHA-256 一致。回填 Win10 4 条、Win11 13 条。其中 8 条 Win11 原先已有下载页证据，本轮提升为所有已知变体均有原厂包。待核降至 **Win10 1,019／Win11 1,003**。本轮签名与匹配审计在 Win11 Build 26300 执行，仍需在目标 Win10/11 实机确认出厂 SUBSYS、驱动绑定和恢复联网。

继续使用 `scripts/map-network-rescue-wlan.py --include-listed --rank-output` 生成下一批候选。先按原厂 SHA-256 下载，再从成品提取签名 INF 并用 `--apply` 回填完整变体证据。


### 成品 ZIP 签名审计缓存

采纳按缺失模块选包。上轮同样是两包预算，按下载项出现次数排序最多涉及 13 条不同型号与系统记录。按缺失变体排序后，成品实测补齐了 17 条记录的所有已知模块，包含 Win10 4 条和 Win11 13 条。用官方标题排序，用成品 INF 审计验收。

本轮将成品签名审计按包缓存。每次先计算完整 ZIP SHA-256。ZIP 相同就直接复用；ZIP 改变时用各包的完整文件路径和内容 SHA-256 判断哪些结果仍可复用。缓存按本机、Windows 构建号、架构和审计程序版本隔离。长路径会让 Windows 的 INF 或 CAT 验证漏报，验证脚本将文件提取到系统临时目录的短路径。缓存用于本地批次复查，发行前或签名信任环境变化时使用 `--fresh` 重新验签。

| 实测场景 | 验签目录 | 复用目录 | 耗时 |
| --- | ---: | ---: | ---: |
| 当前完整版 ZIP 冷跑 | 39 | 0 | 80.28 秒 |
| 同一 ZIP 热跑 | 0 | 39 | 3.63 秒 |

两次证据 CSV 的 SHA-256 一致，含 633 个签名 INF，去重后有 17,555 个 PCI ID 和 1,228 个 USB ID。另用成品的两份原厂驱动模拟增量 ZIP，新加入一份时只重新验签一个目录，58 条匹配证据与全新审计完全一致。ZIP 变更仍需读取包文件计算 SHA-256，本轮没有将小样本耗时外推到完整 ZIP。

用热跑证据重跑当前模块映射，剩余记录未出现新的完整映射。现有原厂标题中另有一份 Realtek 包可供后续核查一条 Win11 组合。本轮未新增驱动、未改主表、未重建 ZIP。

```powershell
python scripts/audit-network-rescue-zip.py <完整版ZIP> <本地缓存目录> <签名证据CSV>
```

## 双击检查新主板与新版驱动

在 Windows 上双击 `scripts/update-network-rescue.cmd`，也可运行 `python scripts/update-network-rescue.py`。需要 Python 3.11 或更新版本、支持 ETag 参数的 `curl` 和 PowerShell 7。默认保存到 `artifacts/network-rescue-update/`，同一目录只允许一个更新进程。

1. 首次运行用 WinDriverIndex 的主板、驱动家族和包元数据建立基线。之后先比较三份数据的 SHA-256，仅下载变化或缺失的数据文件。无变化且没有待重试项时结束。
2. 主板按厂商、插槽、规范化型号和 revision 比较。范围为 ASUS、ASRock、技嘉和 MSI 的 AM4、AM5、LGA1700、LGA1851。新型号才查询单板报告，核对快照、厂商和型号，按厂商、无线家族、版本、日期查找唯一包。多个哈希对应同一组键时不自动关联。
3. 仅处理带哈希的 Win10/11 64 位非 beta WLAN 原厂包。以 SHA-256 去重，识别同一原厂地址换包，并复用索引中已经收录的包。下载后校验哈希，直接 ZIP 中的网络 INF/CAT 使用现有脚本验签。EXE 或内嵌归档保留原件，标记为待静态提取。
4. `last-run.json` 记录当次结果，`last-delta.json` 记录最近一次快照差异，`state.json` 保存主板候选对应关系和重试队列。通过验签的候选放在 `verified/`。单板报告关联和签名证据供型号、系统及硬件 ID 核对。运行脚本不安装驱动，发行 ZIP 仍需按发行流程验收与生成。

现有签名缓存继续用于本地成品复查，发行仍以 `--fresh` 的验签为准。线上首次读取了清单与三份数据，三份数据合计约 14.5 MiB。重复运行只请求清单一次，下载了 0 份元数据和 0 个驱动包。这次线上快照没有变化。 [WinDriverIndex 快照清单](https://windriverindex.tucny.com/v1/latest/manifest.json)

下一轮优化将原来每条 WLAN 报告扫描一遍包列表改成构建一次组合键索引。若有 `P` 个包和 `Q` 条需匹配的报告行，匹配由 `O(P×Q)` 降为平均 `O(P+Q)`，保留唯一匹配规则。受控增量测试模拟一块新板、同地址换包和首次哈希失败。三个元数据文件中只下载两份变化文件，重试时下载零份元数据，真实 ASUS ZIP 通过验签并留下 1 个签名网络 INF。尚无线上批量新板数据可衡量索引带来的实际耗时变化。

### 新增品牌与重复下载优化

- **NZXT** 从官方主板下载目录一次读取型号和 WLAN 下载表。官方表格未明确标注 Windows 版本时，记录包和型号的候选关系，系统范围继续通过 INF 核实。 [NZXT 主板下载目录](https://support.nzxt.com/hc/en-us/sections/39003384521627-Motherboards)
- **七彩虹** 读取官方七个主板系列。按目标芯片组或明确无线名称筛选优先查询支持页的型号，再核对驱动类别、WLAN 标题、Win10/11 64 位和官方 CDN。型号名未命中筛选条件的仍保留在目录。 [七彩虹主板支持样例](https://www.colorful.cn/Home/GetProductDownload?mid=84&id=36280e3a-e942-4b36-80ce-befe5b3758f5)
- **EVGA** 读取官方目录中的 Z690、Z790、X570 主板部件号，选取 Win10 64 位和 Win11 的最新 WLAN 条目。按 ETag 请求目录，服务器返回 304 时复用本地目录。 [EVGA 下载中心](https://www.evga.com/support/drivers/index.html)
- 各品牌分别写入 `nzxt/last-run.json`、`colorful/last-run.json` 和 `evga/last-run.json`。一个下载地址可关联多块主板，下载完成后记录本地 SHA-256。官方列表未提供独立的发布者哈希。下次相同地址且驱动条目未变化时复用已处理结果，地址或条目版本变化时重新处理。地址与条目信息均不变的原地换包仍待增加 CDN 版本检查。
- 映射基准用现有快照的 145 个候选包和 195 次查询。9 轮中位数从 2.169 毫秒降至 0.032 毫秒，两种算法的候选列表一致，单条查询有建索引开销。新一轮验证共用 URL 和变更重查，受控测试三次运行的包下载次数为 1、0、1。
- 线上 NZXT 读到 10 个型号和 11 条 WLAN 记录，合并为 10 个下载地址。5 个包验得共 9 个签名网络 INF，3 个包待静态提取，另 2 个包在本机未取得有效签名证据。重复运行复用 10 个地址，下载 0 个包。七彩虹发现 492 个唯一型号，查询 230 个型号的支持记录，18 条 WLAN 记录合并为 3 个已下载的原厂包，3 个均待静态提取。
- EVGA 官方目录首轮返回 200，重复请求返回 304，节省约 9.2 MiB 目录传输。两次均解析到 3 个主板部件号、7 条最新 WLAN 记录和 4 个唯一地址。
- 映泰官方目录本次返回 403。铭瑄已核验官方目录及两款 B850 WLAN 条目，待接入批量更新。 [映泰主板目录](https://www.biostar.com.tw/app/en/mb/index.php) · [铭瑄支持](https://www.maxsun.com/pages/support)

### 笔记本与日本、中国本土型号

双击原有更新脚本会同时检查笔记本。只跑笔记本可执行 `python scripts/update-network-rescue.py --laptops-only`。首次扫描本土品牌保存型号与原厂 WLAN 下载基线。此后新地址、原厂条目版本变化或新型号引用尚未下载的地址时下载并验签，也可附加 `--backfill-laptops` 下载既有候选。原厂目录、已列 WLAN 下载、签名 INF 和实机覆盖分别记账。

WinDriverIndex 中 1,296 个笔记本型号标识已生成 `artifacts/network-rescue-update/laptops.json`，包括 Dell 474、联想 441、HP 381。键采用厂商和原厂产品 ID，保留可用的 SMBIOS 标识。该快照分支提供型号目录，型号与 WLAN 驱动的对应关系仍需原厂支持资料核实。笔记本专用模式首次只下载 `boards.json`，再次运行只请求清单。主板模式继续使用同一份缓存数据。 [WinDriverIndex 快照清单](https://windriverindex.tucny.com/v1/latest/manifest.json)

- **日本 Panasonic Let's note**，24 个系列、265 个型号前缀。核查最新 6 个系列的 53 个型号页，74 条 WLAN 记录合并为 8 个 Win11 x64 原厂 EXE 地址。CF-FC7C 样本已实际下载并保存哈希，待静态提取。 [Panasonic 机型支持](https://jp-pc-support.connect.panasonic.com/)
- **日本 Dynabook**，从 Win11 25H2 兼容性目录收录 915 个完整型号和 149 个原厂通配模式。驱动入口需要确认厂商许可，本轮保存兼容目录。 [Dynabook 兼容机型](https://dynabook.com/assistpc/osup/win11_25h2/target/index_j.htm)
- **中国小米／REDMI**，81 个型号支持条目，80 个型号列出 WLAN 下载，共 62 个唯一原厂地址。实下载 REDMI Book 14／16 2025 AMD 共用的 ZIP，Windows 验签取得 2 个签名网络 INF。 [小米驱动目录](https://www.mi.com/service/notebook/drivers) · [REDMI Book 16 2025 AMD](https://www.mi.com/service/notebook/drivers/TM2423)
- **中国荣耀**，8 个系列的 187 个原厂配置代码，其中 133 个列出 WLAN，共 65 个唯一原厂地址。实下载 MagicBook Art 14 2025 原厂 ZIP，里面还有内嵌 ZIP，暂待静态提取。原厂记录未标明系统版本时保留空值。 [荣耀驱动目录](https://www.honor.com/cn/support/downloads/)
- 富士通 FMV 已查到具体型号的原厂 WLAN 页面和再分发限制。华为已查到按型号查询的官方入口。两家待补批量来源核验。 [富士通驱动说明](https://azby.fmworld.net/app/customer/driversearch/pc/drvdownload?driverNumber=E1033939&mode=0) · [华为驱动目录](https://consumer.huawei.com/cn/support/driver-list/)

笔记本专用模式完整复跑成功。共复用 Panasonic、小米和荣耀 135 个已记录下载条目，下载 0 个驱动包。受控用例核对了首次建立基线、相同条目复用、新型号关联既有地址触发下载、主动补采和原厂版本变化触发重查。

### 其他整机与独立网卡

双击更新同时检查其他设备。单独运行使用 `python scripts/update-network-rescue.py --devices-only`。首次保存独立网卡原厂下载基线，之后按地址、条目版本和型号关联变化取包。需要补采既有候选时可加 `--backfill-devices`。整机、Intel Mac 和 Surface 记录用于型号发现与原厂支持定位。

- **品牌整机**，`devices.json` 收录 Dell 240、HP 303、联想 179，共 722 个原厂产品 ID。按名称证据标注品牌台式机 378、一体机 129、迷你电脑 77、工作站 99，另有 52 条形态待核。标签可重叠。例如 Dell Precision 5470 的快照类型是 desktop，原厂标为移动工作站，因此不据快照将它计入台式工作站。 [WinDriverIndex 快照](https://windriverindex.tucny.com/v1/latest/manifest.json) · [Dell Precision 5470](https://www.dell.com/en-us/shop/precision-mobile-workstations/14-5470-workstation/spd/precision-14-5470-laptop)
- **Intel Mac**，收录 59 个 Apple Model Identifier，仅按官方 Windows 10 x64 Boot Camp 兼容范围。 [Boot Camp 支持范围](https://support.apple.com/en-us/102622) · [原厂驱动说明](https://support.apple.com/en-us/102465)
- **Microsoft Surface**，收录 25 条 Surface Pro／Go 平板型号与驱动固件包页面，以及 3 条 Surface Studio 一体机记录。整机 MSI 可能同时含固件，本轮保存官方包页面，WLAN INF 和各 Windows 构建适用范围待核。 [Microsoft Surface 驱动固件目录](https://learn.microsoft.com/en-us/surface/Manage-surface-driver-and-firmware-updates)
- **Windows 掌机**，ROG Ally 全球产品目录收录 6 个原厂 SKU 条目，含套装 SKU。WLAN 包待逐型号核对。 [ROG Ally 产品目录](https://rog.asus.com/gaming-handhelds/rog-ally-series/)
- **TP-Link 独立网卡**，美国支持站覆盖 89 个产品、214 条型号修订，含 USB 无线 101、USB 有线 30、PCIe 无线 64、PCI／PCIe 有线 19。实测 60 个原厂下载地址、118 条修订与下载地址的关联。TX401 原厂 ZIP 实下载验得 2 个签名网络 INF。Archer TX20U Plus 样本 ZIP 内含安装程序，待静态提取。 [TP-Link 下载中心](https://www.tp-link.com/us/support/download/) · [TX401 V2.60 支持页](https://www.tp-link.com/us/support/download/tx401/v2.60/)

沿用上轮验证过的按地址复用方法。其他设备模式从空缓存只读取一份 `boards.json`，重复运行下载 0 份快照数据，笔记本模式也能直接复用该文件。TP-Link 直接复用 89 个型号页已显示的默认修订，实跑 215 次目录请求，较逐条重查的 304 次少 29.3%。完整复跑复用 60 个已记录下载地址，未下载驱动包。另用不同 URL 指向同一真实驱动 ZIP 做受控测试，两个地址各下载一次，匹配同一 SHA-256 后 Windows 验签从 2 次减为 1 次，两个型号关联和每条记录的 2 个签名 INF 证据均保留。该优化仅复用本次运行中同字节包的验签结果。

### 固定分母与缺口补录

本轮以 2026-11-02 WinDriverIndex 快照中四厂商、四插槽的主板，以及 Dell、HP、联想的笔记本和品牌整机为统一样本。共 3,996 条原厂产品记录。主板 1,978 条，占 49.50%；笔记本 1,296 条，占 32.43%；品牌整机 722 条，占 18.07%。样本按产品记录计数，独立网卡、区域品牌、Apple、Surface 和掌机另按各自原厂目录计数。当前无可核实的全球 Windows 装机型号与无线变体分母。 [WinDriverIndex 快照](https://windriverindex.tucny.com/v1/latest/manifest.json)

样本目录从 3,994/3,996 增至 3,996/3,996。保留型号名里的 `+` 后，华擎 A620M-HDV/M.2 和 A620M-HDV/M.2+ 分别入库。在线迁移只查询了两块板的报告，复用了全部快照数据。两款原厂规格均注明 Wi-Fi 模块不随板附送。已回填主表，Win10 待核由 1,019 降到 1,017，Win11 由 1,003 降到 1,001。主表 1,237 条内，Win10 OEM WLAN 列出或入索引 140 条，占 11.32%，Win11 有 168 条，占 13.58%。各系统均有 68 条确认无出厂 Wi-Fi。 [A620M-HDV/M.2 规格](https://asrock.com/mb/amd/A620M-HDVM.2/) · [A620M-HDV/M.2+ 规格](https://asrock.com/MB/AMD/A620M-HDVM.2%2B/index.nl.asp)

| 原厂样本 | OEM 下载关联 | 本机有签名 INF 的样本关联 |
| --- | ---: | ---: |
| TP-Link 美国站 USB 无线 | 47/101（46.53%） | 4/101（3.96%） |
| TP-Link 美国站 PCIe 无线 | 45/64（70.31%） | 3/64（4.69%） |
| TP-Link 美国站 USB 有线 | 14/30（46.67%） | 2/30（6.67%） |
| TP-Link 美国站 PCI／PCIe 有线 | 4/19（21.05%） | 2/19（10.53%） |
| D-Link 美国／加拿大站 | 3/34（8.82%） | 1/34（2.94%） |
| 小米／REDMI | 80/81（98.77%） | 2/81（2.47%） |
| 荣耀 | 133/187（71.12%） | 本轮未验得 |
| Panasonic | 52/265（19.62%），已查页 52/53 | 本轮未验得 |

D-Link 本轮补入 34 个原厂网卡型号。首批检查 7 个型号的 11 个修订，保存 3 个原厂地址并实际下载，DUB-1312 Rev A 验得 1 个签名网络 INF。TP-Link 另抽查 3 个 USB Wi-Fi 包，Archer T3U Plus 和 T4U Plus 的包各验得 2 个签名网络 INF，合计补入 4 条修订关联。TP-Link 整体为 110/214（51.40%）有下载关联，11/214（5.14%）有本机签名包样本。其余目录型号继续核查，已列出的包也需核对目标系统和实机。 [D-Link 原厂目录](https://support.dlink.com/allpro.aspx) · [DUB-1312 支持页](https://support.dlink.com/ProductInfo.aspx?m=DUB-1312) · [TP-Link 下载中心](https://www.tp-link.com/us/support/download/)

同为 5 个包的预算，按源顺序选包涉及 11 条不同修订，按尚无验签包的修订数逐次选包涉及 34 条。两组都实下载，前者有 2 条修订关联到签名 INF 包，后者有 3 条。本轮采纳该排序用于限量补采，可执行 `python scripts/update-network-rescue.py --devices-only --backfill-devices --device-backfill-limit 5`。新版本和失败重试仍按正常更新流程处理。

下一轮试验先检查 ZIP 目录。两个真实 TP-Link 包直接可见的 `.inf` 只有 `autorun.inf`，跳过无效验签并标记待静态提取，旧记录可用已保存的原档重分类。用 `python scripts/report-network-rescue-coverage.py` 复算固定快照与主表。另存的设备批次可用 `--device-state`，实下载样本可用 `--evidence 品牌 报告路径` 加入，要求原厂 URL、型号身份与条目版本相符。签名比例记录当前 Windows 环境的包证据，实机绑定、出厂硬件 ID 和恢复联网仍待验证。

### 将原厂目录接入应用检索

型号补充目录现随应用嵌入。导出 **6,660 条源记录**，含主板 2,483、笔记本 3,061、其他设备 1,116。与既有主表合并后，应用返回 7,406 条可检索记录，按主板 2,651、笔记本 3,761、其他设备 994 分组。营销名称和原厂型号代码同时可查，同名机型有不同支持页时保留可区分的产品标识。实测 6,660/6,660 条源记录均能通过应用检索接口查到，并逐条验证 7,323 次非通配别名查询。这个 100% 以本次接入源记录为分母，全球常规民用设备仍缺完整分母。

新增日本富士通 FMV 民用升级目录。一次请求收录 221 个商品名及 710 个不同的零售型号代码。验证 `FMVA40FWJ2` 可查到 `LIFEBOOK AH40/F1`。该来源记录 Windows 11 升级目录与型号，网卡包仍需逐型号核对。 [富士通 FMV 原厂目录](https://azby.fmworld.net/support/win/11/info/)

采纳只在加载时规范化品牌、型号和别名。用同一旧目录和固定 1,440 次搜索做七轮对照，中位数从 740.2 毫秒降到 179.6 毫秒，约快 4.12 倍。计时未包含首次加载和界面绘制。下一轮试验用 OEM 产品代码和 SMBIOS 别名扩展检索，并保留 `+`、独立网卡修订及同名机型的支持页区别。

驱动继续按包核验。另下载 6 个 TP-Link 原厂 ZIP，5 个包在 Windows 11 Build 26300 验得 16 个签名网络 INF，关联 7 条新核修订。UE302C 的包仍待静态提取。D-Link DUB-1312 Rev A 已按 `USB\VID_2001&PID_4A00` 接入在线下载和本地离线构建清单。实测应用从原厂下载、校验 SHA-256、解出驱动并匹配该 ID。另生成仅含此包的本地 ZIP，重新提取验得 1 个签名 INF。Win10 原厂列出，目标 Win10 与实机联网仍待验证。 [TP-Link Archer T3U 支持](https://www.tp-link.com/us/support/download/archer-t3u/v1/) · [D-Link DUB-1312 支持](https://support.dlink.com/ProductInfo.aspx?m=DUB-1312)

先用更新脚本刷新来源，再运行 `python scripts/export-network-rescue-search.py` 重建嵌入目录。设备来源另存于其他状态目录时，传入 `--device-state`。仓库测试覆盖原厂代码、硬件修订、分类和 D-Link 精确硬件 ID。

### 补齐设备分类与多语言模糊搜索

逐一核对应用的 12 个其他设备子类。之前有 8 个子类存在型号记录。本轮加入 20 条 LattePanda 单板机 SKU、2 条 ASRock Beebox HTPC 和 2 条 Microsoft Lumia 手机，增至 11/12 个子类。Lumia 只记录 Windows 10 Mobile 型号，Win10/11 x64 驱动栏标为范围之外。改装 Chromebook 仍待取得逐型号原生 Windows 与网卡证据。Google 的 Chromebook 文档所述 Windows 运行方式为虚拟机。 [LattePanda 官方目录](https://docs.lattepanda.com/) · [Beebox 原厂公告](https://www.asrock.com/news/index.asp?iD=3033) · [Microsoft Lumia 公告](https://news.microsoft.com/en-in/lumia-950-and-lumia-950-xl-launch-in-india/) · [Google 官方说明](https://support.google.com/chrome/a/answer/10044480?hl=en)

新增简中、繁中、日文和英文的品牌／类别词查询，并统一全角型号字符。精确、前缀和包含匹配优先。无结果时才尝试一次增删、替换或相邻字符交换，保留型号中的数字顺序和 `+`，并提示用户核对完整型号和修订。下一轮补测了无空格的品牌加类别查询，以及省略网卡硬件修订的错字查询。`小米笔记本ＴＭ２４２３` 可精确定位型号，`Arhcer T3U Plus` 可显示相关修订，输入 `V1.60` 后保持该修订。

在 27,576 个检索键上，以相同规则比较模糊候选全扫和按数字序列与 `+` 分组。七轮、每轮 1,400 次查询，结果一致，候选阶段中位耗时由 64.097 毫秒降到 1.172 毫秒，约 54.7 倍。已采纳分组，计时未包含首次建索引、精确匹配或界面绘制。完整回查 6,684 条源记录和 7,577 次别名查询，应用合并后有 7,430 条可检索记录。

另核实 A620AM Pro RS、A620AM Pro-A、B650M-HDV/M.2、B650M-HDV/M.2 White、B650M-H/M.2+、B650M PG Lightning 均不随板附送 Wi-Fi 模块。Win10 待核从 1,017 降至 1,011，Win11 从 1,001 降至 995。A520M-ITX/ac、A520M/ac、B550M-ITX/ac、B550M/ac 的逐板报告与候选包版本一致但日期不一致，仍待原厂关联确认。本轮没有新增驱动包。 [华擎 A620AM Pro RS](https://asrock.com/MB/AMD/A620AM%20Pro%20RS/index.asp) · [华擎 B650M-HDV/M.2](https://asrock.com/MB/AMD/B650M-HDVM.2/index.asp)

### 待核短板与分批取证

- 主板主表本轮后仍有 Win10 1,000/1,237（80.84%）和 Win11 983/1,237（79.47%）待核。MSI 与华擎合计占待核的 74.70% 和 76.60%。Win11 最大三类缺口为芯片对应精确硬件 ID 及安装（340）、出厂无线状态及驱动（314）、原厂未列无线状态仍需确认（283）。`report-network-rescue-coverage.py` 新增按系统、厂商、缺口和系列层级统计。
- 笔记本主表 Win10 666/912、Win11 382/912 待核。Win11 中 207 条只到系列粒度。Acer 的 105 条里有 101 条仅为系列，后续需先取得零售 SKU。Dell 的单系统组合单独计数，避免把未适用系统的占位栏计入积压。 [Acer 官方驱动选取说明](https://community.acer.com/en/en/kb/articles/19713-downloading-the-correct-drivers-for-your-acer-computer)
- 核实 8 款华擎 LGA1700 主板的原厂规格均注明不随板附送 Wi-Fi 模块，两栏回填。另核实技嘉 B840M FORCE WIFI6E、B860 DS3H WIFI6E Rev. 1.0、Z890 UD WIFI6E Rev. 1.2/1.3 的 Win10/11 WLAN 列表，及 X870E AORUS MASTER X3D ICE 的 Win11 WLAN 列表。技嘉只提升到 OEM 列出下载，包与出厂子系统 ID 仍待核。合计关闭 23 个型号与系统待核格。 [华擎 B660 Pro RS](https://asrock.com/MB/Intel/B660%20Pro%20RS/index.asp) · [技嘉 B840M](https://www.gigabyte.com/Motherboard/B840M-FORCE-WIFI6E/support) · [技嘉 B860](https://www.gigabyte.com/Motherboard/B860-DS3H-WIFI6E-rev-10/support) · [技嘉 Z890](https://www.gigabyte.com/Motherboard/Z890-UD-WIFI6E-rev-12-13/support) · [技嘉 X870E](https://www.gigabyte.com/Motherboard/X870E-AORUS-MASTER-X3D-ICE/Support)
- 采纳先用原厂规格矩阵按系列取证。两张 MSI 规格表覆盖 12 个精确型号，平均每张回填 6 条；相对于每个型号单独查一页的比较口径，所需页面数少 10 张。Creator M16 五款确认 Wi-Fi 6，Vector GP76 七款确认 Wi-Fi 6E，均列出出厂 Win11。由于具体芯片和 WLAN 下载仍未确认，驱动待核数不变。 [MSI Creator M16](https://www.msi.com/Content-Creation/Creator-M16-A12UX/Specification) · [MSI Vector GP76](https://www.msi.com/Laptop/Vector-GP76-12UX/Specification)
- 下一轮试验用原厂无线合规声明绕开动态下载表的型号发现瓶颈。两份 Acer 声明为 4 条精确待核记录中的 3 条补足候选，A515-48M 为 MT7922A22M，A515-58P 和 58PT 的共享声明列出 AX211NGW、AX203NGW、AX201NGW。保留原支持页，候选仍需精确 SKU 和 Windows 驱动包核对。 [A515-48M 声明](https://global-download.acer.com/GDFiles/Document/CE%20DoC/CE%20DoC_Acer_1.0_A_A.pdf?BC=ACER&LC=en&OS=ALL&SC=PA_6&Step3=ASPIRE+A515-48M&acerid=638164580301702705) · [A515-58P／58PT 声明](https://global-download.acer.com/GDFiles/Document/CE%20DoC/CE%20DoC_Acer_1.0_A_A.pdf?BC=ACER&LC=en&OS=ALL&SC=AAP_2&Step3=ASPIRE+A515-58P&acerid=638133403978665442)

额外实查四块技嘉板的同代逐板报告。六条 WLAN 家族版本中，五条有唯一同日期候选，B840M 一条在逐板报告与归档目录相差一天。保留日期检查，四块板都不据此自动提升为包已入库。A520I AC Rev. 1.5 官方规格列 RTL8821CE，下载项却写仅限 PCB Rev. 1.4，继续保持修订冲突。 [A520I Rev. 1.5 规格](https://www.gigabyte.com/eu/Motherboard/A520I-AC-rev-15/sp) · [下载页](https://www.gigabyte.com/eu/Motherboard/A520I-AC-rev-15/support)

### 零售 SKU 与签名包候选

- Acer 原厂商品页补入 4 个此前未收录的精确 SKU。PHN14-71-906J、PH18-71-756U、PH16-71-74UU 均明确列出 Killer AX1675i，仍待原厂包和实卡 ID。SFG14-01-X006 是 Qualcomm ARM64，原厂只列 802.11be 无线规格。四个料号均可在应用内检索。主表笔记本从 912 增到 916 条，x64 待核分别增加 3 条至 Win10 669、Win11 385，原有系列行保留。 [PHN14-71](https://store.acer.com/en-us/predator-helios-neo-14-ai-gaming-laptop-phn14-71-906j) · [PH18-71](https://store.acer.com/en-us/predator-helios-18-gaming-laptop-ph18-71-756u) · [PH16-71](https://store.acer.com/en-us/predator-helios-16-gaming-laptop-geforce-rtxtm-4060-ph16-71-74uu) · [SFG14-01](https://store.acer.com/en-us/swift-go-14-ai-laptop-sfg14-01-x006)
- 华擎 X870 Steel Legend WiFi、Challenger WiFi、Challenger WiFi White、Nova WiFi、Taichi Creator 的原厂规格明确其出厂 Wi-Fi 7 无 Win10 驱动。Win10 主板待核从 1,000 降至 995，Win11 仍为 983。应用详情显示原厂不支持的结论，ARM64 与 Windows 10 Mobile 等记录统一标为 Windows x64 核验范围外。 [Steel Legend 原厂规格](https://www.asrock.com/mb/AMD/X870%20Steel%20Legend%20WiFi/index.asp) · [Nova 原厂手册](https://download.asrock.com/Manual/X870%20Nova%20WiFi.pdf)
- 技嘉 B840M FORCE WIFI6E 核实 MT7902、B860 DS3H WIFI6E PCB 1.0 核实 AX211、X870E AORUS MASTER X3D ICE 核实 MT7927。按具体芯片重跑 4 个已有驱动目录，在 Win11 Build 26300 上验得对应签名 INF。该证据仅支持芯片候选，各板出厂 SUBSYS 和实机仍待核。PCB 1.0 与 1.1 的无线芯片不同，沿用逐修订规则。 [B840M 规格](https://www.gigabyte.com/ph/Motherboard/B840M-FORCE-WIFI6E/sp) · [B860 规格](https://www.gigabyte.com/eu/Motherboard/B860-DS3H-WIFI6E-rev-10/sp) · [X870E 规格](https://www.gigabyte.com/Motherboard/X870E-AORUS-MASTER-X3D-ICE/sp)
- 保留原厂合规声明作模块线索，并采纳优先查精确零售页。前一轮两份合规声明只能把候选缩小到三条精确型号，本轮 4 个零售页直接明确了 4 个料号和 CPU 架构，3 个还明确到网卡型号。两个样本的证据层级不同，未将差异解释为普遍提速。
- 下一轮试验按逐板快照的精确型号、家族、版本和日期关联，再按包哈希去重。9 块板的 10 条候选关联实际只下载 5 个 OEM ZIP，全部通过哈希校验，共验得 7 个签名 INF。对已有的 4 个包，5 个签名 INF 的文件哈希与本地完整 ZIP 中对应文件逐一相同。Steel Legend 的 MediaTek 5.7.0.6342 是新样本，已保存，未纳入发行。原厂逐板下载页未独立核实，主表 Win11 保持待核。包内 Win10 目录也不覆盖华擎明确的 Win11-only 声明。 [候选关联记录](network-rescue-board-package-candidates.csv)

### 连续多轮核验

1. **出厂配置**。逐型号核对 29 款华擎主板。13 款原厂注明仅预留无线接口，两系统共关闭 26 格。另 16 款原厂明确出厂无线模块无 Win10 驱动，只关闭 Win10 栏。仅说明 Win11 才有 6 GHz 功能的资料未用于判断 Win10 驱动。 [仅预留示例](https://www.asrock.com/mb/AMD/A620AM-HVS/index.us.asp) · [明确系统限制示例](https://pg.asrock.com/MB/AMD/B650M%20PG%20Riptide%20WiFi%20White/index.asp)
2. **精确笔记本下载**。复查 12 条联想 Win11 x64 待核，8 条找到精确型号的原厂下载页，实取 7 个包符合厂商 SHA-256。DS577742 两次下载得相同字节，但与厂商发布哈希不同，只保留下载列表证据。另 3 条只有公告线索，1 条只有 SKU 无线规格。Legion 7 16IAX10 的 DS575326 用校验过的 InnoExtract 静态提取，Win11 Build 26300 验得 2 个签名 INF 和 5 个联想 SUBSYS。五个 ID 均已被既有包覆盖，所以新增型号专属索引，未增加重复自动下载项。 [DS575326](https://support.lenovo.com/in/en/downloads/DS575326) · [DS577742](https://support.lenovo.com/ky/en/downloads/ds577742) · [DS578842](https://support.lenovo.com/gr/en/downloads/ds578842) · [DS579323](https://support.lenovo.com/uu/en/downloads/ds579323)
3. **采纳按哈希批量复用**。扫过当轮 991 条适用的主板待核记录，得到 409 条唯一逐板包关联。MSI 中 222 款板的 239 条关联集中于 6 个已收录包。用本地原包哈希、离线 ZIP 中对应 INF 的字节和当前系统签名逐一复核，实际检查 6 个包、验得 9 个签名 INF，新增下载为零。`collect-windriverindex-wlan.py --package-plan <输出JSON>` 按哈希生成批次并按型号数排序。厂商逐板下载页仍未独立核实，保留主表 OEM 待核状态。 [候选关联记录](network-rescue-board-package-candidates.csv) · [WinDriverIndex 快照](https://windriverindex.tucny.com/v1/latest/manifest.json)
4. **下一轮试验静态拆封装**。华擎 Intel 23.40.0.4_240516 的原厂 ZIP 仅有安装器。试验从内部 CAB 和清单恢复 19 个 WLAN 文件，全程未运行厂商安装器，Win11 Build 26300 验得 3 个签名 INF，补足 8 条逐板候选关联。另一个 Intel 22.70.2.1G ZIP 与快照哈希不符，停止使用该包，未回填候选。 [华擎 23.40.0.4 原包](https://download.asrock.com/Drivers/Intel/WLAN/Intel_WLAN(v23.40.0.4_240516).zip)

合计关闭 **50 个待核格**。主板 Win10 995→966、Win11 983→970。笔记本 Win10 仍为 669，Win11 385→377。候选关联表由 10 增至 252 条。余项集中在逐板原厂关联、精确零售 SKU、出厂硬件 ID 以及实际安装测试，待核尚未清空。主表不会用快照中的缺项、不同哈希的下载或当前系统的一次签名审计代替这些证据。

### 批量扩查与新来源复核

| 路线 | 实测结果 | 结案口径 |
| --- | --- | --- |
| 华硕精确型号下载接口 | 220 款待核，实际重新查询 192 款。确认 51 个有 OEM x64 WLAN 列表的系统格，另有 12 个响应虽列下载但缺出厂无线证据，未回填 | 51 个下载列表待核格 |
| 华硕完整列表复查 | 16 个已有出厂 Wi-Fi 的 Win10 项，15 个返回有效的 LAN 和音频或芯片组列表，但无 WLAN 类目或文件 | 15 个标为 OEM 列表未列，保留系统兼容性未知 |
| 华擎原厂手册 CDN | 140 个候选中取得 136 份 PDF。确认 16 款仅预留，27 款出厂无线仅 Win11 | 59 个系统格，基于包装清单与型号专属规格 |
| 技嘉原厂下载页 | 四款型号列出可适用的 x64 WLAN 下载 | 5 个系统格，未提升到签名或实机 |
| 惠普精确 HPIA 引用 | 47 份 Win11 22H2 x64 CAB 覆盖 57 款待核，产生 96 条型号与包的关联 | 57 个 Win11 下载列表格，保留型号与包的完整关系 |

华硕脚本增加全量待核模式、厂商 x64 文件名范围核对及出厂无线门槛。空响应、只有未解析类目的响应和普通板共用驱动列表都不用于回填。对同一批已核证据再次应用产生 0 项变化。华擎直连 HTML 在本机测试的 4 个地址均未返回有效产品正文，PDF 路线继续用于明确变体。 [华硕逐项证据](network-rescue-asus-oem-listing-proof.csv) · [华擎型号与手册页码](network-rescue-asrock-variant-proof.csv) · [技嘉下载示例](https://www.gigabyte.com/ie/Motherboard/X870E-AORUS-PRO-X3D-ICE/support)

采纳惠普按 SMBIOS SystemID 和 Windows 版本查 HPIA 的方法。第一轮通过 SoftPaq 适用列表找到 30 款，第二轮用 SMBIOS 定位后增补 27 款。每条均检查精确 ProductName、SystemID、活动 WLAN Solution、设备引用和 Windows 11 22H2。另 63 条 HP Win10 待核虽不在 HPIA 的支持配置内，仍缺原厂 WLAN 的独立结论，保持待核。Win11 余 21 条中，20 条也只有 HPIA 配置范围说明。 [HP 原厂矩阵](https://hpia.hpcloud.hp.com/downloads/driverpackcatalog/HP_Driverpack_Matrix_x64.html) · [精确引用与哈希](network-rescue-hp-wlan-reference.csv)

下一轮试验对惠普 SoftPaq 按有效的嵌入归档头与校验值静态提取。抽验 4 个包均符合原厂哈希。`sp165709` 进一步在 Win11 Build 26300 验得 2 个签名网络 INF，关联 19 款 OEM 型号，仍需确认各机型实际安装的网卡。另按已核哈希批查 17 个主板包，11 个验得共 20 个签名 INF，新增 37 条候选关联。4 个包在本机未验得签名 INF，2 个未通过包校验；未用这些结果关闭主表。 [逐板候选证据](network-rescue-board-package-candidates.csv)

这一阶段合计关闭 **187 个待核格**。主板 Win10 966→880、Win11 970→926，笔记本 Win10 仍为 669，Win11 377→320。其余仍需补精确零售 SKU、逐板 OEM 页面、适用的原厂包或实机硬件 ID。HPIA 范围限制、原厂列表缺项、哈希冲突和封装解析失败分别保留证据，避免把这些情况归为已验证驱动。

追加复查 Acer 精确机型时，确认 Aspire A515-41G 的原厂目录列 Windows 10 和 802.11ac。其型号未进入 Acer Win11 升级测试目录，原厂说明未列机型的驱动未随该计划更新。保留 Win11 WLAN 待核。 [原厂产品目录](https://www.acerid.com/content/uploads/downloads/2017/12/Catalogue-Consumer-Q4-2017.pdf) · [Acer Win11 升级目录](https://www.acer.com/gb-en/support/windows/windows-11-compatibility)

继续跑华擎剩余变体，另外 195 个候选手册地址中有 189 个可读。结合 AM4 的原厂产品规格页，再确认 20 款仅预留和 X870E Taichi OCF 无 Win10 出厂无线驱动，额外关闭 41 格。此轮累计关闭 **228 格**，最新待核为主板 Win10 859、Win11 906，笔记本 Win10 669、Win11 320。 [X870E Taichi OCF 手册](https://download.asrock.com/Manual/X870E%20Taichi%20OCF.pdf) · [华擎变体核验](network-rescue-asrock-variant-proof.csv)

华擎后续批次实查 14 个精确快照指向的 OEM ZIP，9 个通过哈希及签名核验，共 18 个签名 INF、43 款板的 50 条候选关系。31 款关联的两个已有包各自完成 INF 字节复核。与此前批次去重后，这一轮追加 27 条，逐板候选表从本阶段开始的 252 增至 316 条。逐板原厂下载页仍未能独立读取，Win11 主表不因候选晋升而关闭。 [逐板候选证据](network-rescue-board-package-candidates.csv)

再试一轮把华硕的「原厂列表是否列出」和「是否配备出厂无线模块」分开取证。筛出 93 款原厂完整规格未列 WLAN 的型号，重查精确型号在两个系统的官方完整下载列表。92 款在两个系统均未列 WLAN，新增 184 个已核的「OEM 列表未列」结果。厂商没有明确排除出厂无线配置的记录继续保留配置缺口；未据此判定无 Wi-Fi 或系统不支持。此路线对同批证据复跑回填 0 项，另 22 款目录型记录的规格页实测均返回 HTTP 451，尚未取得第二路原厂规格证据。 [华硕逐项证据](network-rescue-asus-oem-listing-proof.csv)

以上各轮合计关闭 **412 个系统证据待核格**，其中 199 格是明确核对的 OEM 下载列表未列 WLAN。最新待核为主板 Win10 **767**、Win11 **814**，笔记本 Win10 **669**、Win11 **320**，合计 **2,570**。未清空。Win10 笔记本中 Acer 401 条仍是最大缺口，主板 Win10／11 中 MSI 分别 408／409 条。需要继续取得精确型号的原厂下载内容或硬件实证。

### 2026-11-13 原厂列表批量取证与华硕笔记本 SKU 拆分

本轮先按厂商原厂下载列表批量回填。MSI、Acer、华擎的接口在浏览器同源会话中低速调用，快照的浏览器端和本地 SHA-256 一致后才落盘；华硕用精确型号接口续查。判定口径统一为：“列出”要求已有出厂无线证据且下载列表含 WLAN 文件；“未列出”要求该系统有有效列表，且型号有出厂无线证据或原厂完整规格未列 WLAN。空响应、近似型号、组合系统文件和只有 Bluetooth 的类目保持待核。随后把华硕 82 个 ROG／TUF 系列拆成精确 SKU。

| 阶段 | 主板 Win10／Win11 | 笔记本 Win10／Win11 | 合计 |
| --- | --- | --- | ---: |
| 本轮开始 | 767／814 | 669／320 | 2,570 |
| 批量取证后（`b8d0c0f`） | 93／93 | 383／291 | 860 |
| 华硕 SKU 拆分后（`faf66de`） | 93／93 | 321／221 | 728 |
| 华硕主板手册补证后（`6dac966`） | 79／79 | 321／221 | 700 |

批量取证逐厂商的回填格数与判定依据见[交接文档](network-rescue-handoff.md#2026-11-13-原厂列表批量取证)，本轮不回填没有原厂列表或出厂无线证据的条目。

华硕笔记本共得 **333 个精确 SKU**、337 条系列×SKU 记录、677 条系统证据，见[逐 SKU 证据](network-rescue-asus-laptop-sku-proof.csv)。系列行只在全部 SKU 结论一致时关闭：75 个 Win10 格、75 个 Win11 格更新，82 个系列中 7 个仍有待核格，另 3 个系列未取到型号列表。新增 337 条 SKU 行：Win10 列出 37 条、原厂列表未列 287 条、待核 13 条；Win11 列出 332 条、待核 5 条。采集与回填见 [ASUS 笔记本 SKU 脚本](../scripts/collect-asus-laptop-skus.py)，ROG 页面需要浏览器会话快照（`--rog-capture`），`--apply-oem-evidence` 才写主表。证据表涉及 24 个不同版本、37 个下载地址，其中 7 个地址已在[原厂下载索引](network-rescue-driver-index.csv)。

已把其中 5 个版本加入在线驱动目录：MediaTek 3.00.01.1325（MT7902／MT7921，Win10/11，56 条 SKU 证据）、MediaTek 3.4.2.1046（MT7920／MT7922／MT7902，Win11，50 条）、Realtek 6001.15.165.3（RTL8852BE／CE，Win11，23 条）、Intel 23.160.0.4（Intel Wi-Fi 6/6E/7，Win11，9 条）和 Realtek 6101.19.137.0（Realtek Wi-Fi 6E/7，Win11，3 条，新增 5 个 VEN／DEV）。原厂 EXE 的 SHA-256、内嵌 7z 偏移和 CAT 签名已核对，按 PCI VEN／DEV 前缀匹配；源文件缓存在本地 `artifacts/vendor-wifi/<包 ID>/`，构建时仍按原厂哈希复核。其余 14 个版本逐一解包比对，均未引入新的 VEN／DEV，现有目录已覆盖其芯片，不再重复入库；原厂索引行可按需补。

截至 `6dac966`，待核为主板 Win10 **79**、Win11 **79**，笔记本 Win10 **321**、Win11 **221**，合计 **700**。Acer 笔记本仍是最大缺口（130／102），其次为 MSI 笔记本（85／77）与 HP 笔记本（63／21）。主板余项集中在 ASUS（20／19）、ASRock（19／22）和 MSI（18／18），华硕主板手册补证见下一节。以上均为原厂列表与规格证据，出厂硬件 ID、签名 INF 绑定和实机联网仍分别验收。

### 2026-11-13 华硕主板手册规格核验

新增按精确型号读原厂手册的规格核验（[脚本](../scripts/collect-asus-motherboard-specs.py)）。手册必须是文件名含该型号的英文用户手册（`_UM_` 或 `_EM_`）；系列手册和快速安装指南不参与判断，避免把 WIFI 兄弟型号的模块算到普通版上。手册全文没有 Wireless／WLAN／802.11 字样才记为原厂完整规格未列 WLAN。

32 款待核里，14 款手册无任何无线字样（[证据](network-rescue-asus-mb-spec-proof.csv)）；细化判定后另有 5 款只有「Notices for non Wi-Fi model」，但下载页同时列出 Wi-Fi 驱动，按冲突保留待核；12 款取不到精确型号手册，集中在 CSM 变体和 TUF 系列手册。与原厂下载列表证据合并（手册和下载列表两处都不列 WLAN）后关闭 28 格：主板 Win10 93→79、Win11 93→79，合计 728→700。

第二轮把判定改得更细：规格摘要按「specifications summary」定位后 4 页，只有规格页里出现无线字样才记为「原厂规格列出」；其余若只命中 ASUS 的「Notices for non Wi-Fi model」，记为原厂明示的无 Wi-Fi 型号。结果 5 款（PRIME B840M-A、B850-PLUS、Pro WS B850M-ACE SE、B760M-A D4、H610M-F D4 R3.0）手册明写非 Wi-Fi 型号，但原厂下载页同时列出 Wi-Fi 驱动，两处来源冲突，保留待核；12 款只有系列手册或 CSM 变体，取不到精确型号手册。把 PRIME B760M-A D4 的出厂无线状态从「只有目录」改为「规格未列 WLAN」。同一批判定复跑为 0 项变化。

成本对比：32 份手册约 40 MB，2 线程、每次 0.8 秒间隔共约 3 分钟；同一批证据复跑为 0 项变化。手册一次给出型号、页数和模块三项证据，但只能结「无出厂无线」一侧；有无线字样的手册仍需逐页区分规格行与法规页。华硕下载采集脚本同时加 0.6 秒节流、HTTP 451／429 重试和 `--workers`／`--pause`，本轮 660 次请求未再触发限流。

### 2026-11-13 逐 SKU OS 复核与联想 PSREF

华硕笔记本的系列级快照把整个系列记成同一份 OS 列表，SKU 自己页面没有该系统时只会得到「无驱动列表」并保留待核。新增[逐 SKU OS 复核](../scripts/verify-asus-sku-os.py)：对每个待核 SKU 重查 `GetPDOS`，只有 OEM 的 OS 列表缺少该系统才记为「原厂未列」。18 个待核 SKU 中 11 个自身列表不含 Windows 10（9 款 GA402、FA608UH／WM），另有 2 个系列行因全部 SKU 一致而关闭，共补结 13 格。

联想改用 [PSREF 规格表](../scripts/collect-lenovo-psref.py)：`psref.lenovo.com` 可读，15 款待核 Legion 中 14 款取得规格 PDF，受支持系统全部只有 Windows 11。与型号下载页 WLAN 包元数据 `OperatingSystemKeys=["Windows 11 (64-bit)"]` 一致后关闭 8 个 Win10 格；1 款（Legion Pro 7 16ADR10H）取不到 PSREF 路径，其余 7 款缺独立下载列表。证据见[PSREF 表](network-rescue-lenovo-psref-proof.csv)和[逐 SKU OS 表](network-rescue-asus-sku-os-proof.csv)。

成本：PSREF 15 份 PDF 约 1 分钟，SKU 复核 18 页约 40 秒，同一批证据复跑结果一致。本轮待核 700→**679**（主板 79／79，笔记本 Win10 300、Win11 221）。

### 2026-11-13 传输桥与联想下载页 OS 列表

本机 curl、PowerShell 和 Python 在 Acer 卡在 TLS 重协商，在 MSI、Gigabyte、Dell 被 Akamai 返回 403；WordPress 式的「站点不可读」结论其实来自客户端指纹。新增 [Node 传输桥](../scripts/oem-http.mjs)：只负责取回原始字节并缓存，解析与判定仍在 Python 里，现有采集脚本可复用同一桥。实测 Acer、MSI、Gigabyte、Dell、EVGA、联想 `support.lenovo.com` 均返回 200；Gigabyte 与 Acer 的数据接口仍需会话 Cookie，Biostar 仍 403。

联想方面，型号下载页内嵌 `"OSs":[{"Value":"Windows 11 (64-bit)"}]` 就是原厂 OS 选择器。7 款仍待核的 Legion 中 4 款取到该列表且只列 Windows 11，关闭 4 个 Win10 格；3 款的列表为空（型号页存在但无驱动记录），保持待核。此前 8 格用的是 PSREF 加驱动包元数据，两种口径一致。证据见[联想 OS 列表](network-rescue-lenovo-os-list-proof.csv)。

### 2026-11-13 MSI 规格页与驱动面板

MSI 的规格页和驱动接口在 Node 传输桥下均可读：`Specification` 页面直接写「WIRELESS LAN & BLUETOOTH Wi-Fi 7，模块预装于 M.2 Key-E」，`/api/v1/product/support/os?product=<slug>&type=driver` 返回该型号可选系统，`panel?…&os=<系统>` 返回按系统过滤的驱动表。四款 B850M Wi-Fi 板的 Windows 11 面板列出 MediaTek／Qualcomm Wi-Fi 驱动（5.7.0.5977、3.1.0.1430），Windows 10 面板有 LAN 和音频、没有 Wi-Fi 项，两个系统各 4 格因此关闭，并把出厂无线证据从「只有目录」提升为「原厂规格列出」。证据见 [MSI 规格证据](network-rescue-msi-spec-proof.csv)。

其余 MSI 主板仍有「通用 Wi-Fi 驱动包（如 AMD／Intel WIFI Drivers）与规格未列 WLAN」的冲突：无 Wi-Fi 型号的下载面板也会列出通用 Wi-Fi 驱动，按现有口径保持待核。联想另有 4 款型号的下载页 OS 列表只列 Windows 11，关闭 4 个 Win10 格。

本轮合计关闭 12 格：待核 679→**667**（主板 75／75，笔记本 Win10 296、Win11 221）。

### 2026-11-13 Acer 与 MSI 逐型号接口

Acer 与 MSI 的驱动数据都能取到，方法是先用 Node 传输桥拿页面 Cookie，再按页面自己的接口重放：

- **Acer**：`GET /us-en/support/product-support/<code>` 取 Akamai Cookie，等约 2.5 秒后 `POST /us-en/DynamicContent/GetDriversAndManuals`，body 为 `{"ModelName":"<code>","Local":"en-us"}`。`Local` 必须是 `en-us`（由 `/us-en/` 推导），提前 POST 会被 403。34 个精确 SKU 全部命中：9 格列出 Wireless LAN 驱动（含 MT7921LE、AX201 等文件名与版本），5 格原厂 OS 列表只有 Windows 11。95 行只有系列名的记录仍无法定位精确 SKU，190 格保持待核。证据见 [Acer 证据](network-rescue-acer-oem-listing-proof.csv)。
- **MSI**：`/api/v1/product/support/os?product=<slug>&type=driver` 给可选系统，`panel?…&os=<系统>` 给该系统驱动表。108 款待核型号全部命中，笔记本的「Wireless LAN Driver」带版本和 `download.msi.com` 链接，两轮共关闭 124 格。主板的通用 Wi-Fi 驱动包（AMD／Intel WIFI Drivers）出现在无 Wi-Fi 型号上，与规格未列 WLAN 冲突，只有原厂 OS 选择器缺系统的 5 格和两处都未列的 2 格关闭。证据见 [MSI 证据](network-rescue-msi-oem-listing-proof.csv)。

本轮合计关闭 **152 格**：待核 679→**527**（主板 74／74，笔记本 Win10 221、Win11 158）。MSI 复跑收尾时另有 11 个主板格的原厂页面确实列出 `Intel WIFI Driver`，但型号用的是通用 Wi-Fi 驱动包、规格未列 WLAN，按工厂配置规则挂起并记录在 `specGated`，不计入已核实。Acer 仍有 95 行系列名待拆 SKU，HP 84 格、ASRock 41 格、BIOSTAR 24 格、Gigabyte 14 格仍受站点或证据口径限制。

### 2026-11-13 Acer sitemap 系列拆解

Acer 的 96 个系列行只有营销名，无法直接查询。`https://www.acer.com/sitemap_usen.xml` 列出了 2,039 个精确型号页（如 `/support/product-support/A515-58GM`）。先拿系列名做模糊查询，接口回一个代表型号（例如「Aspire 18 AI」→ `A18-I71M`，描述 `Aspire A18-I71M`），按连字符前的型号族前缀统计 sitemap 中同族型号页：96 个系列里 90 个取到代表型号，73 个族的型号页多于一个。

其中 **15 个系列在美国站只有一个型号页**，映射无歧义：逐一查询该型号的驱动列表，Win10 均无任何文件（`oem-os-not-listed`），Win11 均列出 Wireless LAN 驱动（`oem-wlan-listed`），两个系统各 15 格、共 **30 格**关闭。证据见 [系列证据](network-rescue-acer-series-proof.csv)，其余 81 个系列的候选型号见[系列型号清单](network-rescue-acer-series-skus.csv)。

MSI 另按规格页「Intel Wi-Fi 6E 模块预装」与驱动面板关闭 MAG B660 TOMAHAWK EVA 的 2 格；其余 12 款无 Wi-Fi 主板的通用 Wi-Fi 驱动包继续按工厂规格门禁挂起。本轮合计关闭 **32 格**：待核 527→**495**（主板 73／73，笔记本 Win10 206、Win11 143）。

### 2026-11-13 华擎手册与 Acer 族级查询

华擎的 `www.asrock.com` 被 Incapsula 质询，但 `download.asrock.com` 的手册可读。按精确型号手册的「Wi-Fi 模块」章节与既有下载列表证据交叉：6 款主板手册写明预装 Wi-Fi 模块（Killer／Intel WLAN 驱动对两个系统都列出版本），X370 Pro4 手册无无线章节且 Win10 列表未列 WLAN，合计关闭 13 格。手册章节带「for X470 Master SLI/ac only」这类限定的型号不用于基础型号判断。

Acer 把 73 个多型号系列的 611 个 sitemap SKU 全部查询一遍（约 40 分钟，3 并发），**只有全族结论一致才关闭系列格**：24 个系列、47 格关闭（Win10 均无文件、Win11 均列 Wireless LAN），其余族内出现混合结论或空列表，保持待核。族级逐 SKU 证据见[族级证据](network-rescue-acer-series-family-proof.csv)。

本轮合计关闭 **59 格**：待核 495→**436**（主板 67／67，笔记本 Win10 183、Win11 119）。

### 2026-11-13 华硕 CSM 手册与 Acer 近似型号缺口

华硕 CSM 型号的原厂页面在 `helpdesk_manual` 里直接列出**基础型号手册**（例如 PRIME B450M-A-CSM 页面列 `E14212_PRIME_B450M-A_UM_WEB.pdf`），这是原厂自己给该型号的归属，不再属于近似型号替代。据此对 4 块 CSM 板（B450M-A/CSM、B450M-A II/CSM、X570-P/CSM、Pro H610M-C-CSM）读取手册：全部没有无线章节，且原厂下载列表对两个系统都未列 WLAN，按两处都未列关闭 **8 格**。另有 PRIME B760M-A D4 的两处来源都未列 WLAN，以及 B760M-A-CSM 页面列出无无线章节的 B760M-A 手册，合计再关闭 4 格。Pro WS 665-ACE 的手册页为空，继续待核。

Acer 侧复核了族级混合结论的原因：113 个 sitemap SKU 用精确型号查询时接口返回的是**近似型号**（该 SKU 在支持库里没有独立驱动数据），因此 49 个系列的「全族一致」无法达成。这批记录只有在拿到原厂「营销系列→全部 SKU」映射后才能继续，sitemap 只能给出型号页集合，未据此关闭任何系列。

本轮合计关闭 **12 格**：待核 436→**424**（主板 63／63，笔记本 Win10 183、Win11 119）。

### 2026-11-13 MSI 笔记本系列区域 SKU

MSI 的笔记本系列页 OS 选择器常常为空，区域 SKU 藏在系列 banner 里。用同源接口串起来：`/api/v1/search?group=1` 找到系列并列出 `sub_product`，`/api/v1/product/support/banner?product=<系列 slug>` 给出 `sub_product_list` 的 slug 映射，再逐个查 `/api/v1/product/support/os` 与 `panel?…&os=Win11 64`。

19 个待核系列共取得 57 个区域 SKU：每个 SKU 的 OS 选择器都只有 `Win11 64`，且 Win11 驱动表都列出 Wireless LAN 驱动（Intel／Killer／AMD／MediaTek），因此系列的两个系统格一起关闭，共 **38 格**。`+` 号会让搜索接口返回 500，脚本会去掉 `+` 再查一次。逐 SKU 证据见 [MSI 系列证据](network-rescue-msi-family-proof.csv)，脚本为 [collect-msi-family-listings.py](../scripts/collect-msi-family-listings.py)。

本轮合计关闭 **38 格**：待核 424→**386**（主板 61／61，笔记本 Win10 164、Win11 100）。

### 2026-11-13 剩余证据缺口清单

本轮补结 3 格：H610M/ac 手册明确列出「Wireless LAN: 802.11ac WiFi Module」且下载列表两系统都列 WLAN 驱动（2 格）；ROG Strix G16 (2025) 的 10 个 SKU 全部列出 WLAN 驱动，系列 Win11 格随之关闭（1 格）。待核 386→**383**。

剩余 314 格的缺口分布（每次重算后按此表推进）：

| 范围 | 待核 | 已查来源 | 缺失证据 |
| --- | ---: | --- | --- |
| 主板 ASUS 14／13 | 27 | 原厂规格页、下载接口、手册、CSM 手册归属 | 5 款手册明写非 Wi-Fi 但下载页列通用 Wi-Fi 驱动；4 款只有模块候选；Pro WS 665-ACE 无手册；B850M AYW 与 Z890 HERO 接口不可用 |
| 主板 ASRock 12／15 | 27 | 手册、下载列表快照 | Key-E 槽位板只有通用 Wi-Fi 驱动；Win11 下载列表无效 |
| 主板 MSI 12／12 | 24 | 规格页、驱动面板 | 无 Wi-Fi 主板只列通用 Intel WIFI 驱动（`specGated`） |
| 主板 BIOSTAR 12／12 | 24 | 官网 | 站点对 curl、Python、Node 全部 403 |
| 主板 Gigabyte 8／6 | 14 | 支持页 | Akamai 拒绝 Nuxt 代理 API |
| 主板 EVGA 2／2 | 4 | 支持页、产品 PDF | 页面与 PDF 均返回拦截页 |
| 笔记本 HP 0／21 | 21 | 驱动包目录、CVA、SoftPaq 说明 | 2017–2019 机型没有任何 Win11 包 |
| 笔记本 Acer 52／20 | 72 | 驱动接口、sitemap、族级 SKU、ARM64 排除 | 剩余族内仍有短列表或空列表 |
| 笔记本 ASUS 10／13 | 23 | 下载接口、逐 SKU GetPDOS | 空 OS 列表或无网络类目 |
| 笔记本 Lenovo 7 | 7 | PSREF、下载页 OS 列表 | 3 款 OS 列表为空，4 款缺 WLAN 列表 |
| 笔记本 Dell 5／3 | 8 | 驱动包 XML、驱动目录 | 缺原厂系统支持声明 |
| 戴尔系统 ID 组合 127／39 | 166 | 驱动包 XML、驱动目录 | 同上，需原厂逐系统支持声明 |

这些条目按 `AGENTS.md` 的要求保持待核并保留来源，不把空响应、近似型号或通用驱动包计为已核实。

### 2026-11-13 传输桥缓存键缺陷与 Acer 族级复算

复核发现传输桥 `--post-with-session` 的缓存文件名只按 URL 计算，而所有会话 POST 共用同一个接口地址：并发 worker 会互相覆盖缓存响应，导致真实驱动列表被读成「近似型号」。修正为按「URL + 请求体」计算哈希，并让族级脚本把缺 `payload` 的响应当作接口错误。

用修正后的桥重跑 73 个系列共 611 个 SKU：族内结论一致的有 **47 个系列、86 格**（此前只有 24 个系列、47 格）；已关闭的 24 个系列全部复核通过，0 个需要回退，新增 23 个系列、**39 格**关闭。15 个单型号系列也用修正后的桥复跑，结论一致。

本轮合计关闭 **39 格**：待核 383→**344**（主板 60／60，笔记本 Win10 148、Win11 76）。

### 2026-11-13 Acer ARM64 与空列表排除

族级扫描剩下的阻塞项全部是同一类：族内的 ARM64 SKU。Acer 对 Snapdragon 机型只发布 `11A1`（Win11 ARM64）驱动，`classify` 找不到 x64 文件时把它记成空列表，看起来像矛盾，实际是范围外。新增判定：驱动文件里 ARM 编码 ≥5 且 x64 编码 ≤2 的 SKU 记为 `arm64-out-of-scope`；完全没有文件列表的记为 `no-listing`；两者都不参与 x64 族内聚合。另外 10 个列表为空的 SKU 在更慢的节奏下重查后仍为空或短列表，按同上处理。

排除后 **62 个系列、116 格**的 x64 结论一致；已关闭的 47 个系列全部一致，新增关闭 **15 个系列、30 格**。逐 SKU 证据表已更新为带 `arm64-out-of-scope`／`no-listing` 状态。

本轮合计关闭 **30 格**：待核 344→**314**（主板 60／60，笔记本 Win10 133、Win11 61）。

### 2026-11-13 惠普驱动包目录与 CVA

惠普的 63 个 Win10 待核型号（2025 AI PC）此前只有「HPIA 矩阵没有 Win10 包」这一条间接证据。本轮补齐第二份原厂文件：每个型号在 **HP Client Driver Pack Catalog** 里只出现在 Windows 11 条目下（没有任何 Windows 10 条目），其关联驱动包的 **CVA** 文件在 `[System Information]` 列出精确型号、在 `[Operating Systems]` 只声明 `W11_23H2/24H2/25H2/26H2`。两份原厂文件都指向「该型号只有 Windows 11 驱动包」，据此把 **63 个 Win10 格**关闭为 `oem-os-not-listed`。

脚本 [collect-hp-pack-os.py](../scripts/collect-hp-pack-os.py) 复用 Node 传输桥读取 CVA，先在 CSV 副本上验证：候选 63、可关闭 63、只改目标格。证据见[驱动包证据](network-rescue-hp-pack-os-proof.csv)。惠普剩余 Win11 21 格是 2017–2019 机型没有任何 Win11 包，仍缺原厂系统支持声明。

本轮合计关闭 **63 格**：待核 314→**251**（主板 60／60，笔记本 Win10 70、Win11 61）。

### 2026-11-13 惠普镜像规则收尾

同一套「目录 + 包声明」规则镜像后也适用于旧机型：21 个 Win11 待核型号（2017–2019）在 HP 驱动包目录里只有 Windows 10 条目，其驱动包的 CVA 只声明 `WT64_*`（WT64 = Windows 10 x64）；其中 6 款的某个包没有 CVA OS 段，改用该包发布说明的 `OPERATING SYSTEM(S)`（仅 Windows 10）和 `HARDWARE PRODUCT MODEL(S)`（含精确型号）核对。21 格全部关闭，惠普笔记本待核清零。

本轮合计关闭 **21 格**：待核 251→**230**（主板 60／60，笔记本 Win10 70、Win11 40）。

### 2026-11-13 Swift Air、LiveMixer 与 X570 AQUA

- Swift Air 16 三个系列的 Win10 侧：除一个 SKU 只有 Win11 文件（因此没有 Win10 文件）外，其余全部 `oem-os-not-listed`，Win10 格关闭 3 格；Win11 侧仍有短列表，保持待核。
- B650 LiveMixer、Z790 LiveMixer 的手册只写 M.2 Key-E 插槽（无随板模块），下载列表两系统都未列 WLAN，按两处都未列关闭 4 格。
- X570 AQUA 手册规格写明「Wireless LAN: Intel 802.11ax WiFi Module」，下载列表两系统都列 WLAN 驱动，关闭 2 格并补模块字段。

本轮合计关闭 **9 格**：待核 230→**221**（主板 57／57，笔记本 Win10 67、Win11 40）。

### 2026-11-13 一体机收尾与 EVGA 手册可达

- **惠普 Presence 24 一体机**：驱动包目录里只有 `Windows 10 64-bit, 20H2` 一个条目，包 sp144635 的 CVA 只声明 `WT64_2009/21H1/21H2/22H2` 且 `[System Information]` 含「HP PRESENCE 24 WITH ZOOM ROOMS」，据此把 Win11 格关闭为 `oem-os-not-listed`。一体机待核清零；`collect-hp-pack-os.py` 现在同时处理一体机行。
- **EVGA 手册**：`www.evga.com/support/manuals/files/<PN>.pdf` 可读（`products/pdf/` 路径返回拦截页）。两份 Z790 手册都提到「Wi-Fi 6E / BT 5.2」，但 EVGA 的驱动下载页是 ASP.NET 壳，没有可解析的逐型号驱动列表，两个系统格保持待核。
- **BIOSTAR**：`http`、裸域名与不同 UA 均返回 403，24 格继续阻塞。

本轮合计关闭 **1 格**（一体机）：主板 57／57，笔记本 Win10 67、Win11 40；待核 221，另有戴尔系统 ID 组合 166 格。

### 2026-11-13 戴尔驱动包清单与 System 块

戴尔的 `laptop-os-record` 行是「型号 × SystemID × 系统」组合。用两份原厂文件逐条核对：

- **Driver Pack Catalog**（`downloads.dell.com/catalog/DriverPackCatalog.cab`，内层其实是 `DriverPackManifest` XML）给出每个 SystemID 的驱动包及其 `SupportedOperatingSystems`。88 个待核组合的 SystemID 只有 Windows 11 包 → Win10 格关闭为 `oem-os-not-listed`。
- **Win10 驱动包 XML**（`downloads.dell.com/<folder>/<pack>.xml`）的每个 `<System SystemID=...>` 块声明 `<OS Name="Windows10" Arch="x64">`，并在 `DeviceDescription` 中列出驱动；匹配 Wi-Fi/WLAN 且排除 WWAN/GNSS/Bluetooth 后，78 个组合的 Win10 包都含 Wi-Fi 驱动（Intel BE2xx/AX4xx 或 MediaTek MT792x UWD）→ 关闭为 `oem-wlan-listed`。同一包可覆盖多个 SystemID，按 System 块逐一取证。

脚本 [collect-dell-pack-os.py](../scripts/collect-dell-pack-os.py) 先在 CSV 副本上验证：待核 166、可关闭 166。证据见[戴尔 System 证据](network-rescue-dell-os-record-proof.csv)。**戴尔系统 ID 组合清零**，总待核 221 全部为主表型号。

本轮合计关闭 **166 格**：总待核 387→**221**（主板 57／57，笔记本 Win10 67、Win11 40）。

### 2026-11-13 华硕笔记本 OS 列表空类目

- **FA507RW**：GetPDOS 含 Windows 10，但该系统的驱动类目为 0（Windows 11 有 7 类 32 个文件），按 Acer 同口径判为原厂未列，Win10 关闭。
- **G513IR**：Win10 有 Networking（Realtek LAN、NXP NFC）、Audio、Chipset，但没有 WLAN 文件，判为原厂未列 WLAN，Win10 关闭。
- **TUF Gaming A15 (2022)** 系列：全部 6 个 SKU 的 Win10 结论一致（原厂未列），系列格随之关闭。

华硕笔记本余 7 格是空 OS 列表（FA608PPI／PMI）或无网络类目（G513IR／G713IR／G733QSA 的 Win11、FA608UH）。

本轮合计关闭 **3 格**：待核 221→**218**（主板 57／57，笔记本 Win10 64、Win11 40）。

### 2026-11-13 华硕区域支持页

部分型号在全局支持页取不到 `GetPDOS`／`GetPDDrivers`，但区域页（`/tw/supportonly/<model>/helpdesk_download/`）可用，且返回的是同一套原厂数据：

- **ROG MAXIMUS Z890 HERO**：Win10 与 Win11 都列出「Intel Wi-Fi Driver V24.20.0.4 for Windows10, Windows11 64-bit」，两格关闭并把出厂无线证据升为规格列出。
- **ROG STRIX B860-G GAMING WIFI**：Win11 列 MediaTek MT7925/7927 驱动，Win10 没有任何无线类目 → Win10 关闭为原厂未列。
- **TUF Gaming A16 FA608UH**：Win11 的「網路驅動程式」类目里有 Realtek／MediaTek 無線區域網驱动（V6001.16.174.103、V3.6.2.1434），Win11 关闭。注意类别名是中文，英文类别名匹配会漏。

按此路线复跑后 `collect-asus-wlan-downloads.py` 仍未接入区域页，后续如需可加 `--region`。本轮合计关闭 **4 格**：待核 218→**214**。

### 2026-11-13 BIOSTAR 规格导出是 PDF

BIOSTAR 的 `export/spec_export.php?S_ID=...` 返回的其实是 **PDF 字节**（之前按 HTML 解析所以读不到文本）。用 pymupdf 解析两份早期缓存：

- **X870E VALKYRIE**：`1 x M.2 (E Key) Socket : Supports 2230 type Wi-Fi & Bluetooth module` 且 `* M.2 (E Key) Wi-Fi card is not provided`。
- **B850M-SILVER**：`Supports WiFi 7 & 6E module (No WiFi card included)`，同样注明 E Key 卡不随板提供。

两款都没有随板 Wi-Fi 卡，下载列表也没有 WLAN 项 → 两个系统都关闭为 `oem-wlan-not-listed`（4 格）。其余 10 款 BIOSTAR 的规格 PDF 在站点恢复 403 后无法取得，保持待核；站点恢复时可直接沿用同一解析方法。

本轮合计关闭 **4 格**：待核 214→**210**（主板 53／54，笔记本 Win10 64、Win11 39）。

### 2026-11-13 华硕采集脚本区域页与中文类目

`collect-asus-wlan-downloads.py` 补两项能力：

- `--region <代码>`：全局支持页取不到 `GetPDOS`／`GetPDDrivers` 时，回退到 `/<region>/supportonly/<model>/helpdesk_download/`（已在 14 个待核主板上验证：18 条列出、4 条未列、3 条无 WLAN 行、2 条仍不可用）。
- 无线匹配加入中文类目／文件名（`無線區域網`、`無線網路`、`无线网卡`），避免只匹配英文 `Wireless` 时漏掉台服页面。

顺带复核：`PRIME B760M-A D4-CSM` 的下载列表两系统都没有 WLAN，但其手册只覆盖非 CSM 型号（手册内无 CSM 字样），按精确型号口径不代填；`Pro WS 665-ACE` 的下载列表同样未列 WLAN，但规格页没有可解析的规格表，仍缺出厂无线状态。两者保持待核。

本轮无新增关闭：待核 **210**（主板 53／54，笔记本 Win10 64、Win11 39）。

### 2026-11-13 剩余 210 格逐型号缺口清单

新增[剩余缺口清单](network-rescue-pending-inventory.csv)：每行一个待核格，含型号、类型、平台、系统、无线证据口径、缺口类别、缺失证据说明与已查来源。按类汇总：

| 缺口类别 | 格数 | 说明 |
| --- | --- | --- |
| `factory-vs-listing` | 63 | 下载列表列出通用 Wi-Fi 驱动，但规格/手册写无出厂无线（MSI 24、ASRock 21、ASUS 主板 18） |
| `mixed-family` | 45 | Acer 系列跨代，族内 SKU 结论不一致或为短列表 |
| `no-listing-exact-model` | 24 | Acer 精确型号在支持库无驱动记录（US/TW 均 0 命中） |
| `site-403` | 20 | BIOSTAR 全站 403，规格 PDF 与下载列表无法取回 |
| `no-network-category` | 19 | ASUS 笔记本该系统驱动列表无网络类目 |
| `api-403` | 14 | Gigabyte Akamai 拦截下载 API |
| `consumer-api-403` | 8 | Alienware 不在戴尔驱动包目录，支持页 API 被拦 |
| `os-list-empty` | 7 | Lenovo 产品页 OS 列表为空/驱动 API 403 |
| `no-factory-proof` | 4 | ASUS 主板缺出厂无线证据（下载不可用或未列） |
| `no-per-model-list` | 4 | EVGA 无逐型号驱动列表 |
| `support-api-empty` | 2 | ASUS 支持接口空响应（B850M AYW CSM） |

本轮无新增关闭：待核 **210**（主板 53／54，笔记本 Win10 64、Win11 39）。Lenovo 驱动 API 与 Gigabyte 区域 API 本轮再次确认 403；Dell 驱动包目录不含 Alienware。

### 2026-11-13 消费级目录与 Alienware 复核

- **Dell SDP 目录**：`downloads.dell.com/catalog/DellSDPCatalogPC.cab`（内层 `DellSDPCatalogPC.xml`，172 MB，WSUS `SystemsManagementCatalog`）可正常下载解析，但其中没有 Alienware 16/18 Area-51、15 DA15260 等型号（`Alienware` 仅作为旧条目的品牌名出现，型号代码 0 命中），无法用于这 8 格。
- **Lenovo**：`pcsupport.lenovo.com` 产品页可读（423 KB），页面内嵌 `DefaultOs` 与产品 ID，但驱动数据接口 `/api/v4/downloads/drivers` 无论 productId 形式如何都返回 403，仍缺逐系统驱动列表。
- **Gigabyte**：区域 API（tw/jp/de）路径 404，`www.gigabyte.com/api/proxy/...` 仍 403；EVGA 旧下载路径返回拦截页。
- **Web Archive**：BIOSTAR 规格 PDF 有 2025-12 与 2026-07 快照，但本机访问被 429 限速，未能取回。

本轮无新增关闭：待核 **210**。

### 2026-11-13 华硕规格页空行判定

华硕 techspec 页把规格行渲染成 `rowTableTitle` + `rowTableItems`：没有内容的行（如 `PRIME B760M-A D4-CSM` 的 `Wireless & Bluetooth`）对应空的 `rowTableItems`，同时 Nuxt 数据里该行的 `Content` 指向空占位。用这一条判定「规格未列 WLAN」：

- **PRIME B760M-A D4-CSM**：techspec 的 `Wireless & Bluetooth` 行为空 + 下载列表两系统都没有 WLAN → 两个系统都关闭为 `oem-wlan-not-listed`（2 格）。
- **Pro WS 665-ACE**：`GetPDOS`／`GetPDDrivers`（`product.asmx`）可用，两系统列表只有 LAN、Chipset、VGA、SATA，没有 WLAN；但 techspec 只发布了「News & Updates: Socket AM5」一行，没有完整规格表，缺出厂无线状态，保持待核。

本轮合计关闭 **2 格**：待核 210→**208**（主板 52／53，笔记本 Win10 64、Win11 39）。

### 2026-11-13 华硕有效列表判定放宽

原判定要求「有 LAN 类目 + 音频或芯片组」才算有效列表。实际不少主板对某个系统不发布 LAN 驱动但仍支持该系统，于是把「有效列表」放宽为：

- 含 LAN 类目，**或** 至少 5 个文件且含音频或芯片组类目；
- 且全表没有 WLAN 文件（类目名或文件名匹配，含中文）。

据此关闭：
- **Pro WS B850M-ACE SE** Win10：列表 7 类 13 个文件（芯片组、显卡、USB、SATA 等），无 WLAN；规格未列 WLAN → `oem-wlan-not-listed`。
- **ProArt B850-CREATOR WIFI NEO** Win10：列表 6 类 8 个文件（芯片组、蓝牙等），无 WLAN；出厂模块已确认 → `oem-wlan-not-listed`。
- **PRIME B550M-K/CSM** Win11 只有 2 个软件文件，仍不满足有效列表，保持待核。

采集脚本同时增加了 `supportonly` 页回退（目录指向产品页、产品页没有驱动接口时）。本轮合计关闭 **2 格**：待核 208→**206**。
