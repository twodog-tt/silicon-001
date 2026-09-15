"""美股盘前指标 / 强弱排序 / 风险旗."""
from __future__ import annotations

from typing import Any

from lib.us_premarket import FRAMEWORK, MARKET
from lib.us_premarket.fetch import resolve_us_session


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def _pct_s(x: float | None) -> str:
    if x is None:
        return "—"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.2f}%"


def _sort_by_chg(rows: list[dict], *, reverse: bool = True) -> list[dict]:
    return sorted(
        [r for r in rows if _f(r.get("change_pct")) is not None],
        key=lambda r: float(r["change_pct"]),
        reverse=reverse,
    )


def _side(rows: list[dict], *, strong: bool, n: int = 5) -> list[dict]:
    """强侧取涨幅 Top；弱侧只取下跌（无下跌则空，避免绿盘混进弱势栏）."""
    ranked = _sort_by_chg(rows, reverse=strong)
    if strong:
        return [r for r in ranked if (_f(r.get("change_pct")) or 0) > 0][:n] or ranked[:n]
    return [r for r in ranked if (_f(r.get("change_pct")) or 0) < 0][:n]


def _brief(
    *,
    session: str,
    futures: list[dict],
    indices: list[dict],
    etf_strong: list[dict],
    etf_weak: list[dict],
    watch: list[dict],
    sess_label: str,
) -> str:
    bits = []
    es = next((f for f in futures if f.get("symbol") == "ES=F"), None)
    nq = next((f for f in futures if f.get("symbol") == "NQ=F"), None)
    vix = next((i for i in indices if i.get("symbol") == "^VIX"), None)
    tnx = next((i for i in indices if i.get("symbol") == "^TNX"), None)
    spx = next((i for i in indices if i.get("symbol") == "^GSPC"), None)

    if session == "premarket":
        if es and es.get("change_pct") is not None:
            bits.append(f"ES期指 {_pct_s(es.get('change_pct'))}")
        if nq and nq.get("change_pct") is not None:
            bits.append(f"NQ {_pct_s(nq.get('change_pct'))}")
        if spx and spx.get("change_pct") is not None:
            bits.append(f"标普昨收 {_pct_s(spx.get('change_pct'))}")
    else:
        if spx and spx.get("change_pct") is not None:
            bits.append(f"标普 {_pct_s(spx.get('change_pct'))}")
        if es and es.get("change_pct") is not None:
            bits.append(f"ES {_pct_s(es.get('change_pct'))}")

    if vix and vix.get("price") is not None:
        bits.append(f"VIX {float(vix['price']):.1f}({_pct_s(vix.get('change_pct'))})")
    if tnx and tnx.get("price") is not None:
        bits.append(f"10Y {float(tnx['price']):.2f}%")

    if etf_strong:
        bits.append(f"强 {etf_strong[0].get('name')} {_pct_s(etf_strong[0].get('change_pct'))}")
    if etf_weak:
        bits.append(f"弱 {etf_weak[0].get('name')} {_pct_s(etf_weak[0].get('change_pct'))}")

    up = sum(1 for w in watch if (_f(w.get("change_pct")) or 0) > 0)
    dn = sum(1 for w in watch if (_f(w.get("change_pct")) or 0) < 0)
    if watch:
        bits.append(f"观察池 {up}涨/{dn}跌")

    head = f"{sess_label}速写：" if sess_label else ""
    return head + "；".join(bits) + "。" if bits else f"{sess_label}数据不足，暂无法速写。"


def _risk_flags(
    indices: list[dict],
    futures: list[dict],
    etf_strong: list[dict],
    etf_weak: list[dict],
    watch: list[dict],
) -> list[str]:
    flags: list[str] = []
    vix = next((i for i in indices if i.get("symbol") == "^VIX"), None)
    if vix and _f(vix.get("change_pct")) is not None and abs(float(vix["change_pct"])) >= 8:
        flags.append(f"VIX 波动放大 {_pct_s(vix.get('change_pct'))}")
    if vix and _f(vix.get("price")) is not None and float(vix["price"]) >= 25:
        flags.append(f"VIX 水平偏高 {float(vix['price']):.1f}")

    spx = next((i for i in indices if i.get("symbol") == "^GSPC"), None)
    es = next((f for f in futures if f.get("symbol") == "ES=F"), None)
    if spx and es and _f(spx.get("change_pct")) is not None and _f(es.get("change_pct")) is not None:
        gap = float(es["change_pct"]) - float(spx["change_pct"])
        if abs(gap) >= 0.35:
            flags.append(f"ES 较标普昨收偏离 {gap:+.2f}pct（隔夜 vs 昨收，非同步口径）")

    chgs_ok = [c for c in (_f(w.get("change_pct")) for w in watch) if c is not None]
    if len(chgs_ok) >= 5:
        neg = sum(1 for c in chgs_ok if c < -1.0)
        pos = sum(1 for c in chgs_ok if c > 1.0)
        if neg >= 5:
            flags.append("Mag7/观察池多数下跌超 1%")
        if pos >= 5:
            flags.append("Mag7/观察池多数上涨超 1%")

    if etf_weak and etf_strong:
        top = _f(etf_strong[0].get("change_pct"))
        bot = _f(etf_weak[0].get("change_pct"))
        if top is not None and bot is not None and (top - bot) >= 1.5:
            flags.append(
                f"板块分化：{etf_strong[0].get('name')} vs {etf_weak[0].get('name')}"
            )
    return flags[:8]


def build_us_pre_analysis(snapshot: dict) -> dict[str, Any]:
    sess = resolve_us_session()
    session = snapshot.get("session") or sess["session"]
    session_label = snapshot.get("session_label") or sess["session_label"]

    indices = list(snapshot.get("indices") or [])
    futures = list(snapshot.get("futures") or [])
    etfs = list(snapshot.get("etfs") or [])
    watch = list(snapshot.get("watchlist") or [])

    # 主指数 vs 宏观（VIX/TNX 单独）
    tape_indices = [i for i in indices if i.get("symbol") in ("^GSPC", "^IXIC", "^DJI")]
    macro_indices = [i for i in indices if i.get("symbol") in ("^VIX", "^TNX")]

    etf_strong = _side(etfs, strong=True, n=5)
    etf_weak = _side(etfs, strong=False, n=5)
    watch_up = _side(watch, strong=True, n=5)
    watch_down = _side(watch, strong=False, n=5)
    watch_grid = _sort_by_chg(watch, reverse=True)

    up_n = sum(1 for w in watch if (_f(w.get("change_pct")) or 0) > 0.02)
    dn_n = sum(1 for w in watch if (_f(w.get("change_pct")) or 0) < -0.02)
    flat_n = max(0, len(watch) - up_n - dn_n)
    etf_up = sum(1 for e in etfs if (_f(e.get("change_pct")) or 0) > 0.02)
    etf_dn = sum(1 for e in etfs if (_f(e.get("change_pct")) or 0) < -0.02)

    pre_n = sum(1 for w in watch if w.get("quote_session") == "premarket")
    etf_pre = sum(1 for e in etfs if e.get("quote_session") == "premarket")
    if session == "premarket":
        quote_note = (
            f"盘前口径：ETF {etf_pre}/{len(etfs)}、观察池 {pre_n}/{len(watch)} 用盘前价；"
            "现金指数为昨收（Yahoo 无盘前指数字段）；期指为隔夜连续报价。"
        )
    else:
        quote_note = f"观察池盘前字段 {pre_n}/{len(watch)} · 其余为常规涨跌"

    vix = next((i for i in indices if i.get("symbol") == "^VIX"), None)
    tnx = next((i for i in indices if i.get("symbol") == "^TNX"), None)
    es = next((f for f in futures if f.get("symbol") == "ES=F"), None)
    nq = next((f for f in futures if f.get("symbol") == "NQ=F"), None)
    ym = next((f for f in futures if f.get("symbol") == "YM=F"), None)
    spx = next((i for i in indices if i.get("symbol") == "^GSPC"), None)
    ixic = next((i for i in indices if i.get("symbol") == "^IXIC"), None)

    gaps = []
    if es and spx and _f(es.get("change_pct")) is not None and _f(spx.get("change_pct")) is not None:
        gaps.append({
            "pair": "ES vs SPX昨收",
            "fut": es.get("change_pct"),
            "cash": spx.get("change_pct"),
            "gap": float(es["change_pct"]) - float(spx["change_pct"]),
            "note": "隔夜期指 − 现金昨收",
        })
    if nq and ixic and _f(nq.get("change_pct")) is not None and _f(ixic.get("change_pct")) is not None:
        gaps.append({
            "pair": "NQ vs IXIC昨收",
            "fut": nq.get("change_pct"),
            "cash": ixic.get("change_pct"),
            "gap": float(nq["change_pct"]) - float(ixic["change_pct"]),
            "note": "隔夜期指 − 现金昨收",
        })

    flags = _risk_flags(indices, futures, etf_strong, etf_weak, watch)
    meta = dict(snapshot.get("meta") or {})
    for w in meta.get("warnings") or []:
        flags.append(f"数据：{w}")

    return {
        "framework": snapshot.get("framework") or FRAMEWORK,
        "market": snapshot.get("market") or MARKET,
        "as_of": snapshot.get("as_of"),
        "as_of_et": snapshot.get("as_of_et") or sess.get("et"),
        "session": session,
        "session_label": session_label,
        "indices": tape_indices,
        "macro": macro_indices,
        "futures": futures,
        "etfs": etfs,
        "etf_strong": etf_strong,
        "etf_weak": etf_weak,
        "watch_up": watch_up,
        "watch_down": watch_down,
        "watch_grid": watch_grid,
        "watchlist": watch,
        "futures_gaps": gaps,
        "kpi": {
            "es_change_pct": es.get("change_pct") if es else None,
            "es_price": es.get("price") if es else None,
            "nq_change_pct": nq.get("change_pct") if nq else None,
            "nq_price": nq.get("price") if nq else None,
            "ym_change_pct": ym.get("change_pct") if ym else None,
            "ym_price": ym.get("price") if ym else None,
            "vix": vix.get("price") if vix else None,
            "vix_change_pct": vix.get("change_pct") if vix else None,
            "tnx": tnx.get("price") if tnx else None,
            "tnx_change_pct": tnx.get("change_pct") if tnx else None,
            "watch_up": up_n,
            "watch_down": dn_n,
            "watch_flat": flat_n,
            "watch_total": len(watch),
            "etf_up": etf_up,
            "etf_down": etf_dn,
            "etf_total": len(etfs),
        },
        "brief": _brief(
            session=session,
            futures=futures,
            indices=indices,
            etf_strong=etf_strong,
            etf_weak=etf_weak,
            watch=watch,
            sess_label=session_label,
        ),
        "quote_note": quote_note,
        "risk_flags": flags[:8],
        "meta": meta,
    }
