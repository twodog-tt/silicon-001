"""SQUARE_HTTPS_PROXY 只给广场用."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_square_proxy_url_empty(monkeypatch):
    monkeypatch.delenv("SQUARE_HTTPS_PROXY", raising=False)
    from lib.http_proxy import square_proxy_url

    assert square_proxy_url() is None


def test_square_proxy_url_set(monkeypatch):
    monkeypatch.setenv("SQUARE_HTTPS_PROXY", "http://127.0.0.1:8888")
    from lib.http_proxy import square_proxy_url

    assert square_proxy_url() == "http://127.0.0.1:8888"
