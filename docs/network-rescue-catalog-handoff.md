# 断网急救采集与核验交接

本交接面向继续维护断网急救型号目录、OEM 下载证据和驱动候选的会话。代码与数据基线为 `main` 的 `8dc0c7709362a7767226ad787611242021f5e34e`。上一次行为变更后 542 项测试通过。本次交接只记录已存在的行为和未自动化的流程。历史轮次、统计口径和来源见[覆盖报告](network-rescue-coverage-progress.md)。

## 已进脚本的策略

| 策略 | 入口 | 行为与输出 |
| --- | --- | --- |
| 按快照清单增量更新 | [双击入口](../scripts/update-network-rescue.cmd)、[更新脚本](../scripts/update-network-rescue.py) | 检查快照及 OEM 目录，缓存元数据，按哈希复用包，处理新地址、变更和重试。首次笔记本与其他设备扫描可建立基线。可按设备分跑，限量补采优先选覆盖更多待验型号的包。结果写入本地状态目录。 |
| 华硕全量待核和严格回填 | [ASUS 采集脚本](../scripts/collect-asus-wlan-downloads.py) | `--all-pending` 查询主表的待核型号和系统。精确匹配型号，保留 `+`，并核对 OEM x64 包标题。`--apply-oem-evidence` 才写主表。正向回填要求已有出厂无线证据。回填未列出要求原厂接口返回有效列表，且已有出厂无线证据或原厂完整规格也未列 WLAN。空响应不用于回填。 |
| 华硕笔记本系列拆分 SKU | [ASUS 笔记本 SKU 脚本](../scripts/collect-asus-laptop-skus.py) | 从系列支持页的型号选择器或 ROG `GetPDCPUName` 取得精确 SKU，再逐 SKU 查询 `GetPDOS`／`GetPDDrivers`（45 = Win10、52 = Win11，均 x64）。系列行只在全部 SKU 结论一致时关闭。ROG 页面用浏览器会话快照 `--rog-capture`；`--apply-oem-evidence` 才写主表，重复运行为 0 项变化。 |
| 逐板候选与 SHA-256 批次 | [逐板采集脚本](../scripts/collect-windriverindex-wlan.py) | 校验快照文件和逐板报告的代次、型号、厂商。以厂商、无线家族、版本、日期匹配唯一归档。`--package-plan` 按有效 SHA-256 分组，并按涉及型号数排序。输出供下载与验证，脚本不回填主表。 |
| 静态 ZIP 签名审计 | [库审计](../scripts/audit-network-rescue-library.ps1)、[ZIP 审计](../scripts/audit-network-rescue-zip.py) | 更新器检查直接 ZIP 中可见的驱动 INF，跳过只有 `autorun.inf` 的安装封装。签名审计记录 Windows 构建、INF 路径和硬件 ID。ZIP 审计复用内容未变的包，发行验收使用 `--fresh`。 |
| OEM 页面传输桥 | [Node 桥](../scripts/oem-http.mjs) | 本机 curl、PowerShell 和 Python 在 Acer 卡 TLS 重协商，在 MSI、Gigabyte、Dell 被 Akamai 返回 403。Node 的 fetch 可通过，桥只负责取回原始字节并缓存到 `artifacts/oem-cache/`，解析和判定仍由 Python 脚本完成。`--post <url> <json>` 用于 JSON 接口。 |
| 待核统计和应用检索导出 | [覆盖统计](../scripts/report-network-rescue-coverage.py)、[目录导出](../scripts/export-network-rescue-search.py) | 分系统、厂商、缺口和系列层级统计。导出更新器来源为[嵌入检索目录](network-rescue-search-models.csv)，应用构建后可搜索。双击更新本身只更新本地目录。 |

## 仍需单独核验的策略

- **华擎按型号拆分共用手册。** 已核的原厂页面、手册页码和变体结论在[华擎证据表](network-rescue-asrock-variant-proof.csv)。对同一本手册，先确认包装清单中的精确型号，再核对 WLAN 段落是否限定某个变体。仅预留可分别结案，明确无 Win10 出厂无线驱动只结 Win10。仅限 6 GHz 或 Wi-Fi 7 功能的说明保留驱动待核。当前更新入口未自动获取和判读这批手册。
- **惠普 HPIA 逐系统引用。** 用 SMBIOS SystemID 找原厂 CAB，以 ProductName、SystemID、Windows 版本、活动 WLAN Solution 和设备引用核对。已有 47 份 Win11 22H2 x64 引用覆盖 57 款待核型号，结果在[HP 引用表](network-rescue-hp-wlan-reference.csv)。HPIA 的不支持配置结论只适用于 HPIA，主表 Win10 仍待核。当前更新入口无 HPIA CAB 采集和解析器。
- **封装拆解和联想包核对。** 先比对 OEM SHA-256，再静态提取。已实测过 Intel Burn 内嵌 CAB、HP SoftPaq 的嵌入归档、联想 Inno 安装包。打包脚本已有配置驱动的 Inno 和嵌入归档提取分支，通用更新器仍把此类包排入待静态提取。哈希冲突应保留原始证据，停止使用冲突包。
- **候选与成品字节对照。** [候选关联表](network-rescue-board-package-candidates.csv)记录逐板来源、归档哈希、签名构建和在本地 ZIP 中逐文件确认的 INF 数。快照、原厂归档与签名链齐备可形成候选。逐型号 OEM 关联、出厂硬件 ID、目标系统绑定和断网联网仍分别核对。通用更新器不会自动把这批候选写入主表或发行包。

## 接手命令

在仓库根目录运行。更新和验签使用 Windows、Python 3.11+、支持 ETag 参数的 `curl` 以及 PowerShell 7。

```powershell
# 查看各类待核和已有证据。默认状态目录需先由更新器生成。
python scripts/report-network-rescue-coverage.py --device-state artifacts/network-rescue-device-check

# 刷新本地来源和归档候选。
.\scripts\update-network-rescue.cmd
python scripts/update-network-rescue.py --devices-only --backfill-devices --device-backfill-limit 5

# 华硕先产出审核文件，确认差异后才附加 --apply-oem-evidence。
New-Item -ItemType Directory -Path artifacts/network-rescue-handoff -Force | Out-Null
python scripts/collect-asus-wlan-downloads.py docs/network-rescue-model-gaps.csv docs/asus-motherboard-discovery.csv artifacts/network-rescue-handoff/asus-wlan.csv --all-pending

# 前提是已取得同代的 manifest.json、boards.json、families.json 和 artefacts.json。
python scripts/collect-windriverindex-wlan.py docs/network-rescue-model-gaps.csv artifacts/network-rescue-index-snapshot artifacts/network-rescue-handoff/board-associations.csv --package-plan artifacts/network-rescue-handoff/package-plan.json
```

`artifacts/` 是本机的忽略目录。新工作区需要重新采集或从上一工作区带入快照、原包和签名记录。可提交的接手证据是 `docs/` 下的表。需要更新应用内型号时，先运行 `python scripts/export-network-rescue-search.py`，设备采集另用了状态目录时传 `--device-state`。更改应用、数据或脚本后按 `AGENTS.md` 运行相应门禁。交付包沿用 ZIP。

## 当前待核与接手顺序

截至 `9c1f0c0`（2026-11-13）。主板 Win10／Win11 各 61 条，笔记本 Win10 183 条、Win11 119 条；戴尔系统 ID 组合已清零。

| 范围 | 待核 | 最大缺口 |
| --- | ---: | --- |
| 主板 Win10 x64 | 50 | ASUS 9、ASRock 9 |
| 主板 Win11 x64 | 53 | ASRock 12、ASUS 11 |
| 笔记本 Win10 x64 | 64 | Acer 49、ASUS 7 |
| 笔记本 Win11 x64 | 39 | Acer 20、ASUS 12 |

1. Acer 笔记本现有 106／82 条待核；15 个系列已按单型号族关闭，其余 81 个系列用[系列型号清单](network-rescue-acer-series-skus.csv)逐 SKU 查询，要求该系列全部型号结论一致后才关闭。
2. 联想余 Win10 7／Win11 4，华硕笔记本余 10；MSI 笔记本 85／77 与 HP 63／21：MSI 的 Killer 通用包要拆包核对 INF，新款笔记本的原厂驱动列表为空；HP 用 HPIA 精确引用，只有矩阵范围说明的 Win10 条目继续保留原厂证据缺口。
3. 主板余项集中在 ASRock 19／22、MSI 18／18，另有 ASUS 20／19、BIOSTAR 12／12、GIGABYTE 8／6。华硕主板新增按精确型号读原厂手册的手册规格核验（[脚本](../scripts/collect-asus-motherboard-specs.py)、[证据](network-rescue-asus-mb-spec-proof.csv)），本轮关闭 28 格。华硕笔记本拆分后，82 个系列中 7 个仍有待核格，3 个系列未取到型号列表。
4. 每轮重算四组待核，分别报告已核 OEM 列表、签名候选、实机结果和无新增的来源。若同一路线已经复跑无变化，转到尚可取得的独立证据。待核目标为零，当前未达到。
