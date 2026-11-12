# 统一离线安装包覆盖进度

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

原 6.28 GiB ZIP 的 12,405 个文件均可完整读取并通过 CRC 校验。按内容 SHA-256 分组后有 7,170 份唯一内容，5,235 个重复副本。重复副本占原始文件约 2.94 GiB，在 ZIP 中约占 1.69 GiB。另有约 0.99 GiB 为已解包驱动对应的原始下载归档。固实 7z 成品为 1.95 GiB，减少 68.96%。全部 12,373 个驱动文件的路径、大小和 CRC 与原 ZIP 一致。索引记录 14 个已收录的原厂包。[驱动下载索引](network-rescue-driver-index.csv)

Windows 11 构建 26300 的最新库审计覆盖 1,666 个 INF。其中 682 个匹配当前系统的网络设备 ID，595 个通过签名检查。去重后签名有效的 ID 有 4,566 个 PCI ID 和 1,228 个 USB ID。其余 INF 仍需按系统、架构及驱动组件用途核对。

华硕 PRIME B650M-A AX 的型号专属驱动页列出 Realtek RTL8852BE，适用于 Windows 10/11 x64。原厂 ZIP 的 SHA-256、包内 INF 签名及 21 个 RTL8852BE 子系统 ID 的 Windows 11 匹配已核对，并纳入两版。整机出厂 ID 与实机安装仍待查。[PRIME B650M-A AX 下载页](https://www.asus.com/us/supportonly/prime%20b650m-a%20ax/helpdesk_download/) · [原厂 ZIP](https://dlcdnets.asus.com/pub/ASUS/mb/08WIRELESS/DRV_WiFi_RTK_8852BE_SZ-TSD1_W11_64_V6001151610_20251128R.zip)

华硕的 B850M AYW GAMING WIFI-CSM 官方规格明确列出板载 Wi-Fi 模块。已知样本的无线状态达到 101/101，其中 99 条有板载 Wi-Fi，两条仅预留接口。具体模块候选为 98/99，缺口是该 CSM 型号的芯片。普通版的 MediaTek 驱动和 -E CSM 版的 Realtek 驱动各对应自己的型号。[华硕 CSM 型号规格](https://www.asus.com/product-compare?LevelId=Motherboards-Components-Motherboards&ProductID=31128%2C28588)
