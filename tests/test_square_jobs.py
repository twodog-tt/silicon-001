"""广场定时任务 · 休市跳过 / 交易对 / $ 预算 / dry-run。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
FIXTURE = ROOT / "tests/fixtures/us_premarket/snapshot.json"


def _wave_payload(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "timeframe": "4H",
        "as_of": "2026-09-14 20:00",
        "as_of_4h": "2026-09-14 20:00",
        "last_price": 114000 if ticker == "BTC" else (4200 if ticker == "ETH" else 180),
        "bars_4h": 80,
        "wave": {
            "summary": f"{ticker} 4H 主计数仍按调整浪读。",
            "primary": {"pattern": "corrective", "label": "ABC", "note": "R3 未过"},
            "alternate": {"pattern": "impulse_5", "label": "3", "note": "备选推动"},
            "fib": {"0.618": 110000},
            "confidence": "medium",
        },
    }


def test_nyse_holiday_and_weekend():
    from datetime import date

    from lib.us_calendar import is_nyse_trading_day

    assert not is_nyse_trading_day(date(2026, 9, 7))  # Labor Day
    assert not is_nyse_trading_day(date(2026, 9, 12))  # Saturday
    assert is_nyse_trading_day(date(2026, 9, 15))


def test_should_skip_holiday_and_window():
    from lib.square_jobs import should_skip

    holiday = datetime(2026, 9, 7, 9, 0, tzinfo=ET)
    skip = should_skip("us-pre", now=holiday)
    assert skip and skip["reason"] == "holiday"

    midday = datetime(2026, 9, 15, 10, 0, tzinfo=ET)
    skip = should_skip("us-pre", now=midday)
    assert skip and skip["reason"] == "window"

    pre = datetime(2026, 9, 15, 9, 0, tzinfo=ET)
    assert should_skip("us-pre", now=pre) is None
    assert should_skip("us-pre", force=True, now=holiday) is None

    after = datetime(2026, 9, 15, 16, 15, tzinfo=ET)
    assert should_skip("us-after", now=after) is None
    assert should_skip("us-after", now=pre)["reason"] == "window"

    utc_ok = datetime(2026, 9, 15, 0, 10, tzinfo=UTC)
    assert should_skip("wave-4h", now=utc_ok) is None
    utc_late = datetime(2026, 9, 15, 8, 0, tzinfo=UTC)
    assert should_skip("wave-4h", now=utc_late)["reason"] == "window"


def test_already_published_skips(tmp_path, monkeypatch):
    import lib.square_jobs as jobs

    monkeypatch.setattr(jobs, "CACHE", tmp_path)
    jobs.write_lock("us-pre", "2026-09-15", {"status": "published"})
    pre = datetime(2026, 9, 15, 9, 0, tzinfo=ET)
    skip = jobs.should_skip("us-pre", now=pre)
    assert skip and skip["reason"] == "already"


def test_us_share_spy_plus_strongest_watch():
    from lib.binance_square_playbook import count_cashtags
    from lib.us_premarket.rank import build_us_pre_analysis
    from lib.us_premarket.share import build_us_pre_share_copy, pick_us_cashtags

    snap = json.loads(FIXTURE.read_text(encoding="utf-8"))
    analysis = build_us_pre_analysis(snap)
    tags, focus = pick_us_cashtags(analysis)
    assert tags[0] == "$SPY"
    assert tags[1] == "$MSFT"
    assert focus["symbol"] == "MSFT"
    share = build_us_pre_share_copy(analysis)
    body = share["square_article"]
    assert "SPY" in body
    assert "MSFT" in body
    assert count_cashtags(body) == 2
    assert share["cashtags"] == ["$SPY", "$MSFT"]


def test_wave_share_one_cashtag_and_pair():
    from lib.binance_square_playbook import count_cashtags
    from lib.crypto_structure.share import build_wave_share_copy, pair_for

    for ticker, pair in (("BTC", "BTCUSDT"), ("ETH", "ETHUSDT"), ("SOL", "SOLUSDT")):
        share = build_wave_share_copy(_wave_payload(ticker))
        body = share["square_article"]
        assert pair_for(ticker) == pair
        assert pair in body
        assert f"${ticker}" in body
        assert count_cashtags(body) == 1
        assert share["cashtags"] == [f"${ticker}"]


def test_llm_copy_falls_back_without_key(monkeypatch):
    from lib.llm_copy import rewrite_square_article

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    out = rewrite_square_article(
        facts={"pair": "BTCUSDT"},
        fallback_title="t",
        fallback_body="结构图见封面\n\n$BTC",
        market="C",
        cashtags=["$BTC"],
    )
    assert out["source"] == "template"
    assert out["body"].startswith("结构图见封面")


def test_cover_uses_chart_png_by_default(tmp_path, monkeypatch):
    import lib.square_jobs as jobs

    fallback = tmp_path / "wave.png"
    fallback.write_bytes(b"png-bytes")
    dest = tmp_path / "cover.png"
    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise RuntimeError("dashscope should not run")

    monkeypatch.delenv("SQUARE_AI_COVER", raising=False)
    monkeypatch.setattr(jobs, "generate_cover_png", _boom)
    got = jobs._resolve_cover(
        dest=dest,
        pair="BTCUSDT",
        session="4H",
        fact="test",
        fallback=fallback,
    )
    assert got == dest
    assert dest.read_bytes() == b"png-bytes"
    assert called["n"] == 0


def test_us_job_dry_run_does_not_publish(tmp_path, monkeypatch):
    import lib.square_jobs as jobs
    from lib.us_premarket.rank import build_us_pre_analysis
    from lib.us_premarket.share import build_us_pre_share_copy, write_share_copy

    monkeypatch.setattr(jobs, "CACHE", tmp_path)
    monkeypatch.setattr(jobs, "load_dotenv", lambda *_a, **_k: None)
    monkeypatch.setenv("SQUARE_PUBLISH", "0")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    analysis = build_us_pre_analysis(json.loads(FIXTURE.read_text(encoding="utf-8")))
    out_dir = tmp_path / "report"
    out_dir.mkdir()
    analysis_path = out_dir / "analysis.json"
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False), encoding="utf-8")
    share = build_us_pre_share_copy(analysis)
    share_paths = write_share_copy(share, out_dir)

    def _run_us_pre(**_k):
        return {
            "status": "completed",
            "analysis_path": str(analysis_path),
            "share_json": share_paths["json"],
            "out_dir": str(out_dir),
        }

    published = {"n": 0}

    def _publish(**_k):
        published["n"] += 1
        raise AssertionError("publish_article should not run")

    monkeypatch.setattr("lib.us_premarket.runner.run_us_pre", _run_us_pre)
    monkeypatch.setattr(jobs, "generate_cover_png", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no api")))
    monkeypatch.setattr("lib.square.publish.publish_article", _publish)

    now = datetime(2026, 9, 15, 9, 0, tzinfo=ET)
    result = jobs.run_square_job("us-pre", dry_run=True, force=True, now=now)
    assert result["status"] in ("completed", "dry_run")
    assert published["n"] == 0
    assert (out_dir / "us-pre-onepager.png").is_file()
    assert (out_dir / "square_body.txt").is_file()
    assert "$SPY" in (out_dir / "square_body.txt").read_text(encoding="utf-8")


def test_wave_job_dry_run_three_posts(tmp_path, monkeypatch):
    import lib.square_jobs as jobs

    monkeypatch.setattr(jobs, "CACHE", tmp_path)
    monkeypatch.setattr(jobs, "load_dotenv", lambda *_a, **_k: None)
    monkeypatch.setenv("SQUARE_PUBLISH", "0")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SQUARE_JOB_STAGGER_SEC", "0")

    def _render_one(ticker, *, fetch=True):
        d = tmp_path / ticker
        d.mkdir(exist_ok=True)
        payload = _wave_payload(ticker)
        (d / "structure-wave-4h.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        png = d / f"{ticker.lower()}-wave-4h-structure.png"
        png.write_bytes(b"png")
        return d

    published = {"n": 0}

    def _publish(**_k):
        published["n"] += 1
        raise AssertionError("should not publish")

    monkeypatch.setattr("tools.render_crypto_wave_4h.render_one", _render_one)
    monkeypatch.setattr(jobs, "generate_cover_png", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no api")))
    monkeypatch.setattr("lib.square.publish.publish_article", _publish)

    now = datetime(2026, 9, 15, 0, 10, tzinfo=UTC)
    result = jobs.run_square_job("wave-4h", dry_run=True, force=True, now=now)
    assert result["status"] == "completed"
    assert len(result["posts"]) == 3
    assert published["n"] == 0
    pairs = {p["pair"] for p in result["posts"]}
    assert pairs == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
