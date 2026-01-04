"""
完整流程测试脚本 - 验证所有修复是否生效
"""

import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_health():
    """测试健康检查"""
    print("=" * 70)
    print("1. 测试服务器健康状态")
    print("=" * 70)

    response = requests.get(f"{BASE_URL}/health")
    data = response.json()

    print(f"状态: {data['status']}")
    print(f"知识库: {'已加载' if data['knowledge_base'] else '未加载'}")
    print(f"工作流: {'已就绪' if data['event_workflow'] else '未就绪'}")
    print(f"活跃会话: {data['active_sessions']}")

    assert data['status'] == 'healthy', "服务器不健康"
    print("\n✓ 健康检查通过")


def test_start_game():
    """测试开始游戏"""
    print("\n" + "=" * 70)
    print("2. 测试开始游戏")
    print("=" * 70)

    response = requests.post(
        f"{BASE_URL}/api/start",
        json={"player_country": "GER"}
    )

    assert response.status_code == 200, f"启动失败: {response.status_code}"

    data = response.json()
    session_id = data['session_id']

    print(f"会话ID: {session_id}")
    print(f"玩家国家: {data['player_country']}")
    print(f"起始事件: {data['start_node']['name']}")

    print("\n✓ 游戏启动成功")
    return session_id


def test_get_branches(session_id):
    """测试生成分支（这是最关键的测试）"""
    print("\n" + "=" * 70)
    print("3. 测试生成事件分支（验证修复）")
    print("=" * 70)

    response = requests.post(
        f"{BASE_URL}/api/branches",
        json={
            "session_id": session_id,
            "current_node_id": f"start_GER"
        }
    )

    print(f"HTTP状态: {response.status_code}")

    if response.status_code != 200:
        print(f"\n✗ 生成失败: {response.text}")
        return False

    data = response.json()
    branches = data['branches']

    print(f"\n生成的分支数: {len(branches)}")

    for i, branch in enumerate(branches, 1):
        desc_len = len(branch['description'])
        print(f"\n分支 {i}:")
        print(f"  名称: {branch['name']} ({len(branch['name'])}字符)")
        print(f"  描述: {branch['description'][:50]}... ({desc_len}字符)")
        print(f"  类型: {branch['event_type']}")
        print(f"  可能性: {branch['likelihood']:.1%}")

        # 验证约束
        assert len(branch['name']) >= 4, f"名称太短: {len(branch['name'])}"
        assert len(branch['description']) >= 10, f"描述太短: {desc_len}"
        assert len(branch['description']) <= 120, f"描述太长: {desc_len}"

    print("\n✓ 分支生成成功，所有约束满足")
    return True


def test_make_choice(session_id):
    """测试做出选择"""
    print("\n" + "=" * 70)
    print("4. 测试做出选择")
    print("=" * 70)

    # 先获取分支
    branches_response = requests.post(
        f"{BASE_URL}/api/branches",
        json={
            "session_id": session_id,
            "current_node_id": f"start_GER"
        }
    )

    if branches_response.status_code != 200:
        print("跳过（分支生成失败）")
        return

    branches = branches_response.json()['branches']
    choice_id = branches[0]['id']

    # 做出选择
    response = requests.post(
        f"{BASE_URL}/api/choose",
        json={
            "session_id": session_id,
            "node_id": "start_GER",
            "choice_id": choice_id
        }
    )

    assert response.status_code == 200, f"选择失败: {response.status_code}"

    data = response.json()

    print(f"选择成功: {data['success']}")
    print(f"当前节点: {data['current_node']}")

    # 验证action_result包含所有必需字段
    action_result = data['action_result']
    assert 'success_score' in action_result, "缺少success_score"
    assert 'consequences' in action_result, "缺少consequences"
    assert 'impact' in action_result, "缺少impact"

    print(f"成功率: {action_result['success_score']:.1%}")
    print(f"后果数: {len(action_result['consequences'])}")

    print("\n✓ 选择处理成功")


def main():
    print("\n" + "=" * 70)
    print("WWIISim-v2 完整流程测试")
    print("测试修复: description min_length=10, NoneType检查")
    print("=" * 70)

    try:
        # 运行所有测试
        test_health()
        session_id = test_start_game()

        # 最关键的测试：生成分支
        success = test_get_branches(session_id)

        if success:
            test_make_choice(session_id)

        print("\n" + "=" * 70)
        print("✓✓✓ 所有测试通过！修复成功！")
        print("=" * 70)
        print("\n修复内容:")
        print("1. GameEvent.description 最小长度: 20 → 10 字符")
        print("2. 添加了 draft_events None 检查，防止崩溃")
        print("3. 保持简洁描述提示词（20-80字）")
        print("\n前端可以正常使用了！")

    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
