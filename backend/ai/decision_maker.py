"""
AI决策系统
"""

import json
from typing import List
from langchain.prompts import ChatPromptTemplate

from backend.core.agent import CountryAgent, WorldState
from backend.core.models import GameEvent


class AIDecisionMaker:
    """AI决策系统"""

    def __init__(self, llm):
        self.llm = llm

    def select_best_action(
        self,
        agent: CountryAgent,
        options: List[GameEvent],
        world_state: WorldState
    ) -> GameEvent:
        """选择最佳行动"""

        print(f"\n[AI决策] {agent.country_name} 正在分析 {len(options)} 个选项...")

        # 构建决策提示词
        prompt = ChatPromptTemplate.from_template("""
你是{country_name}的最高决策者AI。

【当前态势】
时间: {year}年{month}月
军事实力: {military_power}
经济实力: {economic_strength}
外交点数: {diplomatic_points}

【外交关系】
{diplomatic_relations}

【战略目标】
{objectives}

【性格特征】
激进度: {aggression} (0-1, 越高越倾向军事行动)
外交倾向: {diplomacy} (0-1, 越高越倾向外交手段)
经济重视度: {economic_focus} (0-1, 越高越重视经济发展)
风险承受度: {risk_tolerance} (0-1, 越高越敢冒险)

【可选行动】
{options}

【评估标准】
1. 目标契合度: 行动是否有助于实现战略目标
2. 风险评估: 行动的潜在风险是否在承受范围内
3. 时机判断: 当前是否是执行该行动的最佳时机
4. 国际影响: 行动对外交关系的影响
5. 资源消耗: 行动所需资源是否充足
6. 性格匹配: 行动是否符合Agent的性格特征

根据性格特征选择:
- 如果 aggression 高: 优先考虑 military 类型
- 如果 diplomacy 高: 优先考虑 diplomatic 类型
- 如果 economic_focus 高: 优先考虑 economic 类型

请分析每个选项，选择最优行动。

输出格式（纯JSON，不要markdown标记）:
{{
  "selected_action_id": "行动ID",
  "reasoning": "选择理由（50字内）",
  "expected_outcome": "预期结果",
  "risk_level": 0.5
}}
""")

        # 格式化选项
        options_text = self._format_options(options)

        # 格式化外交关系
        relations_text = self._format_relations(agent, world_state)

        # 调用LLM
        try:
            response = self.llm.invoke(
                prompt.format(
                    country_name=agent.country_name,
                    year=agent.current_year,
                    month=agent.current_month,
                    military_power=agent.resources.get("military", 100),
                    economic_strength=agent.resources.get("economic", 100),
                    diplomatic_points=agent.resources.get("diplomatic", 100),
                    diplomatic_relations=relations_text,
                    objectives="\n".join(f"- {obj}" for obj in agent.objectives),
                    aggression=agent.personality.get("aggression", 0.5),
                    diplomacy=agent.personality.get("diplomacy", 0.5),
                    economic_focus=agent.personality.get("economic_focus", 0.5),
                    risk_tolerance=agent.risk_tolerance,
                    options=options_text
                )
            )

            # 解析响应
            content = response.content.strip()

            # 移除可能的markdown代码块标记
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

            decision = json.loads(content)
            selected_id = decision["selected_action_id"]

            # 记录决策理由
            print(f"[AI决策] {agent.country_name} 选择: {selected_id}")
            print(f"  理由: {decision['reasoning']}")
            print(f"  风险: {decision.get('risk_level', 0.5):.1%}\n")

            # 查找选择的行动
            selected_action = next(
                (opt for opt in options if opt.id == selected_id),
                None
            )

            if selected_action is None:
                print(f"[AI决策] 警告: 未找到ID={selected_id}的行动，使用第一个选项")
                selected_action = options[0]

            return selected_action

        except Exception as e:
            print(f"[AI决策] 错误: {e}")
            print(f"[AI决策] 降级使用第一个选项")
            return options[0]

    def _format_options(self, options: List[GameEvent]) -> str:
        """格式化选项列表"""
        lines = []
        for i, opt in enumerate(options, 1):
            lines.append(
                f"{i}. [{opt.event_type}] {opt.name} (ID: {opt.id})\n"
                f"   描述: {opt.description}\n"
                f"   历史可能性: {opt.likelihood:.1%}"
            )
        return "\n\n".join(lines)

    def _format_relations(self, agent: CountryAgent, world: WorldState) -> str:
        """格式化外交关系"""
        lines = []
        for country, other_agent in world.agents.items():
            if country == agent.country_code:
                continue

            relation = world.get_relation(agent.country_code, country)
            status = self._relation_status(relation)

            lines.append(
                f"与{other_agent.country_name}: {relation:+.2f} ({status})"
            )

        return "\n".join(lines) if lines else "无外交关系记录"

    def _relation_status(self, value: float) -> str:
        """关系状态描述"""
        if value >= 0.7:
            return "盟友"
        elif value >= 0.3:
            return "友好"
        elif value >= -0.3:
            return "中立"
        elif value >= -0.7:
            return "敌对"
        else:
            return "交战"
