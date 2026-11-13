# 断网急救实机验收

用于验收「缺驱动 → 安装 → 驱动绑定 → 恢复联网」。只在可隔离、可重装的测试机上执行，不使用客户机器或开发宿主。

## 准备

- 测试机只连接被测网卡。有线测试拔掉 Wi-Fi 天线或在固件中关闭 WLAN；Wi-Fi 测试拔掉网线。USB 网卡测试时不接其他网络。
- 准备一台可联网的路由器，记录它是否提供 IPv4 DHCP、IPv6 和 DNS。网络名和密码不写入记录。
- U 盘使用 exFAT 或 NTFS，放入离线完整版 ZIP 及 `scripts/collect-network-rescue-evidence.ps1`、`scripts/summarize-network-rescue-evidence.ps1`。核对 ZIP 的 SHA-256。
- 制造缺驱动状态时优先用微软官方介质全新安装，安装后不连网。已有系统可在测试机上用 `pnputil /delete-driver oemNN.inf /uninstall` 删除被测网卡驱动；先用 `pnputil /enum-drivers /class Net` 确认 INF 名称。若 Windows 自带驱动仍能绑定，该组合记为「系统自带可用」，不计入断网恢复。

## 每个场景的记录步骤

在测试机以管理员身份打开 Windows PowerShell，`-Scenario` 只写场景编号。

```powershell
powershell -ExecutionPolicy Bypass -File .\collect-network-rescue-evidence.ps1 -Stage baseline -Scenario W11H-WIFI-OS
```

1. `baseline`：确认被测设备 `problemCode` 为 28，`driver` 为空，连通性失败。
2. 运行断网急救并安装推荐驱动。截图记录界面选中的 INF、签名者和结果。
3. `after-install`：确认 `problemCode` 为 0，`driver.isSigned` 为真，记下 `infName`、版本和提供商。
4. 若程序或 Windows 要求重启，重启后执行 `after-restart`。
5. 通过标准：设备已绑定签名驱动，`adapter.status` 为 `Up`，有 IPv4 或 IPv6 网关，`dnsResolved` 为真，`httpsStatus` 为 200–399。

脚本不写 MAC、IP、网络名、主机名、用户名、序列号和设备实例 ID。JSON 可直接附到验证记录。

## 场景矩阵

运行方式：OS 为在正在运行的 Windows 中修复；PE 为从 WinPE 向已有离线 Windows 写入驱动后启动；NEW 为 PE 无人值守新装后首次联网。

| 编号 | Windows | 网卡 | 方式 | 结果 |
| --- | --- | --- | --- | --- |
| W10-ETH-OS | Windows 10 22H2 x64 | 有线 | OS | Unverified |
| W10-WIFI-OS | Windows 10 22H2 x64 | Wi-Fi | OS | Unverified |
| W10-ETH-PE | Windows 10 22H2 x64 | 有线 | PE | Unverified |
| W10-WIFI-PE | Windows 10 22H2 x64 | Wi-Fi | PE | Unverified |
| W11H-ETH-OS | Windows 11 Home x64 | 有线 | OS | Unverified |
| W11H-WIFI-OS | Windows 11 Home x64 | Wi-Fi | OS | Unverified |
| W11H-WIFI-NEW | Windows 11 Home x64 | Wi-Fi | NEW | Unverified |
| W11P-ETH-OS | Windows 11 Pro x64 | 有线 | OS | Unverified |
| W11P-WIFI-OS | Windows 11 Pro x64 | Wi-Fi | OS | Unverified |
| W11P-ETH-PE | Windows 11 Pro x64 | 有线 | PE | Unverified |
| W11P-WIFI-PE | Windows 11 Pro x64 | Wi-Fi | PE | Unverified |
| W11P-ETH-NEW | Windows 11 Pro x64 | 有线 | NEW | Unverified |
| W11P-WIFI-NEW | Windows 11 Pro x64 | Wi-Fi | NEW | Unverified |

每行另记主板或整机型号、BIOS 版本、网卡硬件 ID、Windows 构建号和 UBR、INF 版本、是否需要重启。同一型号的不同出厂网卡分别建行。

## 汇总判定

把同一目录下的 JSON 交给 `summarize-network-rescue-evidence.ps1`，生成场景 × 阶段的 Markdown 表：

```powershell
powershell -ExecutionPolicy Bypass -File .\summarize-network-rescue-evidence.ps1 -EvidenceDirectory .\evidence -OutputPath .\matrix.md -FailOnIncomplete
```

- **Pass**：最终阶段问题码 0、已绑定签名驱动、适配器 `Up`、有 IPv4 或 IPv6 网关、有 DNS 服务器、DNS 解析成功、HTTPS 返回 200–399。
- **Fail**：基线有缺驱动设备，但最终阶段未满足上述任一项；说明列列出未通过项。
- **Incomplete**：缺 `baseline` 或 `after-install`／`after-restart`，补采后重跑。
- **Inbox**：基线设备已绑定签名驱动，说明该组合由系统自带驱动可用，按准备规则不计入断网恢复。

同一场景有多条 `after-*` 记录时取时间最新的一条，并优先 `after-restart`。加 `-FailOnIncomplete` 时任一非 Pass 会返回退出码 1，可直接作为验收门禁。

## 需重点观察

- 虚拟机已用合成缺驱动设备验证四种新装、PE 修复和运行中安装的流程，见[验证记录](validation-record.md#2026-11-13-hyper-v-消费版断网部署与修复)。矩阵结果仍只记录实体网卡。
- Windows 11 Home 的首次设置要求联网。NEW 场景需确认无人值守本地账户能否在 Home 版完成，以及进入桌面后能否用驱动恢复联网。
- Windows 10 22H2 与 Windows 11 使用不同的 INF 适用范围。同一驱动包在 Windows 10 上若被拒绝，记录 INF 的 `TargetOSVersion` 和程序提示。
- Wi-Fi 绑定后还需手动连接无线网络。记录从安装完成到 HTTPS 成功的操作步骤，但不记录网络名。
- 结果为「需要重启」或「绑定未确认」时，重启后补录 `after-restart`，不直接记为失败。
