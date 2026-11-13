# 联网驱动核实：剩余工作分工

截至本轮，主表剩余 **166 格**待核（起点 2,570）。本文件把剩余工作分成「我可以继续做」「需要你决定或提供条件」两部分，并记录日后复跑的方法。

## 一、需要你决定（决定后我可以立即执行）

### 1. 通用 Wi-Fi 驱动与「规格无出厂无线」的记账口径（约 52 格）

MSI 24 格、ASRock 14 格、ASUS 主板 14 格属于同一情形：规格页明确没有出厂 WLAN，但下载页仍列出通用 `Intel WIFI Driver`／`MediaTek WLAN Driver`（通常面向 M.2 E-Key 选配模块）。现行口径要求「列出」必须同时有出厂无线证据，两边都不成立，因此保持待核。

三种可选口径：

| 方案 | 处理 | 影响 |
| --- | --- | --- |
| A. 维持现状 | 继续待核，记录冲突 | 0 格变化 |
| B. 按硬件配置记账 | 出厂无 WLAN → 该格记 `oem-wlan-not-listed`，并把通用驱动写入备注 | 约 -52 格 |
| C. 按页面列出记账 | 下载页列了即 `oem-wlan-listed`，出厂状态另记 `wlanEvidence` | 约 -52 格，但会显示「无 Wi-Fi 主板有无线驱动」 |

逐格证据见 `network-rescue-pending-inventory.csv`（`factory-vs-listing` 类）与各厂商 proof 表。

### 2. 系列级行是否替换为精确 SKU（约 58 格）

Acer 27 个系列行（45 格）与 ASUS 7 个系列行（13 格）是「系列级候选」，不是精确型号。族内 SKU 结论经常不一致（如 TravelMate P2 跨代），系列行因此无法给出单一结论。Acer 的 611 个 SKU 与 ASUS 的 333 个 SKU 证据已在族级 proof 表里。

可选：

| 方案 | 处理 | 影响 |
| --- | --- | --- |
| A. 维持现状 | 系列行继续待核 | 0 格变化 |
| B. 拆分为精确 SKU 行 | 用族级 proof 生成 SKU 行并删除系列行 | 待核 -58 格，新增约 200 个精确型号行 |
| C. 系列行移出主表 | 系列行迁到单独的候选表 | 待核 -58 格，主表只保留精确型号 |

## 二、我可以继续做（无需你介入）

| 方向 | 格数 | 下一步 |
| --- | --- | --- |
| Acer 精确型号 | 19 | 已扫 14+25 个区域库，全部 0 命中（记录为「原厂无记录」，按现行规则不算已核实）。可再试 Acer 归档接口或旧版产品码 |
| Dell Alienware | 8 | 驱动列表走前端 XHR，已试直连、代理、无头抓包；下一步可尝试 Dell 的 `dl.dell.com` 包索引或浏览器自动化 |
| Lenovo | 7 | 驱动 API 403；下一步可尝试 Lenovo TVSU/DCS 目录或 PSREF 补充 |
| Gigabyte | 6 | `B860M A PRO WIFI7` 官网/US/JP 路径均 404；下一步可从 Gigabyte 搜索索引或经销商页面反查官方 slug |
| EVGA | 4 | 产品页已下线（PN 页面重定向首页）；仅手册可用，属站点内容移除 |
| ASUS 主板缺规格 | 4 | `B850M AYW GAMING WIFI-CSM`（接口空）与 `Pro WS 665-ACE`（无手册、规格仅一行） |
| ASUS 笔记本 SKU | 7 | FA608PPI/PMI 空 OS 列表；G513IR/G713IR/G733QSA 的 Win11 列表只有 2–3 个工具 |

以上每一项都已记录来源与缺失证据；没有新方法时它们会保持待核。

## 三、日后复跑方法

1. 每轮改完表后运行：

   ```
   python scripts/audit-network-rescue.py
   ```

   它会校验表结构/状态值/重复键，重建 `docs/network-rescue-pending-inventory.csv`，并对比上一次快照输出本轮关闭与新增的格数。

2. 各厂商采集脚本（均可 `--apply` 回写，先干跑核对）：

   - `collect-hp-pack-os.py`：HP 驱动包目录 + CVA
   - `collect-dell-pack-os.py`：Dell 驱动包清单 + 包 XML
   - `collect-asus-wlan-downloads.py`（`--region` 区域页回退）
   - `collect-asus-motherboard-specs.py`、`collect-asus-laptop-skus.py`
   - `collect-acer-series-skus.py`（ARM64/空列表排除）
   - `collect-acer-locale-listings.py`（区域库扫描，Windows Update 占位判定）
   - `collect-msi-oem-listings.py`、`collect-msi-family-listings.py`
   - `collect-asrock-wlan-downloads.py`（浏览器快照）、`collect-asrock-via-reader.py`（阅读器渲染）
   - `collect-gigabyte-wlan-downloads.py`（阅读器渲染 + PCB 修订版限定）
   - `collect-lenovo-os-list.py`、`collect-lenovo-psref.py`

3. 被 403/Cloudflare 拦截的站点优先尝试阅读器代理 `https://r.jina.ai/<url>`（已用于 BIOSTAR、Gigabyte、ASRock），纯前端 XHR 取数的页面代理无效。

4. 证据一律写入 `docs/network-rescue-*-proof.csv`，主表只改目标格；提交前确认 `user.name` 为 `Expurgator`。
