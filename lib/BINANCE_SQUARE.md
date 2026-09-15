# 币安广场发文规范（全品类强制）

所有将发到 **Binance Square / 币安广场** 的短文与长文，必须走 `lib/binance_square_playbook.py`（`playbook_square=binance_square_v2`）。

## 发布铁律（2026-08-05 · 实战修正）

| 形态 | contentType | 必填 | 说明 |
|------|-------------|------|------|
| **长文（默认）** | `2` | `title` + `cover` + `imageList`（**同一张**图） | 详情页要出图必须挂 `imageList` |
| **长文 cover_only** | `2` | `title` + `cover` | 对齐官方脚本；**详情页常不出图**（OpenAPI quirk） |
| **短文多图** | `1` | `imageList`（1–4） | 无 title / 无 cover |

### 为什么默认是 cover+imageList

1. 官方 `square-post` 写长文只用 `cover`，**禁止** `--images`。  
2. 实战（含 `352438240895441`）：只设 `cover` 时，信息流卡片可能有封面，**点进详情经常没有图**。  
3. 同时挂 `cover` + `imageList=[同一 URL]`：正文/媒体区能出图；多图仍建议先合成 1 张，避免被当成短图文刷。

### 重要：不要往正文写 markdown 图

`bodyTextOnly` 是**纯文本**，不会渲染 `![说明](url)`。  
写进去会原样显示成一行源码。

正文只写中文读图说明，例如：「结构图见封面与正文配图……」。

### 构造器

- 长文（默认）：`build_article_publish_payload(title=..., body=..., image_urls=[cover])`  
  → `square_publish_mode=cover+imageList`
- 仅实验/对齐官方：`mode="cover_only"`（接受详情可能无图）
- 短文多图：`build_short_image_publish_payload(body=..., image_urls=[...])`

## 硬约束

1. **结构**：钩子 → 2–4 证据 → 怎么读盘 → 真问题 CTA → `$`/`#` 标签 → 短签  
2. **标签**：`#` 话题 1–5 个；**`$` 代币符全文出现 ≤2 次**（`MAX_CASHTAGS`）  
3. **【$ 铁律 · Write to Earn】**  
   - 在**关键结论旁**或 **CTA 之后、签名之前**固定挂对口 `$TICKER`（或交易组件）  
   - 读者点 `$`/组件再交易，才有手续费返佣入口（基础约 20%）  
   - **禁止**钩子与尾标重复同一 `$`（重复计入次数，且易触 OpenAPI 限额）  
   - 加密/美股/汇率帖缺 `$` 拒发；A/港股帖可不挂 `$`，但仍受「全文 ≤2」约束  
4. **合规**：禁止微信/电报导流、私聊带单、稳赚话术、留 UID 领奖  
5. **配图**：见上方铁律  
6. **运营**：`square_ops` 发后 1–2h 守评  

构造器会在发布前 `assert_cashtag_budget`：缺 `$` 或超过 2 次均拒发。

## 发布

Key：`BINANCE_SQUARE_OPENAPI_KEY`（勿入库）。  
流程：upload 图 → `build_article_publish_payload` → `POST .../content/add`。

## 活人感（可选）

长文正文可走 vendored skill `skills/human-writing/`（见 `QINGTING.md`）。  
设 `QINGTING_HUMAN_WRITING_CHECK=1` 时，发布构造器会对 `bodyTextOnly` 跑 `lib/human_writing_gate`（article 模式硬失败则拒发）。
