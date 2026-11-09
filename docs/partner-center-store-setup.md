# Partner Center：发行者本人操作清单

Partner Center 是微软管理 Store 产品名称、包身份、商店介绍和正式提交的后台。这里取得的三个值会写入
`AppxManifest.xml`；它们不是密码，但必须与该产品在 Partner Center 中显示的值逐字一致，否则上传会被拒绝。

## 回家后需要本人完成

1. 打开 [Partner Center](https://partner.microsoft.com/dashboard)，使用准备作为发行者的 Microsoft 账号登录。
2. 如果尚未注册 Windows 开发者账户，按页面完成账户类型、法定名称、地址、付款和身份验证。费用、协议和身份确认
   必须由账户持有人本人处理。
3. 进入 **Apps and games**，选择 **New product**，创建 **MSIX or PWA app**。
4. 检查并保留产品名。建议先尝试 `秋和PC 硬件测试工具`；名称不可用时不要随意改品牌，先记录页面提示。
5. 打开该产品的 **Product management > Product identity**。
6. 把以下三项原样复制到纯文本中并交给 Codex：
   - **Package/Identity/Name**（脚本参数 `IdentityName`）
   - **Package/Identity/Publisher**（脚本参数 `Publisher`，通常以 `CN=` 开头）
   - **Publisher display name**（脚本参数 `PublisherDisplayName`）

不要发送账号密码、验证码、恢复代码、API 密钥、证书私钥或 `.pfx` 密码。上述三个身份字符串本身不是秘密。

官方说明：

- [为 MSIX 应用保留名称](https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/reserve-your-apps-name)
- [Windows 应用包身份说明](https://learn.microsoft.com/windows/apps/desktop/modernize/package-identity-overview)
- [创建 MSIX 应用提交](https://learn.microsoft.com/windows/apps/publish/publish-your-app/create-app-submission?pivots=store-installer-msix)
- [截图、图标和展示图片要求](https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/screenshots-and-images)

## 已由项目准备

- Store 构建会移除 PawnIO、自动提权、自启动、清理、跨进程优化和系统修改入口。
- `packaging/store/Assets/` 已包含包清单需要的四张 PNG。
- `packaging/store/ListingAssets/AppTileIcon-300x300.png` 已包含推荐的 1:1 商店图标。
- `scripts/publish-store-msix.ps1` 会校验三个真实身份值，生成 MSIX 并输出 SHA-256。

至少一张桌面截图是正式提交的必需项。应在最终候选版本和真实 Windows 桌面上截图；当前不提前使用开发中界面冒充
最终截图。微软建议准备至少四张，单张 PNG 不超过 50 MB。

## 取得身份后的构建命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts/publish-store-msix.ps1 `
  -IdentityName '<Package Identity Name>' `
  -Publisher '<Publisher>' `
  -PublisherDisplayName '<Publisher Display Name>' `
  -MakeAppxPath '<Windows SDK 中的 makeappx.exe>'
```

提交、接受协议和点击正式发布仍由发行者本人完成；本地生成成功不等于 Store 认证通过。
