# ECS 访问币安主站：走自己的 HTTPS 代理

阿里云国内 ECS 直连 `www.binance.com` 会超时。行情继续直连新浪 / `data-api.binance.vision`。
只有广场 OpenAPI 走代理，环境变量是 `SQUARE_HTTPS_PROXY`。

**不要用公司机器当跳板**（含本机 `~/.ssh/config` 里的 `hk-server`）。代理必须开在你自己的云主机或你付费的代理上。

不要设全局 `HTTPS_PROXY`，否则新浪 / DeepSeek / 百炼也会被拖走。

## 推荐：自己买一台香港轻量，当发文机或当跳板

同一阿里云账号开 **香港** 轻量/ECS（1 核 1G 即可）。两种用法：

1. **最省事**：cron 直接跑在香港机上，不需要代理。香港能通币安主站、也能拉新浪和 `data-api.binance.vision`。
2. **国内 ECS 继续跑任务**：香港机只装 tinyproxy，国内 ECS 用 SSH 转到本机 `8888`。

香港机上：

```bash
sudo bash deploy/hk-tinyproxy.sh
```

国内 ECS 上（把 `USER@你的香港公网IP` 换成自己的机器，不要填公司 IP）：

```bash
sudo bash deploy/ecs-install-tunnel.sh USER@你的香港公网IP
```

第一次会打印公钥，贴进**你自己那台**香港机的 `~/.ssh/authorized_keys`，再跑同一条命令。

## 备选：买一条 HTTP 代理

把服务商给的地址填进 ECS `.env` 即可，不必 SSH 隧道：

```
SQUARE_HTTPS_PROXY=http://用户:密码@host:port
```

代理必须支持 HTTPS CONNECT。不要用来路不明的免费代理。

## `.env`

```
SQUARE_HTTPS_PROXY=http://127.0.0.1:8888
SQUARE_PUBLISH=1
```

若用商家代理，把上面换成商家 URL。

## 自检

```bash
curl -sS -o /dev/null -w "%{http_code}\n" --max-time 10 \
  -x "$SQUARE_HTTPS_PROXY" https://www.binance.com/
```

隧道方案看到 `200` 或 `202` 即通。
