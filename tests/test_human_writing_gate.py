"""human_writing_gate."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_gate_loads_and_masks_cashtags():
    from lib.human_writing_gate import check_text, mask_finance_scaffolding

    raw = (
        "回访昨天的锚点。ETH 摸到过确认带，但没站住。\n\n"
        "$BTC $ETH #波浪理论\n\n"
        "硅基生命001｜结构回访 · 非实时"
    )
    masked = mask_finance_scaffolding(raw)
    assert "$BTC" not in masked
    assert "CASHTAG" in masked
    assert "HASHTAG" in masked
    assert "SIGNATURE" in masked

    tweet = check_text(raw, mode="tweet")
    assert "mode" in tweet
    assert isinstance(tweet["failures"], list)
    assert isinstance(tweet["warnings"], list)


def test_article_gate_flags_hard_jargon():
    from lib.human_writing_gate import check_text

    bad = "我们要赋能整个链路，抓住抓手，完成底层逻辑的跃迁。"
    result = check_text(bad, mode="article")
    assert result["ok"] is False
    assert any("黑话" in x or "赋能" in x for x in result["failures"])
