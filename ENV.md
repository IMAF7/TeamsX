# TeamsX 运行环境（WebView2 单内核）

## 推荐架构

| 组件 | 选择 |
|------|------|
| **Teams 页面** | **WebView2 单内核**（Edge 148 原生，与系统 Edge 一致） |
| UI 壳 | PyQt6 |
| 回退 | 仅当 `TEAMSX_ENGINE=qtwebengine` 时使用 Qt WebEngine（不推荐，视频/DRM 易出问题） |

**结论：用一个内核（WebView2）即可。** 双内核仅增加包体积和拦截逻辑复杂度，对 Teams 网页版没有额外收益。

---

## 系统要求

- Windows 10/11 **64 位**
- **Python 3.10+ 64 位**（与 WebView2 固定版 x64 位数一致）
- 磁盘：`D:\TeamsX` 数据目录（可用环境变量改路径）

---

## Python 依赖（开发 / 打包）

```powershell
cd C:\Users\admin\Desktop\DDDA
.\setup_build_env.ps1
# 或手动：
pip install -r requirements-build.txt
```

| 包 | 用途 |
|----|------|
| PyQt6 | 界面 |
| qtwebview2, qtpy, pythonnet, pywin32 | WebView2 嵌入 |
| certifi | HTTPS 证书 |
| markdown, mistune, pygments | AI 面板 |
| PyQt6-WebEngine | **仅** `TEAMSX_ENGINE=qtwebengine` 回退时需要 |
| pyinstaller | 打包 |

---

## WebView2 运行时（你已安装 148.0.3967.83 x64）

两种方式任选其一：

### 方式 A：Evergreen（推荐）

系统已装 Edge / Evergreen WebView2 Runtime 即可，**无需**再指定路径。

### 方式 B：固定版 x64（你已下载的包）

目录内需有 `msedgewebview2.exe`，且必须是 **x64**（64 位 Python 不能用 x86 包）。

PowerShell 启动前：

```powershell
$env:TEAMSX_WEBVIEW2_BROWSER_FOLDER = "C:\Path\To\Microsoft.WebView2.FixedVersionRuntime.148.0.3967.83.x64"
python TeamsX.py
```

或写入用户环境变量永久生效。

---

## 常用环境变量

| 变量 | 说明 |
|------|------|
| `TEAMSX_DATA_ROOT` | 数据目录，默认 `D:\TeamsX` |
| `TEAMSX_WEBVIEW2_BROWSER_FOLDER` | 固定版 WebView2 x64 目录 |
| `TEAMSX_ENGINE` | 默认 `webview2`；设 `qtwebengine` 才走 Chromium 回退 |
| `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` | 高级：额外浏览器参数（引擎会自动合并 SSO） |

---

## 启动

```powershell
cd C:\Users\admin\Desktop\DDDA
python TeamsX.py
```

正常日志应包含：

```text
[TeamsX] Teams 页面引擎: WebView2
[TeamsX] 当前 Teams 引擎: webview2
```

---

## 关于「别人发的视频 / SharePoint 要权限」

这是 **Teams 网页版 + 跨用户 SharePoint 文件** 的已知限制，不是 TeamsX 独有：

- 自己发的视频：通常走聊天内联播放
- 别人发的：Teams 常 `window.open` 到发件人 SharePoint，需要 Microsoft 在会话里下发临时令牌

**重构后原则：TeamsX 不再拦截 `window.open` / 新窗口 / SharePoint 导航**，行为与 Edge 里打开 Teams 一致。若 Edge 浏览器登录 Teams 后同样「需要访问权限」，说明是账号/共享权限问题，需在 Teams 里向发件人申请访问或使用官方 Teams 客户端。

---

## 打包

```powershell
.\build.ps1
```

详见 `BUILD.md`。
