<p align="center">
  <img src="logo.ico" width="72" alt="TeamsX" />
</p>

<h1 align="center">TeamsX</h1>

<p align="center">
  <strong>Microsoft Teams 网页版多账号管理客户端</strong><br>
  基于 WebView2 内核 · 独立会话 · 专业办公场景
</p>

<p align="center">
  <a href="https://github.com/IMAF7/TeamsX/releases/latest"><img src="https://img.shields.io/github/v/release/IMAF7/TeamsX?label=Release&style=flat-square" alt="Release" /></a>
  <a href="https://github.com/IMAF7/TeamsX/blob/master/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="License" /></a>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?style=flat-square" alt="Platform" />
  <img src="https://img.shields.io/badge/Engine-WebView2-6264A7?style=flat-square" alt="Engine" />
</p>

<p align="center">
  <a href="https://imaf7.github.io/TeamsX/download/"><b>下载安装包</b></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/IMAF7/TeamsX/releases">历史版本</a>
  &nbsp;·&nbsp;
  <a href="使用介绍.txt">使用说明</a>
</p>

---

## 简介

TeamsX 是一款面向 Windows 的 **Teams 网页版多开管理工具**。在单一窗口中管理多个 Teams 账号，每个账号拥有独立的 Cookie 与登录态，互不串号。内置 TeamsXAi 辅助模块，支持消息通知、来电提醒与完整的账号组织能力。

<p align="center">
  <img src="assets/1.png" width="780" alt="TeamsX 主界面" />
  <br>
  <sub>左侧账号列表与右侧 Teams 网页同屏管理</sub>
</p>

<p align="center">
  <img src="assets/2.png" width="780" alt="TeamsXAi" />
  <br>
  <sub>TeamsXAi 内置对话模块，按 Esc 返回主界面</sub>
</p>

---

## 功能概览

| 模块 | 说明 |
|------|------|
| **多账号管理** | 独立登录态，支持添加、导入、分组、置顶与备注搜索 |
| **Teams 网页** | Edge WebView2 内核，与系统 Edge 行为一致 |
| **TeamsXAi** | 内置 DeepSeek 对话，与 Teams 会话隔离 |
| **消息通知** | 未读角标、提示音、来电铃声 |
| **资源调度** | 并发上限、休眠/唤醒、内存监控与缓存清理 |
| **侧栏锁定** | 防止误触切换，适合固定工位使用 |

---

## 下载与安装

| 渠道 | 地址 |
|------|------|
| 官方下载页 | https://imaf7.github.io/TeamsX/download/ |
| 最新安装包 | [TeamsX_Setup_2.2.0.exe](https://github.com/IMAF7/TeamsX/releases/latest/download/TeamsX_Setup_2.2.0.exe) |
| 所有版本 | [GitHub Releases](https://github.com/IMAF7/TeamsX/releases) |

**系统要求：** Windows 10 / 11（64 位）· WebView2 Runtime · 无需 Python

安装后数据默认保存在 `D:\TeamsX`，可通过环境变量 `TEAMSX_DATA_ROOT` 自定义。

---

## 账号状态

| 指示 | 状态 |
|------|------|
| 绿色圆点 | 已登录，处于活跃池 |
| 黄色圆点 | 已登录，休眠中（保留登录态） |
| 红色圆点 | 未登录或登录失败 |
| 红色数字 | Teams 未读消息数 |

---

## 快速开始

### 用户使用

1. 下载并运行安装包，按向导完成安装
2. 启动 TeamsX，点击侧栏 **添加** 录入账号
3. 点击账号条目进入 Teams 网页；默认主界面为 TeamsXAi
4. 按 `Esc` 从 Teams 页面返回 TeamsXAi 主界面

详细操作请参阅 [使用介绍.txt](使用介绍.txt)。

### 开发者构建

```powershell
# 首次环境准备
.\setup_build_env.ps1

# 源码运行
python -m teamsx

# 打包（便携版 + 安装包）
.\build.ps1

# 发布到 GitHub Releases
.\publish_release.ps1
```

更多技术细节见 [BUILD.md](BUILD.md)、[ENV.md](ENV.md)。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TEAMSX_DATA_ROOT` | `D:\TeamsX` | 数据存储根目录 |
| `TEAMSX_WEBVIEW2_BROWSER_FOLDER` | — | 固定版 WebView2 x64 运行时路径 |

---

## 项目结构

```
TeamsX/
├── TeamsX.py          # 主程序
├── teamsx/            # 核心模块（引擎、通知、UI）
├── audio/             # 通知音与铃声
├── build.ps1          # 一键打包
├── download/          # 官方下载页
└── release/           # 构建产物（不纳入版本库）
```

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源。

```
Copyright (c) 2026 IMAF7
```

---

<p align="center">
  <sub>TeamsX 为第三方工具，与 Microsoft Teams 无官方关联。</sub>
</p>
