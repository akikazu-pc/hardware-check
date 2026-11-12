# 统一离线安装包覆盖进度

日期为 2026-11-12。统一的断网急救离线包适用于桌面和笔记本，通用包与 OEM 补充包按设备 ID 和系统选取。两类设备分别验收。先核对 AM5、LGA1851 及 2025 年起出货的笔记本，完成后再系统扩展到 AM4、LGA1700 及更旧的笔记本。

| 统计范围 | 分母 | 已核对 | 比例 |
| --- | ---: | ---: | ---: |
| 华硕 AM5 / LGA1851 已发现的 Wi-Fi 主板（全球目录 100 条加 ROG HERO 手册 1 条） | 101 | 5 条有原厂手册模块证据 | 4.95% |
| 戴尔近期笔记本，Windows 11 x64 系统 ID 组合 | 127 | 125 条 OEM 元数据列出 WLAN INF | 98.43% |
| 戴尔近期笔记本，Windows 10 x64 系统 ID 组合 | 39 | 39 条 OEM 元数据列出 WLAN INF | 100% |
| HP sp173191 文档的具体 PCI SUBSYS，在 Windows 11 构建 26300 | 23 | 23 条被离线库的签名 INF 匹配 | 100% |

华硕统计只包括已发现且明确提到 Wi-Fi 的型号。手册中有多个出厂模块的，仍待核对每种实卡硬件 ID。台式机证据见 [华硕样本](asus-recent-wireless-module-evidence.csv)和[目录](asus-motherboard-discovery.csv)。

戴尔统计来自 2026-11-09 的 [Dell Driver Pack Catalog](https://downloads.dell.com/catalog/DriverPackCatalog.cab)，覆盖 52 个近期型号。不同 system ID 和 Windows 构成独立记录。Windows 11 x64 有两条 OEM 目录指向的元数据未列相同系统 ID，已标为待补。另有一条 ARM64 OEM 元数据记录，不计入 x64。见[逐条索引](dell-recent-laptop-wlan-discovery.csv)。驱动元数据只证明厂商包列有 WLAN INF。

HP 从[官方 SoftPaq](https://ftp.ext.hp.com/pub/softpaq/sp173001-173500/sp173191.html)提取了 23 个带 SUBSYS 的 PCI ID，再用应用的 SetupAPI 匹配和 INF 签名校验核对。硬件 ID 按缺驱动样例传给程序，未对本机安装驱动。一次 Windows 11 审计不能代表 Windows 10 或实机联网。

总体百分比分母尚未冻结。上述新型号没有完整的缺驱动实机安装联网记录。下一批补戴尔元数据不匹配的两条、华硕 96 条待核记录及技嘉、微星、华擎等新平台型号。随后核对 HP、联想及其他笔记本 OEM，按各型号实际网卡变体分别验证 Windows 10/11。
