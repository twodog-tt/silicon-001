"""Load a local .env without adding python-dotenv."""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(root: Path | None = None) -> Path | None:
    path = (root or Path(__file__).resolve().parents[1]) / ".env"
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val
    return path
