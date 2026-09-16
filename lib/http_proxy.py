"""HTTP(S) 出站：广场发文可走代理；行情/DeepSeek/百炼直连.

阿里云 ECS 到 www.binance.com 不通。不要设全局 HTTPS_PROXY，
否则新浪和百炼也会被拖去香港。只设 SQUARE_HTTPS_PROXY。
"""
from __future__ import annotations

import os
import urllib.request
from typing import Any


def square_proxy_url() -> str | None:
    raw = (os.environ.get("SQUARE_HTTPS_PROXY") or "").strip()
    return raw or None


def urlopen(req: urllib.request.Request, *, timeout: int, proxy: str | None = None) -> Any:
    """``proxy=None`` 时忽略环境变量里的 http(s)_proxy，强制直连."""
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    else:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(req, timeout=timeout)


def urlopen_square(req: urllib.request.Request, *, timeout: int) -> Any:
    return urlopen(req, timeout=timeout, proxy=square_proxy_url())


def urlopen_direct(req: urllib.request.Request, *, timeout: int) -> Any:
    return urlopen(req, timeout=timeout, proxy=None)
