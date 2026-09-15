"""BTC / ETH / SOL 4H 波浪 · 币安广场长文（一篇一币）。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lib.binance_square_playbook import (
    PLAYBOOK_ID,
    append_square_to_markdown,
    build_square_bundle,
    count_cashtags,
)
from lib.crypto_signals import crypto_meta, normalize_crypto_symbol

AUTHOR = "硅基生命001"

_TOPIC = {
    "BTC": "#比特币",
    "ETH": "#以太坊",
    "SOL": "#Solana",
}


def pair_for(ticker: str) -> str:
    sym = normalize_crypto_symbol(ticker)
    meta = crypto_meta(sym) or {}
    return meta.get("binance_spot") or f"{sym}USDT"


def cashtag_for(ticker: str) -> str:
    return f"${normalize_crypto_symbol(ticker)}"


def _pct_or_px(v: Any) -> str:
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


def _clock(text: Any) -> str:
    s = str(text or "").strip() or "n/a"
    return re.sub(r"(\d{1,2}):(\d{2})(?::\d{2})?", r"\1时\2分", s)


def build_wave_share_copy(payload: dict) -> dict:
    ticker = normalize_crypto_symbol(str(payload.get("ticker") or "BTC"))
    pair = pair_for(ticker)
    cash = cashtag_for(ticker)
    topic = _TOPIC.get(ticker, f"#{ticker}")
    wave = payload.get("wave") or {}
    prim = wave.get("primary") or {}
    alt = wave.get("alternate") or {}
    fib = wave.get("fib") or {}
    last = _pct_or_px(payload.get("last_price"))
    as_of = _clock(payload.get("as_of_4h") or payload.get("as_of") or "")
    conf = wave.get("confidence") or "n/a"
    summary = str(wave.get("summary") or "").strip()
    bars = payload.get("bars_4h") or "n/a"

    hook = f"{pair} 日线刚收，4H 主计数还站得住吗？"
    evidence = [
        f"{pair} 现价 {last} 美元，样本 {bars} 根4H，截至 {as_of} UTC",
        f"主计数 {prim.get('pattern') or 'n/a'}（{prim.get('label') or 'n/a'}），置信度 {conf}",
        f"备选 {alt.get('pattern') or 'n/a'}（{alt.get('label') or 'n/a'}）",
    ]
    if fib.get("0.618") is not None:
        evidence.append(f"Fib 0.618 在 {_pct_or_px(fib.get('0.618'))}")

    cta = "这根4H你按主计数走，还是按备选？"
    sig = f"{AUTHOR}｜{pair} 4H · 非实时"
    title = f"{pair} 4H 日线收线后怎么数"

    square = build_square_bundle(
        market="C",
        hook=hook,
        evidence=evidence,
        reads=[
            "蓝折线是摆动高低点，右侧虚线是 Fib 指南位，封面是结构图。",
            "4H 噪声高于日线，主计数没过 R1/R2/R3 就不要当成推动浪叙事。",
        ],
        stance=summary or None,
        cta=cta,
        tags=[cash, topic],
        article_title=title,
        article_sections=[
            ("交易对", f"{pair} · 现价 {last} · 4H截至 {as_of} UTC"),
            ("主计数", f"{prim.get('pattern') or 'n/a'} {prim.get('label') or ''}。{prim.get('note') or ''}".strip()),
            ("备选", f"{alt.get('pattern') or 'n/a'} {alt.get('label') or ''}。{alt.get('note') or ''}".strip()),
            ("怎么读", "结构图见封面与正文配图。数浪不唯一，4H 假突破更多。"),
        ],
        signature=sig,
        cover_hint="4H 波浪结构图作 cover+imageList；正文写见封面，不写 markdown 图链",
    )

    md_head = "\n".join(
        [
            f"# {AUTHOR} · {pair} 波浪4H",
            "",
            f"**as_of** {as_of} UTC",
            f"**pair** `{pair}` · cashtag `{cash}`",
            "",
        ]
    )
    body = square.get("square_article") or ""
    n_cash = count_cashtags(body)
    if n_cash != 1:
        raise ValueError(f"{pair} 广场文案 $ 次数应为 1，实际 {n_cash}")
    if pair not in body:
        raise ValueError(f"{pair} 广场文案缺少交易对明文")

    return {
        "ticker": ticker,
        "pair": pair,
        "cashtags": [cash],
        "market": "C",
        "author": AUTHOR,
        "as_of": as_of,
        "markdown": append_square_to_markdown(md_head, square),
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
