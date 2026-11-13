# 联网驱动核实：剩余工作分工

主表剩余 **80 格**待核（起点 2,570，表 2,723 行）。两项口径决定已落地；Gigabyte/ASRock/MSI 又收尾 10 格。本文件记录剩余工作与日后复跑方法。

## 已落地的决定

1. **按硬件配置记账**：已核实「规格无出厂 WLAN」的主板，下载页里的通用 Wi-Fi 驱动视为 M.2 E-Key 选配模块驱动，该格记 `oem-wlan-not-listed`。覆盖 MSI 21 格、ASRock 14 格、ASUS 11 格，证据见 [冲突记账证据](network-rescue-conflict-resolution-proof.csv)。
2. **系列行拆分**：Acer 19 个有族级数据的系列行替换为 88 个精确 SKU 行（模型名即 Acer 型号代码），映射见 [Acer SKU 证据](network-rescue-acer-sku-proof.csv)；ASUS 4 个已有 SKU 行的系列行直接删除。

## 剩余 80 格分布

| 厂商 | 格数 | 缺口 |
| --- | --- | --- |
| Acer | 40 | 8 个无 SKU 数据的系列行（16）、20 个精确型号 Win10（21）、2 个 SKU 短列表（3） |
| ASUS | 13 | 3 个无 SKU 数据的系列行（6）、5 个 SKU（FA608PPI/PMI 空 OS 列表、G513IR/G713IR/G733QSA 的 Win11 列表过短）（7） |
| Dell | 8 | Alienware 驱动页为前端 XHR，Akamai 拦截直连与无头浏览器；需要登录态浏览器复制页面（见浏览器抓取指引） |
| Lenovo | 7 | 驱动 API 403，页面无服务端驱动表；同样需要浏览器复制（见浏览器抓取指引） |

| MSI | 4 | `MEG X570 GODLIKE`（Killer 通用包无法落到型号）、`PRO H610M-S WIFI DDR4 II`（面板为空） |
| ASUS 主板 | 4 | `B850M AYW GAMING WIFI-CSM`（接口空）、`Pro WS 665-ACE`（无手册、规格仅一行） |
| EVGA | 4 | 产品页已下线（PN 重定向首页），仅手册可用 |


## 需要你决定或提供条件

| 事项 | 说明 |
| --- | --- |
| Acer 8 个系列行 | `Aspire 14/16 AI AMD/Intel/Snapdragon`、`Aspire AMD/Intel`、`PREDATOR TRITON 500 SE`、`TravelMate P2 16 AI AMD`、`TravelMate P4 13` 没有族级 SKU 扫描数据。可选：a) 维持待核；b) 同样移出主表；c) 你提供这些系列的精确型号清单 |
| ASUS 3 个系列行 | `ROG Flow Z13-KJP`、`ROG Zephyrus G14 (2026) GA403`、`G14 AW SE` 尚无 SKU 行；需要提供 SKU/产品页或允许继续用 ASUS 产品页抓 SKU |
| Dell / Lenovo / EVGA | 官方驱动数据依赖登录态或已被移除。若你有 Dell/Lenovo 账号或可用的商用代理，可授权我接入 |
| 实机验证 | 全部结论来自原厂页面与包清单，无实机联网验证；需要真实设备时由你提供 |
| 公共阅读器代理 | 已用 `r.jina.ai` 绕过 Cloudflare/Akamai；如你不接受第三方代理，请告知，我改用本地浏览器方案（覆盖会下降） |

## 日后复跑

1. 改完表后运行 `python scripts/audit-network-rescue.py`：校验结构/状态/重复键、重建待核清单、对比快照输出本轮关闭/新增格数。
2. 采集脚本（先干跑核对再 `--apply`）：`collect-hp-pack-os.py`、`collect-dell-pack-os.py`、`collect-asus-wlan-downloads.py --region tw`、`collect-asus-motherboard-specs.py`、`collect-asus-laptop-skus.py`、`collect-acer-series-skus.py`、`collect-acer-locale-listings.py`、`collect-msi-oem-listings.py`、`collect-msi-family-listings.py`、`collect-asrock-wlan-downloads.py`、`collect-asrock-via-reader.py`、`collect-gigabyte-wlan-downloads.py`、`collect-lenovo-os-list.py`、`collect-lenovo-psref.py`。
3. 被 403/Cloudflare 拦截的站点先试 `https://r.jina.ai/<url>`；纯前端 XHR 页面代理无效。

## 本轮补充决定

- **已关闭的系列行保留**：拆分只处理了待核的系列行；已关闭的聚合行作为系列索引保留，不删除已验证数据。
- **实机验证**：由你按需抽少量机型确认，其余以「发现问题再改」方式反馈。
- **非官方来源**：Softpedia 直连 403、阅读器空；Wayback 对本机持续 429。EVGA 产品页已下线，暂只能靠手册；Dell/Lenovo 需浏览器配合。
