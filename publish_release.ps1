# TeamsX — 发布安装包到 GitHub Releases
# 用法: .\publish_release.ps1
# 前置: 已运行 .\build.ps1，且 gh 已登录 (gh auth login)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Version = "2.2.0"
$Tag = "v$Version"
$SetupName = "TeamsX_Setup_$Version.exe"
$SetupPath = Join-Path $Root "release\$SetupName"
$Repo = "IMAF7/TeamsX"

function Find-Gh {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) { return $gh.Source }
    $portable = Join-Path $env:TEMP "gh-cli\bin\gh.exe"
    if (Test-Path $portable) { return $portable }
    throw "未找到 gh CLI。请安装 GitHub CLI 或先运行: winget install GitHub.cli"
}

if (-not (Test-Path $SetupPath)) {
    throw "安装包不存在: $SetupPath`n请先运行 .\build.ps1"
}

$Gh = Find-Gh
Write-Host "GitHub CLI: $Gh"

& $Gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "gh 未登录。请运行: gh auth login"
}

Push-Location $Root
try {
    if (-not (Test-Path ".git")) {
        & "C:\Program Files\Git\bin\git.exe" init
        & "C:\Program Files\Git\bin\git.exe" branch -M main
    }

    $remoteUrl = "https://github.com/$Repo.git"
    $remotes = & "C:\Program Files\Git\bin\git.exe" remote 2>$null
    if ($remotes -notcontains "origin") {
        & "C:\Program Files\Git\bin\git.exe" remote add origin $remoteUrl
    }

    $repoExists = & $Gh repo view $Repo --json name -q .name 2>$null
    if (-not $repoExists) {
        Write-Host "创建仓库 $Repo ..."
        & $Gh repo create $Repo --public --source=. --remote=origin --description "Microsoft Teams 多开客户端" --push
    }

    Write-Host "发布 $Tag ..."
    $existing = & $Gh release view $Tag --repo $Repo 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Release $Tag 已存在，上传/更新安装包 ..."
        & $Gh release upload $Tag $SetupPath --repo $Repo --clobber
    }
    else {
        & $Gh release create $Tag $SetupPath `
            --repo $Repo `
            --title "TeamsX $Version" `
            --notes "## TeamsX $Version`n`n- Windows 64 位安装包`n- 多账号、消息通知、通话提醒`n`n下载页: https://imaf7.github.io/TeamsX/download/"
    }

    Write-Host ""
    Write-Host "发布完成!"
    Write-Host "  安装包: https://github.com/$Repo/releases/latest/download/$SetupName"
    Write-Host "  下载页: download\index.html (GitHub Pages)"
}
finally {
    Pop-Location
}
