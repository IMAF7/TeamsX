# -*- coding: utf-8 -*-
"""
Qt WebEngine 回退路径：Chromium 标志、Widevine、ffmpeg。
WebView2 为默认引擎时，仅在 TEAMSX_ENGINE=qtwebengine 或 WebView2 不可用时加载。
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import sys
from typing import List, Optional, Set, Tuple

from teamsx.config import DATA_ROOT

_WEBENGINE_MEDIA_READY = False
_QT_WEBENGINE_CHROMIUM_VERSION: str = ""
_WIDEVINE_DLL_REL = os.path.join("_platform_specific", "win_x64", "widevinecdm.dll")


def set_qt_webengine_chromium_version(version: str) -> None:
    global _QT_WEBENGINE_CHROMIUM_VERSION
    _QT_WEBENGINE_CHROMIUM_VERSION = version or ""


def apply_qtwebengine_default_chromium_flags() -> None:
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    for flag in (
        "--autoplay-policy=no-user-gesture-required",
        "--ignore-gpu-blocklist",
        "--enable-accelerated-video-decode",
        "--enable-encrypted-media",
        "--enable-features=PlatformHEVCDecoderSupport,UseMediaFoundationRenderer,WidevinePersistentLicenseSupport",
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
    ):
        if flag not in flags:
            flags = f"{flags} {flag}".strip()
    if flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags


def _append_qtwebengine_chromium_flag(flag: str) -> None:
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    if flag not in flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{flags} {flag}".strip()


def _chromium_flag_path_for_win(path: str) -> str:
    return os.path.normpath(os.path.abspath(path)).replace("\\", "/")


def _strip_widevine_flags_from_env() -> None:
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    if not flags:
        return
    flags = re.sub(r'--widevine-path=(?:"[^"]*"|[^\s]+)', "", flags)
    flags = re.sub(r'--widevine-cdm-path=(?:"[^"]*"|[^\s]+)', "", flags)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags.split()).strip()


def _apply_widevine_chromium_flags(dll_path: str) -> None:
    if not dll_path or not os.path.isfile(dll_path):
        return
    norm = _chromium_flag_path_for_win(dll_path)
    _strip_widevine_flags_from_env()
    wv_flag = f'--widevine-path="{norm}"'
    cdm_flag = f'--widevine-cdm-path="{norm}"'
    _append_qtwebengine_chromium_flag(wv_flag)
    _append_qtwebengine_chromium_flag(cdm_flag)
    print(f"[媒体] 最终 Widevine flag: {wv_flag}")
    print(f"[媒体] Widevine CDM 文件: {os.path.abspath(dll_path)}")


def _prefer_widevine_dll_for_flags(candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None

    def _sort_key(p: str) -> Tuple[int, int, int]:
        upper = os.path.normcase(os.path.abspath(p))
        data_prefix = os.path.normcase(os.path.abspath(DATA_ROOT))
        no_space = 0 if " " not in p else 1
        on_teamsx = 0 if upper.startswith(data_prefix) else 1
        return (no_space, on_teamsx, len(p))

    return sorted(candidates, key=_sort_key)[0]


def _register_widevine_dll_dir(dll_path: str) -> None:
    if not dll_path or not os.path.isfile(dll_path):
        return
    dll_dir = os.path.dirname(os.path.abspath(dll_path))
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(dll_dir)
        except Exception as e:
            print(f"[媒体] 注册 DLL 目录失败: {e}")


def _app_bin_dirs() -> List[str]:
    dirs: List[str] = []
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    if os.path.isdir(exe_dir):
        dirs.append(exe_dir)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and os.path.isdir(meipass):
        dirs.append(meipass)
        for sub in ("PyQt6/Qt6/bin", os.path.join("PyQt6", "Qt6", "bin")):
            p = os.path.join(meipass, sub)
            if os.path.isdir(p):
                dirs.append(p)
    internal = os.path.join(exe_dir, "_internal", "PyQt6", "Qt6", "bin")
    if os.path.isdir(internal):
        dirs.append(internal)
    seen: Set[str] = set()
    out: List[str] = []
    for d in dirs:
        d = os.path.normpath(d)
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _widevine_dll_in_tree(widevine_root: str) -> Optional[str]:
    if not widevine_root or not os.path.isdir(widevine_root):
        return None
    direct = os.path.join(widevine_root, _WIDEVINE_DLL_REL)
    if os.path.isfile(direct):
        return direct
    try:
        for name in os.listdir(widevine_root):
            nested_root = os.path.join(widevine_root, name)
            if not os.path.isdir(nested_root):
                continue
            nested = os.path.join(nested_root, _WIDEVINE_DLL_REL)
            if os.path.isfile(nested):
                return nested
    except OSError:
        pass
    return None


def _dedupe_existing_files(paths: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for raw in paths:
        if not raw:
            continue
        p = os.path.normpath(os.path.abspath(raw))
        if p in seen or not os.path.isfile(p):
            continue
        seen.add(p)
        out.append(p)
    return out


def _edge_application_roots() -> List[str]:
    roots: List[str] = []
    seen: Set[str] = set()
    bases: List[str] = []
    for key in ("ProgramFiles(x86)", "ProgramFiles"):
        val = os.environ.get(key, "").strip()
        if val:
            bases.append(val)
    bases.extend((r"C:\Program Files (x86)", r"C:\Program Files"))
    for base in bases:
        base = os.path.normpath(base)
        if not base or base in seen or not os.path.isdir(base):
            continue
        seen.add(base)
        app = os.path.join(base, "Microsoft", "Edge", "Application")
        if os.path.isdir(app):
            roots.append(app)
    return roots


def _edge_version_dirs(app_root: str) -> List[str]:
    if not app_root or not os.path.isdir(app_root):
        return []
    try:
        vers = sorted(
            (d for d in os.listdir(app_root) if re.match(r"^\d+\.\d+", d)),
            reverse=True,
        )
        return [os.path.join(app_root, v) for v in vers]
    except OSError:
        return []


def _iter_edge_version_dirs_program_files():
    for app_root in _edge_application_roots():
        for ver_dir in _edge_version_dirs(app_root):
            yield ver_dir


def _chromium_major(version: str) -> Optional[int]:
    m = re.match(r"^(\d+)", (version or "").strip())
    return int(m.group(1)) if m else None


def _find_chrome_application_dirs() -> List[str]:
    roots: List[str] = []
    for base in (
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        r"C:\Program Files (x86)",
        r"C:\Program Files",
    ):
        base = os.path.normpath(base)
        app_root = os.path.join(base, "Google", "Chrome", "Application")
        if not os.path.isdir(app_root):
            continue
        try:
            vers = sorted(
                (d for d in os.listdir(app_root) if re.match(r"^\d+\.\d+", d)),
                reverse=True,
            )
        except OSError:
            continue
        for ver in vers:
            roots.append(os.path.join(app_root, ver))
    return roots


def _iter_all_browser_version_dirs():
    for ver_dir in _iter_edge_version_dirs_program_files():
        base = os.path.basename(ver_dir)
        m = re.match(r"^(\d+)\.", base)
        if m:
            yield int(m.group(1)), ver_dir, "Edge"
    for ver_dir in _find_chrome_application_dirs():
        base = os.path.basename(ver_dir)
        m = re.match(r"^(\d+)\.", base)
        if m:
            yield int(m.group(1)), ver_dir, "Chrome"


def _find_version_matched_widevine() -> Tuple[Optional[str], Optional[str], Optional[str], int]:
    env_dll = os.environ.get("TEAMSX_EDGE_WIDEVINE_DLL", "").strip()
    if env_dll and os.path.isfile(env_dll):
        return None, env_dll, "", 0
    qt_major = _chromium_major(_QT_WEBENGINE_CHROMIUM_VERSION)
    best_delta = 9999
    best: Tuple[Optional[str], Optional[str], Optional[str]] = (None, None, None)
    for browser_major, ver_dir, browser in _iter_all_browser_version_dirs():
        wv_dir = os.path.join(ver_dir, "WidevineCdm")
        dll = _widevine_dll_in_tree(wv_dir)
        if not dll:
            continue
        delta = abs(browser_major - qt_major) if qt_major is not None else browser_major
        if delta < best_delta:
            best_delta = delta
            best = (wv_dir, dll, ver_dir)
    wv_dir, dll, ver_dir = best
    return wv_dir, dll, ver_dir, best_delta


def _collect_edge_widevine_dll_paths() -> List[str]:
    paths: List[str] = []
    _wv_dir, dll, _ver, _delta = _find_version_matched_widevine()
    if dll:
        paths.append(dll)
    for _major, ver_dir, _browser in _iter_all_browser_version_dirs():
        dll = _widevine_dll_in_tree(os.path.join(ver_dir, "WidevineCdm"))
        if dll:
            paths.append(dll)
    return _dedupe_existing_files(paths)


def detect_installed_edge_version() -> str:
    """返回 Program Files 中已安装 Edge 的最高版本号（如 148.0.3967.83），无则空串。"""
    for ver_dir in _iter_edge_version_dirs_program_files():
        ver = os.path.basename(ver_dir)
        if re.match(r"^\d+\.\d+", ver):
            return ver
    return ""


def teams_edge_user_agent(*, for_webview2: bool = False) -> str:
    if for_webview2:
        return ""
    ver = (_QT_WEBENGINE_CHROMIUM_VERSION or "131.0.0.0").strip()
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36 Edg/{ver}"
    )


def _find_edge_media_from_program_files() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    ffmpeg_src: Optional[str] = None
    widevine_dir: Optional[str] = None
    widevine_dll: Optional[str] = None
    for ver_dir in _iter_edge_version_dirs_program_files():
        ff = os.path.join(ver_dir, "ffmpeg.dll")
        wv = os.path.join(ver_dir, "WidevineCdm")
        dll = _widevine_dll_in_tree(wv)
        if not ffmpeg_src and os.path.isfile(ff):
            ffmpeg_src = ff
        if not widevine_dll and dll:
            widevine_dir = wv
            widevine_dll = dll
        if ffmpeg_src and widevine_dll:
            break
    return ffmpeg_src, widevine_dir, widevine_dll


def _widevine_dll_candidates() -> List[str]:
    candidates: List[str] = []
    dll = _widevine_dll_in_tree(os.path.join(DATA_ROOT, "WidevineCdm"))
    if dll:
        candidates.append(dll)
    for base in _app_bin_dirs():
        dll = _widevine_dll_in_tree(os.path.join(base, "WidevineCdm"))
        if dll:
            candidates.append(dll)
    candidates.extend(_collect_edge_widevine_dll_paths())
    for root in _find_chrome_application_dirs():
        dll = _widevine_dll_in_tree(os.path.join(root, "WidevineCdm"))
        if dll:
            candidates.append(dll)
    return _dedupe_existing_files(candidates)


def _find_browser_media_components() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    wv_dir, wv_dll, ver_dir, delta = _find_version_matched_widevine()
    if wv_dll and ver_dir:
        ff = os.path.join(ver_dir, "ffmpeg.dll")
        ffmpeg_src = ff if os.path.isfile(ff) else None
        if delta > 2 and _QT_WEBENGINE_CHROMIUM_VERSION:
            print(
                f"[媒体] 警告: Qt Chromium {_QT_WEBENGINE_CHROMIUM_VERSION} 与 "
                f"浏览器 CDM 主版本相差 {delta}"
            )
        return ffmpeg_src, wv_dir, wv_dll
    ffmpeg_src, widevine_dir, widevine_dll = _find_edge_media_from_program_files()
    if ffmpeg_src and widevine_dll:
        return ffmpeg_src, widevine_dir, widevine_dll
    for root in _find_chrome_application_dirs():
        ff = os.path.join(root, "ffmpeg.dll")
        wv = os.path.join(root, "WidevineCdm")
        dll = _widevine_dll_in_tree(wv)
        if os.path.isfile(ff) and dll:
            return ff, wv, dll
    return ffmpeg_src, widevine_dir, widevine_dll


def _deploy_widevine_tree(src_dir: str, dst_dir: str, force: bool = False) -> bool:
    if not src_dir or not os.path.isdir(src_dir):
        return False
    dst_dll = _widevine_dll_in_tree(dst_dir)
    if dst_dll and os.path.isfile(dst_dll) and not force:
        return True
    try:
        if os.path.isdir(dst_dir):
            shutil.rmtree(dst_dir, ignore_errors=True)
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        dst_dll = _widevine_dll_in_tree(dst_dir)
        return bool(dst_dll and os.path.isfile(dst_dll))
    except Exception as e:
        print(f"[媒体] Widevine 部署失败 ({dst_dir}): {e}")
        return False


def _deploy_ffmpeg(src: str, dst_dir: str) -> bool:
    if not src or not os.path.isfile(src) or not dst_dir:
        return False
    dst = os.path.join(dst_dir, "ffmpeg.dll")
    try:
        os.makedirs(dst_dir, exist_ok=True)
        if os.path.isfile(dst):
            try:
                if os.path.getsize(dst) >= os.path.getsize(src):
                    return True
            except OSError:
                pass
        shutil.copy2(src, dst)
        return os.path.isfile(dst)
    except Exception as e:
        print(f"[媒体] ffmpeg 部署失败 ({dst_dir}): {e}")
        return False


def _log_media_diagnostics() -> None:
    lines = ["[媒体] ---------- 诊断 ----------"]
    if _QT_WEBENGINE_CHROMIUM_VERSION:
        lines.append(f"[媒体] Qt WebEngine Chromium: {_QT_WEBENGINE_CHROMIUM_VERSION}")
    for line in lines:
        print(line)


def bootstrap_webengine_media() -> None:
    global _WEBENGINE_MEDIA_READY
    if _WEBENGINE_MEDIA_READY:
        return
    apply_qtwebengine_default_chromium_flags()
    if sys.platform == "win32":
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    try:
        os.makedirs(DATA_ROOT, exist_ok=True)
    except Exception as e:
        print(f"[媒体] 无法创建数据目录 {DATA_ROOT}: {e}")
    ffmpeg_src, widevine_src, widevine_dll_src = _find_browser_media_components()
    deploy_dirs = list(_app_bin_dirs())
    widevine_data = os.path.join(DATA_ROOT, "WidevineCdm")
    if widevine_src:
        _deploy_widevine_tree(widevine_src, widevine_data, force=True)
        for d in deploy_dirs:
            _deploy_widevine_tree(widevine_src, os.path.join(d, "WidevineCdm"), force=True)
    if ffmpeg_src:
        for d in deploy_dirs:
            _deploy_ffmpeg(ffmpeg_src, d)
    widevine_candidates = _widevine_dll_candidates()
    if not widevine_candidates and widevine_dll_src and os.path.isfile(widevine_dll_src):
        widevine_candidates = [os.path.abspath(widevine_dll_src)]
    chosen = _prefer_widevine_dll_for_flags(widevine_candidates)
    if chosen:
        _register_widevine_dll_dir(chosen)
        _apply_widevine_chromium_flags(chosen)
        print(f"[媒体] 使用 Widevine: {chosen}")
    else:
        print("[媒体] 未找到 Widevine CDM（Qt 回退路径）")
    _log_media_diagnostics()
    _WEBENGINE_MEDIA_READY = True


def bootstrap_webengine_media_pyqt_bins() -> None:
    try:
        from PyQt6.QtWebEngineCore import qWebEngineVersion

        set_qt_webengine_chromium_version(str(qWebEngineVersion() or ""))
    except Exception as e:
        print(f"[媒体] 无法读取 Qt WebEngine 版本: {e}")
    ffmpeg_src, widevine_src, widevine_dll_src = _find_browser_media_components()
    extra_dirs: List[str] = []
    try:
        import PyQt6

        qt_bin = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "bin")
        if os.path.isdir(qt_bin):
            extra_dirs.append(qt_bin)
    except Exception:
        pass
    extra_dirs.extend(_app_bin_dirs())
    seen: Set[str] = set()
    changed = False
    for d in extra_dirs:
        d = os.path.normpath(d)
        if d in seen:
            continue
        seen.add(d)
        if widevine_src:
            if _deploy_widevine_tree(widevine_src, os.path.join(d, "WidevineCdm"), force=True):
                changed = True
        if ffmpeg_src:
            if _deploy_ffmpeg(ffmpeg_src, d):
                changed = True
        qep = os.path.join(d, "QtWebEngineProcess.exe")
        if os.path.isfile(qep):
            os.environ["QTWEBENGINEPROCESS_PATH"] = os.path.abspath(qep)
    if changed or widevine_dll_src:
        candidates = _widevine_dll_candidates()
        chosen = _prefer_widevine_dll_for_flags(candidates)
        if chosen:
            _register_widevine_dll_dir(chosen)
            _apply_widevine_chromium_flags(chosen)
    _log_media_diagnostics()
