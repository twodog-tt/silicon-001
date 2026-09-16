"""新浪/腾讯美股报价解析 · 不打真实网络."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.us_premarket.cn_quotes import (  # noqa: E402
    parse_sina_gb,
    parse_sina_hf,
    parse_sina_int,
    parse_sina_payload,
    parse_tencent_us,
    sina_code_for,
)


def test_sina_code_map():
    assert sina_code_for("SPY") == "gb_spy"
    assert sina_code_for("ES=F") == "hf_ES"
    assert sina_code_for("^GSPC") == "int_sp500"
    assert sina_code_for("^VIX") == "hf_VX"
    assert sina_code_for("^TNX") is None


def test_parse_sina_gb_spy():
    body = (
        "SPDR标普500 ETF,760.8800,-0.45,2026-09-15 09:40:35,-3.4100,759.0000,"
        "763.5200,757.9300,779.3700,627.3770,43992428,38964488,802600660422,0.00,--,"
        "0.00,0.00,0.00,0.00,1054832116,0,761.1598,0.04,0.28,Sep 14 07:59PM EDT,"
        "Sep 14 04:00PM EDT,764.2900,4391700"
    )
    q = parse_sina_gb(body, "SPY", prefer_pre=True)
    assert q is not None
    assert q["price"] == 760.88
    assert q["change_pct"] == -0.45
    assert q["previous_close"] == 764.29
    assert q["quote_session"] == "premarket"
    assert q["source"] == "sina_gb"


def test_parse_sina_int_and_hf():
    dji = parse_sina_int("道琼斯,46247.29,299.97,0.65", "^DJI", prefer_pre=True)
    assert dji is not None
    assert dji["price"] == 46247.29
    assert dji["change_pct"] == 0.65
    assert dji["quote_session"] == "prior_close"

    es = parse_sina_hf(
        "7588.960,,7589.000,7589.250,7633.250,7588.500,15:48:05,7625.000,7631.000,"
        "0,6,4,2026-09-15,标普500指数期货,0",
        "ES=F",
    )
    assert es is not None
    assert es["price"] == 7588.96
    assert es["previous_close"] == 7625.0
    assert abs(es["change_pct"] - ((7588.96 / 7625.0 - 1) * 100)) < 1e-9
    assert es["quote_session"] == "overnight"


def test_parse_sina_payload_skips_empty():
    text = (
        'var hq_str_gb_spy="SPDR,760.8800,-0.45,t,-3.4,1,1,1,1,1,1,1,1,0,--,0,0,0,0,1,0,1,0,0,a,b,764.2900";\n'
        'var hq_str_int_vix="";\n'
    )
    out = parse_sina_payload(text, {"gb_spy": "SPY", "int_vix": "^VIX"}, prefer_pre=True)
    assert "SPY" in out
    assert "^VIX" not in out


def test_parse_tencent_us_spy():
    body = (
        "200~标普500指数ETF-SPDR~SPY.AM~760.88~764.29~759.00~43992428~0~0~761.12"
        "~160~0~0~0~0~0~0~0~0~761.16~480~0~0~0~0~0~0~0~0~~2026-09-14 16:00:01"
        "~-3.41~-0.45~763.52~757.93~USD"
    )
    q = parse_tencent_us(body, "SPY", prefer_pre=True)
    assert q is not None
    assert q["price"] == 760.88
    assert abs(q["change_pct"] - ((760.88 / 764.29 - 1) * 100)) < 1e-6
    assert q["source"] == "tencent"
