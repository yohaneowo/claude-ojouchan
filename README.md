# Claude-Ojouchan

用 Claude 驅動、跑在 Discord 上的角色 bot。平台層是 [AstrBot](https://github.com/AstrBotDevs/AstrBot)，「像個人」的部分寫在自己的插件 `plugins/ojou_core/`。

Claude-Ojouchan 是 [whale-chan-pre-agi](https://github.com/yohaneowo/whale-chan-pre-agi)（DeepSeek 版的大肥魚）的姊妹專案，很多做法從那邊來：原文帳本是記憶的唯一正本、整理出的筆記附出處、花費有上限。

## 組成

| 位置 | 內容 |
| --- | --- |
| `compose.yaml` | AstrBot（版本固定），後台只開在本機 |
| `deploy/configure.py` | 把模型、Discord、對話長度等設定寫進 AstrBot 的 `cmd_config.json`，密鑰從環境變數來 |
| `deploy/up.sh` | 在 VM 上用 Doppler 跑 `configure.py`，再啟動 AstrBot |
| `plugins/ojou_core/` | 原文帳本（`data/ojou/archive/`）、每日花費上限（`data/ojou/usage/`）、暫時的人設 |

## 模型與花費

- 主力聊天用 Claude Sonnet 5.5，判斷要不要插話、整理記憶這類雜事用 Claude Haiku 5.5。
- 開啟 Claude 的自動提示詞快取（`custom_extra_body.cache_control`），每次呼叫只為新的內容付全價。
- 對話超過 40 輪時一次砍掉最舊的 15 輪，而不是每輪砍一輪，避免每次都讓快取失效。
- 每次呼叫按 token 用量算錢，一天到上限（`OJOU_DAILY_BUDGET_USD`）就不再呼叫模型，並私訊站長。

## 部署

```sh
# 在 VM 的 /opt/ojouchan，以 root 執行
sh deploy/up.sh
```

需要 Doppler 專案 `claude-ojouchan` 的 `prd` 設定裡有 `DISCORD_BOT_TOKEN`、`ANTHROPIC_API_KEY` 和 `OJOU_OWNER_ID`（站長的 Discord 使用者 ID），以及放在 `/etc/ojouchan/doppler-token` 的唯讀服務 token。

## 授權

AGPL-3.0（見 `LICENSE`）。在 Discord 輸入 `/source` 可以拿到這個 repo 的連結。
