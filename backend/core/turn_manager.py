"""
回合管理系统
"""

from typing import Dict, Optional
from backend.core.agent import (
    WorldState, CountryAgent, ControlMode,
    TurnPhase, TurnResult
)
from backend.core.models import GameEvent


class TurnManager:
    """回合管理器"""

    def __init__(self, world_state: WorldState):
        self.world = world_state
        self.current_phase = TurnPhase.PLANNING
        self.pending_actions: Dict[str, GameEvent] = {}  # country -> action

    def get_current_turn(self) -> int:
        """获取当前回合"""
        return self.world.current_turn

    def get_current_phase(self) -> TurnPhase:
        """获取当前阶段"""
        return self.current_phase

    def set_phase(self, phase: TurnPhase):
        """设置当前阶段"""
        self.current_phase = phase
        print(f"[回合管理] 进入阶段: {phase.value}")

    def record_action(self, country: str, action: GameEvent):
        """记录国家行动"""
        self.pending_actions[country] = action
        print(f"[回合管理] {country} 提交行动: {action.name}")

    def has_all_actions(self) -> bool:
        """检查是否收集到所有行动"""
        for country, agent in self.world.agents.items():
            # 跳过观察者
            if agent.control_mode == ControlMode.OBSERVER:
                continue

            # 检查是否有行动记录
            if country not in self.pending_actions:
                return False

        return True

    def get_pending_action(self, country: str) -> Optional[GameEvent]:
        """获取待处理行动"""
        return self.pending_actions.get(country)

    def clear_pending_actions(self):
        """清空待处理行动"""
        self.pending_actions.clear()

    def execute_resolution(self) -> TurnResult:
        """执行结算阶段"""
        print(f"\n{'='*70}")
        print(f"回合 {self.world.current_turn} 结算")
        print(f"{'='*70}")

        # 收集所有行动
        all_actions = {}
        for country, action in self.pending_actions.items():
            all_actions[country] = {
                "id": action.id,
                "name": action.name,
                "type": action.event_type,
                "description": action.description
            }
            print(f"  {country}: {action.name} ({action.event_type})")

        # 检测冲突
        conflicts = self._detect_conflicts()

        # 计算外交影响
        diplomatic_changes = self._calculate_diplomatic_impact()

        # 计算经济影响
        economic_changes = self._calculate_economic_impact()

        # 检查游戏是否结束
        is_game_over, ending_trigger = self._check_game_ending()

        # 创建结果
        result = TurnResult(
            turn_number=self.world.current_turn,
            all_actions=all_actions,
            conflicts=conflicts,
            diplomatic_changes=diplomatic_changes,
            economic_changes=economic_changes,
            major_events=[],
            is_game_over=is_game_over,
            ending_trigger=ending_trigger
        )

        if is_game_over:
            print(f"\n[游戏结束] {ending_trigger}")

        print(f"{'='*70}\n")

        return result

    def _check_game_ending(self) -> tuple[bool, Optional[str]]:
        """检查游戏是否结束"""

        # 1. 时间限制：到达1945年5月（二战欧洲战场结束）
        if self.world.current_year >= 1945 and self.world.current_month >= 5:
            return True, "时间到达1945年5月，欧洲战场战争结束"

        # 2. 回合限制：超过100回合
        if self.world.current_turn >= 100:
            return True, "游戏达到最大回合数限制"

        # 3. 军事胜利：某国军事资源为0
        for country, agent in self.world.agents.items():
            if agent.resources.get("military", 100) <= 0:
                return True, f"{agent.country_name}军事力量完全崩溃"

        # 4. 经济崩溃：某国经济资源为0
        for country, agent in self.world.agents.items():
            if agent.resources.get("economic", 100) <= 0:
                return True, f"{agent.country_name}经济彻底崩溃"

        # 5. 军事霸权：某国军事资源超过250
        for country, agent in self.world.agents.items():
            if agent.resources.get("military", 100) >= 250:
                return True, f"{agent.country_name}建立了压倒性的军事优势"

        # 6. 全面战争：所有国家都进行军事行动且资源低
        military_count = sum(
            1 for action in self.pending_actions.values()
            if action.event_type == "military"
        )
        if military_count == len(self.pending_actions):
            # 检查是否所有国家资源都很低
            low_resource_count = sum(
                1 for agent in self.world.agents.values()
                if agent.resources.get("military", 100) < 50
                and agent.resources.get("economic", 100) < 50
            )
            if low_resource_count >= 2:
                return True, "各国陷入全面战争，资源枯竭"

        # 7. 外交孤立：某国与所有其他国家关系都低于-0.8
        for country1 in self.world.agents.keys():
            isolated = True
            for country2 in self.world.agents.keys():
                if country1 != country2:
                    relation = self.world.get_relation(country1, country2)
                    if relation >= -0.8:
                        isolated = False
                        break
            if isolated:
                agent = self.world.get_agent(country1)
                return True, f"{agent.country_name}陷入完全外交孤立"

        return False, None

    def _detect_conflicts(self) -> list:
        """检测军事冲突"""
        conflicts = []

        # 简化版：检查是否有多个国家选择了军事行动
        military_actions = []
        for country, action in self.pending_actions.items():
            if action.event_type == "military":
                military_actions.append((country, action))

        if len(military_actions) >= 2:
            # 有多个国家进行军事行动，可能发生冲突
            for country, action in military_actions:
                conflicts.append({
                    "country": country,
                    "action": action.name,
                    "description": f"{country}进行军事行动: {action.name}"
                })

        return conflicts

    def _calculate_diplomatic_impact(self) -> list:
        """计算外交影响"""
        changes = []

        # 简化版：军事行动降低关系，外交行动提升关系
        for country1, action1 in self.pending_actions.items():
            for country2 in self.world.agents.keys():
                if country1 == country2:
                    continue

                old_value = self.world.get_relation(country1, country2)

                # 根据行动类型调整关系
                delta = 0.0
                if action1.event_type == "military":
                    delta = -0.1  # 军事行动降低关系
                elif action1.event_type == "diplomatic":
                    delta = 0.05  # 外交行动提升关系

                if delta != 0:
                    self.world.update_relations(country1, country2, delta)
                    new_value = self.world.get_relation(country1, country2)

                    changes.append({
                        "country1": country1,
                        "country2": country2,
                        "old_value": round(old_value, 2),
                        "new_value": round(new_value, 2),
                        "delta": round(delta, 2),
                        "reason": f"{country1}的{action1.event_type}行动"
                    })

        return changes

    def _calculate_economic_impact(self) -> list:
        """计算经济影响"""
        changes = []

        for country, action in self.pending_actions.items():
            agent = self.world.get_agent(country)
            if not agent:
                continue

            # 根据行动类型消耗/增加资源
            if action.event_type == "military":
                # 军事行动消耗资源
                old_military = agent.resources.get("military", 100)
                agent.resources["military"] = max(0, old_military - 10)

                changes.append({
                    "country": country,
                    "resource": "military",
                    "old_value": old_military,
                    "new_value": agent.resources["military"],
                    "delta": -10,
                    "reason": f"军事行动: {action.name}"
                })

            elif action.event_type == "economic":
                # 经济行动增加资源
                old_economic = agent.resources.get("economic", 100)
                agent.resources["economic"] = min(200, old_economic + 5)

                changes.append({
                    "country": country,
                    "resource": "economic",
                    "old_value": old_economic,
                    "new_value": agent.resources["economic"],
                    "delta": 5,
                    "reason": f"经济行动: {action.name}"
                })

        return changes

    def advance_time(self):
        """推进时间"""
        self.world.current_month += 1

        if self.world.current_month > 12:
            self.world.current_month = 1
            self.world.current_year += 1

        self.world.current_turn += 1

        # 更新所有Agent的时间
        for agent in self.world.agents.values():
            agent.current_year = self.world.current_year
            agent.current_month = self.world.current_month

        print(f"[回合管理] 时间推进到 {self.world.current_year}年{self.world.current_month}月")

    def get_world_state(self) -> WorldState:
        """获取世界状态"""
        return self.world
