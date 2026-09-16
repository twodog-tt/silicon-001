"""美股盘前快照 · 新浪/腾讯主源 · 可选 yfinance · TTL 缓存."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from lib.us_premarket import FRAMEWORK, MARKET
from lib.us_premarket.cn_quotes import fetch_sina_quotes, fetch_tencent_quotes

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
CACHE_ROOT = SCRIPTS_DIR / ".cache" / "us_premarket"
DEFAULT_TTL = int(os.environ.get("US_PRE_CACHE_TTL", str(10 * 60)))  # 10 min

ET = ZoneInfo("America/New_York")
BJ = ZoneInfo("Asia/Shanghai")

INDEX_SYMBOLS = {
    "^GSPC": {"name": "S&P 500", "short": "SPX"},
    "^IXIC": {"name": "Nasdaq Composite", "short": "IXIC"},
    "^DJI": {"name": "Dow Jones", "short": "DJI"},
    "^VIX": {"name": "VIX", "short": "VIX"},
    "^TNX": {"name": "US 10Y Yield", "short": "TNX"},
}

FUTURES_SYMBOLS = {
    "ES=F": {"name": "E-mini S&P", "short": "ES"},
    "NQ=F": {"name": "E-mini Nasdaq", "short": "NQ"},
    "YM=F": {"name": "E-mini Dow", "short": "YM"},
}

ETF_SYMBOLS = {
    "SPY": "标普500 ETF",
    "QQQ": "纳指100 ETF",
    "IWM": "罗素2000 ETF",
    "XLK": "科技",
    "XLF": "金融",
    "XLE": "能源",
    "XLV": "医疗",
    "XLY": "可选消费",
    "XLI": "工业",
    "SMH": "半导体",
}

WATCHLIST = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "META": "Meta",
    "GOOGL": "Alphabet",
    "TSLA": "Tesla",
    "AMD": "AMD",
    "AVGO": "Broadcom",
}


def _no_cache() -> bool:
    return os.environ.get("STOCK_NO_CACHE") == "1" or os.environ.get("US_PRE_NO_CACHE") == "1"


def _yf_enabled() -> bool:
    """Yahoo 在国内 ECS 通常不可达，默认关闭以免 cron 卡死."""
    return (os.environ.get("US_PRE_YF") or "").strip().lower() in ("1", "true", "yes")


def _f(v: Any, default: float | None = None) -> float | None:
    if v is None or v == "" or v == "-":
        return default
    try:
        x = float(v)
        if x != x:
            return default
        return x
    except (TypeError, ValueError):
        return default


def _now_et() -> datetime:
    return datetime.now(ET)


def _now_bj() -> datetime:
    return datetime.now(BJ)


def resolve_us_session(dt_et: datetime | None = None) -> dict[str, Any]:
    """美东时钟：盘前 <09:30 · 盘中 09:30–16:00 · 盘后 ≥16:00."""
    d = dt_et or _now_et()
    mins = d.hour * 60 + d.minute
    open_m, close_m = 9 * 60 + 30, 16 * 60
    if mins < open_m:
        session, label = "premarket", "盘前"
    elif mins < close_m:
        session, label = "regular", "盘中"
    else:
        session, label = "afterhours", "盘后"
    return {
        "session": session,
        "session_label": label,
        "et": d.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "bj": d.astimezone(BJ).strftime("%Y-%m-%d %H:%M:%S"),
    }


def _read_cache(path: Path, ttl: int, *, allow_stale: bool = False) -> Any | None:
    if _no_cache() or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - float(payload.get("_cached_at", 0))
        if age < ttl or allow_stale:
            return payload.get("data")
    except (json.JSONDecodeError, TypeError, ValueError, OSError):
        return None
    return None


def _write_cache(path: Path, data: Any, ttl: int) -> None:
    if _no_cache():
        return
    if data is None or data == [] or data == {}:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"_cached_at": time.time(), "_ttl": ttl, "data": data},
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def _cached_call(
    key: str,
    fetch_fn: Callable[[], Any],
    ttl: int = DEFAULT_TTL,
    *,
    force: bool = False,
) -> Any:
    path = CACHE_ROOT / "api" / f"{key}.json"
    if not force:
        hit = _read_cache(path, ttl)
        if hit is not None:
            return hit
    try:
        data = fetch_fn()
        _write_cache(path, data, ttl)
        return data
    except Exception:
        stale = _read_cache(path, ttl, allow_stale=True)
        if stale is not None:
            return stale
        raise


def _quote_from_info(symbol: str, info: dict, *, prefer_pre: bool = True) -> dict[str, Any]:
    """从 yfinance info 抽现价/涨跌 · 优先盘前字段.

    现金指数通常无盘前字段 → quote_session=prior_close（昨收口径）。
    股指期货近月为隔夜连续报价 → overnight。
    """
    name = info.get("shortName") or info.get("longName") or symbol
    pre_px = _f(info.get("preMarketPrice"))
    pre_chg = _f(info.get("preMarketChangePercent"))
    reg_px = _f(info.get("regularMarketPrice") or info.get("currentPrice"))
    reg_chg = _f(info.get("regularMarketChangePercent"))
    prev = _f(info.get("regularMarketPreviousClose") or info.get("previousClose"))

    is_index = symbol.startswith("^")
    is_fut = symbol.endswith("=F")

    quote_session = "regular"
    price, chg = reg_px, reg_chg
    if prefer_pre and pre_px is not None:
        price = pre_px
        chg = pre_chg
        quote_session = "premarket"
        # 若 Yahoo 盘前涨跌缺失，用昨收推算
        if chg is None and prev and prev != 0 and price is not None:
            chg = (price / prev - 1.0) * 100.0
    elif is_fut and price is not None:
        quote_session = "overnight"
    elif is_index:
        # 现金指数盘前无独立报价 → 明确标昨收，避免被读成「盘前指数」
        quote_session = "prior_close" if prefer_pre else "regular"
    elif price is None and pre_px is not None:
        price, chg = pre_px, pre_chg
        quote_session = "premarket"

    return {
        "symbol": symbol,
        "name": name,
        "price": price,
        "change_pct": chg,
        "previous_close": prev,
        "quote_session": quote_session,
        "pre_price": pre_px,
        "pre_change_pct": pre_chg,
        "regular_price": reg_px,
        "regular_change_pct": reg_chg,
        "source": "yfinance",
    }


def _fetch_yf_quotes(symbols: list[str], *, prefer_pre: bool = True) -> dict[str, dict]:
    import yfinance as yf

    out: dict[str, dict] = {}
    # Tickers batch is faster but info still per-ticker; use individual with light retry
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            if not info:
                # fallback: fast_info + history
                fi = getattr(t, "fast_info", None)
                hist = t.history(period="5d", interval="1d")
                price = None
                chg = None
                prev = None
                if fi is not None:
                    price = _f(getattr(fi, "last_price", None) or (fi.get("last_price") if isinstance(fi, dict) else None))
                if hist is not None and len(hist) >= 2:
                    closes = hist["Close"].tolist()
                    prev = float(closes[-2])
                    last = float(closes[-1])
                    price = price or last
                    chg = (last / prev - 1.0) * 100.0 if prev else None
                out[sym] = {
                    "symbol": sym,
                    "name": sym,
                    "price": price,
                    "change_pct": chg,
                    "previous_close": prev,
                    "quote_session": "regular",
                    "source": "yfinance.history",
                }
                continue
            out[sym] = _quote_from_info(sym, info, prefer_pre=prefer_pre)
        except Exception as e:  # noqa: BLE001
            out[sym] = {
                "symbol": sym,
                "name": sym,
                "price": None,
                "change_pct": None,
                "quote_session": "n/a",
                "source": "yfinance",
                "error": f"{type(e).__name__}",
            }
    return out


def _sina_index_fallback() -> list[dict]:
    """akshare 新浪美股指数兜底."""
    import akshare as ak

    mapping = {".INX": "^GSPC", ".IXIC": "^IXIC", ".DJI": "^DJI", ".NDX": "^NDX"}
    rows = []
    for sina_sym, yf_sym in mapping.items():
        try:
            df = ak.index_us_stock_sina(symbol=sina_sym)
            if df is None or getattr(df, "empty", True):
                continue
            # typically date index / close columns vary — take last row
            last = df.iloc[-1]
            # try common column names
            close = None
            for c in last.index:
                cs = str(c).lower()
                if cs in ("close", "收盘价", "price") or "close" in cs:
                    close = _f(last[c])
                    break
            if close is None:
                # last numeric
                for c in reversed(list(last.index)):
                    close = _f(last[c])
                    if close is not None:
                        break
            rows.append({
                "symbol": yf_sym,
                "name": INDEX_SYMBOLS.get(yf_sym, {}).get("name", yf_sym),
                "short": INDEX_SYMBOLS.get(yf_sym, {}).get("short", yf_sym),
                "price": close,
                "change_pct": None,
                "quote_session": "regular",
                "source": "index_us_stock_sina",
            })
        except Exception:
            continue
    return rows


def fetch_us_pre_snapshot(*, force: bool = False) -> dict[str, Any]:
    """拉指数 + 期指 + ETF + watchlist."""
    sess = resolve_us_session()
    prefer_pre = sess["session"] != "regular"
    sources: list[str] = []
    warnings: list[str] = []

    index_syms = list(INDEX_SYMBOLS.keys())
    fut_syms = list(FUTURES_SYMBOLS.keys())
    etf_syms = list(ETF_SYMBOLS.keys())
    watch_syms = list(WATCHLIST.keys())
    all_syms = index_syms + fut_syms + etf_syms + watch_syms

    quotes: dict[str, dict] = {}
    try:
        quotes = _cached_call(
            "cn_quotes_bundle",
            lambda: fetch_sina_quotes(all_syms, prefer_pre=prefer_pre),
            force=force,
        ) or {}
        if quotes:
            sources.append("sina")
    except Exception as e:  # noqa: BLE001
        warnings.append(f"sina 失败: {type(e).__name__}")

    missing = [s for s in all_syms if not (quotes.get(s) or {}).get("price")]
    if missing:
        try:
            extra = fetch_tencent_quotes(missing, prefer_pre=prefer_pre)
            for sym, row in extra.items():
                if (row.get("price") is not None or row.get("change_pct") is not None) and not (
                    quotes.get(sym) or {}
                ).get("price"):
                    quotes[sym] = row
            if extra:
                sources.append("tencent")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"tencent 失败: {type(e).__name__}")

    still = [s for s in all_syms if not (quotes.get(s) or {}).get("price")]
    if still and _yf_enabled():
        try:
            yf_q = _cached_call(
                "yf_quotes_bundle",
                lambda: _fetch_yf_quotes(still, prefer_pre=prefer_pre),
                force=force,
            ) or {}
            for sym, row in yf_q.items():
                if row.get("price") is not None or row.get("change_pct") is not None:
                    quotes[sym] = row
            sources.append("yfinance")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"yfinance 失败: {type(e).__name__}")
    elif still and not _yf_enabled():
        warnings.append(f"缺 {len(still)} 个标的（未开 US_PRE_YF）")

    indices = []
    for sym, meta in INDEX_SYMBOLS.items():
        q = dict(quotes.get(sym) or {})
        q["symbol"] = sym
        q["name"] = meta["name"]
        q["short"] = meta["short"]
        if q.get("price") is not None or q.get("change_pct") is not None:
            indices.append(q)

    if len(indices) < 2:
        try:
            fb = _sina_index_fallback()
            if fb:
                sources.append("index_us_stock_sina")
                have = {i["symbol"] for i in indices}
                for row in fb:
                    if row["symbol"] not in have:
                        indices.append(row)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"sina 指数兜底失败: {type(e).__name__}")

    futures = []
    for sym, meta in FUTURES_SYMBOLS.items():
        q = dict(quotes.get(sym) or {})
        q["symbol"] = sym
        q["name"] = meta["name"]
        q["short"] = meta["short"]
        if q.get("price") is not None or q.get("change_pct") is not None:
            futures.append(q)
        elif q.get("error"):
            warnings.append(f"期指 {sym} 暂缺")

    etfs = []
    for sym, cname in ETF_SYMBOLS.items():
        q = dict(quotes.get(sym) or {})
        q["symbol"] = sym
        q["name"] = cname
        q["group"] = "etf"
        if q.get("change_pct") is not None or q.get("price") is not None:
            etfs.append(q)

    watch = []
    for sym, cname in WATCHLIST.items():
        q = dict(quotes.get(sym) or {})
        q["symbol"] = sym
        q["name"] = cname
        q["group"] = "watch"
        if q.get("change_pct") is not None or q.get("price") is not None:
            watch.append(q)

    as_of_bj = _now_bj().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "framework": FRAMEWORK,
        "market": MARKET,
        "as_of": as_of_bj,
        "as_of_et": sess["et"],
        "session": sess["session"],
        "session_label": sess["session_label"],
        "indices": indices,
        "futures": futures,
        "etfs": etfs,
        "watchlist": watch,
        "meta": {
            "sources": sources,
            "warnings": warnings,
            "ttl_sec": DEFAULT_TTL,
            "prefer_pre": prefer_pre,
            "index_universe": list(INDEX_SYMBOLS.keys()),
            "etf_universe": list(ETF_SYMBOLS.keys()),
            "watch_universe": list(WATCHLIST.keys()),
        },
    }
