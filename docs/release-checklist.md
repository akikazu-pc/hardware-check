# 发布清单

全部完成前不要公开下载。

## 硬件验证

在有风扇的真实电脑上，双击运行并点“是”。详细结果记入 [验证记录](validation-record.md)。

- [ ] Intel LGA1700 / LGA1851 平台
- [ ] AMD AM5 平台
- [ ] NVIDIA 独立显卡
- [ ] AMD 独立显卡
- [ ] 不同厂商主板的 CPU_FAN 和 PUMP 传感器名称
- [ ] 水冷、风冷、只接 PUMP 三种接线的散热判断
- [ ] 无独立显卡的电脑
- [ ] 笔记本：整机型号、电池健康、触控板、内置屏幕和扬声器
- [ ] SATA 硬盘和 USB 硬盘盒的健康读取
- [ ] 接上扬声器和麦克风后的识别，扬声器测试和麦克风回放实际听一次
- [ ] 带 UAC 提示的电脑：点“是”、点“否”两种路径；未装 PawnIO 时自动安装，退出后自动卸载
- [ ] 查清并关闭验证记录中的启动崩溃（0xC0000409）；现已在 `%LOCALAPPDATA%\AkikazuHardwareCheck\startup.log` 记录启动阶段，复现后看最后一行
- [ ] USB 水冷的品牌显示；Wi-Fi 信号；无 TPM 或传统 BIOS 的电脑
- [ ] 真实双显卡（不同型号、同型号）的目标选择和传感器对应
- [ ] 未安装 .NET 的干净 Windows 10 和 Windows 11
- [ ] 标准流程完整运行一次（约 5 分钟）
- [ ] 驱动异常场景（设备丢失、驱动重置）
- [ ] 实际打印 A4 测试报告
- [ ] 有 CPU 传感器权限时的功耗、频率、电压读数；AMD 和 NVIDIA 的传感器名称
- [ ] 在有散热的电脑上跑完整双烤，确认整机功耗下负载和温度保护
- [ ] 安全启动未开启的电脑：重启进入 BIOS（`shutdown /r /fw`）
- [ ] 把真实工具导出的 JSON 导入网站服务表单并打印

## 法务

- [ ] 审阅 `THIRD-PARTY-NOTICES.md` 中的待确认项
- [ ] 确认报告文案（尤其是免责说明）的日文表述

## Portable ZIP/EXE

- [x] 确认 `Directory.Build.props` 的版本号（0.2.1）
- [x] 确认 GitHub Actions 的构建、单元测试和窗口冒烟测试全绿（`main` 与 `v0.2.1` tag 均通过）
- [x] 运行 `scripts/publish.ps1`，确认体积没有异常增长（v0.2.1 实测：程序 53.1 MB，压缩包 47.8 MB，SHA-256 `1717317BBE222D078F9D54FA3651130CB049AB7D2F364FB16514DE259C56C6F6`）
- [x] 在仓库 `akikazu-pc/hardware-check` 的 GitHub Release 上传 `AkikazuHardwareCheck-win-x64.zip`（已发布到 [`v0.2.1`](https://github.com/akikazu-pc/hardware-check/releases/tag/v0.2.1)，另有在线版和仅含 Realtek 8852 Wi-Fi 驱动的公开离线 ESD）
- 公开离线 ESD 使用 `scripts/publish-network-rescue-bundles.ps1 -PublicOffline -RealtekVendorZip <原厂 ZIP>` 构建。核对成品低于 2 GiB，在 Win10 和 Win11 用系统 DISM 还原，逐文件校验并离线启动。发布后从公开链接重新下载核对 SHA-256。
- [x] 在网站仓库的 `app/data/tools/hardware-check-release.json` 填入 `url`、`sha256`、`version`（已填 v0.2.1；网站构建时 `sync-hardware-release.ts` 会自动校验并同步）
- [ ] 每次发新版都同步上述 `sha256` 和 `version`：`latest` 链接会自动指向新版，网页上的版本和校验值不会
- [ ] 尽可能完成代码签名，并在签名后重新计算 SHA-256
- [x] 在网站发布：用途、支持的 Windows 版本、版本号、下载链接、文件大小、SHA-256、更新记录、使用注意事项（Deploy 运行 43398692733 完成，构建日志确认数据为 v0.2.1）
- [x] 确认 ZIP 内含 `licenses/` 和 `THIRD-PARTY-NOTICES.md`（发布脚本已包含，0.2.1 包已核对）

## MSI 安装包

MSI 使用 `Website` 能力并按 per-machine 安装到 Program Files。MSI 只安装应用、许可证、注册信息和开始菜单
快捷方式；PawnIO 仍由应用在用户明确运行时按现有生命周期管理，不注册为 MSI 驱动组件。

- [x] 选择仍维护的 Advanced Installer Freeware；Simple 项目允许商业和非商业用途且可免费分发
- [ ] 从[官方 Freeware 下载页](https://www.advancedinstaller.com/advanced-installer-free.html)安装当前版本；页面要求创建免费账户，安装时只需保留 Freeware/Simple 功能
- [ ] 使用永久 UpgradeCode `{12B63A4E-3E26-4FF5-8A5B-1B0900C54A7A}`，发布后不得更换
- [ ] 安装当前 Advanced Installer Freeware（v22+ 会设置 `ADVINST_COM`），运行 `scripts/publish-msi.ps1`
- [ ] 确认 Program Files 文件、开始菜单入口、应用与 Windows“已安装的应用”中的版本一致
- [ ] 验证交互安装、`msiexec /i ... /quiet /l*v ...` 静默安装和标准用户/UAC 路径
- [ ] 验证 Major Upgrade、同版本修复、低版本降级阻止和 `msiexec /x ... /quiet` 静默卸载
- [ ] 卸载后检查程序文件、快捷方式和安装注册项；保留用户主动保存的报告
- [ ] 先签应用 EXE，再构建 MSI，最后签 MSI；签名后重新计算 SHA-256

已放弃可能产生维护费的 WiX 6/7 和停止维护的 WiX 5。构建脚本只创建 Advanced Installer 的永久免费 Simple
项目，不使用试用或付费功能。当前执行环境阻止静默安装系统软件，因此本机尚未安装编译器、尚未生成 MSI；安装后
脚本会创建项目、加入 Website payload、生成开始菜单快捷方式并输出 MSI 与 SHA-256。

## Microsoft Store 版

商店版和官网完整版共用代码。使用 `DistributionChannel=Store` 构建时，程序不自动提权、不安装或卸载
PawnIO、不显示需要管理员权限的入口，并从程序集排除 PawnIO 安装程序。官网构建默认仍为 `Website`，行为不变。

- [x] 运行 `scripts/publish-store-payload.ps1`；0.2.1 输出确认 `Channel: Store`、`PawnIO=False`，不含 `pawnio.setup.exe`
- [ ] 在 Partner Center 保留产品名称，并取得准确的 Package Identity Name、Publisher 和 Publisher Display Name
- [ ] 根据 Partner Center 身份生成 MSIX manifest；不得使用示例 Publisher 或临时身份提交
- [x] 从 `my-site` 既有品牌图形生成包图标和 300 × 300 Store listing 图标，并记录来源
- [ ] 准备最终版截图、简短说明、完整说明、搜索词、支持 URL 和隐私政策 URL
- [ ] 隐私政策说明硬件信息和报告只保存在本机；Cloudflare 网络测速仅在用户主动启动时发送测试流量
- [ ] 运行 Windows App Certification Kit，并保存结果
- [ ] 在未安装 .NET、未安装 PawnIO 的干净 Windows 10 和 Windows 11 上安装 MSIX 并完成窗口实测
- [ ] 确认商店版启动不出现 UAC，工具菜单没有“重启进入 BIOS”和“修复为日语 106 键”
- [ ] 确认商店版缺少 CPU 温度、主板风扇等特权传感器时不会显示误导性的管理员/PawnIO提示
- [ ] 确认安装、更新、卸载后不残留驱动、服务或自启动项
- [ ] Claude 独立复核 Store 政策、隐私、第三方许可和认证说明
- [ ] 商店提交、公开可见时间和网站宣传分别取得授权；不得用本地构建通过代替认证通过

当前仓库可生成经过能力裁剪的 Store payload，并已提供参数化 manifest、PNG 素材与 MSIX 脚本。最终 MSIX 仍受
Partner Center 真实身份阻断；身份取得前不生成假 manifest。发行者本人步骤见
[`partner-center-store-setup.md`](partner-center-store-setup.md)。

网站规划路径为 `/tools/hardware-check/` 和 `/downloads/`。网站页面和部署不在本目录内，需要单独授权和实施。
