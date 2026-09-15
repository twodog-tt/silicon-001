#!/usr/bin/env python3
"""Elliott Wave structure brief on 4H bars (BTC / ETH).

Usage (from skills/deep-analysis/scripts):
  PYTHONPATH=. python tools/render_crypto_wave_4h.py BTC ETH
  PYTHONPATH=. python tools/render_crypto_wave_4h.py BTC --no-fetch
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.cache import read_task_output, write_task_output  # noqa: E402
from lib.crypto_signals import fetch_crypto_kline_4h  # noqa: E402
from lib.crypto_structure.overlay import extract_4h_bars  # noqa: E402
from lib.crypto_structure.wave import (  # noqa: E402
    analyze_wave,
    _swing_points,
    _fib_levels,
)
from lib.export_watermark import apply_matplotlib_watermark  # noqa: E402


def _setup_font() -> None:
    for fp in (
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        if Path(fp).exists():
            font_manager.fontManager.addfont(fp)
            prop = font_manager.FontProperties(fname=fp)
            plt.rcParams["font.family"] = prop.get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def _draw_candles(ax, opens, highs, lows, closes) -> None:
    for i in range(len(closes)):
        up = closes[i] >= opens[i]
        color = "#c23b22" if up else "#2a6f4e"
        ax.plot([i, i], [lows[i], highs[i]], color=color, lw=0.9, solid_capstyle="round")
        body_lo, body_hi = min(opens[i], closes[i]), max(opens[i], closes[i])
        height = max(body_hi - body_lo, (highs.max() - lows.min()) * 0.001)
        ax.add_patch(
            Rectangle((i - 0.32, body_lo), 0.64, height, facecolor=color, edgecolor=color, lw=0)
        )


def _stagger_label_ys(levels: list[tuple[str, float, str]], min_gap: float):
    items = sorted(levels, key=lambda t: t[1])
    draw = [float(y) for _, y, _ in items]
    for _ in range(12):
        moved = False
        for i in range(1, len(draw)):
            if draw[i] - draw[i - 1] < min_gap:
                mid = (draw[i] + draw[i - 1]) / 2
                draw[i - 1] = mid - min_gap / 2
                draw[i] = mid + min_gap / 2
                moved = True
        if not moved:
            break
    return [(items[i][0], items[i][1], draw[i], items[i][2]) for i in range(len(items))]


def _annotate_levels(ax, levels, n_bars: int, y_span: float, last: float) -> None:
    min_gap = max(y_span * 0.055, last * 0.004)
    staged = _stagger_label_ys(levels, min_gap)
    x_line_end = n_bars - 0.5
    x_text = n_bars + max(1.5, n_bars * 0.02)
    for text, true_y, draw_y, color in staged:
        ax.axhline(true_y, color=color, lw=1.0, ls="--", alpha=0.7, zorder=2)
        if abs(draw_y - true_y) > min_gap * 0.15:
            ax.plot(
                [x_line_end, x_text - 0.3], [true_y, draw_y],
                color=color, lw=0.6, alpha=0.55, zorder=3,
            )
        ax.text(
            x_text, draw_y, text,
            va="center", ha="left", fontsize=7.5, color=color, zorder=7,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#faf9f7", edgecolor="none", alpha=0.92),
        )


def _style_ax(ax, *, n_bars, dates, tick_idx, title, subtitle) -> None:
    ax.set_title("")
    ax.text(
        0.0, 1.085, title, transform=ax.transAxes,
        fontsize=14, fontweight="600", va="bottom", ha="left", color="#0f1720", clip_on=False,
    )
    ax.text(
        0.0, 1.025, subtitle, transform=ax.transAxes,
        fontsize=8.5, va="bottom", ha="left", color="#5c6670", clip_on=False,
    )
    ax.set_xlim(-1.2, n_bars + max(8, int(n_bars * 0.18)))
    ymin, ymax = ax.get_ylim()
    pad = (ymax - ymin) * 0.04
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_xticks(tick_idx)

    def _lab(d: str) -> str:
        d = str(d)
        if len(d) >= 16:
            return d[5:16]  # MM-DD HH:MM
        if len(d) >= 10:
            return d[5:10]
        return d

    ax.set_xticklabels([_lab(dates[i]) for i in tick_idx], fontsize=7.5, rotation=0)
    ax.set_ylabel("价格 (USD)", fontsize=9)
    ax.grid(True, axis="y", alpha=0.25, lw=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_facecolor("#faf9f7")


def _refresh_4h(ticker: str) -> list[dict]:
    rows = fetch_crypto_kline_4h(ticker, limit=300)
    if len(rows) < 40:
        raise SystemExit(f"{ticker}: 4H fetch too thin ({len(rows)})")
    raw = read_task_output(ticker, "raw_data") or {"dimensions": {}}
    dims = raw.setdefault("dimensions", {})
    k = dims.setdefault("2_kline", {"data": {}})
    data = k.setdefault("data", {})
    # Normalize to candles_4h schema used by extract_4h_bars
    candles = []
    for r in rows:
        candles.append({
            "date": r.get("date") or r.get("Date") or "",
            "open": r.get("open"),
            "high": r.get("high"),
            "low": r.get("low"),
            "close": r.get("close"),
            "volume": r.get("volume") or r.get("vol") or 0,
        })
    data["candles_4h"] = candles
    data["candles_4h_count"] = len(candles)
    k["ok"] = True
    write_task_output(ticker, "raw_data", raw)
    print(f"[ok] refreshed {ticker} 4H ×{len(candles)} last={candles[-1].get('date')}")
    return extract_4h_bars(raw)


def _relabel_wave(wave: dict, *, bars_n: int) -> dict:
    """Rewrite daily-centric copy for 4H context without mutating engine rules."""
    w = dict(wave)
    prim = w.get("primary_count") or {}
    alt = w.get("alternate_count") or {}
    conf = w.get("confidence")
    conf_cn = {"low": "低", "medium": "中", "high": "高"}.get(conf, conf)
    summary = (
        f"4H 波浪：主计数={prim.get('pattern')}（{prim.get('label')}）；"
        f"备选={alt.get('pattern')}（{alt.get('label')}）。"
        f"样本={bars_n} 根4H · 摆动点={w.get('swing_count')}。置信度{conf_cn}。"
        f"硬规则来源：Frost/Prechter R1/R2/R3；Fib 为指南位。数浪不唯一；4H 噪声高于日线。"
    )
    w["summary_cn"] = summary
    w["summary_en"] = summary
    w["timeframe"] = "4H"
    disc = w.get("disclaimer") or ""
    if "4H" not in disc:
        w["disclaimer"] = (
            "基于 4H K 线的 Elliott 推动浪三硬规则校验 + 摆动窗口打分 + Fib 指南位；"
            "备选并存。4H 假突破更多，须用更高周期对照。不构成投资建议。"
        )
    return w


def _money(v) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    ax = abs(x)
    if ax >= 1000:
        return f"{x:,.0f}"
    if ax >= 100:
        return f"{x:,.1f}"
    if ax >= 1:
        return f"{x:,.2f}"
    return f"{x:.4f}"


def _px_round(v: float) -> float:
    return round(float(v), 4 if abs(v) < 1 else (2 if abs(v) < 1000 else 1))


def _write_html(out: Path, data: dict, png: Path) -> Path:
    from lib.crypto_structure.html_brief import _css, _e, _export_script, _img_data_uri, _DIR_CN

    w = data.get("wave") or {}
    prim = w.get("primary") or {}
    alt = w.get("alternate") or {}
    fib = w.get("fib") or {}
    swings = (w.get("swings") or [])[-6:]
    img_uri = _img_data_uri(png)
    labels = ["A/1", "B/2", "C/3", "D/4", "E/5", "·"]
    rows = "".join(
        f"<tr><td>{_e(labels[i] if i < len(labels) else '·')}</td>"
        f"<td>{_e(_DIR_CN.get(s.get('kind'), s.get('kind')))}</td>"
        f"<td>{_e(_money(s.get('price')))}</td>"
        f"<td>{_e(s.get('date'))}</td></tr>"
        for i, s in enumerate(swings)
    )
    fib_tiles = "".join(
        f'<div class="st-tile"><div class="lbl">Fib {_e(k)}</div>'
        f'<div class="val">{_e(_money(v))}</div></div>'
        for k, v in (("0.382", fib.get("0.382")), ("0.5", fib.get("0.5")),
                     ("0.618", fib.get("0.618")), ("1.618", fib.get("1.618")))
        if v is not None
    )
    ticker = data.get("ticker")
    body = f"""
<div class="st-hero" id="st-hero-card">
  <div class="brand">硅基生命001 · 结构详析 · 波浪 · 4H</div>
  <h1>{_e(ticker)} 波浪4H详析</h1>
  <p class="meta">4H截至 {_e(data.get('as_of_4h') or data.get('as_of'))}（UTC） ·
    样本 {_e(data.get('bars_4h'))} 根 · 生成 {_e(data.get('generated_at'))}</p>
  <p class="lead">{_e(w.get('summary'))}</p>
  <div class="st-kpis">
    <div class="st-kpi"><i>现价</i><b>${_e(_money(data.get('last_price')))}</b></div>
    <div class="st-kpi"><i>主计数</i><b>{_e(prim.get('label'))}</b></div>
    <div class="st-kpi"><i>备选</i><b>{_e(alt.get('label'))}</b></div>
    <div class="st-kpi"><i>Fib 0.618</i><b>{_e(_money(fib.get('0.618')))}</b></div>
  </div>
  <div class="st-chart"><img src="{img_uri}" alt="波浪4H结构图"/></div>
</div>

<section class="st-section">
  <h2>图怎么读</h2>
  <p>蓝折线是 4H 摆动高低点。近段标了 A/1…E/5：左边字母是调整浪读法，右边数字是推动浪读法。右侧虚线是斐波那契回撤/延伸。黄线是现价。4H 噪声高于日线，数浪更易假破。</p>
</section>

<section class="st-section">
  <h2>近段摆动（4H）</h2>
  <table class="st-table"><thead><tr><th>标签</th><th>类型</th><th>价位</th><th>时间(UTC)</th></tr></thead>
  <tbody>{rows}</tbody></table>
</section>

<section class="st-section">
  <h2>主计数 / 备选</h2>
  <div class="st-grid">
    <div class="st-tile"><div class="lbl">主计数 · {_e(prim.get('pattern'))}</div>
      <div class="val" style="font-size:14px;font-weight:500">{_e(prim.get('label'))}</div>
      <div class="st-muted" style="margin-top:6px">{_e(prim.get('note'))}</div></div>
    <div class="st-tile"><div class="lbl">备选 · {_e(alt.get('pattern'))}</div>
      <div class="val" style="font-size:14px;font-weight:500">{_e(alt.get('label'))}</div>
      <div class="st-muted" style="margin-top:6px">{_e(alt.get('note'))}</div></div>
  </div>
  <div class="st-grid" style="margin-top:10px">{fib_tiles}</div>
</section>

<section class="st-section">
  <h2>两种读法怎么用</h2>
  <ol>
    <li><strong>主计数</strong>：优先看是否通过 Frost/Prechter R1/R2/R3；未通过则不当推动浪下单叙事。</li>
    <li><strong>备选</strong>：数浪不唯一，必须并存；用站稳/破位淘汰。</li>
    <li><strong>Fib</strong>：指南观察位，不是「到位必反」；4H 更容易扫线。</li>
    <li><strong>周期</strong>：本页仅 4H；与日线主计数冲突时，先以更高周期定性。</li>
  </ol>
</section>

<section class="st-section">
  <h2>技术来源</h2>
  <p class="st-muted">{_e(w.get('disclaimer') or '')}</p>
  <ul>
    {"".join(f"<li><strong>{_e(r.get('id'))}</strong> · {_e(r.get('source'))} — {_e(r.get('rule'))}</li>" for r in (w.get('theory_refs') or [])[:6])}
  </ul>
  <p class="st-muted">引擎：{_e(w.get('engine') or 'elliott-r123-v2')} · 周期：4H · 主计数 R1/R2/R3：{_e(prim.get('rules_checked') or '—')}</p>
</section>
"""
    title = f"{ticker} · 波浪4H详析"
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="silicon-001:structure" content="wave-4h"/>
<title>{_e(title)}</title>
<style>{_css()}</style>
</head>
<body>
<div class="st-wrap" id="st-capture-root">
  <div class="st-export">
    <button type="button" class="st-export-btn is-primary" data-st-export="full">导出全文</button>
    <button type="button" class="st-export-btn" data-st-export="hero">导出首屏</button>
  </div>
  {body}
  <div class="st-footer">4H截至 {_e(data.get('as_of_4h') or data.get('as_of'))}（UTC） · 生成 {_e(data.get('generated_at') or '—')} · 规则/数浪启发式，不唯一 · 不构成投资建议 · 硅基生命001</div>
</div>
{_export_script(ticker=str(ticker or 'BTC'), lens='wave')}
</body>
</html>
"""
    path = out / "structure-wave-4h.html"
    path.write_text(doc, encoding="utf-8")
    vendor = ROOT / "assets" / "vendor" / "html2canvas.min.js"
    if not vendor.exists():
        vendor = ROOT / "reports" / "BTC_20260803" / "structure" / "html2canvas.min.js"
    if vendor.exists():
        import shutil
        shutil.copy2(vendor, out / "html2canvas.min.js")
    return path


def render_one(ticker: str, *, fetch: bool = True) -> Path:
    _setup_font()
    ticker = ticker.upper()
    if fetch:
        try:
            bars = _refresh_4h(ticker)
        except Exception as e:
            print(f"[warn] fetch failed ({type(e).__name__}: {e}); using cache")
            raw = read_task_output(ticker, "raw_data")
            if not raw:
                raise SystemExit(f"no cache for {ticker}")
            bars = extract_4h_bars(raw)
    else:
        raw = read_task_output(ticker, "raw_data")
        if not raw:
            raise SystemExit(f"no cache for {ticker}")
        bars = extract_4h_bars(raw)

    if len(bars) < 40:
        raise SystemExit(f"{ticker}: need ≥40 4H bars, got {len(bars)}")

    dates = [b["date"] or str(i) for i, b in enumerate(bars)]
    opens = np.array([b["open"] for b in bars], float)
    highs = np.array([b["high"] for b in bars], float)
    lows = np.array([b["low"] for b in bars], float)
    closes = np.array([b["close"] for b in bars], float)
    last = float(closes[-1])

    wave = _relabel_wave(analyze_wave(bars), bars_n=len(bars))
    swings = _swing_points(highs.tolist(), lows.tolist(), closes.tolist(), order=3)

    date = datetime.now().strftime("%Y%m%d")
    out = ROOT / "reports" / f"{ticker}_{date}" / "structure_4h"
    out.mkdir(parents=True, exist_ok=True)

    cst = timezone(timedelta(hours=8))
    generated_at = datetime.now(cst).strftime("%Y-%m-%d %H:%M CST")
    as_of_4h = dates[-1]

    tick_idx = list(range(0, len(bars), max(1, len(bars) // 6)))
    if len(bars) - 1 not in tick_idx:
        tick_idx.append(len(bars) - 1)
    y_span = float(highs.max() - lows.min())

    fig, ax = plt.subplots(figsize=(12.5, 7.2), dpi=160)
    fig.patch.set_facecolor("#f4f2ee")
    fig.subplots_adjust(top=0.86, right=0.82, left=0.09, bottom=0.09)
    _draw_candles(ax, opens, highs, lows, closes)

    fib_levels: list[tuple[str, float, str]] = [(f"现价 {_money(last)}", last, "#b47a00")]
    fib_map = wave.get("fib_levels") or {}
    if not fib_map and len(swings) >= 2:
        a, b = swings[-2], swings[-1]
        fib_map = _fib_levels(a["price"], b["price"])
    for key, color in (("0.618", "#c45c26"), ("1.0", "#6b7280"), ("1.618", "#2a6f4e")):
        if key in fib_map:
            fib_levels.append((f"Fib {key}  {_money(fib_map[key])}", fib_map[key], color))
    ax.axhline(last, color="#f0a202", lw=1.1, alpha=0.85, zorder=2)
    _annotate_levels(ax, fib_levels, len(bars), y_span, last)

    sx = [s["i"] for s in swings]
    sy = [s["price"] for s in swings]
    ax.plot(sx, sy, color="#1d4e89", lw=1.6, alpha=0.85, zorder=5, label="摆动")
    for s in swings:
        ax.scatter(
            [s["i"]], [s["price"]], s=36, c="#1d4e89",
            marker=("v" if s["kind"] == "high" else "^"), zorder=6,
        )
    recent = swings[-6:]
    labels_abc = ["A/1", "B/2", "C/3", "D/4", "E/5", "·"]
    for i, s in enumerate(recent):
        lab = labels_abc[i] if i < len(labels_abc) else "·"
        if lab == "·":
            continue
        x_off = -22 if s["i"] > len(bars) * 0.72 else (10 if s["kind"] == "high" else -8)
        y_off = 16 if s["kind"] == "high" else -18
        ax.annotate(
            f"{lab}  {_money(s['price'])}",
            (s["i"], s["price"]),
            textcoords="offset points",
            xytext=(x_off, y_off),
            ha="center",
            fontsize=7,
            color="#1d4e89",
            fontweight="600",
            zorder=8,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#faf9f7", edgecolor="none", alpha=0.92),
        )

    prim = wave.get("primary_count") or {}
    alt = wave.get("alternate_count") or {}
    _style_ax(
        ax,
        n_bars=len(bars),
        dates=dates,
        tick_idx=tick_idx,
        title=f"{ticker} · 波浪4H结构",
        subtitle=(
            f"近 {len(bars)} 根4H · 主计数 {prim.get('pattern')}（{prim.get('label')}）· "
            f"备选 {alt.get('pattern')}（{alt.get('label')}）· 置信度{wave.get('confidence')} · "
            f"Frost/Prechter R1/R2/R3"
        ),
    )
    ax.legend(loc="lower left", frameon=True, framealpha=0.9, fontsize=8, edgecolor="#ddd")
    apply_matplotlib_watermark(fig)
    png = out / f"{ticker.lower()}-wave-4h-structure.png"
    fig.savefig(png, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    payload = {
        "ticker": ticker,
        "timeframe": "4H",
        "as_of": as_of_4h,
        "as_of_4h": as_of_4h,
        "generated_at": generated_at,
        "last_price": _px_round(last),
        "bars_4h": len(bars),
        "wave": {
            "summary": wave.get("summary_cn"),
            "primary": {k: v for k, v in prim.items() if k != "waves"},
            "alternate": {k: v for k, v in alt.items() if k != "waves"},
            "fib": fib_map or wave.get("fib_levels"),
            "swings": [
                {
                    "i": s["i"],
                    "kind": s["kind"],
                    "price": _px_round(s["price"]),
                    "date": dates[s["i"]],
                }
                for s in swings
            ],
            "confidence": wave.get("confidence"),
            "structure_price": wave.get("structure_price"),
            "theory_refs": wave.get("theory_refs"),
            "disclaimer": wave.get("disclaimer"),
            "engine": wave.get("engine"),
            "timeframe": "4H",
        },
        "closes": [
            {"date": dates[i], "close": _px_round(float(closes[i]))}
            for i in range(len(bars))
        ],
    }
    (out / "structure-wave-4h.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html = _write_html(out, payload, png)
    print(f"[ok] {ticker} 4H wave → {out}")
    print(f"     png  {png.name}")
    print(f"     html {html.name}")
    print(f"     last={payload['last_price']} primary={prim.get('pattern')} / {prim.get('label')}")
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Render Elliott Wave 4H structure briefs")
    p.add_argument("tickers", nargs="+", help="e.g. BTC ETH")
    p.add_argument("--no-fetch", action="store_true", help="use cached candles_4h only")
    args = p.parse_args(argv)
    for t in args.tickers:
        render_one(t.upper(), fetch=not args.no_fetch)


if __name__ == "__main__":
    main()
