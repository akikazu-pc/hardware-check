# 用浏览器窗口补齐 Dell / Lenovo（我来解析，你只负责复制）

这两家的驱动列表都在登录态或浏览器端接口后面，直连、阅读器代理、无头浏览器都被拦。你用已登录的浏览器打开页面，把内容复制给我即可。以下两种方式选一种，**方式 B 最省事**。

## 需要的页面

**Dell Alienware（5 个型号，8 格待核）**

1. https://www.dell.com/support/home/en-us/product-support/product/alienware-area-51-aa16250-gaming-laptop/drivers
2. https://www.dell.com/support/home/en-us/product-support/product/alienware-area-51-aa18250-gaming-laptop/drivers
3. https://www.dell.com/support/home/en-us/product-support/product/alienware-aurora-ac16250-gaming-laptop/drivers
4. https://www.dell.com/support/home/en-us/product-support/product/alienware-aurora-ac16251-gaming-laptop/drivers
5. https://www.dell.com/support/home/en-us/product-support/product/alienware-da15260-gaming-laptop/drivers

**Lenovo（4 个型号，7 格待核）**

1. https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/legion-series/legion-5-15iax11/downloads
2. https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/legion-series/legion-pro-5-16irx10/downloads
3. https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/legion-series/legion-pro-7-16adr10h/downloads
4. https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/legion-series/legion-pro-7-16afr10h/downloads

## 方式 A：复制整页文本（最简单）

1. 打开页面，等驱动列表完全出现。
2. 如果页面有系统选择器（Windows 10 / Windows 11），先选 Windows 10 复制一次，再选 Windows 11 复制一次。
3. 在页面正文区域按 `Ctrl+A` 再 `Ctrl+C`。
4. 粘贴到聊天里，或用记事本保存为：
   - `D:\Users\user\Documents\GitHub\hardware-check\artifacts\capture-dell-<型号>.txt`
   - `D:\Users\user\Documents\GitHub\hardware-check\artifacts\capture-lenovo-<型号>.txt`
5. 告诉我「已保存」即可。

## 方式 B：浏览器控制台导出表格（更干净）

1. 打开页面，等驱动列表出现（必要时把系统选择器切到 Windows 10 / 11 各做一次）。
2. 按 `F12` → 选 `Console`（控制台）。
3. 粘贴下面这段并回车，它会把页面里所有表格行导出成 JSON 复制到剪贴板：

   ```js
   copy(JSON.stringify([...document.querySelectorAll('table tr, [class*="table"] [class*="row"], [class*="list"] [class*="item"]')].map(el => [...el.querySelectorAll('td, [class*="cell"], [class*="column"]')].map(td => td.innerText.trim()).filter(Boolean)).filter(row => row.length >= 2 && row.join(' ').length < 500).slice(0, 500), null, 1))
   ```

4. 回到聊天，`Ctrl+V` 粘贴。
5. 如果结果为空（页面不是表格结构），改用方式 A。

## 我需要从内容里看到什么

- 驱动名称、版本、发布日期、分类；
- 每一行对应的系统（Windows 10 / Windows 11），尤其是 **Network / Wireless / WLAN / Wi-Fi / Killer / MediaTek / Intel Wi-Fi** 这类条目；
- 如果页面只有“系统选择器 + 列表”，两个系统各给我一份即可。

我会把这些整理成 `docs/network-rescue-dell-lenovo-proof.csv` 并回填主表；非官方来源一律单独标注。

## 注意

- 复制内容里可能带 cookie/token（方式 B 不会）。Don't 粘贴账号密码；只发页面内容即可。
- 如果某个页面打不开或没有驱动列表，直接告诉我型号即可，我记为「页面无数据」。
