"""国内可达的美股行情：新浪 hq（带 Referer）主源 · 腾讯兜底.

阿里云 ECS 上 Yahoo / yfinance 通常连不上；裸请求新浪会 403。
"""
from __future__ import annotations

import re
import urllib.request
from typing import Any

from lib.http_proxy import urlopen_direct

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_SINA_URL = "https://hq.sinajs.cn/list={codes}"
_TENCENT_URL = "https://qt.gtimg.cn/q={codes}"

# Yahoo 符号 → 新浪代码
SINA_CODE = {
    "^GSPC": "int_sp500",
    "^IXIC": "int_nasdaq",
    "^DJI": "int_dji",
    "^VIX": "hf_VX",  # 现金 VIX 新浪常空；用 VIX 期货
    "ES=F": "hf_ES",
    "NQ=F": "hf_NQ",
    "YM=F": "hf_YM",
}

_HQ_RE = re.compile(r'hq_str_([A-Za-z0-9_]+)="(.*)"')
_QQ_RE = re.compile(r'v_(us[A-Za-z0-9]+)="(.*)"')


def _f(v: Any, default: float | None = None) -> float | None:
    if v is None or v == "" or v == "-" or v == "--":
        return default
    try:
        x = float(v)
        if x != x:
            return default
        return x
    except (TypeError, ValueError):
        return default


def sina_code_for(symbol: str) -> str | None:
    if symbol in SINA_CODE:
        return SINA_CODE[symbol]
    if symbol.startswith("^") or symbol.endswith("=F"):
        return None
    return f"gb_{symbol.lower()}"


def _http_text(url: str, *, referer: str | None = None, timeout: int = 12) -> str:
    headers = {"User-Agent": _UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urlopen_direct(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("gb18030", errors="replace")


def _quote(
    symbol: str,
    *,
    name: str,
    price: float | None,
    change_pct: float | None,
    previous_close: float | None,
    quote_session: str,
    source: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": name,
        "price": price,
        "change_pct": change_pct,
        "previous_close": previous_close,
        "quote_session": quote_session,
        "source": source,
    }


def parse_sina_gb(body: str, symbol: str, *, prefer_pre: bool) -> dict[str, Any] | None:
    """美股个股/ETF：price, change_pct, previous_close≈字段 26."""
    parts = [p.strip() for p in body.split(",")]
    if len(parts) < 3:
        return None
    price = _f(parts[1])
    chg = _f(parts[2])
    prev = _f(parts[26]) if len(parts) > 26 else None
    if price is None and chg is None:
        return None
    sess = "premarket" if prefer_pre else "regular"
    return _quote(
        symbol,
        name=parts[0] or symbol,
        price=price,
        change_pct=chg,
        previous_close=prev,
        quote_session=sess,
        source="sina_gb",
    )


def parse_sina_int(body: str, symbol: str, *, prefer_pre: bool) -> dict[str, Any] | None:
    """全球指数：name, last, change, change_pct."""
    parts = [p.strip() for p in body.split(",")]
    if len(parts) < 4:
        return None
    price = _f(parts[1])
    chg = _f(parts[3])
    if price is None and chg is None:
        return None
    sess = "prior_close" if prefer_pre else "regular"
    return _quote(
        symbol,
        name=parts[0] or symbol,
        price=price,
        change_pct=chg,
        previous_close=None,
        quote_session=sess,
        source="sina_int",
    )


def parse_sina_hf(body: str, symbol: str) -> dict[str, Any] | None:
    """外盘期货：last, …, prev_settle(字段7)."""
    parts = [p.strip() for p in body.split(",")]
    if len(parts) < 8:
        return None
    price = _f(parts[0])
    prev = _f(parts[7])
    if prev is None and len(parts) > 8:
        prev = _f(parts[8])
    if price is None:
        return None
    chg = None
    if prev and prev != 0:
        chg = (price / prev - 1.0) * 100.0
    name = parts[13] if len(parts) > 13 and parts[13] else symbol
    return _quote(
        symbol,
        name=name,
        price=price,
        change_pct=chg,
        previous_close=prev,
        quote_session="overnight",
        source="sina_hf",
    )


def parse_sina_payload(text: str, code_to_symbol: dict[str, str], *, prefer_pre: bool) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in _HQ_RE.finditer(text):
        code, body = m.group(1), m.group(2)
        if not body:
            continue
        symbol = code_to_symbol.get(code)
        if not symbol:
            continue
        row = None
        if code.startswith("gb_"):
            row = parse_sina_gb(body, symbol, prefer_pre=prefer_pre)
        elif code.startswith("int_"):
            row = parse_sina_int(body, symbol, prefer_pre=prefer_pre)
        elif code.startswith("hf_"):
            row = parse_sina_hf(body, symbol)
        if row and (row.get("price") is not None or row.get("change_pct") is not None):
            out[symbol] = row
    return out


def parse_tencent_us(body: str, symbol: str, *, prefer_pre: bool) -> dict[str, Any] | None:
    parts = body.split("~")
    if len(parts) < 5:
        return None
    price = _f(parts[3])
    prev = _f(parts[4])
    chg = None
    if price is not None and prev and prev != 0:
        chg = (price / prev - 1.0) * 100.0
    elif len(parts) > 32:
        chg = _f(parts[32])
    if price is None and chg is None:
        return None
    name = parts[1] if len(parts) > 1 else symbol
    sess = "premarket" if prefer_pre else "regular"
    return _quote(
        symbol,
        name=name or symbol,
        price=price,
        change_pct=chg,
        previous_close=prev,
        quote_session=sess,
        source="tencent",
    )


def fetch_sina_quotes(symbols: list[str], *, prefer_pre: bool = True) -> dict[str, dict]:
    code_to_symbol: dict[str, str] = {}
    codes: list[str] = []
    for sym in symbols:
        code = sina_code_for(sym)
        if not code:
            continue
        codes.append(code)
        code_to_symbol[code] = sym
    if not codes:
        return {}
    url = _SINA_URL.format(codes=",".join(codes))
    text = _http_text(url, referer="https://finance.sina.com.cn/")
    return parse_sina_payload(text, code_to_symbol, prefer_pre=prefer_pre)


def fetch_tencent_quotes(symbols: list[str], *, prefer_pre: bool = True) -> dict[str, dict]:
    """只补个股/ETF（usSPY 这类）。指数/期货走新浪."""
    tickers = [s for s in symbols if not s.startswith("^") and not s.endswith("=F")]
    if not tickers:
        return {}
    codes = [f"us{t}" for t in tickers]
    url = _TENCENT_URL.format(codes=",".join(codes))
    text = _http_text(url)
    out: dict[str, dict] = {}
    wanted = {f"us{t}": t for t in tickers}
    for m in _QQ_RE.finditer(text):
        code, body = m.group(1), m.group(2)
        symbol = wanted.get(code)
        if not symbol or not body:
            continue
        row = parse_tencent_us(body, symbol, prefer_pre=prefer_pre)
        if row and (row.get("price") is not None or row.get("change_pct") is not None):
            out[symbol] = row
    return out
