# 美股盘前 / 盘后一页纸

CLI：`python run.py --us-pre` · 环境变量 `US_PRE_CACHE_TTL` / `US_PRE_NO_CACHE=1`

币安广场：`lib/binance_square_playbook`（短文/长文 + `$`/`#`；见 `lib/BINANCE_SQUARE.md`）。不发 X。

## 版式

- 紧凑一页纸，双栏强弱，打印 A4
- 页头：硅基生命001 · **盘前/盘中/盘后**（按美东时钟）· 北京/美东 as_of
- 大盘一行：盘前期指（ES/NQ/YM 隔夜）+ 现金指数（昨收）+ VIX/10Y
- 速写以期指为主，现金指数标明昨收
- KPI：ES/NQ/YM · VIX · 10Y · ETF/观察池广度
- 板块 ETF 强 | 弱（弱势栏只列下跌）
- Mag7+ 强 | 弱 + 全表
- 风险旗 · NFA

## 数据纪律

- 主源 yfinance；可选 sina 指数兜底
- 盘前：现金指数 `prior_close`；期货 `overnight`；个股/ETF 优先 `premarket`
- 弱势侧禁止混入上涨标的
- 缺字段显示 `—`，禁止伪造 0
- `framework=us-premarket` · market=`U`
