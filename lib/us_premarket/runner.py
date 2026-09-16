"""美股盘前一页纸 runner."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.us_premarket.fetch import fetch_us_pre_snapshot
from lib.us_premarket.rank import build_us_pre_analysis
from lib.us_premarket.render import render_us_pre_onepager
from lib.us_premarket.share import build_us_pre_share_copy, write_share_copy

SCRIPTS_DIR = Path(__file__).resolve().parents[2]


def run_us_pre(
    *,
    force: bool = False,
    auto_open: bool = True,
    analysis_override: dict | None = None,
    snapshot_override: dict | None = None,
) -> dict[str, Any]:
    t0 = time.time()
    print()
    print("━" * 60)
    print("美股一页纸 · framework=us-premarket · 硅基生命001")
    print("━" * 60)

    if analysis_override is not None:
        analysis = analysis_override
    else:
        snap = (
            snapshot_override
            if snapshot_override is not None
            else fetch_us_pre_snapshot(force=force)
        )
        has = (snap.get("indices") or snap.get("etfs") or snap.get("watchlist"))
        if not has:
            return {
                "status": "insufficient_data",
                "message": "美股指数/ETF/观察池均未取到 · 检查新浪/腾讯行情",
                "runtime_sec": int(time.time() - t0),
            }
        print(f"📡 as_of={snap.get('as_of')} · ET={snap.get('as_of_et')} · {snap.get('session_label')}")
        analysis = build_us_pre_analysis(snap)

    if not (
        analysis.get("indices")
        or analysis.get("etf_strong")
        or analysis.get("watchlist")
    ):
        return {
            "status": "insufficient_data",
            "message": "分析层无可用数据",
            "runtime_sec": int(time.time() - t0),
        }

    date = datetime.now().strftime("%Y%m%d")
    stamp = datetime.now().strftime("%H%M")
    out_dir = SCRIPTS_DIR / "reports" / f"us_pre_{date}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    analysis_path = out_dir / "analysis.json"
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    html = render_us_pre_onepager(analysis)
    html_path = out_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")

    share = build_us_pre_share_copy(analysis)
    share_paths = write_share_copy(share, out_dir)

    cache_dir = SCRIPTS_DIR / ".cache" / "us_premarket" / "latest"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "analysis.json").write_text(
        analysis_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (cache_dir / "share_copy.json").write_text(
        json.dumps(share, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    dt = int(time.time() - t0)
    label = analysis.get("session_label") or "盘前"
    print(f"\n━━━ 美股{label}一页纸完成 · {dt}s ━━━")
    print(f"📄 HTML: {html_path}")
    print(f"📝 share: {share_paths.get('md')}")
    print(f"📦 analysis: {analysis_path}")

    if auto_open and not os.environ.get("UZI_NO_AUTO_OPEN"):
        try:
            import webbrowser

            webbrowser.open(html_path.as_uri())
        except Exception:
            pass

    return {
        "status": "completed",
        "market": "U",
        "session": analysis.get("session"),
        "session_label": label,
        "report_path": str(html_path),
        "analysis_path": str(analysis_path),
        "share_path": share_paths.get("md"),
        "share_json": share_paths.get("json"),
        "out_dir": str(out_dir),
        "as_of": analysis.get("as_of"),
        "runtime_sec": dt,
    }
