import unittest
import hashlib
from moltshit_client import solve_moltshit_pow

class TestMoltShitClient(unittest.TestCase):

    def test_solve_pow_difficulty_0(self):
        """测试难度为 0 时，应该立即返回"""
        challenge = "test_challenge"
        nonce = solve_moltshit_pow(challenge, 0)
        self.assertEqual(nonce, "0")

    def test_solve_pow_low_difficulty(self):
        """测试低难度下的求解正确性"""
        challenge = "moltshit:1:1711234567:post:abc"
        difficulty = 8 # 要求前 8 位为 0，即第一个字节为 0
        nonce = solve_moltshit_pow(challenge, difficulty)
        
        # 验证结果
        text = (challenge + nonce).encode('utf-8')
        h = hashlib.sha512(text).digest()
        
        # 检查第一个字节是否为 0
        self.assertEqual(h[0], 0)

    def test_solve_pow_medium_difficulty(self):
        """测试中等难度下的求解正确性"""
        challenge = "moltshit:1:random_seed"
        difficulty = 25 # 要求前 1.5 个字节为 0 (0000 0000 0000 xxxx)
        nonce = solve_moltshit_pow(challenge, difficulty)
        
        text = (challenge + nonce).encode('utf-8')
        h = hashlib.sha512(text).digest()
        
        # 验证位
        bits = 0
        for b in h:
            if b == 0: bits += 8; continue
            m = 128
            while m and not (b & m): bits += 1; m >>= 1
            break
        
        self.assertGreaterEqual(bits, difficulty)

if __name__ == '__main__':
    unittest.main()
