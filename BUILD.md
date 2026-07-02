# TeamsX 打包说明

## 前置条件

- Windows 10/11 x64
- Python 3.10+（已加入 PATH）
- 同目录文件：`TeamsX.py`、`logo.ico`、`TeamsX.spec`
- **通知音目录**：`audio\teams_notify_official.mp3`（打包必填，会复制到 exe 旁的 `audio\`）
- **安装包版** 额外需要 [Inno Setup 6](https://jrsoftware.org/isdl.php)

## 一键打包

已安装 **Inno Setup 6** 时，直接运行会同时生成纯净版与安装包：

```powershell
cd c:\Users\admin\Desktop\DDDA
.\build.ps1
```

若 ISCC 不在默认路径，可手动指定：

```powershell
.\build.ps1 -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

仅生成纯净版（跳过 Inno Setup）：

```powershell
.\build.ps1 -PortableOnly
```

完整日志写入同目录 `build.log`。

## 输出目录

| 类型 | 路径 |
|------|------|
| 纯净版（绿色便携） | `release\TeamsX_纯净版\` → 运行 `TeamsX.exe` |
| 安装包版 | `release\TeamsX_Setup_2.2.0.exe` |
| 下载页 | `download\index.html` |

纯净版可直接压缩 `TeamsX_纯净版` 文件夹分发；安装包版会安装到 `C:\Program Files\TeamsX\`。

## 发布到 GitHub Releases

```powershell
.\build.ps1
.\publish_release.ps1
```

- 仓库：https://github.com/IMAF7/TeamsX
- 最新安装包：https://github.com/IMAF7/TeamsX/releases/latest/download/TeamsX_Setup_2.2.0.exe
- 下载页（GitHub Pages）：https://imaf7.github.io/TeamsX/download/

## 说明

- 程序数据仍固定在 `D:\TeamsX`（与源码逻辑一致），与安装位置无关。
- 通知音路径：安装目录或纯净版目录下的 `audio\teams_notify_official.mp3`（可自行替换该文件）。
- 首次在本机打包会自动创建 `.venv-build` 虚拟环境并安装依赖。
- 若本机已安装 Microsoft Edge，程序启动时会尝试复制 `ffmpeg.dll` / Widevine 以改善视频播放。
