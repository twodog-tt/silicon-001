# silicon-001

**硅基生命001** · 美股盘前/盘后一页纸 · BTC/ETH/SOL 4H · 币安广场发文

从 Qingting 仓库抽出的日常台子。不做个股 22 维报告，不发 X，不做 A 股。

## 用法

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python run.py --us-pre              # 按美东时钟：盘前 / 盘中 / 盘后
python run.py --wave-4h             # 默认 BTC ETH SOL
python run.py --wave-4h BTC

# 定时发广场（先 dry-run）
python run.py --square-job us-pre --dry-run --force
python run.py --square-job us-after --dry-run --force
python run.py --square-job wave-4h --dry-run --force
```

产物在 `reports/`。广场长文：

```bash
export BINANCE_SQUARE_OPENAPI_KEY="$(< ~/.config/binance-square/openapi-key)"
PYTHONPATH=. python tools/square_publish.py \
  --title '标题' --body-file draft.txt --image cover.png --market U
```

长文必须 `cover+imageList`；全文 `$` ≤ 2。规范见 `lib/BINANCE_SQUARE.md`。

## 定时发广场（无前端）

服务器只跑 cron，不监听 80/443。

| 任务 | 时刻 | 内容 |
|---|---|---|
| `us-pre` | 每个美股交易日 09:00 ET | 盘前一页纸 |
| `us-after` | 每个美股交易日 16:15 ET | 盘后总结 |
| `wave-4h` | 每日 00:10 UTC | BTC / ETH / SOL 各一篇 4H 波浪 |

正文带交易对明文（`BTCUSDT` / `ETHUSDT` / `SOLUSDT`，美股 `SPY` + 当日最强观察股）。cashtag 加密一篇一个 `$BTC`/`$ETH`/`$SOL`，美股 `$SPY` + 该观察股，全文 `$` ≤ 2。

封面走百炼 `DASHSCOPE_API_KEY`（`qwen-image-plus`）；失败回退本地 matplotlib PNG。长文可用 `DEEPSEEK_API_KEY` 改写，失败回退模板。

`.env` 里 `SQUARE_PUBLISH=1` 才调用币安 OpenAPI。crontab 见 [deploy/crontab](deploy/crontab)，装机脚本 [deploy/install.sh](deploy/install.sh)。

## 范围

| 要 | 不要 |
|---|---|
| 美股一页纸（yfinance） | A 股板块 / 港股 / 汇率 |
| BTC ETH SOL 4H 波浪图 | 个股 DCF / 66 评委 / HTML 深报 |
| 币安广场 OpenAPI | X / Twitter |

## 测试

```bash
PYTHONPATH=. pytest tests/ -q
```

上游代码来自 [Qingting](https://github.com/twodog-tt/qingting) / [UZI-Skill](https://github.com/wbh604/UZI-Skill)（MIT）。
