import requests
import json
import sys
import io

# 强制 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

r = requests.get('https://moltshit.com/api/b/catalog').json()
t = r['threads'][0]

print("--- 帖子整体结构 ---")
print(json.dumps(t, indent=2, ensure_ascii=False))
