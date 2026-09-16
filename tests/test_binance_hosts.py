"""币安行情 host 顺序 · 国内优先 vision."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_spot_bases_prefer_vision(monkeypatch):
    monkeypatch.delenv("BINANCE_API_BASE", raising=False)
    from lib.crypto_signals import binance_spot_bases

    bases = binance_spot_bases()
    assert bases[0] == "https://data-api.binance.vision"
    assert "https://api.binance.com" in bases


def test_spot_bases_env_override(monkeypatch):
    monkeypatch.setenv("BINANCE_API_BASE", "https://example.test")
    from lib.crypto_signals import binance_spot_bases

    assert binance_spot_bases()[0] == "https://example.test"


def test_default_market_source_is_binance(monkeypatch):
    monkeypatch.delenv("QINGTING_CRYPTO_MARKET_SOURCE", raising=False)
    from lib.crypto_signals import crypto_market_source_pref

    assert crypto_market_source_pref() == "binance"
