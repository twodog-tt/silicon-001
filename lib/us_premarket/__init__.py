"""美股盘前/盘中/盘后一页纸 · 指数/期指/ETF/Mag7。

用法::

    from lib.us_premarket.runner import run_us_pre
    result = run_us_pre()

合同 framework = ``us-premarket``。不接 A 股、不发 X。
"""
from __future__ import annotations

FRAMEWORK = "us-premarket"
MARKET = "U"

__all__ = ["FRAMEWORK", "MARKET", "run_us_pre"]


def __getattr__(name: str):
    if name == "run_us_pre":
        from lib.us_premarket.runner import run_us_pre
        return run_us_pre
    raise AttributeError(name)
