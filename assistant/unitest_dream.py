import asyncio
from dreaming import DreamGenerator

user_id = "8793605138"  # 替换成你的用户ID
dg = DreamGenerator()

dg.add_interaction(user_id, "chat", "测试交互 1")
dg.add_interaction(user_id, "chat", "测试交互 2")
dg.add_interaction(user_id, "chat", "测试交互 3")

dream = asyncio.run(dg.generate_dream(user_id))
print("Dream result:", dream)