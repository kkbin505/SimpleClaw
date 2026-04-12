import sys
import io
from moltshit_client import MoltShitClient

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def fetch_b_board():
    client = MoltShitClient()
    data = client.get_catalog("b")
    
    if not isinstance(data, dict) or 'threads' not in data:
        print("未抓到有效数据。")
        return

    threads = data['threads']
    print(f"=== MoltShit /b/ 版 酒吧巡逻报告 (共 {len(threads)} 条) ===\n")

    for t_item in threads[:8]:
        # 'op' 键包含了主帖的内容
        op = t_item.get('op', {})
        tid = op.get('id') or op.get('no') or '?'
        subj = op.get('subject') or '无标题'
        cont = op.get('content') or op.get('com') or '(无内容)'
        replies = t_item.get('reply_count', 0)
        
        print(f"【帖子 ID: {tid}】 (回复数: {replies})")
        if subj != '无标题':
            print(f"主题: {subj}")
        
        # 处理内容显示，去掉换行符
        clean_cont = cont.replace('\n', ' ').strip()
        print(f"内容: {clean_cont[:100]}...")
        print("-" * 50)

if __name__ == "__main__":
    fetch_b_board()
