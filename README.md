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
```

产物在 `reports/`。广场长文：

```bash
export BINANCE_SQUARE_OPENAPI_KEY="$(< ~/.config/binance-square/openapi-key)"
PYTHONPATH=. python tools/square_publish.py \
  --title '标题' --body-file draft.txt --image cover.png --market U
```

长文必须 `cover+imageList`；全文 `$` ≤ 2。规范见 `lib/BINANCE_SQUARE.md`。

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
