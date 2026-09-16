"""币安广场 OpenAPI：上传封面 + 长文 content/add（cover+imageList）。"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from lib.binance_square_playbook import build_article_publish_payload
from lib.http_proxy import urlopen_square

BASE_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi"
BASE_V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi"
DEFAULT_KEY_FILE = Path.home() / ".config" / "binance-square" / "openapi-key"


def load_api_key() -> str:
    key = (os.environ.get("BINANCE_SQUARE_OPENAPI_KEY") or "").strip()
    if key:
        return key
    if DEFAULT_KEY_FILE.is_file():
        return DEFAULT_KEY_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit(
        "missing Binance Square API key "
        "(env BINANCE_SQUARE_OPENAPI_KEY or ~/.config/binance-square/openapi-key)"
    )


def _api(key: str, base: str, endpoint: str, body: dict) -> dict:
    req = urllib.request.Request(
        base + endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Square-OpenAPI-Key": key,
            "clienttype": "binanceSkill",
        },
        method="POST",
    )
    try:
        with urlopen_square(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {detail[:500]}") from exc
    obj = json.loads(raw)
    if obj.get("code") != "000000":
        raise SystemExit(f"API {obj.get('code')}: {obj.get('message')}")
    return obj.get("data") or {}


def upload_image(path: Path, *, key: str | None = None) -> str:
    key = key or load_api_key()
    path = Path(path)
    ctype = mimetypes.guess_type(str(path))[0] or "image/png"
    pres = _api(key, BASE_V2, "/image/presignedUrl", {"imageName": path.name})
    put = urllib.request.Request(
        pres["presignedUrl"],
        data=path.read_bytes(),
        method="PUT",
        headers={"Content-Type": ctype},
    )
    with urlopen_square(put, timeout=120) as resp:
        if resp.status not in (200, 201, 204):
            raise SystemExit(f"image upload failed: {resp.status}")
    for _ in range(12):
        status = _api(key, BASE_V2, "/image/imageStatus", {"fileTicket": pres["fileTicket"]})
        if status.get("status") == 1:
            return status["imageUrl"]
        if status.get("status") == 2:
            raise SystemExit(status.get("failedReason") or "image processing failed")
        time.sleep(3)
    raise SystemExit("image processing timeout")


def publish_article(
    *,
    title: str,
    body: str,
    image_path: Path,
    market: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    key = key or load_api_key()
    cover_url = upload_image(Path(image_path), key=key)
    payload = build_article_publish_payload(
        title=title,
        body=body,
        image_urls=[cover_url],
        mode="cover+imageList",
        market=market,
    )
    result = _api(
        key,
        BASE_V1,
        "/content/add",
        {
            "contentType": payload["contentType"],
            "title": payload["title"],
            "bodyTextOnly": payload["bodyTextOnly"],
            "cover": payload["cover"],
            "imageList": payload["imageList"],
        },
    )
    return {
        "ok": True,
        "result": result,
        "cover_url": cover_url,
        "title": payload["title"],
        "playbook_square": payload.get("playbook_square"),
        "square_publish_mode": payload.get("square_publish_mode"),
        "id": result.get("id"),
        "shareLink": result.get("shareLink"),
    }
