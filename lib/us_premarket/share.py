"""美股盘前/盘后 share_copy · 只出币安广场，不出 X。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.binance_square_playbook import (
    PLAYBOOK_ID,
    append_square_to_markdown,
    build_square_bundle,
)

AUTHOR = "硅基生命001"


def _pct(v: Any) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "n/a"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.2f}%"


def _line(t: dict, i: int) -> str:
    return (
        f"{i}. {t.get('name') or t.get('symbol')} {_pct(t.get('change_pct'))}"
        f" ({t.get('symbol')})"
    )


def build_us_pre_share_copy(analysis: dict) -> dict:
    as_of = analysis.get("as_of") or "n/a"
    sess_label = analysis.get("session_label") or "盘前"
    indices = analysis.get("indices") or []
    etf_s = analysis.get("etf_strong") or []
    etf_w = analysis.get("etf_weak") or []
    w_up = analysis.get("watch_up") or []
    w_dn = analysis.get("watch_down") or []
    risks = analysis.get("risk_flags") or []
    brief = analysis.get("brief") or ""
    kpi = analysis.get("kpi") or {}
    futures = analysis.get("futures") or []
    macro = analysis.get("macro") or []

    top_etf = etf_s[0]["name"] if etf_s else "主线"
    weak_etf = etf_w[0]["name"] if etf_w else None
    top_pct = float(etf_s[0].get("change_pct") or 0) if etf_s else 0.0

    if weak_etf and etf_s:
        hook = f"指数看着不慌，「{weak_etf}」盘前已经先回吐。"
        if top_pct >= 0.5:
            hook = f"「{top_etf}」在抢跑，「{weak_etf}」在回吐——结构已经分家了。"
    elif sess_label == "盘前":
        hook = f"美股还没开，「{top_etf}」已经在抢跑？"
    elif sess_label == "盘后":
        hook = f"收盘了，今天还看「{top_etf}」吗？"
    else:
        hook = f"美股盘中，主线还在「{top_etf}」吗？"

    es = _pct(kpi.get("es_change_pct") or (futures[0].get("change_pct") if futures else None))
    nq = _pct(kpi.get("nq_change_pct") or (futures[1].get("change_pct") if len(futures) > 1 else None))
    strong_bit = f"强 {top_etf} {_pct(etf_s[0].get('change_pct'))}" if etf_s else ""
    weak_bit = (
        f"弱 {weak_etf} {_pct(etf_w[0].get('change_pct'))}" if etf_w else ""
    )
    mag_bits = []
    if w_up:
        mag_bits.append(f"{w_up[0].get('symbol')} {_pct(w_up[0].get('change_pct'))}")
    if w_dn:
        mag_bits.append(
            "弱 " + "/".join(f"{t.get('symbol')} {_pct(t.get('change_pct'))}" for t in w_dn[:2])
        )

    facts = [
        f"隔夜 ES {es} · NQ {nq}",
        " · ".join(x for x in (strong_bit, weak_bit) if x),
    ]
    if mag_bits:
        facts.append("Mag7+：" + " · ".join(mag_bits))
    if sess_label == "盘前":
        facts.append("口径：现金指数多为昨收，盘前看期指/ETF。")

    stance = ""
    if risks:
        stance = "风险旗：" + "；".join(risks[:2])
    elif weak_etf and top_etf:
        stance = f"今开先盯：{top_etf} 能否延续，还是 {weak_etf} 拖累指数。"

    cta = "今开你站强板块，还是盯弱侧反弹？评论区报代码。"
    sig = f"{AUTHOR}｜美股{sess_label} · 非实时"

    fut_tape = " · ".join(
        f"{f.get('short') or f.get('symbol')} {_pct(f.get('change_pct'))}" for f in futures[:3]
    )
    cash_parts = []
    for i in indices[:3]:
        tag = "昨收" if i.get("quote_session") == "prior_close" and sess_label == "盘前" else ""
        label = i.get("short") or i.get("symbol")
        cash_parts.append(f"{label} {_pct(i.get('change_pct'))}" + (f"（{tag}）" if tag else ""))
    cash_tape = " · ".join(cash_parts)
    macro_bits = []
    vix = next((m for m in macro if m.get("symbol") == "^VIX"), None)
    tnx = next((m for m in macro if m.get("symbol") == "^TNX"), None)
    if vix is not None:
        macro_bits.append(f"VIX {_pct(vix.get('change_pct'))}")
    if tnx is not None and tnx.get("price") is not None:
        try:
            macro_bits.append(f"10Y {float(tnx['price']):.2f}%")
        except (TypeError, ValueError):
            pass

    reply_etf_s = [_line(t, i + 1) for i, t in enumerate(etf_s[:5])]
    reply_etf_w = [_line(t, i + 1) for i, t in enumerate(etf_w[:5])]
    reply_up = [_line(t, i + 1) for i, t in enumerate(w_up[:5])]
    reply_dn = [_line(t, i + 1) for i, t in enumerate(w_dn[:5])]

    square = build_square_bundle(
        market="U",
        hook=hook,
        evidence=[x for x in facts if x],
        reads=[
            "先看期指隔夜，再看现金昨收，别混读。",
            "强弱差在开盘后是否收敛，是结构交易关键。",
        ],
        stance=stance,
        cta=cta,
        tags=["$SPY", "$QQQ", "#美股盘前"] if sess_label != "盘后" else ["$SPY", "$QQQ", "#美股盘后"],
        article_title=f"美股{sess_label}：{top_etf} vs {weak_etf or '弱侧'}，结构已分家",
        article_sections=[
            ("快照", f"北京 {as_of}"),
            ("期指", fut_tape or f"ES {es} · NQ {nq}"),
            ("板块强", reply_etf_s),
            ("板块弱", reply_etf_w),
            ("Mag7+", reply_up + (["弱侧："] + reply_dn if reply_dn else [])),
        ],
        signature=sig,
        cover_hint="建议配：美股一页纸 HTML 首屏截图作长文封面",
    )

    summary = f"【{AUTHOR}·美股{sess_label}】{as_of} · {brief} 非实时快照，不构成投资建议。"
    md_head = "\n".join(
        [
            f"# {AUTHOR} · 美股{sess_label}一页纸",
            "",
            f"**as_of** {as_of} · ET `{analysis.get('as_of_et')}`",
            f"**session** `{analysis.get('session')}` · framework=`{analysis.get('framework')}`",
            "",
            "## 摘要",
            "",
            summary,
            "",
        ]
    )
    md = append_square_to_markdown(md_head, square)

    return {
        "summary": summary,
        "markdown": md,
        "as_of": as_of,
        "session": analysis.get("session"),
        "session_label": sess_label,
        "framework": analysis.get("framework"),
        "market": analysis.get("market") or "U",
        "author": AUTHOR,
        **square,
        "playbook_square": square.get("playbook_square") or PLAYBOOK_ID,
    }


def write_share_copy(share: dict, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    j = out_dir / "share_copy.json"
    m = out_dir / "share_copy.md"
    j.write_text(json.dumps(share, ensure_ascii=False, indent=2), encoding="utf-8")
    m.write_text(share.get("markdown") or share.get("square_article") or "", encoding="utf-8")
    return {"json": str(j), "md": str(m)}
