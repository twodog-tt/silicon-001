#!/usr/bin/env python3
"""silicon-001 CLI.

  python run.py --us-pre          # 美股盘前/盘中/盘后一页纸（按美东时钟）
  python run.py --wave-4h         # BTC ETH SOL 4H 波浪图
  python run.py --wave-4h BTC     # 只跑一只
  python run.py --square-job us-pre --dry-run
  python run.py --square-job us-after
  python run.py --square-job wave-4h
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

from lib.envfile import load_dotenv  # noqa: E402

load_dotenv(ROOT)

DEFAULT_WAVE = ["BTC", "ETH", "SOL"]


def main() -> int:
    parser = argparse.ArgumentParser(description="硅基生命001 · 一页纸 / 4H / 广场定时")
    parser.add_argument("--us-pre", action="store_true", help="美股盘前/盘后一页纸")
    parser.add_argument("--wave-4h", nargs="*", metavar="TICKER", help="4H 波浪（默认 BTC ETH SOL）")
    parser.add_argument(
        "--square-job",
        choices=["us-pre", "us-after", "wave-4h"],
        help="定时发币安广场（需 SQUARE_PUBLISH=1 才真发）",
    )
    parser.add_argument("--dry-run", action="store_true", help="广场任务只出稿，不调用 OpenAPI")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--force", action="store_true", help="跳过美股 TTL / 休市窗 / 幂等锁")
    parser.add_argument("--no-fetch", action="store_true", help="4H 只用本地缓存 K 线")
    args = parser.parse_args()

    if args.square_job:
        from lib.square_jobs import run_square_job

        result = run_square_job(
            args.square_job,
            dry_run=args.dry_run,
            force=args.force,
            no_fetch=args.no_fetch,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        status = result.get("status")
        return 0 if status in ("completed", "skipped", "dry_run") else 1

    if not args.us_pre and args.wave_4h is None:
        parser.print_help()
        return 2

    if args.us_pre:
        from lib.us_premarket.runner import run_us_pre

        result = run_us_pre(force=args.force, auto_open=not args.no_browser)
        if result.get("status") != "completed":
            print(result.get("message") or result)
            return 1
        print(result.get("report_path"))

    if args.wave_4h is not None:
        from tools.render_crypto_wave_4h import main as wave_main

        tickers = [t.upper() for t in args.wave_4h] or DEFAULT_WAVE
        argv = tickers + (["--no-fetch"] if args.no_fetch else [])
        wave_main(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
