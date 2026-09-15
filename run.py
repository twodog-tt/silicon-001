#!/usr/bin/env python3
"""silicon-001 CLI.

  python run.py --us-pre          # 美股盘前/盘中/盘后一页纸（按美东时钟）
  python run.py --wave-4h         # BTC ETH SOL 4H 波浪图
  python run.py --wave-4h BTC     # 只跑一只
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

DEFAULT_WAVE = ["BTC", "ETH", "SOL"]


def main() -> int:
    parser = argparse.ArgumentParser(description="硅基生命001 · 一页纸 / 4H")
    parser.add_argument("--us-pre", action="store_true", help="美股盘前/盘后一页纸")
    parser.add_argument("--wave-4h", nargs="*", metavar="TICKER", help="4H 波浪（默认 BTC ETH SOL）")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--force", action="store_true", help="跳过美股 TTL 缓存")
    parser.add_argument("--no-fetch", action="store_true", help="4H 只用本地缓存 K 线")
    args = parser.parse_args()

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
