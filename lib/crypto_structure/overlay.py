"""Overlay Chan/Wave analysis onto synthesis for crypto sibling reports."""
from __future__ import annotations

import copy
from typing import Any


DISCLAIMER = (
    "结构标注为可指名规则子集的工程结果（见 theory_refs / SOURCES.md），"
    "划笔与数浪仍可能因参数与窗口非唯一。"
    "总分与陪审团共识仍来自机构台，本镜头不重新打分。"
    "不构成投资建议；勿用「到位」安排市场。"
)

_REGIME_CN = {
    "range_in_zhongshu": "中枢震荡",
    "trend_above_zhongshu": "中枢上方趋势",
    "trend_below_zhongshu": "中枢下方趋势",
    "no_zhongshu_yet": "尚未形成中枢",
    "n/a": "暂无",
}


def _f(v) -> float | None:
    try:
        if v in (None, "", "—"):
            return None
        x = float(v)
        return x if x == x else None  # NaN check
    except (TypeError, ValueError):
        return None


def extract_daily_bars(raw: dict) -> list[dict[str, Any]]:
    """Build OHLCV list from raw 2_kline.

    Prefer full ``candles`` (structure history) over sparkline ``candles_60d``.
    """
    kline = ((raw.get("dimensions") or {}).get("2_kline") or {}).get("data") or {}
    # Full series first; candles_60d is report sparkline only
    candles = (
        kline.get("candles")
        or kline.get("candles_structure")
        or kline.get("candles_60d")
        or []
    )
    bars = _candles_to_bars(candles)
    if len(bars) >= 20:
        return bars

    closes = kline.get("close_60d") or []
    if isinstance(closes, list) and len(closes) >= 20:
        out: list[dict[str, Any]] = []
        for cl in closes:
            px = _f(cl)
            if px is None or px <= 0:
                continue
            out.append({
                "date": "",
                "open": px,
                "high": px * 1.005,
                "low": px * 0.995,
                "close": px,
                "volume": 0.0,
            })
        return out
    return bars


def extract_4h_bars(raw: dict) -> list[dict[str, Any]]:
    """Build 4H OHLCV from ``2_kline.data.candles_4h`` (structure-only)."""
    kline = ((raw.get("dimensions") or {}).get("2_kline") or {}).get("data") or {}
    return _candles_to_bars(kline.get("candles_4h") or [])


def _candles_to_bars(candles: list) -> list[dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    if not isinstance(candles, list):
        return bars
    for c in candles:
        if not isinstance(c, dict):
            continue
        close = _f(c.get("close") if c.get("close") is not None else c.get("Close"))
        high = _f(c.get("high") if c.get("high") is not None else c.get("High"))
        low = _f(c.get("low") if c.get("low") is not None else c.get("Low"))
        open_ = _f(c.get("open") if c.get("open") is not None else c.get("Open"))
        if close is None or close <= 0:
            continue
        if high is None:
            high = close
        if low is None:
            low = close
        if open_ is None:
            open_ = close
        if high <= 0 or low <= 0:
            continue
        vol = _f(c.get("volume") if c.get("volume") is not None else c.get("vol")) or 0.0
        # Keep intraday timestamps (may be longer than 10 chars)
        date_raw = str(c.get("date") or c.get("Date") or "")
        bars.append({
            "date": date_raw[:16] if len(date_raw) > 10 else date_raw[:10],
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        })
    return bars


def apply_structure_lens(syn: dict, analysis: dict, lens: str) -> dict:
    """Shallow-copy synthesis; attach structure_lens; tweak zones/plan notes only."""
    out = copy.deepcopy(syn) if syn else {}
    lens = (lens or "").lower()
    theory = "chan" if lens == "chan" else "wave" if lens == "wave" else lens
    analysis = analysis or {}
    sp = analysis.get("structure_price")

    out["structure_lens"] = {
        "theory": theory,
        "lens": lens,
        "analysis": analysis,
        "disclaimer": analysis.get("disclaimer") or DISCLAIMER,
        "theory_refs": analysis.get("theory_refs") or [],
        "engine": analysis.get("engine"),
    }

    zones = out.get("buy_zones")
    if isinstance(zones, dict):
        zones = dict(zones)
        tech = dict(zones.get("technical") or {})
        if sp is not None:
            try:
                tech["price"] = round(float(sp), 2)
            except (TypeError, ValueError):
                pass
        if theory == "chan":
            zs = analysis.get("zhongshu") or {}
            regime = str(analysis.get("trend_vs_range") or "")
            regime_cn = _REGIME_CN.get(regime, regime.replace("_", " "))
            tech["rationale"] = (
                f"缠论日线 · {regime_cn} · "
                + (
                    f"中枢 [{zs.get('zd')}, {zs.get('zg')}]"
                    if zs else "无中枢"
                )
                + " · 结构观察位，非下单指令。"
                "划笔不唯一；总分仍沿用机构台。"
            )
        else:
            prim = analysis.get("primary_count") or {}
            fib = analysis.get("fib_levels") or {}
            fib618 = fib.get("0.618")
            tech["rationale"] = (
                f"波浪日线 · 主计数 {prim.get('pattern', '暂无')} "
                f"（{prim.get('label', '—')}）"
                + (f" · Fib 0.618≈{fib618}" if fib618 is not None else "")
                + " · 务必保留备选计数 · 结构观察位，非下单指令。"
            )
        zones["technical"] = tech
        zones["_structure_lens"] = theory
        out["buy_zones"] = zones

    dash = dict(out.get("dashboard") or {})
    bp = dict(dash.get("battle_plan") or {})
    summary = analysis.get("summary_cn") or analysis.get("summary_en") or ""
    bp["structure_note"] = (summary[:220] if summary else DISCLAIMER[:160])
    if sp is not None:
        note = str(bp.get("entry_note") or "")
        tag = f"结构参考 {sp}"
        if tag not in note and f"structure ref {sp}" not in note:
            bp["entry_note"] = f"{note} · {tag}".strip(" ·") if note else tag
    dash["battle_plan"] = bp
    out["dashboard"] = dash
    return out
