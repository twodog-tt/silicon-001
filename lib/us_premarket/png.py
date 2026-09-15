"""美股一页纸 PNG（无浏览器，给广场封面失败时回退）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from lib.export_watermark import apply_matplotlib_watermark


def _setup_font() -> None:
    for fp in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        if Path(fp).exists():
            try:
                font_manager.fontManager.addfont(fp)
                prop = font_manager.FontProperties(fname=fp)
                plt.rcParams["font.family"] = prop.get_name()
            except Exception:
                plt.rcParams["font.family"] = "sans-serif"
            break
    plt.rcParams["axes.unicode_minus"] = False


def _pct(v: Any) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.2f}%"


def render_us_pre_png(analysis: dict, dest: Path) -> Path:
    _setup_font()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    sess = analysis.get("session_label") or "盘前"
    kpi = analysis.get("kpi") or {}
    etf_s = analysis.get("etf_strong") or []
    w_up = analysis.get("watch_up") or []
    brief = str(analysis.get("brief") or "")[:160]
    as_of = str(analysis.get("as_of") or "")

    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=140)
    fig.patch.set_facecolor("#f4f2ee")
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(0.03, 0.93, "硅基生命001 · 美股一页纸", fontsize=11, color="#5c6670", va="top")
    ax.text(0.03, 0.86, f"美股{sess}", fontsize=22, fontweight="600", color="#0f1720", va="top")
    ax.text(0.03, 0.78, as_of, fontsize=10, color="#5c6670", va="top")
    ax.text(0.03, 0.70, brief or "—", fontsize=11, color="#1a1512", va="top", wrap=True)

    cells = [
        ("ES", _pct(kpi.get("es_change_pct"))),
        ("NQ", _pct(kpi.get("nq_change_pct"))),
        ("VIX", f"{kpi.get('vix') or '—'}"),
        ("强板块", (etf_s[0].get("symbol") if etf_s else "—")),
        ("强观察", (w_up[0].get("symbol") if w_up else "—")),
        ("涨跌", _pct((w_up[0] or {}).get("change_pct") if w_up else None)),
    ]
    x0 = 0.03
    for i, (lab, val) in enumerate(cells):
        x = x0 + (i % 3) * 0.31
        y = 0.42 if i < 3 else 0.22
        ax.text(x, y + 0.08, lab, fontsize=9, color="#5c6670", va="bottom")
        ax.text(x, y, str(val), fontsize=16, fontweight="600", color="#0f1720", va="bottom")

    ax.text(0.03, 0.06, "非实时快照 · 不构成投资建议", fontsize=9, color="#5c6670")
    apply_matplotlib_watermark(fig)
    fig.savefig(dest, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return dest
