"""Author watermark for PNG exports (matplotlib).

Identity line (sole author attribution):
  硅基生命001
"""
from __future__ import annotations

from typing import Any

AUTHOR_WATERMARK = "硅基生命001"


def js_apply_watermark_fn() -> str:
    """Return a browser-side ``applyAuthorWatermark(canvas)`` function body.

    Draws a bottom-right attribution bar onto the captured canvas before download.
    """
    # Escape for embedding inside JS string literal
    text = AUTHOR_WATERMARK.replace("\\", "\\\\").replace('"', '\\"')
    return f"""
  var AUTHOR_WATERMARK = "{text}";
  function applyAuthorWatermark(canvas) {{
    if (!canvas || !canvas.getContext) return canvas;
    var ctx = canvas.getContext("2d");
    if (!ctx) return canvas;
    var w = canvas.width, h = canvas.height;
    if (!w || !h) return canvas;
    var pad = Math.max(10, Math.round(w * 0.012));
    var fontSize = Math.max(12, Math.min(22, Math.round(w * 0.013)));
    ctx.save();
    ctx.font = "600 " + fontSize + "px 'PingFang SC','Hiragino Sans GB','Noto Sans SC','Microsoft YaHei',sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    var metrics = ctx.measureText(AUTHOR_WATERMARK);
    var tw = metrics.width;
    var barH = Math.round(fontSize * 1.85);
    var barW = tw + pad * 2;
    var x0 = Math.max(0, w - barW - pad * 0.4);
    var y0 = h - barH - pad * 0.35;
    ctx.fillStyle = "rgba(12, 16, 22, 0.62)";
    ctx.fillRect(x0, y0, barW, barH);
    ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
    ctx.fillText(AUTHOR_WATERMARK, w - pad, h - pad * 0.55);
    ctx.restore();
    return canvas;
  }}
"""


def apply_matplotlib_watermark(fig: Any, *, color: str = "#5c6670", alpha: float = 0.85) -> None:
    """Stamp author watermark on a matplotlib Figure (bottom-right)."""
    try:
        fig.text(
            0.995,
            0.008,
            AUTHOR_WATERMARK,
            ha="right",
            va="bottom",
            fontsize=7.5,
            color=color,
            alpha=alpha,
            fontweight="500",
            transform=fig.transFigure,
            clip_on=False,
            zorder=100,
        )
    except Exception:
        pass
