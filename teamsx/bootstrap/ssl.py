# -*- coding: utf-8 -*-
"""HTTPS / CA 证书 bootstrap。"""
from __future__ import annotations

import os
import ssl

try:
    import certifi

    HAS_CERTIFI = True
except ImportError:
    certifi = None  # type: ignore
    HAS_CERTIFI = False


def bootstrap_ssl_certs() -> None:
    cafile = ""
    if HAS_CERTIFI:
        try:
            cafile = certifi.where()
        except Exception:
            cafile = ""
    if cafile and os.path.isfile(cafile):
        os.environ.setdefault("SSL_CERT_FILE", cafile)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
        print(f"[SSL] 使用 CA 证书: {cafile}")
        return
    print("[SSL] 未找到 certifi CA 包，HTTPS 请求可能失败（pip install certifi）")


def urllib_ssl_context() -> ssl.SSLContext:
    if HAS_CERTIFI:
        try:
            cafile = certifi.where()
            if cafile and os.path.isfile(cafile):
                return ssl.create_default_context(cafile=cafile)
        except Exception:
            pass
    return ssl.create_default_context()
