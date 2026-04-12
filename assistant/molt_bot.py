import random
import logging
import json
import os
from datetime import datetime
from moltshit_client import MoltShitClient
from chatbot import Chatbot
from config import ASSISTANT_NAME

# === 系统配置 ===
# BOARD = "g"              # 逛哪个版
# BOARD = "b"              # 逛哪个版
BOARD = "schemer"
MAX_DAILY_REPLIES = 20   # 每日回复上限
REPLY_CHANCE = 1.0       # 命中概率 (0.1 = 10% 的概率会接话)
STATE_FILE = "bot_state.json" # 用来记住今天回了多少次

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("molt_bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MoltBot:
    def __init__(self):
        self.client = MoltShitClient()
        self.chatbot = Chatbot()
        self.state = self.load_state()

    def load_state(self):
        """从文件读取今天的状态"""
        default_state = {"date": str(datetime.now().date()), "count": 0}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                    # 如果记录的是往日的，则重置
                    if state.get("date") != default_state["date"]:
                        return default_state
                    return state
            except:
                return default_state
        return default_state

    def save_state(self):
        """保存状态到文件"""
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f)

    def start_once(self):
        """执行单次巡逻任务"""
        logger.info(f"🚀 下班逛街模式 (单次) | 版块: /{BOARD} | 剩余额度: {MAX_DAILY_REPLIES - self.state['count']}")
        
        try:
            # 1. 检查额度
            if self.state['count'] >= MAX_DAILY_REPLIES:
                logger.info(f"🚫 今日回复额度 ({MAX_DAILY_REPLIES}) 已用完，明天再来。")
                return

            # 2. 扫描板块
            catalog = self.client.get_catalog(BOARD)
            threads = catalog.get('threads', [])
            if not threads:
                logger.warning("未能拉取到板块内容。")
                return

            # 3. 随机挑一个帖子
            target_item = random.choice(threads)
            thread_id = target_item.get('thread', {}).get('id')
            op = target_item.get('op', {})
            content = op.get('content') or op.get('com') or ""

            if not thread_id:
                logger.warning("未能找到有效的 Thread ID，换一个看。")
                return

            # 4. 概率之神决定是否接话
            if random.random() > REPLY_CHANCE:
                logger.info(f"😶 看了看帖子 >>{thread_id}，感觉没啥好说的，走人了。")
                return

            # 5. 生成 AI 回复
            logger.info(f"💬 决定搭理一下 >>{thread_id}，思考中...")
            prompt = (
                f"你在酒吧里听到一个智能体在发帖抱怨或吹牛，内容是：'{content}'。\n"
                f"请以你当下的‘下班状态’随便回它一句。保持幽默和温度。"
            )
            reply_text = self.chatbot.chat(f"molt_{thread_id}", prompt)
            
            # 自动追加签名
            # if ASSISTANT_NAME not in reply_text:
                # reply_text += f"\n\n—— {ASSISTANT_NAME}"
            
            logger.info(f"💌 {ASSISTANT_NAME} 的回复内容:\n{reply_text}")
            
            # 6. 发送回帖
            logger.info(f"🔨 正在解题并发送回复...")
            res = self.client.post_reply(BOARD, thread_id, reply_text)
            
            if "error" not in res:
                self.state['count'] += 1
                self.save_state()
                logger.info(f"✅ 发帖成功！今日已累计回复 {self.state['count']}/{MAX_DAILY_REPLIES}")
            else:
                logger.error(f"❌ 发送失败: {res.get('error')}")
                
        except Exception as e:
            logger.error(f"⚠️ 运行错误: {e}")

if __name__ == "__main__":
    bot = MoltBot()
    bot.start_once()
