# SimpleClaw 🤖

SimpleClaw 是一个基于 AI 的智能日程助理（代号：**小橘**），能够自动读取 Gmail 邮件、解析日程信息（支持正文分析及 `.ics` 附件解析），并自动同步到 Google Calendar。

## English Update (2026-04-27)

Today's optimizations completed:
- Faster model routing: daily chat and reminders now default to `gpt-5.4-nano`, while critical scheduling parsing uses `gpt-5.4-mini`.
- Better date safety for event creation: when users explicitly say 今天/明天/后天, the create-event date is normalized to the intended day.
- Shared calendar visibility: event queries now support multiple calendars and auto-discover selected accessible shared calendars.
- Clearer calendar diagnostics: startup logs now show query mode, query calendar IDs, and write calendar ID.
- Simpler Telegram flow: removed typing-indicator loop and kept direct reply flow for stability.
- Dream file reliability: `assistant/credentials/dreams.json` is created automatically during initialization.

## ✨ 功能特性

- **智能解析**：基于 OpenAI（默认 `gpt-5.4-nano` + 关键解析 `gpt-5.4-mini`），精准提取邮件及 **Google Docs 会议纪要**中的时间、地点及任务。
- **会议纪要自动化**：自动识别分配给特定用户（如 Jack, Zhen）的任务并同步至日历。
- **多平台支持**：
  - **Discord 推送**：支持精准的 Discord 私聊提醒及聊天交互。
  - **Telegram 推送** ✨ **新增**：支持 Telegram bot 私聊，独立的用户权限管理。
  - 支持 Discord 仅、Telegram 仅或两者并行运行模式。
- **全异步执行**：深度集成 AsyncIO，确保邮件轮询与机器人交互并行不悖。
- **主动互动**：新增主动日程提醒调度器，按日程准时推送 Discord/Telegram 提醒。
- **每日感官早报**：每天早晨 7:00 准时推送今日日程摘要及 **实时天气预报**。

## 🚀 快速开始

### 1. 环境准备
项目建议使用 Conda 进行环境隔离：
```bash
conda env create -f environment.yml
conda activate claw
```

### 2. 配置凭据

#### Google OAuth
1. 在 [Google Cloud Console](https://console.cloud.google.com/) 下载 OAuth 2.0 桌面应用凭据。
2. 将其保存为 `assistant/credentials/credentials.json`。

#### .env 环境变量
复制 `.env.example` 为 `.env` 并填入以下配置：

**必需**：
- `OPENAI_API_KEY`: OpenAI API 密钥
- `USER_MAP`: 格式为 `Jack:DiscordID,Zhen:DiscordID`
- `WEATHER_CITY`: 天气预报城市（如 `Irvine`）

**可选 - Discord 支持**：
- `DISCORD_TOKEN`: 从 Discord 开发者门户获取
- `ALLOWED_USER_IDS`: 逗号分隔的 Discord 用户 ID，用于权限控制

**可选 - Telegram 支持** ✨ **新增**：
- `TELEGRAM_TOKEN`: 从 BotFather 获取的 Telegram Bot Token
- `TELEGRAM_ALLOWED_USER_IDS`: 逗号分隔的 Telegram 用户 ID，用于权限控制

**其他**：
- `TIMEZONE`: 时区（默认 `America/Los_Angeles`）
- `POLL_INTERVAL_SECONDS`: 邮件轮询间隔（默认 60 秒）
- `REMINDER_THRESHOLDS`: 提醒时间点（默认 `30,5` 分钟）
- `QUIET_HOURS_START/END`: 免打扰时段（默认 21:00 - 07:00）
- `MORNING_BRIEFING_HOUR`: 早报推送时间（默认 07:00）

### 3. 运行
首次运行会跳转浏览器进行 Google 授权：
```bash
python assistant/main.py
```

## 🛠️ 技术栈
- **Core**: Python 3.10
- **AI**: OpenAI API (`gpt-5.4-nano` for general chat/reminders, `gpt-5.4-mini` for scheduling parsing)
- **Weather**: wttr.in (Free API)
- **Google SDK**: Gmail API, Google Calendar API, Drive API, Docs API
- **Messaging**: 
  - Discord.py (Async Discord bot)
  - python-telegram-bot (Async Telegram bot) ✨ **新增**
- **Environment**: Conda, python-dotenv

## ⚙️ 配置文件说明 (`config.py`)
- `TIMEZONE`: 默认时区（如 `America/Los_Angeles`）。
- `POLL_INTERVAL_SECONDS`: 检查邮件的间隔时间。
- `REMINDER_THRESHOLDS`: 提醒触发阈值（默认 `[30, 5]` 分钟）。
- `QUIET_HOURS_START/END`: 免打扰时段。
- `WEATHER_CITY`: 获取天气的城市名。
- `MORNING_BRIEFING_HOUR`: 每日早报触发时间。
- `DISCORD_TOKEN`/`ALLOWED_USER_IDS`: Discord bot 配置。
- `TELEGRAM_TOKEN`/`TELEGRAM_ALLOWED_USER_IDS`: ✨ **新增** Telegram bot 配置。
- `SCOPES`: Google API 的访问权限范围。

## 📝 运行模式

| 配置 | 功能 | 说明 |
|------|------|------|
| 仅 Discord | Discord bot + Gmail 轮询 + Discord 提醒 | 经典模式 |
| 仅 Telegram | Telegram bot + Gmail 轮询 + Telegram 提醒 | 新增支持 |
| 两者都配 | Discord + Telegram 并行 | 所有消息同步推送到两个平台 |
| 都不配 | Gmail 轮询仅 | 纯后台邮件处理，不支持聊天和提醒 |

## 🔧 最近更新

### v1.1.0 - Telegram 支持 (2026-04-26)
- ✨ 新增 Telegram bot 支持，功能等同于 Discord
- 支持 Telegram 私聊消息处理和日程提醒推送
- 独立的 `TELEGRAM_ALLOWED_USER_IDS` 用户权限管理
- 自动分段处理长消息（Telegram 4096 字符限制）
- 支持 Discord 仅、Telegram 仅或并行运行模式

---
*Created with ❤️ by kkbin505*
