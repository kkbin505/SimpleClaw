# SimpleClaw 🤖

SimpleClaw 是一个基于 AI 的智能日程助理（代号：**小橘**），能够自动读取 Gmail 邮件、解析日程信息（支持正文分析及 `.ics` 附件解析），并自动同步到 Google Calendar。

## ✨ 功能特性

- **智能解析**：基于 OpenAI GPT-4o-mini，精准提取邮件中的时间、地点及事件描述。
- **ICS 深度集成**：自动下载并解析邮件中的 `.ics` 日历附件，支持 UTC 到本地时区的精准转换。
- **硬逻辑去重**：代码级判断，防止重复创建相同日程。
- **时区对齐**：专为跨时区场景优化（默认洛杉矶时间），具备强大的基准对齐和日期推算能力。
- **个性化助理**：内置“老朋友”般的助理人格，交互自然。

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
3. 复制 `.env.example` 为 `.env` 并填入你的 `OPENAI_API_KEY`。

### 3. 运行
首次运行会跳转浏览器进行 Google 授权：
```bash
python assistant/main.py
```

## 🛠️ 技术栈
- **Core**: Python 3.10
- **AI**: OpenAI API
- **Google SDK**: Gmail API, Google Calendar API
- **Environment**: Conda, python-dotenv

## ⚙️ 配置文件说明 (`config.py`)
- `TIMEZONE`: 默认时区（如 `America/Los_Angeles`）。
- `POLL_INTERVAL_SECONDS`: 检查邮件的间隔时间。
- `SCOPES`: Google API 的访问权限范围。

---
*Created with ❤️ by SimpleClaw Team*
