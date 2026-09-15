"""Qingting bridge to vendored human-writing check_prose.

- masks finance tokens so cashtags / section headers don't false-fail
- mode=tweet demotes colon/dash punctuation failures to warnings
- optional hard gate via QINGTING_HUMAN_WRITING_CHECK=1 on Square long posts
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

Mode = Literal["article", "tweet"]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHECK_PROSE = _REPO_ROOT / "skills" / "human-writing" / "scripts" / "check_prose.py"

# Protect finance / Square / X scaffolding from punctuation & jargon false positives
_MASK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\$[A-Za-z]{1,12}\b"), "CASHTAG"),
    (re.compile(r"#[\w\u4e00-\u9fff]{1,30}"), "HASHTAG"),
    (re.compile(r"【[^】]{1,40}】"), "SECTION"),
    (re.compile(r"Fib\s*[0-9.]+", re.I), "FIBLEVEL"),
    (re.compile(r"https?://\S+"), "URL"),
    (re.compile(r"(?:蜻蜓队长|硅基生命001)｜[^\n]+"), "SIGNATURE"),
]

_PUNCT_FAIL_RE = re.compile(r"^(中文冒号|英文冒号|破折号|连接号式破折号)")


def _load_check_prose():
    if not _CHECK_PROSE.exists():
        raise FileNotFoundError(f"missing vendored checker: {_CHECK_PROSE}")
    name = "qingting_hw_check_prose"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CHECK_PROSE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_CHECK_PROSE}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # required before exec for @dataclass
    spec.loader.exec_module(mod)
    return mod


def mask_finance_scaffolding(text: str) -> str:
    out = text or ""
    for pat, token in _MASK_PATTERNS:
        out = pat.sub(token, out)
    return out


def check_enabled() -> bool:
    return os.environ.get("QINGTING_HUMAN_WRITING_CHECK", "").strip() in (
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    )


def check_text(text: str, *, mode: Mode = "article") -> dict[str, Any]:
    """Run human-writing analyze() with Qingting masks / mode policy."""
    mod = _load_check_prose()
    masked = mask_finance_scaffolding(text)
    raw = mod.analyze(masked)
    failures = list(raw.get("failures") or [])
    warnings = list(raw.get("warnings") or [])

    if mode == "tweet":
        kept: list[str] = []
        for item in failures:
            if _PUNCT_FAIL_RE.match(item):
                warnings.append(f"[tweet宽松] {item}")
            else:
                kept.append(item)
        failures = kept

    return {
        "ok": not failures,
        "mode": mode,
        "total_han": raw.get("total_han", 0),
        "failures": failures,
        "warnings": warnings,
        "stats": raw.get("stats") or {},
        "masked": True,
        "source": "human-writing/check_prose.analyze",
    }


def assert_article_ok(text: str) -> dict[str, Any]:
    """Raise ValueError when article mode has hard failures."""
    result = check_text(text, mode="article")
    if not result["ok"]:
        detail = "; ".join(result["failures"][:6])
        raise ValueError(f"human_writing_gate 未通过: {detail}")
    return result
