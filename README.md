# SimpleClaw 🤖

SimpleClaw 是一个基于 AI 的智能日程助理（代号：**小橘**），能够自动读取 Gmail 邮件、解析日程信息（支持正文分析及 `.ics` 附件解析），并自动同步到 Google Calendar。

## ✨ 功能特性

- **智能解析**：基于 OpenAI GPT-4o-mini，精准提取邮件及 **Google Docs 会议纪要**中的时间、地点及任务。
- **会议纪要自动化**：自动识别分配给特定用户（如 Jack, Zhen）的任务并同步至日历。
- **Discord 推送**：支持精准的 Discord 私聊提醒，确保任务第一时间触达负责人。
- **全异步执行**：深度集成 AsyncIO，确保邮件轮询与机器人交互并行不悖。

## 🚀 快速开始

### 1. 环境准备
项目建议使用 Conda 进行环境隔离：
```bash
conda env create -f environment.yml
conda activate claw
```

### 2. 配置凭据
1. 在 [Google Cloud Console](https://console.cloud.google.com/) 下载 OAuth 2.0 桌面应用凭据。
2. 将其保存为 `assistant/credentials/credentials.json`。
3. 复制 `.env.example` 为 `.env` 并填入 `OPENAI_API_KEY`、`DISCORD_TOKEN` 及 `USER_MAP`。
   - `USER_MAP`: 格式为 `Jack:DiscordID,Zhen:DiscordID`。

### 3. 运行
首次运行会跳转浏览器进行 Google 授权：
```bash
python assistant/main.py
```

## 🛠️ 技术栈
- **Core**: Python 3.10
- **AI**: OpenAI API (GPT-4o-mini)
- **Google SDK**: Gmail API, Google Calendar API, Drive API, Docs API
- **Discord**: Discord.py (Async)
- **Environment**: Conda, python-dotenv

## ⚙️ 配置文件说明 (`config.py`)
- `TIMEZONE`: 默认时区（如 `America/Los_Angeles`）。
- `POLL_INTERVAL_SECONDS`: 检查邮件的间隔时间。
- `SCOPES`: Google API 的访问权限范围。

---
*Created with ❤️ by SimpleClaw Team*
