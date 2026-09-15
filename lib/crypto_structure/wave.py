"""Elliott Wave 日线子集 — 推动浪三硬规则可回溯至 Frost & Prechter.

一级来源见同目录 SOURCES.md：
- Elliott Wave Principle：R1/R2/R3 推动浪硬规则
- Fibonacci 指南位（实践共识）
- 主计数 + 备选并存

本文件实现摆动枚举 + 规则打分，不是完整波浪工作站。
"""
from __future__ import annotations

from typing import Any


THEORY_REFS = [
    {
        "id": "ew-r1",
        "source": "Frost & Prechter, Elliott Wave Principle",
        "rule": "R1：Wave 2 永不越过 Wave 1 起点（上涨推动不过起点之下；下跌推动不过起点之上）。",
    },
    {
        "id": "ew-r2",
        "source": "Frost & Prechter, Elliott Wave Principle",
        "rule": "R2：Wave 3 永远不是 Wave 1/3/5 中最短的一浪。",
    },
    {
        "id": "ew-r3",
        "source": "Frost & Prechter, Elliott Wave Principle",
        "rule": "R3：标准推动中 Wave 4 不进入 Wave 1 价格区间（斜三角例外，本实现单独标记）。",
    },
    {
        "id": "ew-fib",
        "source": "Elliott 实践指南（Fib 回撤/延伸）",
        "rule": "常用 0.382/0.5/0.618/1.0/1.618 等；非硬规则，作结构观察位。",
    },
    {
        "id": "ew-alternate",
        "source": "Elliott 实践共识",
        "rule": "数浪不唯一；须同时保留备选计数并用价格行为淘汰。",
    },
]


def _swing_points(
    highs: list[float], lows: list[float], closes: list[float], order: int = 3,
) -> list[dict]:
    """Fractal swings: extremum vs `order` bars each side."""
    n = len(closes)
    pts: list[dict] = []
    for i in range(order, n - order):
        window_h = highs[i - order:i + order + 1]
        window_l = lows[i - order:i + order + 1]
        if highs[i] == max(window_h) and highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            pts.append({"i": i, "kind": "high", "price": highs[i]})
        if lows[i] == min(window_l) and lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            pts.append({"i": i, "kind": "low", "price": lows[i]})
    cleaned: list[dict] = []
    for p in pts:
        if not cleaned:
            cleaned.append(p)
            continue
        if p["kind"] == cleaned[-1]["kind"]:
            if p["kind"] == "high" and p["price"] >= cleaned[-1]["price"]:
                cleaned[-1] = p
            elif p["kind"] == "low" and p["price"] <= cleaned[-1]["price"]:
                cleaned[-1] = p
        else:
            cleaned.append(p)
    return cleaned


def _px_round(x: float, *, ref: float | None = None) -> float:
    scale = abs(ref if ref is not None else x)
    nd = 4 if scale < 1 else 2
    return round(float(x), nd)


def _fib_levels(a: float, b: float) -> dict[str, float]:
    """Retracement/extension from swing a → b (指南位)."""
    diff = b - a
    ref = max(abs(a), abs(b))
    return {
        "0.0": _px_round(b, ref=ref),
        "0.236": _px_round(b - 0.236 * diff, ref=ref),
        "0.382": _px_round(b - 0.382 * diff, ref=ref),
        "0.5": _px_round(b - 0.5 * diff, ref=ref),
        "0.618": _px_round(b - 0.618 * diff, ref=ref),
        "0.786": _px_round(b - 0.786 * diff, ref=ref),
        "1.0": _px_round(a, ref=ref),
        "1.272": _px_round(b + 0.272 * diff, ref=ref),
        "1.618": _px_round(b + 0.618 * diff, ref=ref),
    }


def _wave_len(p0: float, p1: float) -> float:
    return abs(p1 - p0)


def _validate_impulse(pts: list[dict], bullish: bool) -> dict[str, Any]:
    """pts: 6 alternating swings forming W0..W5 endpoints (5 waves).

    Layout for bullish: L H L H L H  → starts at low (wave1 start)
    or H L H L H L for bearish start at high.
    We pass exactly 6 points that alternate.
    """
    if len(pts) != 6:
        return {"ok": False, "violations": ["need_6_pivots"], "rules": {}}

    kinds = [p["kind"] for p in pts]
    prices = [p["price"] for p in pts]

    # Expect alternating
    for a, b in zip(kinds, kinds[1:]):
        if a == b:
            return {"ok": False, "violations": ["non_alternating"], "rules": {}}

    if bullish:
        # start low: LHLHLH
        if kinds[0] != "low" or kinds[-1] != "high":
            return {"ok": False, "violations": ["bullish_layout"], "rules": {}}
        w1 = _wave_len(prices[0], prices[1])
        w2 = _wave_len(prices[1], prices[2])
        w3 = _wave_len(prices[2], prices[3])
        w4 = _wave_len(prices[3], prices[4])
        w5 = _wave_len(prices[4], prices[5])
        # R1: wave2 low >= wave1 start
        r1 = prices[2] >= prices[0]
        # R3: wave4 low >= wave1 high
        r3 = prices[4] >= prices[1]
        diagonal = (not r3) and prices[4] < prices[1]
    else:
        # start high: HLHLHL
        if kinds[0] != "high" or kinds[-1] != "low":
            return {"ok": False, "violations": ["bearish_layout"], "rules": {}}
        w1 = _wave_len(prices[0], prices[1])
        w2 = _wave_len(prices[1], prices[2])
        w3 = _wave_len(prices[2], prices[3])
        w4 = _wave_len(prices[3], prices[4])
        w5 = _wave_len(prices[4], prices[5])
        r1 = prices[2] <= prices[0]
        r3 = prices[4] <= prices[1]
        diagonal = (not r3) and prices[4] > prices[1]

    # R2: wave3 not shortest
    r2 = w3 >= w1 or w3 >= w5  # not strictly shorter than both → not the unique shortest
    # Frost: wave 3 never the shortest — equivalent to not (w3 < w1 and w3 < w5)
    r2 = not (w3 < w1 and w3 < w5)

    violations = []
    if not r1:
        violations.append("R1_wave2_beyond_wave1_start")
    if not r2:
        violations.append("R2_wave3_shortest")
    if not r3 and not diagonal:
        violations.append("R3_wave4_overlaps_wave1")

    ok = r1 and r2 and (r3 or diagonal)
    score = 0
    score += 3 if r1 else 0
    score += 3 if r2 else 0
    score += 3 if r3 else (1 if diagonal else 0)
    # Fib guideline: w3 often ~1.618 w1
    if w1 > 0:
        ratio = w3 / w1
        if 1.2 <= ratio <= 2.2:
            score += 1
    if w5 > 0 and w1 > 0 and 0.7 <= w5 / w1 <= 1.3:
        score += 1

    return {
        "ok": ok,
        "violations": violations,
        "diagonal_candidate": bool(diagonal and r1 and r2),
        "rules": {"R1": r1, "R2": r2, "R3": r3},
        "lengths": {
            "w1": _px_round(w1, ref=max(abs(prices[0]), 1e-9)),
            "w2": _px_round(w2, ref=max(abs(prices[0]), 1e-9)),
            "w3": _px_round(w3, ref=max(abs(prices[0]), 1e-9)),
            "w4": _px_round(w4, ref=max(abs(prices[0]), 1e-9)),
            "w5": _px_round(w5, ref=max(abs(prices[0]), 1e-9)),
        },
        "score": score,
        "bullish": bullish,
    }


def _validate_abc(pts: list[dict]) -> dict[str, Any]:
    """3-swing corrective: 4 pivots A-B-C (start + 3 legs) → need 4 points."""
    if len(pts) != 4:
        return {"ok": False, "score": 0, "violations": ["need_4_pivots"]}
    kinds = [p["kind"] for p in pts]
    for a, b in zip(kinds, kinds[1:]):
        if a == b:
            return {"ok": False, "score": 0, "violations": ["non_alternating"]}
    # shallow structure score: C often near A or beyond
    score = 2
    return {"ok": True, "score": score, "violations": [], "pattern": "corrective_abc"}


def _enumerate_counts(swings: list[dict]) -> tuple[dict, dict]:
    """Score impulse windows of 6 pivots and ABC windows of 4; pick primary/alternate."""
    if len(swings) < 4:
        return (
            {"label": "未完成", "pattern": "暂无", "note": "摆动点不足", "waves": [], "score": 0, "rules_checked": {}},
            {"label": "等待", "pattern": "暂无", "note": "备选暂缓", "waves": [], "score": 0, "rules_checked": {}},
        )

    impulse_hits: list[dict] = []
    for i in range(0, len(swings) - 5):
        window = swings[i:i + 6]
        for bullish in (True, False):
            v = _validate_impulse(window, bullish=bullish)
            if v.get("ok") or v.get("diagonal_candidate"):
                impulse_hits.append({
                    "window": window,
                    "validation": v,
                    "score": v["score"] + (2 if v.get("ok") else 0),
                    "pattern": "impulse_5" if v.get("ok") and not v.get("diagonal_candidate") else "diagonal_or_impulse",
                    "label": ("推动浪上行" if bullish else "推动浪下行")
                    + ("（斜三角候选）" if v.get("diagonal_candidate") and not v.get("rules", {}).get("R3") else ""),
                })

    abc_hits: list[dict] = []
    for i in range(0, len(swings) - 3):
        window = swings[i:i + 4]
        v = _validate_abc(window)
        if v.get("ok"):
            net = window[-1]["price"] - window[0]["price"]
            abc_hits.append({
                "window": window,
                "validation": v,
                "score": v["score"],
                "pattern": "corrective_abc",
                "label": "ABC 调整" if abs(net) / max(abs(window[0]["price"]), 1e-9) < 0.15 else "调整浪偏离",
            })

    # Prefer recent windows
    def recency_bonus(hit: dict) -> float:
        end_i = hit["window"][-1]["i"]
        return end_i / 1000.0

    impulse_hits.sort(key=lambda h: h["score"] + recency_bonus(h), reverse=True)
    abc_hits.sort(key=lambda h: h["score"] + recency_bonus(h), reverse=True)

    def pack(hit: dict | None, fallback_swings: list[dict], role: str) -> dict:
        if not hit:
            recent = fallback_swings[-6:] if len(fallback_swings) >= 4 else fallback_swings
            return {
                "label": "启发式整理" if role == "primary" else "等待确认",
                "pattern": "corrective_abc" if role == "primary" else "alternate_pending",
                "note": "无窗口同时满足推动浪三硬规则；退回近端摆动描述（非唯一）。",
                "waves": [{"i": p["i"], "kind": p["kind"], "price": _px_round(p["price"])} for p in recent],
                "score": 0,
                "rules_checked": {},
                "violations": ["no_valid_impulse_window"],
            }
        v = hit["validation"]
        waves = [{"i": p["i"], "kind": p["kind"], "price": _px_round(p["price"])} for p in hit["window"]]
        rules = v.get("rules") or {}
        note_bits = []
        if rules:
            note_bits.append(
                f"R1={'通过' if rules.get('R1') else '违反'} · "
                f"R2={'通过' if rules.get('R2') else '违反'} · "
                f"R3={'通过' if rules.get('R3') else '违反/斜三角候选'}"
            )
        if v.get("violations"):
            note_bits.append("违规: " + ",".join(v["violations"]))
        if v.get("lengths"):
            L = v["lengths"]
            note_bits.append(f"浪长 w1={L['w1']} w3={L['w3']} w5={L['w5']}")
        return {
            "label": hit["label"],
            "pattern": hit["pattern"],
            "note": "；".join(note_bits) if note_bits else hit.get("label", ""),
            "waves": waves,
            "score": hit["score"],
            "rules_checked": rules,
            "violations": v.get("violations") or [],
            "lengths": v.get("lengths"),
            "diagonal_candidate": v.get("diagonal_candidate", False),
            "bias": "bullish" if v.get("bullish") else "bearish" if "bullish" in v else None,
        }

    primary_hit = impulse_hits[0] if impulse_hits else (abc_hits[0] if abc_hits else None)
    # alternate: next different pattern family
    alternate_hit = None
    if primary_hit and impulse_hits:
        # prefer abc as alternate when primary is impulse
        alternate_hit = abc_hits[0] if abc_hits else (impulse_hits[1] if len(impulse_hits) > 1 else None)
    elif primary_hit and abc_hits:
        alternate_hit = impulse_hits[0] if impulse_hits else (abc_hits[1] if len(abc_hits) > 1 else None)

    primary = pack(primary_hit, swings, "primary")
    alternate = pack(alternate_hit, swings, "alternate")
    # Ensure alternate note mentions 备选原则
    if alternate.get("note"):
        alternate["note"] = "备选计数 · " + alternate["note"]
    else:
        alternate["note"] = "备选计数 · 数浪不唯一，保留对照。"
    return primary, alternate


_CONF_CN = {"low": "低", "medium": "中", "high": "高"}


def analyze_wave(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Elliott daily subset with R1/R2/R3 validation where possible."""
    refs = list(THEORY_REFS)
    if not bars or len(bars) < 40:
        msg = "波浪结构不可用 — 日线不足（需≥40）。"
        return {
            "theory": "wave",
            "ok": False,
            "confidence": "low",
            "primary_count": {"label": "暂无", "pattern": "暂无", "note": "需要 ≥40 根日线", "waves": []},
            "alternate_count": {"label": "暂无", "pattern": "暂无", "note": "", "waves": []},
            "fib_levels": {},
            "summary_en": msg,
            "summary_cn": msg,
            "structure_price": None,
            "theory_refs": refs,
            "engine": "elliott-r123-v2",
        }

    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    closes = [float(b["close"]) for b in bars]
    last_price = closes[-1]

    swings = _swing_points(highs, lows, closes, order=3)
    primary, alternate = _enumerate_counts(swings)

    fib: dict[str, float] = {}
    structure_price = None
    # Fib from primary window last swing pair, else last two swings
    src_waves = primary.get("waves") or []
    if len(src_waves) >= 2:
        a, b = src_waves[-2], src_waves[-1]
        fib = _fib_levels(a["price"], b["price"])
        structure_price = fib.get("0.618")
    elif len(swings) >= 2:
        a, b = swings[-2], swings[-1]
        fib = _fib_levels(a["price"], b["price"])
        structure_price = fib.get("0.618")

    conf = "low"
    if primary.get("score", 0) >= 6 and primary.get("rules_checked"):
        conf = "medium"
    if primary.get("pattern", "").startswith("impulse") and not primary.get("violations"):
        conf = "medium"

    primary["vs_spot"] = (
        "above_last_swing" if last_price >= (src_waves[-1]["price"] if src_waves else last_price)
        else "below_last_swing"
    )

    summary = (
        f"日线波浪：主计数={primary.get('pattern')}（{primary.get('label')}）；"
        f"备选={alternate.get('pattern')}（{alternate.get('label')}）。"
        f"摆动点={len(swings)}。置信度{_CONF_CN.get(conf, conf)}。"
        f"硬规则来源：Frost/Prechter R1/R2/R3；Fib 为指南位。数浪不唯一。"
    )

    return {
        "theory": "wave",
        "ok": True,
        "confidence": conf,
        "swing_count": len(swings),
        "primary_count": primary,
        "alternate_count": alternate,
        "fib_levels": fib,
        "summary_en": summary,
        "summary_cn": summary,
        "structure_price": structure_price,
        "last_price": _px_round(last_price),
        "theory_refs": refs,
        "engine": "elliott-r123-v2",
        "disclaimer": (
            "Elliott 推动浪三硬规则校验 + 摆动窗口打分 + Fib 指南位；备选并存。"
            "未覆盖全部波浪指南与多周期嵌套。不构成投资建议。"
        ),
    }
