"""4H 波浪引擎最小回归."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_analyze_wave_on_synthetic_uptrend():
    from lib.crypto_structure.wave import analyze_wave

    bars = []
    px = 100.0
    for i in range(80):
        # slow uptrend with pullbacks
        px = px * (1.008 if i % 8 else 0.985)
        bars.append(
            {
                "date": f"2026-01-01 {i:02d}:00",
                "open": px * 0.999,
                "high": px * 1.004,
                "low": px * 0.996,
                "close": px,
                "volume": 1.0,
            }
        )
    w = analyze_wave(bars)
    assert w.get("engine") or w.get("primary_count") or w.get("summary_cn")
    assert "disclaimer" in w or w.get("primary_count") is not None


def test_extract_4h_bars():
    from lib.crypto_structure.overlay import extract_4h_bars

    raw = {
        "dimensions": {
            "2_kline": {
                "data": {
                    "candles_4h": [
                        {
                            "date": "2026-01-01 00:00",
                            "open": 100,
                            "high": 102,
                            "low": 99,
                            "close": 101,
                            "volume": 1,
                        }
                    ]
                }
            }
        }
    }
    bars = extract_4h_bars(raw)
    assert len(bars) == 1
    assert bars[0]["close"] == 101
