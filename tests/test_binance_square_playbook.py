"""binance_square_playbook · 广场发文规范回归."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def test_compose_short_requires_tags_and_blocks_wechat():
    from lib.binance_square_playbook import compose_square_short, validate_square_text

    ok = compose_square_short(
        hook="流动性在变薄。",
        evidence=["BTC 量能低于20日均"],
        reads=["先看深度再看价格"],
        cta="你站哪边？",
        tags=["$BTC", "#加密"],
        market="C",
    )
    assert "$BTC" in ok
    assert "你站哪边" in ok

    assert "third_party_wechat" in validate_square_text("加微信私聊带单稳赚")
    try:
        compose_square_short(
            hook="来",
            evidence=["x"],
            cta="加微信私聊",
            tags=["$BTC"],
            market="C",
        )
        assert False, "should raise"
    except ValueError as e:
        assert "合规失败" in str(e)


def test_article_publish_payload_default_cover_and_imagelist():
    from lib.binance_square_playbook import (
        PLAYBOOK_ID,
        build_article_publish_payload,
        build_short_image_publish_payload,
        compose_square_article,
        strip_markdown_images,
    )

    art = compose_square_article(
        title="BTC 结构还站得住吗？",
        hook="现价已离开 Fib 带。",
        sections=[("图怎么读", "封面是日线结构图。"), ("读数", "主计数 impulse_5")],
        cta="你站主计数还是备选？",
        tags=["$BTC"],
        market="C",
    )
    url = "https://public.bnbstatic.com/image/pgc/20260803/demo.png"
    dirty = art["body"] + f"\n\n![BTC波浪日线结构]({url})\n"
    assert "![" in dirty
    payload = build_article_publish_payload(
        title=art["title"],
        body=dirty,
        image_urls=[url],
    )
    assert payload["contentType"] == 2
    assert payload["cover"] == url
    assert payload["imageList"] == [url]
    assert "![" not in payload["bodyTextOnly"]
    assert url not in payload["bodyTextOnly"]
    assert payload["square_publish_mode"] == "cover+imageList"
    assert payload["playbook_square"] == PLAYBOOK_ID
    assert "![x](http://a.com/b.png)" not in strip_markdown_images("a ![x](http://a.com/b.png) b")

    try:
        build_article_publish_payload(title="x", body="no image section", image_urls=[])
        assert False, "empty images should fail"
    except ValueError:
        pass

    cover_only = build_article_publish_payload(
        title=art["title"],
        body=art["body"],
        image_urls=[url],
        mode="cover_only",
    )
    assert "imageList" not in cover_only
    assert cover_only["square_publish_mode"] == "cover_only"

    try:
        build_article_publish_payload(
            title="x",
            body="见封面\n\n$BTC",
            image_urls=[url, url],
            mode="cover_only",
        )
        assert False, "cover_only should reject >1 image"
    except ValueError as e:
        assert "仅允许 1 张" in str(e)

    short = build_short_image_publish_payload(
        body="短讯配图\n\n$BTC #加密",
        image_urls=[url],
    )
    assert short["contentType"] == 1
    assert short["imageList"] == [url]
    assert "title" not in short
    assert "cover" not in short
    assert "$BTC" in short["bodyTextOnly"]

    try:
        build_short_image_publish_payload(body="没有任何代币符", image_urls=[url])
        assert False, "missing cashtag should fail"
    except ValueError as e:
        assert "$" in str(e) or "代币" in str(e)

    try:
        build_article_publish_payload(
            title="太多$",
            body="见封面\n\n$BTC $ETH $BNB",
            image_urls=[url],
        )
        assert False, ">2 cashtags should fail"
    except ValueError as e:
        assert "最多" in str(e) or "2" in str(e)


def test_cashtag_budget_helpers():
    from lib.binance_square_playbook import (
        MAX_CASHTAGS,
        assert_cashtag_budget,
        compose_square_article,
        count_cashtags,
        extract_cashtags,
    )

    assert MAX_CASHTAGS == 2
    assert extract_cashtags("收$BTC后看$ETH") == ["$BTC", "$ETH"]
    assert count_cashtags("$BTC $BTC") == 2
    assert_cashtag_budget("$BTC $ETH")
    try:
        assert_cashtag_budget("$BTC $ETH $SOL")
        assert False
    except ValueError:
        pass

    art = compose_square_article(
        title="双币同向？",
        hook="4H 主计数偏多。",
        sections=[("读数", "见封面与正文配图。")],
        cta="你站哪边？",
        tags=["$BTC", "$ETH", "#波浪"],
        market="C",
    )
    assert 1 <= count_cashtags(art["body"]) <= 2
    cta_pos = art["body"].find("你站哪边")
    cash_pos = art["body"].find("$")
    assert cta_pos >= 0 and cash_pos > cta_pos


def test_us_pre_share_emits_square_fields():
    from lib.us_premarket.rank import build_us_pre_analysis
    from lib.us_premarket.share import build_us_pre_share_copy

    snap = json.loads(
        (SCRIPTS / "tests/fixtures/us_premarket/snapshot.json").read_text(encoding="utf-8")
    )
    share = build_us_pre_share_copy(build_us_pre_analysis(snap))
    assert share["playbook_square"] == "binance_square_v2"
    assert share["square_publish_mode"] == "cover+imageList"
    assert share["square_short"]
    assert share["square_title"]
    assert share["square_article"]
    assert share["square_tags"]
    assert "币安广场短文" in share["markdown"]
    assert "硅基生命001" in share["square_article"]
    from lib.binance_square_playbook import count_cashtags

    assert share["cashtags"] == ["$SPY", "$MSFT"]
    assert count_cashtags(share["square_article"]) == 2
    assert "SPY" in share["square_article"] and "MSFT" in share["square_article"]
