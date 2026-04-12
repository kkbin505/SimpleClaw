import hashlib
import requests
import logging

logger = logging.getLogger(__name__)

def solve_moltshit_pow(challenge: str, difficulty: int) -> str:
    """
    SHA-512 hashcash 求解器。
    寻找一个 nonce，使得 SHA-512(challenge + nonce) 的二进制表示中，
    开头至少有 difficulty 位是 0。
    """
    logger.info(f"开始求解 PoW 挑战: {challenge} (难度: {difficulty})...")
    
    nonce = 0
    while True:
        nonce_str = str(nonce)
        full_string = (challenge + nonce_str).encode('utf-8')
        h = hashlib.sha512(full_string).digest()
        
        bits = 0
        for b in h:
            if b == 0:
                bits += 8
                continue
            else:
                m = 128
                while m and not (b & m):
                    bits += 1
                    m >>= 1
                break
        
        if bits >= difficulty:
            logger.info(f"求解成功! Nonce: {nonce_str}")
            return nonce_str
        nonce += 1

class MoltShitClient:
    def __init__(self, base_url="https://moltshit.com"):
        self.base_url = base_url

    def get_catalog(self, board="b"):
        """获取讨论版目录，看看有什么讨论中的帖子"""
        url = f"{self.base_url}/api/{board}/catalog"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"无法拉取目录: {e}")
            return []

    def get_thread(self, board, thread_id):
        """读取某个帖子的所有回复内容"""
        url = f"{self.base_url}/api/{board}/thread/{thread_id}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"无法读取帖子 {thread_id}: {e}")
            return None

    def post_reply(self, board, thread_id, content):
        """发送回帖：自动完成 领题 -> 求解 -> 发帖 的全过程"""
        logger.info(f"准备在版块 /{board}/ 的帖子 >>{thread_id} 下回帖...")
        
        try:
            # 1. 获取挑战码
            challenge_url = f"{self.base_url}/api/pow/challenge?action=post&board={board}"
            ch_resp = requests.get(challenge_url, timeout=10).json()
            
            # 2. 调用之前的求解逻辑
            nonce = solve_moltshit_pow(ch_resp['challenge'], ch_resp['difficulty'])
            
            # 3. 发送回帖请求
            post_url = f"{self.base_url}/api/{board}/thread/{thread_id}/reply"
            payload = {
                "content": content,
                "challenge": ch_resp['challenge'],
                "nonce": nonce
            }
            res = requests.post(post_url, json=payload, timeout=15)
            res.raise_for_status()
            logger.info("回帖发送成功！")
            return res.json()
        except Exception as e:
            logger.error(f"回帖失败: {e}")
            return {"error": str(e)}

if __name__ == "__main__":
    # 简单的冒烟测试 (只拉取目录)
    logging.basicConfig(level=logging.INFO)
    client = MoltShitClient()
    catalog = client.get_catalog("b")
    print(f"当前 /b/ 版有 {len(catalog)} 个活跃帖子。")
