"""币安广场发文统一规范（全品类 square_copy 共用）.

调研结论固化（推荐流 + 热门话题池 · 2026）：
  - 测推窗 1–2 小时：讨论/完读决定是否扩池
  - 结构：钩子 → 证据 → 读盘 → 真问题 CTA → $/# 标签 → 短签
  - 长文要有可点击标题；配图默认 cover+imageList（见下方发布铁律）
  - Write to Earn：$币种/交易组件驱动手续费返佣；禁止第三方私域导流

【发布铁律 · 2026-08-05 实战修正】
  长文（contentType=2）默认 cover+imageList：title + cover + imageList（同一张图）。
  原因：OpenAPI 只设 cover 时详情页常不出图（已复现 352438240895441）。
  cover_only 仅显式 opt-in（对齐官方脚本，接受详情可能无图）。
  短文多图（contentType=1）= imageList（1–4），无 title / 无 cover。
  禁止把 ![alt](url) 写进 bodyTextOnly；正文只写「见封面/正文配图」。

【$ 币种铁律 · Write to Earn】
  正文须在关键结论旁或 CTA 之后、签名之前挂对口 $TICKER（可点跳转交易）。
  全文 $ 代币符出现次数 ≤ MAX_CASHTAGS（默认 2；OpenAPI 过多会报错）。
  勿在钩子与尾标重复同一 $。能挂交易组件时优先组件。

产物约定（写入 share_copy）：
  square_short / square_title / square_article / square_tags
  square_cover_hint / square_ops / square_publish_mode
  playbook_square = binance_square_v2  # 长文默认 cover+imageList
"""
from __future__ import annotations

import re
from typing import Any, Literal, Sequence

PLAYBOOK_ID = "binance_square_v2"

SHORT_SOFT_LIMIT = 900
TITLE_SOFT_LIMIT = 40
MAX_TAGS = 5
MIN_TAGS = 1
MAX_IMAGES = 4
# Write to Earn：官方 FAQ 写每帖最多 3 个 cashtag；OpenAPI 实战更严，默认 ≤2。
MAX_CASHTAGS = 2

ArticlePublishMode = Literal["cover_only", "cover+imageList"]
DEFAULT_ARTICLE_MODE: ArticlePublishMode = "cover+imageList"

# 匹配 $BTC / $ETH 等；后接中文时也算一次（不用 \b）。
_CASHTAG_RE = re.compile(r"\$[A-Za-z]{1,10}")

_ALLOWED_IMG_HOST_RE = re.compile(
    r"https://public\.bnbstatic\.com/\S+",
    re.I,
)

_FORBIDDEN_RES: list[tuple[str, re.Pattern[str]]] = [
    ("third_party_telegram", re.compile(r"(t\.me/|telegram|电报群|加电报)", re.I)),
    ("third_party_wechat", re.compile(r"(微信|weixin|vx\s*[:：]|加微)", re.I)),
    ("private_signal", re.compile(r"(私聊带单|加我私聊|免费带单|稳赚不赔|百分百盈利|关注必富)", re.I)),
    ("uid_airdrop_bait", re.compile(r"(留\s*uid|评论区.*uid.*奖|私信.*领)", re.I)),
]

_URL_RE = re.compile(r"https?://\S+", re.I)


def join_blocks(*blocks: str | None) -> str:
    parts = [b.strip() for b in blocks if b and str(b).strip()]
    return "\n\n".join(parts)


def normalize_tags(tags: Sequence[str] | None, *, market: str | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for t in tags or []:
        s = str(t).strip()
        if not s:
            continue
        if not (s.startswith("#") or s.startswith("$")):
            if re.fullmatch(r"[A-Za-z]{2,10}", s):
                s = f"${s.upper()}"
            else:
                s = f"#{s.lstrip('#')}"
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= MAX_TAGS:
            break
    if len(out) < MIN_TAGS:
        for d in default_tags_for_market(market):
            key = d.lower()
            if key not in seen:
                out.append(d)
                seen.add(key)
            if len(out) >= MIN_TAGS:
                break
    return out[:MAX_TAGS]


def default_tags_for_market(market: str | None) -> list[str]:
    m = (market or "").upper()
    if m == "C":
        return ["$BTC", "$ETH", "#加密流动性"]
    if m == "U":
        return ["$SPY", "$QQQ", "#美股"]
    if m == "H":
        return ["#港股", "#板块"]
    if m == "FX":
        return ["#汇率", "$USD"]
    if m == "A":
        return ["#A股", "#板块"]
    return ["#硅基生命001"]


def validate_square_text(text: str) -> list[str]:
    if not text or not str(text).strip():
        return ["empty_body"]
    hits: list[str] = []
    for vid, pat in _FORBIDDEN_RES:
        if pat.search(text):
            hits.append(vid)
    return hits


def extract_cashtags(text: str) -> list[str]:
    """按出现顺序提取正文中的 $TICKER（含重复）。"""
    if not text:
        return []
    return [m.group(0).upper() for m in _CASHTAG_RE.finditer(text)]


def count_cashtags(text: str) -> int:
    return len(extract_cashtags(text))


def cashtag_required_for_market(market: str | None) -> bool:
    """A/港股广场帖可不挂 $；加密/美股/汇率默认必须挂（Write to Earn）。"""
    m = (market or "C").upper()
    return m not in ("A", "H")


def assert_cashtag_budget(text: str, *, max_n: int = MAX_CASHTAGS) -> list[str]:
    """全文 $ 出现次数不得超过 max_n；超限抛错。返回去重后的代币列表。"""
    tags = extract_cashtags(text)
    if len(tags) > max_n:
        raise ValueError(
            f"binance_square_playbook：$ 代币符最多 {max_n} 次（当前 {len(tags)}：{' '.join(tags)}）。"
            "请放在关键结论/CTA 后、签名前，且勿在钩子与尾标重复。"
        )
    # 保序去重
    seen: set[str] = set()
    uniq: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def assert_cashtag_present_if_required(
    text: str,
    *,
    market: str | None = "C",
    required: bool | None = None,
) -> None:
    need = cashtag_required_for_market(market) if required is None else required
    if need and count_cashtags(text) < 1:
        raise ValueError(
            "binance_square_playbook：正文缺少 $ 代币符。"
            "请在关键结论旁或 CTA 之后、签名之前挂对口 $TICKER（全文 ≤"
            f"{MAX_CASHTAGS} 次），以承接 Write to Earn 跳转交易。"
        )


def split_cash_and_hash_tags(tags: Sequence[str] | None) -> tuple[list[str], list[str]]:
    cash: list[str] = []
    hash_: list[str] = []
    for t in tags or []:
        s = str(t).strip()
        if not s:
            continue
        if s.startswith("$") or re.fullmatch(r"[A-Za-z]{2,10}", s):
            if not s.startswith("$"):
                s = f"${s.upper()}"
            else:
                s = f"${s[1:].upper()}"
            if s not in cash:
                cash.append(s)
        else:
            if not s.startswith("#"):
                s = f"#{s.lstrip('#')}"
            if s not in hash_:
                hash_.append(s)
    return cash[:MAX_CASHTAGS], hash_


def scrub_forbidden(text: str) -> str:
    """去掉非广场图床外链；保留 public.bnbstatic.com 插图 URL。"""
    if not text:
        return text

    def _repl(m: re.Match[str]) -> str:
        url = m.group(0)
        if _ALLOWED_IMG_HOST_RE.match(url):
            return url
        return ""

    cleaned = _URL_RE.sub(_repl, text)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def format_tag_line(tags: Sequence[str]) -> str:
    return " ".join(normalize_tags(list(tags)))


_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


def strip_markdown_images(text: str) -> str:
    """去掉 ![alt](url)，避免广场纯文本露出源码。"""
    if not text:
        return text
    cleaned = _MD_IMG_RE.sub("", text)
    # 顺带去掉孤立的 public.bnbstatic 裸链（图已由 imageList 承担）
    cleaned = _ALLOWED_IMG_HOST_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def inject_image_caption(
    body: str,
    caption: str = "（结构图见封面与正文配图，请对照蓝折线摆动与右侧 Fib 虚线阅读。）",
) -> str:
    """在首个【】小节后插入纯文字读图指引，不插入 URL。"""
    if caption in body:
        return body
    m = re.search(r"【[^】]+】", body)
    if m:
        end = m.end()
        return body[:end] + f"\n\n{caption}\n" + body[end:]
    return f"{caption}\n\n{body}"


def _prepare_article_body(body: str, *, market: str | None = "C") -> str:
    body_s = strip_markdown_images(body)
    if "配图" not in body_s and "结构图" not in body_s and "见封面" not in body_s:
        body_s = inject_image_caption(body_s)
    hard = [v for v in validate_square_text(body_s) if v != "empty_body"]
    if hard:
        raise ValueError(f"binance_square_playbook 合规失败: {', '.join(hard)}")
    if re.search(r"!\[[^\]]*\]\([^)]+\)", body_s):
        raise ValueError("正文仍含 markdown 图链；广场会原样显示，请先 strip")
    assert_cashtag_budget(body_s)
    assert_cashtag_present_if_required(body_s, market=market)
    return body_s


def build_article_publish_payload(
    *,
    title: str,
    body: str,
    image_urls: Sequence[str],
    mode: ArticlePublishMode = DEFAULT_ARTICLE_MODE,
    market: str | None = "C",
) -> dict[str, Any]:
    """长文 OpenAPI body。默认 cover+imageList（详情页要出图）。

    - cover+imageList（默认）：contentType=2 + title + cover + imageList
    - cover_only：对齐官方 square-post；OpenAPI 下详情页常不出图，仅显式使用

    bodyTextOnly 是纯文本：写入 ![x](url) 会原样显示。出图靠 cover / imageList。
    加密/美股等默认须挂 ≤2 个对口 $；market=A/H 可不挂 $。
    """
    urls = [u.strip() for u in image_urls if u and str(u).strip()]
    if not urls:
        raise ValueError("长文发布必须提供至少 1 张已上传图片 URL（作 cover）")
    if not (title or "").strip():
        raise ValueError("长文必须有 title")
    body_s = _prepare_article_body(body, market=market)
    # Optional human-writing gate (vendored skill). Off by default.
    try:
        from lib.human_writing_gate import assert_article_ok, check_enabled

        if check_enabled():
            assert_article_ok(body_s)
    except ImportError:
        pass
    cover = urls[0]

    if mode == "cover_only":
        if len(urls) > 1:
            raise ValueError(
                "长文 cover_only 仅允许 1 张 cover；多图请合成一张封面，"
                "或改用 build_short_image_publish_payload（contentType=1）"
            )
        return {
            "contentType": 2,
            "title": title.strip(),
            "bodyTextOnly": body_s,
            "cover": cover,
            "playbook_square": PLAYBOOK_ID,
            "square_publish_mode": "cover_only",
        }

    if mode == "cover+imageList":
        if len(urls) > MAX_IMAGES:
            raise ValueError(f"图片最多 {MAX_IMAGES} 张")
        return {
            "contentType": 2,
            "title": title.strip(),
            "bodyTextOnly": body_s,
            "cover": cover,
            "imageList": list(urls),
            "playbook_square": PLAYBOOK_ID,
            "square_publish_mode": "cover+imageList",
        }

    raise ValueError(f"未知长文发布模式: {mode!r}（仅 cover_only / cover+imageList）")


def build_short_image_publish_payload(
    *,
    body: str,
    image_urls: Sequence[str],
    market: str | None = "C",
) -> dict[str, Any]:
    """短文多图 OpenAPI body：contentType=1 + imageList，无 title/cover。"""
    urls = [u.strip() for u in image_urls if u and str(u).strip()]
    if not urls:
        raise ValueError("短文多图必须提供 1–4 张已上传图片 URL")
    if len(urls) > MAX_IMAGES:
        raise ValueError(f"图片最多 {MAX_IMAGES} 张")
    body_s = strip_markdown_images(body)
    hard = [v for v in validate_square_text(body_s) if v != "empty_body"]
    if hard:
        raise ValueError(f"binance_square_playbook 合规失败: {', '.join(hard)}")
    if not body_s.strip():
        raise ValueError("短文正文不能为空")
    assert_cashtag_budget(body_s)
    assert_cashtag_present_if_required(body_s, market=market)
    return {
        "contentType": 1,
        "bodyTextOnly": body_s,
        "imageList": list(urls),
        "playbook_square": PLAYBOOK_ID,
        "square_publish_mode": "short_imageList",
    }


def compose_square_short(
    *,
    hook: str,
    evidence: Sequence[str] | None = None,
    reads: Sequence[str] | None = None,
    stance: str | None = None,
    cta: str | None = None,
    tags: Sequence[str] | None = None,
    signature: str | None = None,
    market: str | None = None,
    soft_limit: int = SHORT_SOFT_LIMIT,
) -> str:
    ev = "\n".join(f"· {x.strip()}" for x in (evidence or []) if x and str(x).strip())
    rd = "\n".join(f"· {x.strip()}" for x in (reads or []) if x and str(x).strip())
    head = join_blocks(
        hook,
        ev,
        ("怎么读：\n" + rd) if rd else None,
        stance,
        cta,
    )
    already = {t.upper() for t in extract_cashtags(head)}
    cash_tags, hash_tags = split_cash_and_hash_tags(normalize_tags(tags, market=market))
    room = max(0, MAX_CASHTAGS - len(extract_cashtags(head)))
    cash_tail = [t for t in cash_tags if t.upper() not in already][:room]
    if not already and not cash_tail:
        for d in default_tags_for_market(market):
            if d.startswith("$") and d.upper() not in already and d not in cash_tail:
                cash_tail.append(d)
            if len(cash_tail) >= max(1, min(room, MAX_CASHTAGS)):
                break
        cash_tail = cash_tail[:room]
    tag_line = " ".join(cash_tail + hash_tags[: max(0, MAX_TAGS - len(cash_tail))])
    raw = join_blocks(head, tag_line or None, signature)
    out = scrub_forbidden(raw)
    hard = [v for v in validate_square_text(out) if v != "empty_body"]
    if hard:
        raise ValueError(f"binance_square_playbook 合规失败: {', '.join(hard)}")
    assert_cashtag_budget(out)
    assert_cashtag_present_if_required(out, market=market)
    if soft_limit and len(out) > soft_limit:
        out = out[: soft_limit - 1].rstrip() + "…"
    return out


def compose_square_article(
    *,
    title: str,
    hook: str,
    sections: Sequence[tuple[str, str | Sequence[str]]] | None = None,
    cta: str | None = None,
    tags: Sequence[str] | None = None,
    disclaimer: str | None = None,
    market: str | None = None,
    signature: str | None = None,
) -> dict[str, str]:
    """长文文案。真正发布前必须再走 build_article_publish_payload 注入图。"""
    title_s = scrub_forbidden((title or "").strip())
    if len(title_s) > TITLE_SOFT_LIMIT:
        title_s = title_s[: TITLE_SOFT_LIMIT - 1].rstrip() + "…"

    chunks: list[str] = [hook.strip()] if hook and hook.strip() else []
    for name, body in sections or []:
        name_s = (name or "").strip()
        if isinstance(body, (list, tuple)):
            body_s = "\n".join(str(x).rstrip() for x in body if str(x).strip())
        else:
            body_s = str(body or "").strip()
        if not body_s:
            continue
        if name_s:
            chunks.append(f"【{name_s}】\n{body_s}")
        else:
            chunks.append(body_s)
    if cta and cta.strip():
        chunks.append(cta.strip())

    # $ 放在 CTA 后、签名前；# 话题可同行。若正文已有 $，尾部不再重复追加同名。
    draft_so_far = scrub_forbidden("\n\n".join(chunks))
    already = {t.upper() for t in extract_cashtags(draft_so_far)}
    cash_tags, hash_tags = split_cash_and_hash_tags(normalize_tags(tags, market=market))
    room = max(0, MAX_CASHTAGS - len(extract_cashtags(draft_so_far)))
    cash_tail = [t for t in cash_tags if t.upper() not in already][:room]
    if not already and not cash_tail and market and (market or "").upper() == "C":
        # 加密默认补对口 $，避免漏挂导致发不出 / 无返佣入口
        for d in ("$BTC", "$ETH"):
            if len(cash_tail) >= room:
                break
            if d not in already and d not in cash_tail:
                cash_tail.append(d)
        cash_tail = cash_tail[:room]
    tag_line = " ".join(cash_tail + hash_tags[: max(0, MAX_TAGS - len(cash_tail))])
    if tag_line:
        chunks.append(tag_line)
    if signature and signature.strip():
        chunks.append(signature.strip())
    if disclaimer and disclaimer.strip():
        chunks.append(disclaimer.strip())

    body = scrub_forbidden("\n\n".join(chunks))
    hard = [v for v in validate_square_text(body) if v != "empty_body"]
    if hard:
        raise ValueError(f"binance_square_playbook 合规失败: {', '.join(hard)}")
    if validate_square_text(title_s):
        raise ValueError("binance_square_playbook 标题合规失败")
    assert_cashtag_budget(body)
    assert_cashtag_present_if_required(body, market=market)
    return {"title": title_s, "body": body}


DEFAULT_OPS = [
    "发前：确认垂直话题；有则挂官方 Topic / CreatorPad 任务",
    "发时【铁律】：长文 = title + cover + imageList（同一张图，详情才出图）；勿只用 cover；正文禁止 ![图](url)",
    "发时【$ 铁律】：关键结论旁或 CTA 后、签名前挂对口 $TICKER；全文 $ 出现 ≤2 次；勿钩子与尾标重复；可挂交易组件",
    "发后 60–120 分钟：守评秒回，自建讨论链；顺带看 Write to Earn 是否有跳转成交",
    "可选：发后把 shareLink 留在广场评论置顶",
    "复盘：创作者中心看完读/讨论/返佣，下次调钩子、配图与 $ 位置",
]


def pack_square(
    *,
    short: str,
    title: str,
    article: str,
    tags: Sequence[str],
    cover_hint: str | None = None,
    ops: Sequence[str] | None = None,
    market: str | None = None,
) -> dict[str, Any]:
    tags_n = normalize_tags(tags, market=market)
    return {
        "square_short": short,
        "square_title": title,
        "square_article": article,
        "square_tags": tags_n,
        "square_cover_hint": cover_hint
        or "长文配图：合成 1 张报告图 → 上传后同时作 cover + imageList；正文写「见封面与正文配图」，不写 markdown 图链",
        "square_ops": list(ops or DEFAULT_OPS),
        "square_publish_mode": DEFAULT_ARTICLE_MODE,
        "playbook_square": PLAYBOOK_ID,
    }


def format_square_markdown_sections(square: dict[str, Any]) -> list[tuple[str, str]]:
    tags = " ".join(square.get("square_tags") or [])
    ops = "\n".join(f"- {x}" for x in (square.get("square_ops") or []))
    mode = square.get("square_publish_mode") or DEFAULT_ARTICLE_MODE
    return [
        (
            "币安广场短文（直接发 · contentType=1）",
            f"```\n{square.get('square_short') or '（无）'}\n```\n\n标签：{tags}",
        ),
        (
            "币安广场长文（contentType=2 · 发布铁律）",
            f"**标题** {square.get('square_title') or '（无）'}\n\n"
            f"**发布模式** `{mode}`（默认 cover+imageList；只用 cover 详情常无图）\n\n"
            f"```\n{square.get('square_article') or '（无）'}\n```\n\n"
            f"配图：{square.get('square_cover_hint') or '—'}",
        ),
        ("币安广场发后 checklist", ops or "- （无）"),
    ]


def append_square_to_markdown(md: str, square: dict[str, Any]) -> str:
    parts = [md.rstrip(), "", "---", "", f"_规范：lib/binance_square_playbook · {PLAYBOOK_ID}_", ""]
    for h, body in format_square_markdown_sections(square):
        parts += [f"## {h}", "", body, ""]
    return "\n".join(parts)


def build_square_bundle(
    *,
    market: str | None,
    hook: str,
    evidence: Sequence[str],
    reads: Sequence[str] | None = None,
    stance: str | None = None,
    cta: str | None = None,
    tags: Sequence[str] | None = None,
    article_title: str,
    article_sections: Sequence[tuple[str, str | Sequence[str]]] | None = None,
    signature: str | None = None,
    disclaimer: str | None = "非实时快照 · 不构成投资建议。",
    cover_hint: str | None = None,
) -> dict[str, Any]:
    sig = signature or "硅基生命001｜币安广场 · 非实时"
    short = compose_square_short(
        hook=hook,
        evidence=evidence,
        reads=reads,
        stance=stance,
        cta=cta,
        tags=tags,
        signature=sig,
        market=market,
    )
    art = compose_square_article(
        title=article_title,
        hook=hook,
        sections=article_sections,
        cta=cta,
        tags=tags,
        disclaimer=disclaimer,
        market=market,
        signature=sig,
    )
    return pack_square(
        short=short,
        title=art["title"],
        article=art["body"],
        tags=tags or default_tags_for_market(market),
        cover_hint=cover_hint,
        market=market,
    )
