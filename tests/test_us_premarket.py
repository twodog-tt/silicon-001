"""美股盘前一页纸 · 离线 fixture 回归."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

FIXTURE = Path(__file__).parent / "fixtures" / "us_premarket" / "snapshot.json"
ET = ZoneInfo("America/New_York")


def _load_snap() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_contract():
    snap = _load_snap()
    assert snap["framework"] == "us-premarket"
    assert snap["market"] == "U"
    assert snap["as_of"]
    assert len(snap.get("indices") or []) >= 2
    assert len(snap.get("etfs") or []) >= 3
    assert len(snap.get("watchlist") or []) >= 5


def test_session_labels_by_et_clock():
    from lib.us_premarket.fetch import resolve_us_session

    pre = resolve_us_session(datetime(2026, 8, 3, 8, 0, tzinfo=ET))
    assert pre["session"] == "premarket" and pre["session_label"] == "盘前"
    reg = resolve_us_session(datetime(2026, 8, 3, 10, 0, tzinfo=ET))
    assert reg["session"] == "regular" and reg["session_label"] == "盘中"
    aft = resolve_us_session(datetime(2026, 8, 3, 17, 0, tzinfo=ET))
    assert aft["session"] == "afterhours" and aft["session_label"] == "盘后"


def test_build_analysis_ranks_etf():
    from lib.us_premarket.rank import build_us_pre_analysis

    a = build_us_pre_analysis(_load_snap())
    assert a["framework"] == "us-premarket"
    assert a["etf_strong"]
    # 弱势侧若有数据，必须全部为负
    for row in a.get("etf_weak") or []:
        assert float(row["change_pct"]) < 0
    for row in a.get("watch_down") or []:
        assert float(row["change_pct"]) < 0
    assert a["brief"]
    assert "昨收" in a["brief"] or "ES" in a["brief"] or "标普" in a["brief"]
    assert a["kpi"]["watch_total"] >= 1
    assert "watch_grid" in a


def test_render_has_snapshot_badge():
    from lib.us_premarket.rank import build_us_pre_analysis
    from lib.us_premarket.render import render_us_pre_onepager

    html = render_us_pre_onepager(build_us_pre_analysis(_load_snap()))
    assert "硅基生命001" in html
    assert "快照 · 非实时" in html
    assert "us-premarket" in html
    assert "Mag7" in html or "观察池" in html
    assert "昨收" in html or "隔夜" in html


def test_runner_offline(tmp_path, monkeypatch):
    from lib.us_premarket import runner as us_runner
    from lib.us_premarket.rank import build_us_pre_analysis

    analysis = build_us_pre_analysis(_load_snap())
    monkeypatch.setattr(us_runner, "SCRIPTS_DIR", tmp_path)
    result = us_runner.run_us_pre(analysis_override=analysis, auto_open=False)
    assert result["status"] == "completed"
    assert Path(result["report_path"]).exists()
    assert "快照" in Path(result["report_path"]).read_text(encoding="utf-8")
