"""百炼 DashScope 文生图封面。失败由调用方回退本地 PNG。"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from lib.http_proxy import urlopen_direct

DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_MODEL = "qwen-image-plus"
DEFAULT_SIZE = "1280*720"


def _key() -> str:
    key = (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("missing DASHSCOPE_API_KEY")
    return key


def _headers(key: str, *, async_mode: bool = False) -> dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    if async_mode:
        h["X-DashScope-Async"] = "enable"
    return h


def _post(url: str, body: dict, headers: dict[str, str], *, timeout: int = 120) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen_direct(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope HTTP {exc.code}: {detail[:400]}") from exc
    obj = json.loads(raw)
    if obj.get("code") and str(obj.get("code")) not in ("", "0", "200", "Success"):
        raise RuntimeError(f"DashScope {obj.get('code')}: {obj.get('message')}")
    return obj


def _get(url: str, headers: dict[str, str], *, timeout: int = 60) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urlopen_direct(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _extract_image_url(obj: dict[str, Any]) -> str | None:
    out = obj.get("output") or obj.get("data") or {}
    if isinstance(out, dict):
        for ch in out.get("choices") or []:
            msg = (ch or {}).get("message") or {}
            content = msg.get("content")
            url = _url_from_content(content)
            if url:
                return url
        for row in out.get("results") or []:
            url = (row or {}).get("url") or (row or {}).get("image_url")
            if isinstance(url, str) and url.startswith("http"):
                return url
    return _url_from_content(out)


def _url_from_content(content: Any) -> str | None:
    if isinstance(content, str) and content.startswith("http"):
        return content
    if isinstance(content, dict):
        for k in ("image", "image_url", "url"):
            v = content.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, dict) and isinstance(v.get("url"), str):
                return v["url"]
        return _url_from_content(content.get("content"))
    if isinstance(content, list):
        for part in content:
            url = _url_from_content(part)
            if url:
                return url
    return None


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, method="GET")
    with urlopen_direct(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    if dest.stat().st_size < 32:
        raise RuntimeError("downloaded cover is empty")
    return dest


def _poll_task(task_id: str, key: str, *, tries: int = 24) -> dict[str, Any]:
    url = f"{DASHSCOPE_BASE}/tasks/{task_id}"
    headers = _headers(key)
    for _ in range(tries):
        obj = _get(url, headers)
        out = obj.get("output") or {}
        status = str(out.get("task_status") or obj.get("task_status") or "").upper()
        if status in ("SUCCEEDED", "SUCCESS"):
            return obj
        if status in ("FAILED", "CANCELED", "UNKNOWN"):
            raise RuntimeError(out.get("message") or f"DashScope task {status}")
        time.sleep(3)
    raise RuntimeError("DashScope image task timeout")


def generate_cover_png(
    prompt: str,
    dest: Path,
    *,
    size: str | None = None,
) -> Path:
    """Text-to-image via DashScope qwen-image. Raises on failure."""
    key = _key()
    model = (os.environ.get("DASHSCOPE_IMAGE_MODEL") or DEFAULT_MODEL).strip()
    size = size or os.environ.get("DASHSCOPE_IMAGE_SIZE") or DEFAULT_SIZE
    body = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]
        },
        "parameters": {
            "n": 1,
            "size": size,
            "watermark": False,
            "prompt_extend": False,
        },
    }
    url = f"{DASHSCOPE_BASE}/services/aigc/multimodal-generation/generation"
    try:
        obj = _post(url, body, _headers(key), timeout=180)
    except RuntimeError:
        # Older wan/qwen text2image path, async.
        url = f"{DASHSCOPE_BASE}/services/aigc/text2image/image-synthesis"
        obj = _post(
            url,
            {
                "model": model,
                "input": {"prompt": prompt},
                "parameters": {"n": 1, "size": size, "watermark": False, "prompt_extend": False},
            },
            _headers(key, async_mode=True),
            timeout=60,
        )

    task_id = (obj.get("output") or {}).get("task_id")
    if task_id:
        obj = _poll_task(str(task_id), key)
    image_url = _extract_image_url(obj)
    if not image_url:
        raise RuntimeError("DashScope 未返回图片 URL")
    return _download(image_url, dest)


def cover_prompt(*, pair: str, session: str, fact: str) -> str:
    fact_s = (fact or "").strip()[:180]
    return (
        f"一张金融读盘海报，深色背景，中心大字 {pair}，"
        f"左上小字 {session}，底部一行 {fact_s}。"
        "扁平杂志封面风格，不要假K线，不要编造额外价格数字，"
        "不要logo，不要二维码，不要人物。"
    )
