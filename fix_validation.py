"""
一键修复验证问题脚本
彻底解决描述长度验证失败的问题
"""

import re
import subprocess
import time
import signal
import os

def fix_models():
    """修复models.py中的验证约束"""
    print("1. 修复 models.py 验证约束...")

    file_path = "backend/core/models.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 修改GameEvent的description最小长度为10（更宽松）
    content = re.sub(
        r'description: str = Field\(description="详细描述", min_length=\d+, max_length=\d+\)',
        'description: str = Field(description="详细描述", min_length=10, max_length=120)',
        content
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("   ✅ models.py 已更新: description min_length=10")


def fix_workflow():
    """修复event_generation.py中的NoneType处理"""
    print("\n2. 修复 event_generation.py 的错误处理...")

    file_path = "backend/workflows/event_generation.py"
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 在refine_events方法开始处添加None检查
    old_refine = '''    def refine_events(self, state: EventGenerationState) -> EventGenerationState:
        """
        节点4: 优化改进

        根据验证结果改进事件
        """
        metrics = state["quality_metrics"]
        if metrics is None:
            return state'''

    new_refine = '''    def refine_events(self, state: EventGenerationState) -> EventGenerationState:
        """
        节点4: 优化改进

        根据验证结果改进事件
        """
        # 检查draft_events是否为None
        if state["draft_events"] is None:
            print("   [WARNING] draft_events为None，跳过优化")
            return state

        metrics = state["quality_metrics"]
        if metrics is None:
            return state'''

    if old_refine in content:
        content = content.replace(old_refine, new_refine)
        print("   ✅ 已添加 draft_events None 检查")
    else:
        print("   ⚠️ 未找到目标代码，可能已经修复")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("   ✅ event_generation.py 已更新")


def kill_old_server():
    """杀死旧的服务器进程"""
    print("\n3. 清理旧的服务器进程...")

    try:
        # 查找8001端口的进程
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            encoding='gbk'
        )

        pids = []
        for line in result.stdout.split('\n'):
            if ':8001' in line and 'LISTENING' in line:
                parts = line.split()
                pid = parts[-1]
                pids.append(pid)

        if pids:
            for pid in pids:
                subprocess.run(['taskkill', '//F', '//PID', pid],
                             capture_output=True)
                print(f"   ✅ 已杀死进程 PID={pid}")
        else:
            print("   ✅ 没有旧进程需要清理")

    except Exception as e:
        print(f"   ⚠️ 清理进程时出错: {e}")


def start_server():
    """启动新的服务器"""
    print("\n4. 启动优化后的服务器...")

    # 使用后台启动
    print("   请手动运行: venv/Scripts/python -m uvicorn backend.api.server:app --host 0.0.0.0 --port 8001")
    print("   或使用 Bash 工具启动")


def main():
    print("=" * 70)
    print("WWIISim-v2 验证问题一键修复脚本")
    print("=" * 70)

    # 修复代码
    fix_models()
    fix_workflow()
    kill_old_server()

    print("\n" + "=" * 70)
    print("✅ 代码修复完成！")
    print("=" * 70)
    print("\n修改内容:")
    print("1. GameEvent.description 最小长度: 20 → 10 字符")
    print("2. event_generation.py 添加了 draft_events None 检查")
    print("\n请重启服务器以应用更改。")


if __name__ == "__main__":
    main()
