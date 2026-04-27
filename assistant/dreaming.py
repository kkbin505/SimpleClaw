"""
梦幻思考器 (Dream Generator)

功能：
1. 跟踪用户交互历史（对话、日程查询、事件创建等）
2. 根据配置的时间间隔（默认4小时）定期生成"梦"
3. 梦是对用户意图、模式和改进建议的自然语言总结
4. 将梦存储到JSON文件供用户查看
5. 支持用户按需查看梦
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from openai import OpenAI

from config import OPENAI_API_KEY, TIMEZONE, ASSISTANT_NAME, DREAM_INTERVAL_HOURS

logger = logging.getLogger(__name__)
ai_client = OpenAI(api_key=OPENAI_API_KEY)


class DreamGenerator:
    """梦幻思考器：生成和管理用户的梦"""
    
    def __init__(self):
        self.tz = ZoneInfo(TIMEZONE)
        self.dreams_file = Path(__file__).parent / "credentials" / "dreams.json"
        self.dreams_file.parent.mkdir(parents=True, exist_ok=True)
        self.interval_seconds = DREAM_INTERVAL_HOURS * 3600
        
        # 追踪每个用户最后一次梦的时间：{user_id: datetime}
        self._last_dream_time: dict = {}
        
        # 追踪每个用户的交互历史：{user_id: list of interactions}
        self._interaction_histories: dict = {}
        
        # 加载现有的梦
        self._load_dreams()

    def _load_dreams(self):
        """从文件加载已存储的梦"""
        try:
            if self.dreams_file.exists():
                with open(self.dreams_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} user dreams from file")
            else:
                logger.info(f"Dreams file not found, will create on first save")
        except Exception as e:
            logger.error(f"Failed to load dreams: {e}")

    def _save_dreams(self, dreams_data: dict):
        """保存梦到文件"""
        try:
            with open(self.dreams_file, "w", encoding="utf-8") as f:
                json.dump(dreams_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved dreams for {len(dreams_data)} users")
        except Exception as e:
            logger.error(f"Failed to save dreams: {e}", exc_info=True)

    def _load_all_dreams(self) -> dict:
        """加载所有已存储的梦"""
        try:
            if self.dreams_file.exists():
                with open(self.dreams_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load all dreams: {e}")
            return {}

    def add_interaction(self, user_id: str, interaction_type: str, content: str):
        """添加用户交互到历史记录
        
        Args:
            user_id: 用户ID
            interaction_type: 交互类型（chat, calendar_query, event_create, etc）
            content: 交互内容描述
        """
        if user_id not in self._interaction_histories:
            self._interaction_histories[user_id] = []
        
        interaction = {
            "timestamp": datetime.now(self.tz).isoformat(),
            "type": interaction_type,
            "content": content
        }
        self._interaction_histories[user_id].append(interaction)
        
        # 只保留最近100条交互
        if len(self._interaction_histories[user_id]) > 100:
            self._interaction_histories[user_id] = self._interaction_histories[user_id][-100:]

    def should_generate_dream(self, user_id: str) -> bool:
        """检查是否应该为该用户生成新梦"""
        now = datetime.now(self.tz)
        
        if user_id not in self._last_dream_time:
            # 如果从未生成过梦，检查交互是否足够
            if user_id in self._interaction_histories and len(self._interaction_histories[user_id]) >= 3:
                return True
            return False
        
        # 检查是否超过了间隔时间
        time_since_last_dream = now - self._last_dream_time[user_id]
        return time_since_last_dream >= timedelta(seconds=self.interval_seconds)

    async def generate_dream(self, user_id: str) -> str | None:
        """为用户生成一个梦
        
        Args:
            user_id: 用户ID
            
        Returns:
            生成的梦内容（自然语言格式），或None如果生成失败
        """
        if user_id not in self._interaction_histories:
            logger.warning(f"No interaction history for user {user_id}")
            return None
        
        interactions = self._interaction_histories[user_id]
        if not interactions:
            logger.warning(f"Empty interaction history for user {user_id}")
            return None
        
        # 格式化交互历史供AI分析
        interactions_text = "\n".join([
            f"[{i['timestamp']}] {i['type']}: {i['content']}"
            for i in interactions[-20:]  # 只用最近20条
        ])
        
        prompt = f"""你是{ASSISTANT_NAME}，一个智慧的私人助理。现在进行一次"梦幻思考"——深层分析用户的意图和模式。

【用户最近的交互记录】
{interactions_text}

请生成一个自然语言的"梦幻思考"，包括：
1. **用户的核心意图**：基于这些交互，用户真正想要什么？
2. **行为模式**：用户的日程、偏好和规律是什么？
3. **改进建议**：如何更好地为用户提醒和服务？
4. **下一步预测**：基于当前模式，用户接下来可能需要什么？

要求：
- 用2-3个自然段落，语气温暖但专业
- 具体引用用户的交互内容
- 提供可行的改进建议
- 不超过 500 字"""

        try:
            response = ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"你是{ASSISTANT_NAME}，一个深思熟虑的私人助理。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=500,
            )
            
            dream_content = response.choices[0].message.content
            
            # 保存梦到文件
            all_dreams = self._load_all_dreams()
            if user_id not in all_dreams:
                all_dreams[user_id] = []
            
            dream_record = {
                "timestamp": datetime.now(self.tz).isoformat(),
                "content": dream_content
            }
            all_dreams[user_id].append(dream_record)
            
            # 只保留最近30个梦
            if len(all_dreams[user_id]) > 30:
                all_dreams[user_id] = all_dreams[user_id][-30:]
            
            self._save_dreams(all_dreams)
            
            # 更新最后梦的时间
            self._last_dream_time[user_id] = datetime.now(self.tz)
            
            logger.info(f"Dream generated for user {user_id}")
            return dream_content
            
        except Exception as e:
            logger.error(f"Failed to generate dream for user {user_id}: {e}", exc_info=True)
            return None

    def get_latest_dream(self, user_id: str) -> str | None:
        """获取用户的最新梦"""
        all_dreams = self._load_all_dreams()
        
        if user_id not in all_dreams or not all_dreams[user_id]:
            return None
        
        return all_dreams[user_id][-1]["content"]

    def get_dream_history(self, user_id: str, limit: int = 5) -> list:
        """获取用户的梦历史"""
        all_dreams = self._load_all_dreams()
        
        if user_id not in all_dreams:
            return []
        
        return [
            {
                "timestamp": dream["timestamp"],
                "content": dream["content"]
            }
            for dream in all_dreams[user_id][-limit:]
        ]