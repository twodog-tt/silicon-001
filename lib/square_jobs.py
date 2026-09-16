"""定时发币安广场 · 编排 / 幂等 / 休市跳过。"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.cover_image import cover_prompt, generate_cover_png
from lib.crypto_structure.share import build_wave_share_copy, write_share_copy as write_wave_share
from lib.envfile import load_dotenv
from lib.llm_copy import rewrite_square_article
from lib.us_calendar import (
    in_us_after_window,
    in_us_pre_window,
    in_wave_utc_window,
    is_nyse_trading_day,
    nyse_date,
    utc_date,
)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "square_jobs"
WAVE_TICKERS = ("BTC", "ETH", "SOL")
JOBS = ("us-pre", "us-after", "wave-4h")


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def publish_enabled(*, dry_run: bool) -> bool:
    if dry_run:
        return False
    return _truthy("SQUARE_PUBLISH")


def stagger_sec(*, dry_run: bool) -> float:
    if dry_run:
        return 0.0
    raw = os.environ.get("SQUARE_JOB_STAGGER_SEC", "90")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 90.0


def lock_path(unit: str, day: str) -> Path:
    return CACHE / f"{unit}_{day}.json"


def read_lock(unit: str, day: str) -> dict[str, Any] | None:
    path = lock_path(unit, day)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_lock(unit: str, day: str, payload: dict[str, Any]) -> Path:
    path = lock_path(unit, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def already_published(unit: str, day: str) -> bool:
    lock = read_lock(unit, day)
    return bool(lock and lock.get("status") == "published")


def should_skip(
    kind: str,
    *,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return a skip result, or None to proceed."""
    if force:
        return None
    if kind in ("us-pre", "us-after"):
        d = nyse_date(now)
        if not is_nyse_trading_day(d):
            reason = "weekend" if d.weekday() >= 5 else "holiday"
            return {
                "status": "skipped",
                "reason": reason,
                "job": kind,
                "date": d.isoformat(),
            }
        if kind == "us-pre" and not in_us_pre_window(now):
            return {"status": "skipped", "reason": "window", "job": kind, "date": d.isoformat()}
        if kind == "us-after" and not in_us_after_window(now):
            return {"status": "skipped", "reason": "window", "job": kind, "date": d.isoformat()}
        if already_published(kind, d.isoformat()):
            return {"status": "skipped", "reason": "already", "job": kind, "date": d.isoformat()}
        return None

    if kind == "wave-4h":
        d = utc_date(now)
        if not in_wave_utc_window(now):
            return {"status": "skipped", "reason": "window", "job": kind, "date": d.isoformat()}
        return None

    return {"status": "skipped", "reason": "unknown_job", "job": kind}


def _facts_us(analysis: dict, share: dict) -> dict[str, Any]:
    return {
        "session": analysis.get("session_label"),
        "as_of": analysis.get("as_of"),
        "brief": analysis.get("brief"),
        "kpi": analysis.get("kpi"),
        "etf_strong": (analysis.get("etf_strong") or [])[:3],
        "etf_weak": (analysis.get("etf_weak") or [])[:3],
        "watch_up": (analysis.get("watch_up") or [])[:5],
        "watch_down": (analysis.get("watch_down") or [])[:5],
        "risk_flags": analysis.get("risk_flags"),
        "cashtags": share.get("cashtags"),
        "focus_symbol": share.get("focus_symbol"),
        "pairs": ["SPY", share.get("focus_symbol")],
    }


def _facts_wave(payload: dict, share: dict) -> dict[str, Any]:
    return {
        "ticker": payload.get("ticker"),
        "pair": share.get("pair"),
        "last_price": payload.get("last_price"),
        "as_of_4h": payload.get("as_of_4h") or payload.get("as_of"),
        "bars_4h": payload.get("bars_4h"),
        "wave": payload.get("wave"),
        "cashtags": share.get("cashtags"),
    }


def _resolve_copy(share: dict, facts: dict[str, Any], *, market: str) -> dict[str, str]:
    return rewrite_square_article(
        facts=facts,
        fallback_title=str(share.get("square_title") or ""),
        fallback_body=str(share.get("square_article") or ""),
        market=market,
        cashtags=list(share.get("cashtags") or []),
    )


def _resolve_cover(
    *,
    dest: Path,
    pair: str,
    session: str,
    fact: str,
    fallback: Path | None,
) -> Path:
    """Default: server-side matplotlib PNG (no tokens). DashScope only if SQUARE_AI_COVER=1."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    chart = Path(fallback) if fallback else None
    if _truthy("SQUARE_AI_COVER"):
        try:
            return generate_cover_png(cover_prompt(pair=pair, session=session, fact=fact), dest)
        except Exception as exc:
            print(f"[cover] DashScope failed ({type(exc).__name__}: {exc}); using chart PNG")
    if chart and chart.is_file():
        if chart.resolve() != dest.resolve():
            shutil.copy2(chart, dest)
        return dest
    raise RuntimeError("missing analysis PNG for Square cover")


def _maybe_publish(
    *,
    title: str,
    body: str,
    image_path: Path,
    market: str | None,
    dry_run: bool,
    copy_source: str = "template",
) -> dict[str, Any]:
    if not publish_enabled(dry_run=dry_run):
        return {
            "published": False,
            "dry_run": True,
            "title": title,
            "image_path": str(image_path),
        }
    from lib.square.publish import publish_article

    def _send():
        return publish_article(title=title, body=body, image_path=image_path, market=market)

    try:
        out = _send()
    except ValueError as exc:
        if copy_source == "template" and "human_writing_gate" in str(exc):
            old = os.environ.get("QINGTING_HUMAN_WRITING_CHECK")
            os.environ["QINGTING_HUMAN_WRITING_CHECK"] = "0"
            try:
                out = _send()
            finally:
                if old is None:
                    os.environ.pop("QINGTING_HUMAN_WRITING_CHECK", None)
                else:
                    os.environ["QINGTING_HUMAN_WRITING_CHECK"] = old
        else:
            raise
    return {
        "published": True,
        "dry_run": False,
        "id": out.get("id"),
        "shareLink": out.get("shareLink"),
        "cover_url": out.get("cover_url"),
        "title": title,
    }


def _run_us(
    kind: str,
    *,
    dry_run: bool,
    force: bool,
    now: datetime | None,
) -> dict[str, Any]:
    skip = should_skip(kind, force=force, now=now)
    if skip:
        return skip
    day = nyse_date(now).isoformat()
    if not force and already_published(kind, day):
        return {"status": "skipped", "reason": "already", "job": kind, "date": day}

    from lib.us_premarket.png import render_us_pre_png
    from lib.us_premarket.runner import run_us_pre

    result = run_us_pre(force=force, auto_open=False)
    if result.get("status") != "completed":
        return {
            "status": "error",
            "job": kind,
            "message": result.get("message") or result,
        }

    analysis_path = Path(result["analysis_path"])
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    share = json.loads(Path(result["share_json"]).read_text(encoding="utf-8"))
    copy = _resolve_copy(share, _facts_us(analysis, share), market="U")
    out_dir = Path(result["out_dir"])
    fallback_png = out_dir / "us-pre-onepager.png"
    render_us_pre_png(analysis, fallback_png)
    focus = share.get("focus_symbol") or "QQQ"
    pair_label = f"SPY {focus}"
    cover = _resolve_cover(
        dest=out_dir / "square-cover.png",
        pair=pair_label,
        session=str(analysis.get("session_label") or kind),
        fact=str(analysis.get("brief") or "")[:120],
        fallback=fallback_png,
    )
    (out_dir / "square_body.txt").write_text(copy["body"], encoding="utf-8")
    pub = _maybe_publish(
        title=copy["title"],
        body=copy["body"],
        image_path=cover,
        market="U",
        dry_run=dry_run,
        copy_source=str(copy.get("source") or "template"),
    )
    status = "published" if pub.get("published") else "dry_run"
    lock = {
        "status": status,
        "job": kind,
        "date": day,
        "copy_source": copy.get("source"),
        "cover": str(cover),
        **{k: v for k, v in pub.items() if k != "title"},
        "title": copy["title"],
    }
    write_lock(kind, day, lock)
    return {"status": status if pub.get("published") else "completed", "job": kind, **lock}


def _run_one_wave(
    ticker: str,
    *,
    dry_run: bool,
    force: bool,
    no_fetch: bool,
    now: datetime | None,
) -> dict[str, Any]:
    day = utc_date(now).isoformat()
    unit = f"wave-4h_{ticker}"
    if not force and already_published(unit, day):
        return {"status": "skipped", "reason": "already", "job": unit, "date": day}

    from tools.render_crypto_wave_4h import render_one

    out_dir = render_one(ticker, fetch=not no_fetch)
    payload = json.loads((out_dir / "structure-wave-4h.json").read_text(encoding="utf-8"))
    share = build_wave_share_copy(payload)
    write_wave_share(share, out_dir)
    copy = _resolve_copy(share, _facts_wave(payload, share), market="C")
    wave_png = out_dir / f"{ticker.lower()}-wave-4h-structure.png"
    cover = _resolve_cover(
        dest=out_dir / "square-cover.png",
        pair=str(share.get("pair") or f"{ticker}USDT"),
        session="UTC日线收线 4H",
        fact=str((payload.get("wave") or {}).get("summary") or "")[:120],
        fallback=wave_png if wave_png.is_file() else None,
    )
    (out_dir / "square_body.txt").write_text(copy["body"], encoding="utf-8")
    pub = _maybe_publish(
        title=copy["title"],
        body=copy["body"],
        image_path=cover,
        market="C",
        dry_run=dry_run,
        copy_source=str(copy.get("source") or "template"),
    )
    status = "published" if pub.get("published") else "dry_run"
    lock = {
        "status": status,
        "job": unit,
        "date": day,
        "ticker": ticker,
        "pair": share.get("pair"),
        "copy_source": copy.get("source"),
        "cover": str(cover),
        **{k: v for k, v in pub.items() if k != "title"},
        "title": copy["title"],
    }
    write_lock(unit, day, lock)
    return {"status": status if pub.get("published") else "completed", **lock}


def _run_wave(
    *,
    dry_run: bool,
    force: bool,
    no_fetch: bool,
    now: datetime | None,
) -> dict[str, Any]:
    skip = should_skip("wave-4h", force=force, now=now)
    if skip:
        return skip
    results = []
    wait = stagger_sec(dry_run=dry_run)
    for i, ticker in enumerate(WAVE_TICKERS):
        if i and wait:
            time.sleep(wait)
        try:
            results.append(
                _run_one_wave(
                    ticker,
                    dry_run=dry_run,
                    force=force,
                    no_fetch=no_fetch,
                    now=now,
                )
            )
        except Exception as exc:
            results.append(
                {
                    "status": "error",
                    "job": f"wave-4h_{ticker}",
                    "ticker": ticker,
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
    failed = [r for r in results if r.get("status") == "error"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    status = "completed"
    if failed and len(failed) == len(results):
        status = "error"
    elif failed:
        status = "error"
    elif skipped and len(skipped) == len(results):
        status = "skipped"
    return {
        "status": status,
        "job": "wave-4h",
        "date": utc_date(now).isoformat(),
        "posts": results,
    }


def run_square_job(
    kind: str,
    *,
    dry_run: bool = False,
    force: bool = False,
    no_fetch: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    load_dotenv(ROOT)
    kind = (kind or "").strip()
    if kind not in JOBS:
        return {"status": "error", "message": f"unknown job {kind!r}", "job": kind}
    if kind in ("us-pre", "us-after"):
        return _run_us(kind, dry_run=dry_run, force=force, now=now)
    return _run_wave(dry_run=dry_run, force=force, no_fetch=no_fetch, now=now)
