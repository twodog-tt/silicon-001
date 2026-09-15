#!/usr/bin/env python3
"""发布币安广场长文（cover+imageList）。

  PYTHONPATH=. python tools/square_publish.py \\
    --title '标题' --body-file draft.txt --image cover.png --market U
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.square.publish import publish_article  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Publish Binance Square long article")
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True, type=Path)
    p.add_argument("--image", required=True, type=Path)
    p.add_argument("--market", default=None, help="U or C")
    args = p.parse_args(argv)
    body = args.body_file.read_text(encoding="utf-8").strip()
    out = publish_article(
        title=args.title,
        body=body,
        image_path=args.image,
        market=args.market,
    )
    print(json.dumps(
        {"id": out.get("id"), "shareLink": out.get("shareLink"), "mode": out.get("square_publish_mode")},
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
