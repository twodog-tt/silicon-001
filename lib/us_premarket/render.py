"""硅基生命001 · 美股盘前/盘中/盘后快照 HTML."""
from __future__ import annotations

import html as _html
from typing import Any


def _e(v: Any, default: str = "—") -> str:
    if v is None or v == "":
        return default
    return _html.escape(str(v), quote=True)


def _pct(v: Any, digits: int = 2) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.{digits}f}%"


def _pct_class(v: Any) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "flat"
    if x > 0.02:
        return "up"
    if x < -0.02:
        return "down"
    return "flat"


def _num(v: Any, digits: int = 2) -> str:
    try:
        x = float(v)
        if abs(x) >= 1000:
            return f"{x:,.2f}"
        return f"{x:.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _sess_tag(q: str | None) -> str:
    return {
        "premarket": "盘前",
        "regular": "日涨跌",
        "afterhours": "盘后",
        "prior_close": "昨收",
        "overnight": "隔夜",
    }.get(q or "", q or "—")


def _tape(analysis: dict) -> str:
    session = analysis.get("session")
    futures = analysis.get("futures") or []
    indices = analysis.get("indices") or []
    macro = analysis.get("macro") or []
    parts = []

    # 盘前：期指先行
    if session == "premarket":
        for fut in futures:
            label = fut.get("short") or fut.get("symbol")
            parts.append(
                f'<b>{_e(label)}</b> {_e(_num(fut.get("price"), 2))} '
                f'<span class="{_pct_class(fut.get("change_pct"))}">{_pct(fut.get("change_pct"))}</span>'
                f'<i class="tag">隔夜</i>'
            )
        for ix in indices:
            label = ix.get("short") or ix.get("symbol")
            parts.append(
                f'<b>{_e(label)}</b> {_e(_num(ix.get("price"), 2))} '
                f'<span class="{_pct_class(ix.get("change_pct"))}">{_pct(ix.get("change_pct"))}</span>'
                f'<i class="tag">昨收</i>'
            )
    else:
        for ix in indices:
            label = ix.get("short") or ix.get("symbol")
            parts.append(
                f'<b>{_e(label)}</b> {_e(_num(ix.get("price"), 2))} '
                f'<span class="{_pct_class(ix.get("change_pct"))}">{_pct(ix.get("change_pct"))}</span>'
            )
        for fut in futures[:2]:
            label = fut.get("short") or fut.get("symbol")
            parts.append(
                f'<b>{_e(label)}</b> '
                f'<span class="{_pct_class(fut.get("change_pct"))}">{_pct(fut.get("change_pct"))}</span>'
            )

    for ix in macro:
        label = ix.get("short") or ix.get("symbol")
        if label == "TNX" and ix.get("price") is not None:
            parts.append(
                f'<b>10Y</b> {_e(_num(ix.get("price"), 2))}% '
                f'<span class="{_pct_class(ix.get("change_pct"))}">{_pct(ix.get("change_pct"))}</span>'
            )
        else:
            parts.append(
                f'<b>{_e(label)}</b> {_e(_num(ix.get("price"), 2))} '
                f'<span class="{_pct_class(ix.get("change_pct"))}">{_pct(ix.get("change_pct"))}</span>'
            )

    return " · ".join(parts) if parts else '<span class="muted">指数/期指暂缺</span>'


def _rows_side(rows: list[dict], *, show_prior: bool = False) -> str:
    out = []
    for i, t in enumerate(rows, 1):
        prior = ""
        if show_prior:
            prior = (
                f"<td class='num {_pct_class(t.get('regular_change_pct'))}'>"
                f"{_pct(t.get('regular_change_pct'))}</td>"
            )
        out.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td class='name'>{_e(t.get('name'))} <span class='sym'>{_e(t.get('symbol'))}</span></td>"
            f"<td class='num'>{_e(_num(t.get('price'), 2))}</td>"
            f"<td class='num {_pct_class(t.get('change_pct'))}'>{_pct(t.get('change_pct'))}</td>"
            f"{prior}"
            f"<td><span class='muted'>{_e(_sess_tag(t.get('quote_session')))}</span></td>"
            "</tr>"
        )
    return "".join(out)


def _rows_grid(rows: list[dict]) -> str:
    out = []
    for i, t in enumerate(rows, 1):
        out.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td class='name'>{_e(t.get('name'))} <span class='sym'>{_e(t.get('symbol'))}</span></td>"
            f"<td class='num'>{_e(_num(t.get('price'), 2))}</td>"
            f"<td class='num {_pct_class(t.get('change_pct'))}'>{_pct(t.get('change_pct'))}</td>"
            f"<td class='num {_pct_class(t.get('regular_change_pct'))}'>{_pct(t.get('regular_change_pct'))}</td>"
            f"<td><span class='muted'>{_e(_sess_tag(t.get('quote_session')))}</span></td>"
            "</tr>"
        )
    return "".join(out)


def _rows_gap(rows: list[dict]) -> str:
    out = []
    for g in rows:
        out.append(
            "<tr>"
            f"<td class='name'>{_e(g.get('pair'))}</td>"
            f"<td class='num {_pct_class(g.get('fut'))}'>{_pct(g.get('fut'))}</td>"
            f"<td class='num {_pct_class(g.get('cash'))}'>{_pct(g.get('cash'))}</td>"
            f"<td class='num {_pct_class(g.get('gap'))}'>{_pct(g.get('gap'))}</td>"
            f"<td class='muted'>{_e(g.get('note'))}</td>"
            "</tr>"
        )
    return "".join(out)


def _table(headers: list[str], body: str, empty: str = "—") -> str:
    if not body:
        body = f'<tr><td colspan="{len(headers)}" class="muted">{_e(empty)}</td></tr>'
    th = "".join(f"<th>{_e(h)}</th>" for h in headers)
    return f'<table class="g"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def render_us_pre_onepager(analysis: dict) -> str:
    sess_label = analysis.get("session_label") or "盘前"
    as_of = analysis.get("as_of") or "—"
    as_of_et = analysis.get("as_of_et") or "—"
    brief = analysis.get("brief") or ""
    kpi = analysis.get("kpi") or {}
    etf_s = analysis.get("etf_strong") or []
    etf_w = analysis.get("etf_weak") or []
    w_up = analysis.get("watch_up") or []
    w_dn = analysis.get("watch_down") or []
    grid = analysis.get("watch_grid") or analysis.get("watchlist") or []
    gaps = analysis.get("futures_gaps") or []
    flags = analysis.get("risk_flags") or []
    meta = analysis.get("meta") or {}
    quote_note = analysis.get("quote_note") or ""
    sources = " · ".join(meta.get("sources") or []) or "—"
    warn = meta.get("warnings") or []

    risk_html = ""
    if flags:
        risk_html = (
            '<div class="risk"><b>风险旗</b> · '
            + "；".join(_e(f) for f in flags[:6])
            + "</div>"
        )
    dq = ""
    if warn:
        dq = f'<p class="dq">降级/告警：{_e("；".join(warn[:3]))}</p>'

    gap_section = ""
    if gaps:
        gap_section = f"""
  <section class="cmp">
    <h2>期指 vs 现金昨收（口径差，不是同步盘口）</h2>
    {_table(["对照", "期指%", "昨收%", "差", "说明"], _rows_gap(gaps), "—")}
  </section>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>硅基生命001 · 美股{_e(sess_label)}一页纸</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=Sora:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
:root {{
  --paper:#f2efe8; --ink:#1a1512; --accent:#c23b22; --accent-2:#0e7c6b;
  --surface:#fffdf9; --muted:#6b6258; --line:rgba(26,21,18,.12);
  --up:#c23b22; --down:#0e7c6b;
  --fd:'Noto Serif SC','Songti SC',serif; --fb:'Sora','PingFang SC',sans-serif;
}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--paper);color:var(--ink);font:12.5px/1.35 var(--fb)}}
.sheet{{max-width:1040px;margin:0 auto;padding:10px 14px 14px}}
.hero{{
  background:linear-gradient(145deg,#1a1512 0%,#2c241c 40%,#1a3a5c 100%);
  color:#f6f1ea;border-radius:12px;padding:12px 14px 10px;
}}
.brand{{font:700 22px/1.1 var(--fd);margin:0;letter-spacing:.03em}}
.ed{{opacity:.75;font-size:10px;letter-spacing:.14em;text-transform:uppercase}}
.hrow{{display:flex;justify-content:space-between;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-top:6px}}
h1{{font:700 16px/1.25 var(--fd);margin:0}}
.asof{{opacity:.85;font-size:11px;text-align:right}}
.badge{{
  display:inline-block;margin-top:4px;padding:2px 7px;border-radius:4px;
  background:rgba(246,241,234,.14);border:1px solid rgba(246,241,234,.28);
  font-size:10px;letter-spacing:.06em
}}
.tape{{margin-top:8px;padding-top:8px;border-top:1px solid rgba(246,241,234,.18);font-size:11.5px;line-height:1.55}}
.tape .up{{color:#ff8a75}}.tape .down{{color:#7dceb8}}
.tape .tag{{font-style:normal;opacity:.65;font-size:9px;margin-left:3px}}
.dq{{margin:8px 0 0;font-size:10.5px;color:var(--muted)}}
.brief{{
  margin:8px 0;padding:8px 10px;background:var(--surface);
  border-left:3px solid var(--accent);border-radius:0 8px 8px 0;font:600 13px/1.4 var(--fd)
}}
.note{{margin:0 0 8px;font-size:10.5px;color:var(--muted)}}
.kpi{{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin:8px 0}}
.kpi>div{{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 8px}}
.kpi .k{{font-size:10px;color:var(--muted)}}
.kpi .v{{font:700 15px/1.1 var(--fb);font-variant-numeric:tabular-nums;margin-top:2px}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0}}
.panel{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:6px 8px 8px;min-width:0}}
.panel h2,.cmp h2{{
  font:700 12.5px/1.2 var(--fd);margin:0 0 4px;display:flex;justify-content:space-between;align-items:baseline
}}
.panel h2 span{{font:400 10px var(--fb);color:var(--muted)}}
.panel.strong h2{{color:var(--accent)}}
.panel.weak h2{{color:var(--accent-2)}}
.cmp{{margin:8px 0;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:6px 8px}}
.g{{width:100%;border-collapse:collapse}}
.g th,.g td{{padding:3px 5px;text-align:left;border-bottom:1px solid var(--line);font-size:11.5px;vertical-align:top}}
.g th{{font-size:10px;color:var(--muted);font-weight:600}}
.g .name{{font-weight:600}}
.g .sym{{font-weight:400;color:var(--muted);font-size:10px;margin-left:4px}}
.g .num{{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}}
.g tr:last-child td{{border-bottom:0}}
.up{{color:var(--up)}}.down{{color:var(--accent-2)}}.flat{{color:var(--muted)}}.muted{{color:var(--muted)}}
.risk{{
  margin:8px 0 0;padding:7px 10px;background:rgba(194,59,34,.06);
  border:1px solid rgba(194,59,34,.16);border-radius:8px;font-size:11.5px
}}
.foot{{margin-top:8px;font-size:10px;color:var(--muted);line-height:1.45}}
@media print{{
  body{{background:#fff}}
  .sheet{{max-width:none;padding:0}}
  .hero{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  @page{{size:A4;margin:10mm}}
}}
@media (max-width:820px){{
  .pair,.kpi{{grid-template-columns:1fr 1fr}}
}}
</style>
</head>
<body>
<main class="sheet">
  <header class="hero">
    <div class="ed">silicon-001 · US Memo · {_e(sess_label)} Snapshot</div>
    <div class="hrow">
      <div>
        <p class="brand">硅基生命001</p>
        <h1>美股{_e(sess_label)}一页纸 · 期指 / 板块 / Mag7</h1>
      </div>
      <div class="asof">
        北京 {_e(as_of)}<br/>美东 {_e(as_of_et)}
        <div class="badge">{_e(sess_label)}快照 · 非实时</div>
      </div>
    </div>
    <div class="tape">{_tape(analysis)}</div>
  </header>
  {dq}
  <p class="brief">{_e(brief)}</p>
  <p class="note">{_e(quote_note)}</p>
  <div class="kpi">
    <div><div class="k">ES 隔夜</div><div class="v {_pct_class(kpi.get('es_change_pct'))}">{_pct(kpi.get('es_change_pct'))}</div></div>
    <div><div class="k">NQ 隔夜</div><div class="v {_pct_class(kpi.get('nq_change_pct'))}">{_pct(kpi.get('nq_change_pct'))}</div></div>
    <div><div class="k">YM 隔夜</div><div class="v {_pct_class(kpi.get('ym_change_pct'))}">{_pct(kpi.get('ym_change_pct'))}</div></div>
    <div><div class="k">VIX</div><div class="v">{_e(_num(kpi.get('vix'), 2))} <span class="{_pct_class(kpi.get('vix_change_pct'))}" style="font-size:11px">{_pct(kpi.get('vix_change_pct'))}</span></div></div>
    <div><div class="k">10Y</div><div class="v">{_e(_num(kpi.get('tnx'), 2))}%</div></div>
    <div><div class="k">广度 ETF/观察</div><div class="v">{_e(kpi.get('etf_up'),'0')}/{_e(kpi.get('etf_down'),'0')} · {_e(kpi.get('watch_up'),'0')}/{_e(kpi.get('watch_down'),'0')}</div></div>
  </div>
  {gap_section}
  <div class="pair">
    <section class="panel strong">
      <h2>板块 ETF 强势<span>上涨侧</span></h2>
      {_table(["#","名称","现价","涨跌","昨收%","口径"], _rows_side(etf_s, show_prior=True), "暂无上涨板块")}
    </section>
    <section class="panel weak">
      <h2>板块 ETF 弱势<span>仅下跌</span></h2>
      {_table(["#","名称","现价","涨跌","昨收%","口径"], _rows_side(etf_w, show_prior=True), "暂无下跌板块")}
    </section>
  </div>
  <div class="pair">
    <section class="panel strong">
      <h2>观察池强势<span>Mag7+</span></h2>
      {_table(["#","名称","现价","涨跌","昨收%","口径"], _rows_side(w_up, show_prior=True), "暂无")}
    </section>
    <section class="panel weak">
      <h2>观察池弱势<span>仅下跌</span></h2>
      {_table(["#","名称","现价","涨跌","昨收%","口径"], _rows_side(w_dn, show_prior=True), "暂无下跌个股")}
    </section>
  </div>
  <section class="cmp">
    <h2>Mag7+ 全表<span>盘前优先 · 附昨收对照</span></h2>
    {_table(["#","名称","现价","本档%","昨收%","口径"], _rows_grid(grid), "暂无")}
  </section>
  {risk_html}
  <footer class="foot">
    时段按美东：盘前 &lt;09:30 · 盘中 09:30–16:00 · 盘后 ≥16:00。
    盘前页：现金指数=昨收；股指期货=隔夜；个股/ETF 优先盘前字段。framework=us-premarket · 源：{_e(sources)}。
    非实时快照 · 不构成投资建议 · 硅基生命001。
  </footer>
</main>
</body>
</html>
"""
