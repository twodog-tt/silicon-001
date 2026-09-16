"""DeepSeek 把当次分析 JSON 改写成广场长文。失败则交回模板。"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from lib.binance_square_playbook import (
    assert_cashtag_budget,
    assert_cashtag_present_if_required,
    count_cashtags,
    strip_markdown_images,
    validate_square_text,
)
from lib.http_proxy import urlopen_direct

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-flash"
AUTHOR = "硅基生命001"

_SYSTEM = """你是硅基生命001，把给定 JSON 写成一篇币安广场长文。

硬规则
1. 只输出 JSON 对象，键为 title 与 body，不要 markdown 围栏。
2. 数字、价位、涨跌、主计数、备选、Fib 只能来自输入 JSON，禁止编造。
3. 正文必须出现交易对明文（如 BTCUSDT 或 SPY），cashtag 只能使用 JSON 里的 cashtags 列表，每个最多一次，全文 $ 出现次数不超过 2。
4. cashtag 放在 CTA 之后、签名之前，不要写进钩子。
5. 禁止微信、电报、私聊带单、稳赚话术。
6. 禁止中文冒号、英文冒号、破折号。时间写成 20时35分 这种。
7. 禁止「不是……而是……」「说白了」「赋能」等模型腔。
8. 结构：钩子 → 证据 → 怎么读盘 → CTA → $/# 标签 → 签名「硅基生命001」。
9. 正文写「结构图见封面与正文配图」，不要写 ![ ](url)。
10. title 不超过 40 字，不要冒号。
"""


def _api_key() -> str:
    return (os.environ.get("DEEPSEEK_API_KEY") or "").strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError("DeepSeek 未返回 JSON 对象")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("DeepSeek JSON 不是对象")
    return obj


def rewrite_square_article(
    *,
    facts: dict[str, Any],
    fallback_title: str,
    fallback_body: str,
    market: str,
    cashtags: list[str],
) -> dict[str, str]:
    """Return title/body/source. source is deepseek or template."""
    template = {
        "title": fallback_title,
        "body": fallback_body,
        "source": "template",
    }
    key = _api_key()
    if not key:
        return template
    payload = {
        "model": os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"market": market, "cashtags": cashtags, "facts": facts},
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ],
        "stream": False,
    }
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urlopen_direct(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        obj = json.loads(raw)
        text = (
            ((obj.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        )
        parsed = _parse_json_object(text)
        title = str(parsed.get("title") or "").strip()
        body = strip_markdown_images(str(parsed.get("body") or "").strip())
        if not title or not body:
            return template
        hard = [v for v in validate_square_text(body) if v != "empty_body"]
        if hard:
            return template
        assert_cashtag_budget(body)
        assert_cashtag_present_if_required(body, market=market)
        wanted = {t.upper() for t in cashtags}
        got = {t.upper() for t in re.findall(r"\$[A-Za-z]{1,10}", body)}
        if wanted and not wanted.issubset(got):
            return template
        if count_cashtags(body) > 2:
            return template
        try:
            from lib.human_writing_gate import assert_article_ok, check_enabled

            if check_enabled():
                assert_article_ok(body)
        except Exception:
            return template
        return {"title": title, "body": body, "source": "deepseek"}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
        return template
