"""M5a · Crypto hard-signal helpers (BTC / ETH MVP).

Design:
- No hard deps on pycoingecko / ccxt — raw ``requests`` only.
- Spot ticker / K-line / funding: OKX + Binance public REST.
  Default primary = Binance（国内走 data-api.binance.vision，主站 api.binance.com 常不可达）.
  Force primary via ``QINGTING_CRYPTO_MARKET_SOURCE=okx|binance``.
- Optional: CoinGecko (mcap / ATH / supply / dominance) when reachable.
- Sentiment: alternative.me Fear & Greed + perpetual funding (OKX/Binance).

Callers must tolerate empty / flaky responses (same as US/HK M3/M4).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Literal

try:
    import requests
except ImportError:
    requests = None  # type: ignore


_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MarketSource = Literal["okx", "binance"]

# 国内 ECS 测通：data-api.binance.vision；api.binance.com / fapi / OKX 常超时
_BINANCE_SPOT_BASES = (
    "https://data-api.binance.vision",
    "https://api.binance.com",
)
_BINANCE_FAPI_BASES = (
    "https://fapi.binance.com",
)

# Canonical symbol → ids / exchange instruments
_CRYPTO_META: dict[str, dict[str, str]] = {
    "BTC": {
        "name": "Bitcoin",
        "name_cn": "比特币",
        "coingecko_id": "bitcoin",
        "okx_spot": "BTC-USDT",
        "okx_swap": "BTC-USDT-SWAP",
        "binance_spot": "BTCUSDT",
        "binance_perp": "BTCUSDT",
        "industry": "Layer-1 / Digital Gold",
    },
    "ETH": {
        "name": "Ethereum",
        "name_cn": "以太坊",
        "coingecko_id": "ethereum",
        "okx_spot": "ETH-USDT",
        "okx_swap": "ETH-USDT-SWAP",
        "binance_spot": "ETHUSDT",
        "binance_perp": "ETHUSDT",
        "industry": "Layer-1 / Smart Contract",
    },
    "BNB": {
        "name": "BNB",
        "name_cn": "币安币",
        "coingecko_id": "binancecoin",
        "okx_spot": "BNB-USDT",
        "okx_swap": "BNB-USDT-SWAP",
        "binance_spot": "BNBUSDT",
        "binance_perp": "BNBUSDT",
        "industry": "Exchange / Layer-1",
    },
    "ARB": {
        "name": "Arbitrum",
        "name_cn": "Arbitrum",
        "coingecko_id": "arbitrum",
        "okx_spot": "ARB-USDT",
        "okx_swap": "ARB-USDT-SWAP",
        "binance_spot": "ARBUSDT",
        "binance_perp": "ARBUSDT",
        "industry": "Layer-2 / Ethereum",
    },
    "SOL": {
        "name": "Solana",
        "name_cn": "Solana",
        "coingecko_id": "solana",
        "okx_spot": "SOL-USDT",
        "okx_swap": "SOL-USDT-SWAP",
        "binance_spot": "SOLUSDT",
        "binance_perp": "SOLUSDT",
        "industry": "Layer-1 / Smart Contract",
    },
    "DOGE": {
        "name": "Dogecoin",
        "name_cn": "狗狗币",
        "coingecko_id": "dogecoin",
        "okx_spot": "DOGE-USDT",
        "okx_swap": "DOGE-USDT-SWAP",
        "binance_spot": "DOGEUSDT",
        "binance_perp": "DOGEUSDT",
        "industry": "Meme / Payments",
    },
}


def normalize_crypto_symbol(code: str) -> str:
    """``BTC`` / ``btc-usdt`` / ``ETH.CRYPTO`` → ``BTC`` / ``ETH``."""
    s = str(code or "").strip().upper()
    s = s.replace(".CRYPTO", "").replace(".CRYP", "")
    for sep in ("-", "/", "_"):
        if sep in s:
            s = s.split(sep, 1)[0]
    return s


def crypto_meta(code: str) -> dict[str, str] | None:
    return _CRYPTO_META.get(normalize_crypto_symbol(code))


def crypto_market_source_pref() -> MarketSource:
    """Preferred primary exchange for ticker/klines/funding."""
    raw = (os.environ.get("QINGTING_CRYPTO_MARKET_SOURCE") or "binance").strip().lower()
    if raw in ("okx",):
        return "okx"
    return "binance"


def binance_spot_bases() -> list[str]:
    env = (os.environ.get("BINANCE_API_BASE") or "").strip().rstrip("/")
    bases = list(_BINANCE_SPOT_BASES)
    if env:
        return [env] + [b for b in bases if b != env]
    return bases


def binance_fapi_bases() -> list[str]:
    env = (os.environ.get("BINANCE_FAPI_BASE") or "").strip().rstrip("/")
    bases = list(_BINANCE_FAPI_BASES)
    if env:
        return [env] + [b for b in bases if b != env]
    return bases


def _market_source_order() -> list[MarketSource]:
    primary = crypto_market_source_pref()
    other: MarketSource = "binance" if primary == "okx" else "okx"
    return [primary, other]


def _http_proxies() -> dict[str, str] | None:
    p = (
        os.environ.get("UZI_HTTP_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("ALL_PROXY")
    )
    if not p:
        return None
    return {"http": p, "https": p}


def _safe_float(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _get_json(url: str, *, params: dict | None = None, timeout: int = 20,
              use_proxy: bool | None = None) -> Any:
    if requests is None:
        raise RuntimeError("requests not installed")
    headers = {"User-Agent": _CHROME_UA, "Accept": "application/json"}
    proxies = _http_proxies() if use_proxy is not False else None
    if use_proxy is True and not proxies:
        proxies = None
    r = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_json_try(url: str, *, params: dict | None = None, timeout: int = 20) -> Any | None:
    """Try with proxy first, then without (CoinGecko often needs one or the other)."""
    errors: list[str] = []
    for use_proxy in (True, False):
        try:
            return _get_json(url, params=params, timeout=timeout, use_proxy=use_proxy)
        except Exception as e:
            errors.append(f"proxy={use_proxy}:{type(e).__name__}")
            continue
    return None


# ── OKX helpers ───────────────────────────────────────────────


def _okx_ticker(inst_id: str) -> dict:
    j = _get_json(
        "https://www.okx.com/api/v5/market/ticker",
        params={"instId": inst_id},
        timeout=8,
    )
    rows = (j or {}).get("data") or []
    return rows[0] if rows else {}


def _okx_candles(inst_id: str, bar: str = "1D", limit: int = 120) -> list[list]:
    j = _get_json(
        "https://www.okx.com/api/v5/market/candles",
        params={"instId": inst_id, "bar": bar, "limit": str(limit)},
        timeout=8,
    )
    # OKX returns newest first: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    return list((j or {}).get("data") or [])


def _okx_funding(inst_id_swap: str) -> dict:
    j = _get_json(
        "https://www.okx.com/api/v5/public/funding-rate",
        params={"instId": inst_id_swap},
        timeout=8,
    )
    rows = (j or {}).get("data") or []
    return rows[0] if rows else {}


def _binance_get_json(path: str, *, params: dict | None = None, futures: bool = False) -> Any:
    """Try China-reachable vision host first, then the global main site."""
    bases = binance_fapi_bases() if futures else binance_spot_bases()
    errors: list[str] = []
    for base in bases:
        try:
            return _get_json(base + path, params=params, timeout=10)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{base}:{type(e).__name__}")
            continue
    raise RuntimeError("binance unreachable: " + "; ".join(errors))


# ── Binance helpers ───────────────────────────────────────────


def _binance_bar(bar: str) -> str:
    """Map OKX-style bar labels to Binance intervals."""
    b = (bar or "1D").strip()
    mapping = {
        "1D": "1d",
        "1W": "1w",
        "1M": "1M",
        "4H": "4h",
        "1H": "1h",
        "2H": "2h",
        "6H": "6h",
        "12H": "12h",
        "15m": "15m",
        "5m": "5m",
        "1m": "1m",
    }
    if b in mapping:
        return mapping[b]
    # already binance-ish
    if len(b) >= 2 and b[-1] in "hdwmM" and b[:-1].isdigit():
        return b
    return b.lower()


def _binance_ticker(symbol: str) -> dict:
    j = _binance_get_json("/api/v3/ticker/24hr", params={"symbol": symbol})
    return j if isinstance(j, dict) else {}


def _binance_klines(symbol: str, bar: str = "1D", limit: int = 120) -> list[list]:
    j = _binance_get_json(
        "/api/v3/klines",
        params={
            "symbol": symbol,
            "interval": _binance_bar(bar),
            "limit": str(max(1, min(int(limit), 1000))),
        },
    )
    # Binance returns oldest → newest: [openTime, o, h, l, c, volume, closeTime, quoteVol, ...]
    return list(j) if isinstance(j, list) else []


def _binance_funding(symbol_perp: str) -> dict:
    j = _binance_get_json(
        "/fapi/v1/premiumIndex",
        params={"symbol": symbol_perp},
        futures=True,
    )
    return j if isinstance(j, dict) else {}


def _normalize_ohlcv_rows(
    raw: list[list],
    *,
    bar: str,
    source: str,
    newest_first: bool,
) -> list[dict]:
    """Normalize exchange candle arrays to shared OHLCV dicts (oldest → newest)."""
    seq = list(reversed(raw)) if newest_first else list(raw)
    rows: list[dict] = []
    for c in seq:
        if not c or len(c) < 6:
            continue
        ts_ms = _safe_float(c[0])
        if ts_ms is None:
            continue
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        if bar in ("1D", "1W", "1M"):
            date_s = dt.strftime("%Y-%m-%d")
        else:
            date_s = dt.strftime("%Y-%m-%d %H:%M")
        o, h, l, cl = (_safe_float(c[1]), _safe_float(c[2]), _safe_float(c[3]), _safe_float(c[4]))
        vol = _safe_float(c[5])
        # OKX (newest_first): volCcy at [6]; Binance: quote volume at [7]
        if newest_first:
            amount = _safe_float(c[6]) if len(c) > 6 else None
        else:
            amount = _safe_float(c[7]) if len(c) > 7 else None
        rows.append({
            "日期": date_s,
            "date": date_s,
            "开盘": o,
            "open": o,
            "最高": h,
            "high": h,
            "最低": l,
            "low": l,
            "收盘": cl,
            "close": cl,
            "成交量": vol,
            "volume": vol,
            "成交额": amount,
            "amount": amount,
            "bar": bar,
            "_source": source,
        })
    return rows


def _fetch_spot_ticker_fields(meta: dict[str, str]) -> tuple[dict[str, Any], str]:
    """Try preferred exchange then fallback. Returns (fields, source_tag)."""
    errors: list[str] = []
    for src in _market_source_order():
        try:
            if src == "okx":
                tick = _okx_ticker(meta["okx_spot"])
                if not tick:
                    raise RuntimeError("empty okx ticker")
                price = _safe_float(tick.get("last"))
                open24 = _safe_float(tick.get("open24h"))
                change_pct = None
                if price is not None and open24 and open24 > 0:
                    change_pct = round((price / open24 - 1.0) * 100, 2)
                fields = {
                    "price": price,
                    "change_pct": change_pct,
                    "high_24h": _safe_float(tick.get("high24h")),
                    "low_24h": _safe_float(tick.get("low24h")),
                    "volume_24h_exchange": (
                        _safe_float(tick.get("volCcy24h")) or _safe_float(tick.get("vol24h"))
                    ),
                    "okx_inst": meta["okx_spot"],
                    "exchange_inst": meta["okx_spot"],
                }
                return fields, "okx:ticker"
            tick = _binance_ticker(meta["binance_spot"])
            if not tick:
                raise RuntimeError("empty binance ticker")
            price = _safe_float(tick.get("lastPrice"))
            change_pct = _safe_float(tick.get("priceChangePercent"))
            if change_pct is not None:
                change_pct = round(change_pct, 2)
            fields = {
                "price": price,
                "change_pct": change_pct,
                "high_24h": _safe_float(tick.get("highPrice")),
                "low_24h": _safe_float(tick.get("lowPrice")),
                "volume_24h_exchange": (
                    _safe_float(tick.get("quoteVolume")) or _safe_float(tick.get("volume"))
                ),
                "binance_symbol": meta["binance_spot"],
                "exchange_inst": meta["binance_spot"],
            }
            return fields, "binance:ticker"
        except Exception as e:
            errors.append(f"{src}:{type(e).__name__}")
            continue
    raise RuntimeError("ticker failed: " + ",".join(errors) if errors else "ticker failed")


def _fetch_funding_rate(meta: dict[str, str]) -> tuple[float, str]:
    """Return (funding_rate, source_tag)."""
    errors: list[str] = []
    for src in _market_source_order():
        try:
            if src == "okx":
                fr = _okx_funding(meta["okx_swap"])
                rate = _safe_float(fr.get("fundingRate"))
                if rate is None:
                    raise RuntimeError("empty okx funding")
                return rate, "okx:funding"
            fr = _binance_funding(meta["binance_perp"])
            rate = _safe_float(fr.get("lastFundingRate"))
            if rate is None:
                raise RuntimeError("empty binance funding")
            return rate, "binance:funding"
        except Exception as e:
            errors.append(f"{src}:{type(e).__name__}")
            continue
    raise RuntimeError("funding failed: " + ",".join(errors) if errors else "funding failed")


# ── CoinGecko (optional) ──────────────────────────────────────


def _coingecko_coin(cg_id: str) -> dict:
    j = _get_json_try(
        f"https://api.coingecko.com/api/v3/coins/{cg_id}",
        params={
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
        },
        timeout=25,
    )
    return j if isinstance(j, dict) else {}


def _coingecko_global() -> dict:
    j = _get_json_try("https://api.coingecko.com/api/v3/global", timeout=20)
    if isinstance(j, dict):
        return j.get("data") or {}
    return {}


# ── Fear & Greed ──────────────────────────────────────────────


def fetch_fear_greed(limit: int = 1) -> dict:
    """alternative.me Crypto Fear & Greed Index."""
    out: dict[str, Any] = {"value": None, "label": None, "history": []}
    try:
        j = _get_json(
            "https://api.alternative.me/fng/",
            params={"limit": str(max(1, min(int(limit), 30)))},
            timeout=15,
        )
        rows = (j or {}).get("data") or []
        hist = []
        for row in rows:
            hist.append({
                "value": _safe_float(row.get("value")),
                "label": str(row.get("value_classification") or ""),
                "timestamp": str(row.get("timestamp") or ""),
            })
        out["history"] = hist
        if hist:
            out["value"] = hist[0]["value"]
            out["label"] = hist[0]["label"]
    except Exception as e:
        out["_err"] = f"{type(e).__name__}: {str(e)[:120]}"
    return out


# ── Public fetchers ───────────────────────────────────────────


def fetch_crypto_basic(code: str) -> dict:
    """Schema-compatible basic snapshot for market=C."""
    sym = normalize_crypto_symbol(code)
    meta = crypto_meta(sym)
    out: dict[str, Any] = {
        "code": sym,
        "name": (meta or {}).get("name") or sym,
        "name_cn": (meta or {}).get("name_cn"),
        "industry": (meta or {}).get("industry") or "Cryptocurrency",
        "currency": "USD",
        "currency_symbol": "$",
        "market": "C",
        "pe_ttm": "不适用",  # crypto: no earnings yield
        "pb": "不适用",
    }
    if not meta:
        out["_err"] = f"unsupported crypto symbol: {code}"
        out["_has_signal"] = False
        return out

    sources: list[str] = []
    # Spot ticker: preferred exchange → fallback
    try:
        fields, tag = _fetch_spot_ticker_fields(meta)
        # Keep legacy key volume_24h_okx when OKX hit; else exchange-agnostic key
        vol_ex = fields.pop("volume_24h_exchange", None)
        out.update(fields)
        if tag.startswith("okx:"):
            out["volume_24h_okx"] = vol_ex
        else:
            out["volume_24h_binance"] = vol_ex
            out["volume_24h_okx"] = vol_ex  # downstream fallbacks still read this key
        sources.append(tag)
    except Exception as e:
        out["_ticker_err"] = f"{type(e).__name__}: {str(e)[:160]}"

    # CoinGecko enrichment (optional)
    try:
        coin = _coingecko_coin(meta["coingecko_id"])
        md = coin.get("market_data") or {}
        if md:
            price_cg = _safe_float((md.get("current_price") or {}).get("usd"))
            if out.get("price") is None and price_cg is not None:
                out["price"] = price_cg
            mcap = _safe_float((md.get("market_cap") or {}).get("usd"))
            fdv = _safe_float((md.get("fully_diluted_valuation") or {}).get("usd"))
            vol = _safe_float((md.get("total_volume") or {}).get("usd"))
            ath = _safe_float((md.get("ath") or {}).get("usd"))
            ath_chg = _safe_float((md.get("ath_change_percentage") or {}).get("usd"))
            circ = _safe_float(md.get("circulating_supply"))
            total_sup = _safe_float(md.get("total_supply"))
            max_sup = _safe_float(md.get("max_supply"))
            out.update({
                "market_cap_raw": mcap,
                "market_cap": f"${mcap / 1e9:.2f}B" if mcap and mcap >= 1e9 else (
                    f"${mcap / 1e6:.1f}M" if mcap else None
                ),
                "fdv": fdv,
                # 全球 24h 成交额优先（与市值同口径）；交易所单所另存 volume_24h_okx
                "volume_24h_global": vol,
                "volume_24h": vol if vol is not None else out.get("volume_24h_okx"),
                "ath": ath,
                "ath_change_pct": round(ath_chg, 2) if ath_chg is not None else None,
                "circulating_supply": circ,
                "total_supply": total_sup,
                "max_supply": max_sup,
                "coingecko_id": meta["coingecko_id"],
            })
            if out.get("change_pct") is None:
                out["change_pct"] = _safe_float(md.get("price_change_percentage_24h"))
            sources.append("coingecko:coin")
        g = _coingecko_global()
        btc_dom = _safe_float((g.get("market_cap_percentage") or {}).get("btc"))
        eth_dom = _safe_float((g.get("market_cap_percentage") or {}).get("eth"))
        if btc_dom is not None:
            out["btc_dominance_pct"] = round(btc_dom, 2)
        if eth_dom is not None:
            out["eth_dominance_pct"] = round(eth_dom, 2)
        if g:
            sources.append("coingecko:global")
    except Exception as e:
        out["_cg_err"] = f"{type(e).__name__}: {str(e)[:120]}"

    # Fallback: no CoinGecko → keep exchange volume but flag口径
    if out.get("volume_24h") is None and out.get("volume_24h_okx") is not None:
        out["volume_24h"] = out["volume_24h_okx"]
        tick_src = next((s for s in sources if s.endswith(":ticker")), "")
        out["volume_24h_scope"] = (
            "binance_spot_only" if tick_src.startswith("binance:") else "okx_spot_only"
        )
    elif out.get("volume_24h_global") is not None:
        out["volume_24h_scope"] = "coingecko_global"

    out["_source"] = " + ".join(sources) if sources else "none"
    out["_has_signal"] = out.get("price") is not None
    out["_market_source_pref"] = crypto_market_source_pref()
    out["_note"] = (
        "Crypto basic: OKX/Binance spot for price (pref via QINGTING_CRYPTO_MARKET_SOURCE); "
        "CoinGecko for mcap/ATH/global 24h volume/supply/dominance. PE/PB n/a. "
        "volume_24h = global when CG available."
    )
    return out


def fetch_crypto_kline(code: str, limit: int = 120, bar: str = "1D") -> list[dict]:
    """OHLCV rows from OKX or Binance spot candles (preferred → fallback).

    ``bar``: OKX-style interval (``1D``, ``4H``, ``1H``, …); mapped for Binance.
    Daily rows use ``YYYY-MM-DD``; intraday keeps ``YYYY-MM-DD HH:MM`` (UTC).
    Column aliases match A-share Chinese keys where possible so
    ``compute_indicators`` / viz helpers keep working on daily bars.
    Each row includes ``_source`` (``okx:candles`` or ``binance:klines``).
    """
    sym = normalize_crypto_symbol(code)
    meta = crypto_meta(sym)
    if not meta or requests is None:
        return []

    errors: list[str] = []
    for src in _market_source_order():
        try:
            if src == "okx":
                raw = _okx_candles(meta["okx_spot"], bar=bar, limit=limit)
                if not raw:
                    raise RuntimeError("empty okx candles")
                return _normalize_ohlcv_rows(
                    raw, bar=bar, source="okx:candles", newest_first=True
                )
            raw = _binance_klines(meta["binance_spot"], bar=bar, limit=limit)
            if not raw:
                raise RuntimeError("empty binance klines")
            return _normalize_ohlcv_rows(
                raw, bar=bar, source="binance:klines", newest_first=False
            )
        except Exception as e:
            errors.append(f"{src}:{type(e).__name__}")
            continue
    return []


def fetch_crypto_kline_4h(code: str, limit: int = 300) -> list[dict]:
    """4H OHLCV for structure-lens 区间套 (not used in Crypto Desk scoring)."""
    return fetch_crypto_kline(code, limit=limit, bar="4H")


def fetch_crypto_valuation(code: str, basic: dict | None = None) -> dict:
    """Crypto valuation proxies (not PE/PB/DCF).

    Fields:
      - ath_drawdown_pct
      - volume_to_mcap (turnover / soft NVT proxy)
      - realized_vol_30d (from OKX daily closes)
      - funding_rate (perp)
      - fear_greed
    """
    sym = normalize_crypto_symbol(code)
    meta = crypto_meta(sym)
    basic = basic or {}
    out: dict[str, Any] = {
        "pe": "—",
        "pb": "—",
        "pe_quantile": "—",
        "pb_quantile": "—",
        "industry_pe": "—",
        "dcf": "—",
        "pe_history": [],
        "dcf_simple": {},
        "dcf_sensitivity": {},
        "_valuation_framework": "crypto-proxy",
    }
    if not meta:
        out["_note"] = f"unsupported crypto: {code}"
        out["_has_signal"] = False
        return out

    price = _safe_float(basic.get("price"))
    mcap = _safe_float(basic.get("market_cap_raw"))
    # Prefer global 24h volume for turnover; fall back to volume_24h
    vol24 = _safe_float(basic.get("volume_24h_global"))
    if vol24 is None:
        vol24 = _safe_float(basic.get("volume_24h"))
    vol_scope = basic.get("volume_24h_scope") or (
        "coingecko_global" if basic.get("volume_24h_global") is not None else "unknown"
    )
    ath = _safe_float(basic.get("ath"))
    ath_chg = _safe_float(basic.get("ath_change_pct"))

    if ath_chg is not None:
        out["ath_drawdown_pct"] = round(ath_chg, 2)
    elif ath and price and ath > 0:
        out["ath_drawdown_pct"] = round((price / ath - 1.0) * 100, 2)

    if mcap and mcap > 0 and vol24 is not None:
        out["volume_to_mcap"] = round(vol24 / mcap, 4)
        scope_tag = "全球" if vol_scope == "coingecko_global" else "单所"
        out["volume_to_mcap_label"] = (
            f"{out['volume_to_mcap'] * 100:.2f}% of mcap / 24h（{scope_tag}成交）"
        )
        out["volume_24h_used"] = vol24
        out["volume_24h_scope"] = vol_scope

    # 30d realized vol from daily closes
    try:
        kl = fetch_crypto_kline(sym, limit=45)
        closes = [float(r["close"]) for r in kl if r.get("close")]
        if len(closes) >= 10:
            import math
            rets = []
            for i in range(1, len(closes)):
                if closes[i - 1] > 0:
                    rets.append(math.log(closes[i] / closes[i - 1]))
            if len(rets) >= 5:
                mean = sum(rets) / len(rets)
                var = sum((x - mean) ** 2 for x in rets) / max(1, len(rets) - 1)
                vol_ann = math.sqrt(var) * math.sqrt(365) * 100
                out["realized_vol_30d"] = round(vol_ann, 1)
                # soft "quantile" label using vol bands
                if vol_ann < 40:
                    out["vol_regime"] = "低波"
                elif vol_ann < 70:
                    out["vol_regime"] = "中波"
                else:
                    out["vol_regime"] = "高波"
    except Exception as e:
        out["_vol_err"] = f"{type(e).__name__}: {str(e)[:80]}"

    funding_src = None
    try:
        rate, funding_src = _fetch_funding_rate(meta)
        out["funding_rate"] = rate
        out["funding_rate_pct"] = round(rate * 100, 4)
        out["funding_label"] = (
            "多头拥挤" if rate > 0.0003 else ("空头拥挤" if rate < -0.0001 else "中性")
        )
        out["funding_source"] = funding_src
    except Exception as e:
        out["_funding_err"] = f"{type(e).__name__}: {str(e)[:80]}"

    fg = fetch_fear_greed(limit=7)
    if fg.get("value") is not None:
        out["fear_greed"] = fg.get("value")
        out["fear_greed_label"] = fg.get("label")
        out["fear_greed_history"] = fg.get("history") or []

    # Human summary line used like pe_quantile in reports
    bits = []
    if out.get("ath_drawdown_pct") is not None:
        bits.append(f"距ATH {out['ath_drawdown_pct']:+.1f}%")
    if out.get("realized_vol_30d") is not None:
        bits.append(f"年化波动 {out['realized_vol_30d']}%({out.get('vol_regime') or '—'})")
    if out.get("funding_rate_pct") is not None:
        bits.append(f"资金费率 {out['funding_rate_pct']}%")
    if out.get("fear_greed") is not None:
        bits.append(f"Fear&Greed {out['fear_greed']:.0f}({out.get('fear_greed_label')})")
    out["crypto_valuation_summary"] = " · ".join(bits) if bits else "—"
    # Map into pe_quantile slot so coverage / labels light up without PE
    out["pe_quantile"] = out["crypto_valuation_summary"]
    out["pe"] = "不适用"
    out["pb"] = "不适用"
    # pb_quantile → turnover / soft NVT proxy (no book equity)
    if out.get("volume_to_mcap_label"):
        out["pb_quantile"] = f"成交额/市值 {out['volume_to_mcap_label']}"
    else:
        out["pb_quantile"] = "不适用（无账面净资产）"

    out["_note"] = (
        "Crypto valuation proxy: ATH drawdown + 30d realized vol + OKX/Binance funding + "
        "Fear&Greed. Not equity PE/PB/DCF."
    )
    out["_has_signal"] = bool(bits)
    src_bits = ["candles+funding (okx|binance)", "alternative.me:fng"]
    if funding_src:
        src_bits.insert(0, funding_src)
    out["_source"] = " + ".join(src_bits) + " (+coingecko if in basic)"
    return out


def fetch_crypto_sentiment(code: str, basic: dict | None = None) -> dict:
    """Sentiment dim for market=C."""
    sym = normalize_crypto_symbol(code)
    meta = crypto_meta(sym) or {"name": sym}
    basic = basic or {}
    fg = fetch_fear_greed(limit=14)
    funding_pct = None
    funding_label = "—"
    funding_src = None
    funding_url = ""
    try:
        if crypto_meta(sym):
            rate, funding_src = _fetch_funding_rate(crypto_meta(sym))
            funding_pct = round(rate * 100, 4)
            funding_label = (
                "多头拥挤" if rate > 0.0003 else ("空头拥挤" if rate < -0.0001 else "中性")
            )
            if funding_src and funding_src.startswith("binance:"):
                funding_url = f"https://www.binance.com/en/futures/{sym}USDT"
            else:
                funding_url = f"https://www.okx.com/trade-swap/{sym.lower()}-usdt-swap"
    except Exception:
        pass

    fg_val = fg.get("value")
    # Map fear&greed 0-100 → positive_pct-ish + label
    if fg_val is not None:
        positive_pct = float(fg_val)
        if positive_pct >= 55:
            sent_label = "乐观"
        elif positive_pct <= 45:
            sent_label = "悲观"
        else:
            sent_label = "中性"
        heat = int(min(100, max(5, positive_pct)))
    else:
        positive_pct = 50.0
        sent_label = "中性"
        heat = 50

    # Adjust heat slightly by funding extremes
    if funding_pct is not None and abs(funding_pct) >= 0.05:
        heat = min(100, heat + 10)

    change = _safe_float(basic.get("change_pct"))
    snippets = []
    if fg_val is not None:
        snippets.append({
            "platform": "fear_greed",
            "title": f"Fear & Greed {fg_val:.0f} · {fg.get('label')}",
            "url": "https://alternative.me/crypto/fear-and-greed-index/",
        })
    if funding_pct is not None:
        snippets.append({
            "platform": funding_src or "funding",
            "title": f"{sym} funding {funding_pct}% · {funding_label}",
            "url": funding_url,
        })
    if change is not None:
        snippets.append({
            "platform": "spot_24h",
            "title": f"{sym} 24h {change:+.2f}%",
            "url": "",
        })

    has = fg_val is not None or funding_pct is not None
    return {
        "xueqiu_heat": f"情绪热度 {heat}",
        "thermometer_value": heat,
        "guba_volume": f"funding {funding_label}",
        "big_v_mentions": "—",
        "positive_pct": None,  # A-share field; crypto uses fear_greed instead
        "fear_greed_pct": f"{positive_pct:.0f}" if fg_val is not None else None,
        "sentiment_label": sent_label,
        "platform_snippets": snippets,
        "platform_hits": {
            "fear_greed": 1 if fg_val is not None else 0,
            "funding": 1 if funding_pct is not None else 0,
        },
        "total_mentions": len(snippets),
        "fear_greed": fg_val,
        "fear_greed_label": fg.get("label"),
        "fear_greed_history": fg.get("history") or [],
        "funding_rate_pct": funding_pct,
        "funding_label": funding_label,
        "funding_source": funding_src,
        "btc_dominance_pct": basic.get("btc_dominance_pct"),
        "hot_trend_mentions": {
            "stock_name": meta.get("name") or sym,
            "total_hits": 0,
            "_note": "CN hottrend n/a for crypto",
        },
        "hot_trend_hit_count": 0,
        "news_multi_source": {"sources": {}, "sources_ok": 0, "total_hits": 0},
        "news_sources_ok": 0,
        "news_total_hits": 0,
        "sentiment_market": "C",
        "_note": (
            "Crypto sentiment: Fear&Greed index (0-100) + OKX/Binance funding. "
            "positive_pct left empty — do not read as news-positive ratio; use fear_greed."
        ),
        "_has_signal": has,
        "_source": (
            f"alternative.me:fng + {funding_src}"
            if funding_src
            else "alternative.me:fng + okx|binance:funding"
        ),
    }


def fetch_crypto_events(code: str, *, name: str | None = None) -> dict:
    """Event timeline for market=C · CoinGecko status + trusted web search."""
    sym = normalize_crypto_symbol(code)
    meta = crypto_meta(sym) or {}
    display = name or meta.get("name") or sym
    cg_id = meta.get("coingecko_id") or sym.lower()

    recent_news: list[dict] = []
    timeline: list[str] = []
    sources: list[str] = []

    # CoinGecko status_updates (best-effort; may 404 on free tier)
    try:
        j = _get_json_try(
            f"https://api.coingecko.com/api/v3/coins/{cg_id}/status_updates",
            params={"per_page": 10},
            timeout=15,
        )
        updates = (j or {}).get("status_updates") or []
        for u in updates[:8]:
            desc = (u.get("description") or "").strip().replace("\n", " ")
            if not desc:
                continue
            created = str(u.get("created_at") or "")[:10] or "—"
            cat = (u.get("category") or "update").strip()
            title = desc[:100]
            recent_news.append({
                "date": created,
                "title": title,
                "type": cat,
                "source": "coingecko:status_updates",
                "url": "",
            })
            timeline.append(f"{created} · {title}")
        if updates:
            sources.append("coingecko:status_updates")
    except Exception:
        pass

    # Trusted crypto news search
    try:
        from lib.web_search import search_trusted, search as web_search
        queries = [
            f"{display} {sym} latest news ETF flows",
            f"{display} Bitcoin ETF inflows outflows catalyst",
        ]
        seen: set[str] = set()
        for q in queries:
            res = list(search_trusted(q, dim_key="15_events", max_results=4, market="C") or [])
            if len(res) < 2:
                res += list(web_search(q, max_results=3) or [])
            for r in res:
                if not isinstance(r, dict) or r.get("error"):
                    continue
                title = (r.get("title") or "").strip()[:100]
                if not title or title in seen:
                    continue
                # Drop site homepage / section index titles (not events)
                tl = title.lower()
                if any(k in tl for k in (
                    "live prices", "blockchain news", "crypto news |",
                    "latest bitcoin etf news on", "bitcoin & ethereum blockchain news",
                    "bitcoin, ethereum & crypto news",
                )):
                    continue
                if title.rstrip(".").endswith("News") and len(title) < 60 and "etf" not in tl:
                    # e.g. "Cointelegraph Bitcoin & Ethereum Blockchain News"
                    if ":" in title or "|" in title:
                        continue
                seen.add(title)
                url = r.get("url") or ""
                recent_news.append({
                    "date": "—",
                    "title": title,
                    "type": "web_search",
                    "source": url,
                    "url": url,
                })
                timeline.append(f"— · {title}")
        if seen:
            sources.append("ddgs:crypto_news")
    except Exception:
        pass

    # Soft catalysts from basic ATH / F&G if still thin
    if len(timeline) < 2:
        try:
            basic = fetch_crypto_basic(sym)
            ath_chg = basic.get("ath_change_pct")
            if ath_chg is not None:
                tip = f"距历史高点 {ath_chg:+.1f}%（CoinGecko ATH）"
                timeline.append(f"— · {tip}")
                recent_news.append({
                    "date": "—", "title": tip, "type": "market",
                    "source": "coingecko", "url": "",
                })
            fg = fetch_fear_greed(limit=1)
            if fg.get("value") is not None:
                tip = f"Fear & Greed {fg['value']:.0f} · {fg.get('label') or ''}"
                timeline.append(f"— · {tip}")
                recent_news.append({
                    "date": "—", "title": tip, "type": "sentiment",
                    "source": "alternative.me", "url": "https://alternative.me/crypto/fear-and-greed-index/",
                })
            if basic.get("price"):
                sources.append("okx+fng:soft_events")
        except Exception:
            pass

    has = len(timeline) > 0
    return {
        "event_timeline": timeline[:20],
        "recent_news": recent_news[:12],
        "recent_notices": [],
        "catalysts": [t for t in timeline if any(k in t.lower() for k in ("etf", "halving", "approval", "list")) ][:6],
        "warnings": [],
        "_note": "Crypto events: CoinGecko status_updates + trusted crypto news search.",
        "_has_signal": has,
        "_source": " + ".join(sources) if sources else "none",
    }


def fetch_crypto_bundle(code: str) -> dict:
    """One-shot helper for smoke tests / CLI."""
    basic = fetch_crypto_basic(code)
    kline = fetch_crypto_kline(code, limit=60)
    valuation = fetch_crypto_valuation(code, basic)
    sentiment = fetch_crypto_sentiment(code, basic)
    events = fetch_crypto_events(code, name=basic.get("name"))
    return {
        "basic": basic,
        "kline_count": len(kline),
        "kline_tail": kline[-3:] if kline else [],
        "valuation": valuation,
        "sentiment": sentiment,
        "events": events,
        "fetched_at": int(time.time()),
    }


if __name__ == "__main__":
    import json
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    print(json.dumps(fetch_crypto_bundle(sym), ensure_ascii=False, indent=2, default=str)[:4000])
