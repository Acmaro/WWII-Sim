#!/usr/bin/env python3
"""
测试 /api/choose 端点的响应格式
"""
import requests
import json

def test_choose_endpoint():
    """测试选择分支端点"""

    print("=" * 70)
    print("开始测试 /api/choose 端点")
    print("=" * 70)

    # 1. 先开始一个游戏
    print("\n1. 开始游戏...")
    start_response = requests.post(
        "http://localhost:8001/api/start",
        json={"player_country": "UK"}
    )

    if start_response.status_code != 200:
        print(f"[ERROR] 开始游戏失败: {start_response.status_code}")
        print(start_response.text)
        return

    start_data = start_response.json()
    session_id = start_data["session_id"]
    print(f"[OK] 游戏已开始，会话ID: {session_id}")

    # 2. 获取分支
    print("\n2. 获取分支...")
    branches_response = requests.post(
        "http://localhost:8001/api/branches",
        json={
            "session_id": session_id,
            "current_node_id": start_data["start_node"]["id"]
        }
    )

    if branches_response.status_code != 200:
        print(f"[ERROR] 获取分支失败: {branches_response.status_code}")
        print(branches_response.text)
        return

    branches_data = branches_response.json()
    print(f"[OK] 获取到 {len(branches_data['branches'])} 个分支")

    if len(branches_data['branches']) == 0:
        print("[ERROR] 没有分支可选择")
        return

    # 3. 选择第一个分支
    first_branch = branches_data['branches'][0]
    print(f"\n3. 选择分支: {first_branch['name']}")
    print(f"   分支ID: {first_branch['id']}")

    choose_response = requests.post(
        "http://localhost:8001/api/choose",
        json={
            "session_id": session_id,
            "node_id": start_data["start_node"]["id"],
            "choice_id": first_branch['id']
        }
    )

    print(f"\n4. 检查响应...")
    print(f"   状态码: {choose_response.status_code}")

    if choose_response.status_code != 200:
        print(f"[ERROR] 选择分支失败: {choose_response.status_code}")
        print(choose_response.text)
        return

    # 4. 检查响应格式
    choose_data = choose_response.json()
    print(f"\n5. 响应内容:")
    print(json.dumps(choose_data, indent=2, ensure_ascii=False))

    # 5. 验证必需字段
    print(f"\n6. 验证字段:")
    required_fields = {
        "success": bool,
        "current_node": str,
        "result_node": dict,
        "action_result": dict,
        "reaction_nodes": list,
        "world_state": dict,
        "message": str
    }

    all_ok = True
    for field, expected_type in required_fields.items():
        if field not in choose_data:
            print(f"   [ERROR] 缺少字段: {field}")
            all_ok = False
        elif not isinstance(choose_data[field], expected_type):
            print(f"   [ERROR] 字段类型错误: {field} (期望 {expected_type}, 实际 {type(choose_data[field])})")
            all_ok = False
        else:
            print(f"   [OK] {field}: {expected_type.__name__}")

    # 6. 检查错误字段
    if "reaction_events" in choose_data:
        print(f"\n   [WARNING]  警告: 响应中包含旧字段 'reaction_events'，应该是 'reaction_nodes'")
        all_ok = False

    print("\n" + "=" * 70)
    if all_ok:
        print("[OK] 测试通过！所有字段格式正确")
    else:
        print("[ERROR] 测试失败！响应格式不正确")
    print("=" * 70)

    return all_ok


if __name__ == "__main__":
    try:
        test_choose_endpoint()
    except requests.exceptions.ConnectionError:
        print("[ERROR] 无法连接到服务器，请确保服务器正在运行在 http://localhost:8001")
    except Exception as e:
        print(f"[ERROR] 测试出错: {e}")
        import traceback
        traceback.print_exc()
