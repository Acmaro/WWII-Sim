"""
AI驱动的结局生成服务
"""

from typing import Dict, List
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from backend.core.agent import WorldState, CountryAgent, GameEnding


class EndingGenerator:
    """结局生成器"""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def generate_ending(
        self,
        world_state: WorldState,
        trigger_reason: str,
        player_country: str
    ) -> GameEnding:
        """
        基于当前世界状态生成游戏结局

        Args:
            world_state: 当前世界状态
            trigger_reason: 结局触发原因
            player_country: 玩家控制的国家

        Returns:
            GameEnding: 生成的结局数据
        """

        # 收集游戏状态信息
        game_summary = self._build_game_summary(world_state, player_country)

        # 使用LLM生成结局叙事
        narrative = self._generate_narrative(
            game_summary,
            trigger_reason,
            world_state,
            player_country
        )

        # 生成各国后续发展
        epilogue = self._generate_epilogue(world_state, player_country)

        # 确定结局类型和胜利者
        ending_type, winner = self._determine_ending_type(
            world_state,
            trigger_reason,
            player_country
        )

        # 收集关键事件
        key_events = self._collect_key_events(world_state)

        # 生成最终统计
        final_stats = self._build_final_stats(world_state)

        return GameEnding(
            ending_type=ending_type,
            winner=winner,
            trigger_reason=trigger_reason,
            narrative=narrative,
            epilogue=epilogue,
            final_stats=final_stats,
            key_events=key_events
        )

    def _build_game_summary(self, world_state: WorldState, player_country: str) -> str:
        """构建游戏摘要"""
        summary_lines = [
            f"游戏时间: {world_state.current_year}年{world_state.current_month}月",
            f"总回合数: {world_state.current_turn}",
            f"玩家国家: {player_country}",
            "",
            "各国状态:"
        ]

        for country, agent in world_state.agents.items():
            resources = agent.resources
            summary_lines.append(
                f"  {agent.country_name} ({country}):"
            )
            summary_lines.append(
                f"    军事: {resources.get('military', 100)}, "
                f"经济: {resources.get('economic', 100)}, "
                f"外交: {resources.get('diplomatic', 100)}"
            )

            # 添加行动历史
            if agent.action_history:
                recent_actions = agent.action_history[-3:]  # 最近3个行动
                summary_lines.append(
                    f"    最近行动: {', '.join(recent_actions)}"
                )

        summary_lines.append("")
        summary_lines.append("外交关系:")
        for country1 in world_state.diplomatic_relations:
            for country2, value in world_state.diplomatic_relations[country1].items():
                if country1 < country2:  # 避免重复
                    agent1 = world_state.get_agent(country1)
                    agent2 = world_state.get_agent(country2)
                    summary_lines.append(
                        f"  {agent1.country_name} ↔ {agent2.country_name}: {value:.2f}"
                    )

        return "\n".join(summary_lines)

    def _generate_narrative(
        self,
        game_summary: str,
        trigger_reason: str,
        world_state: WorldState,
        player_country: str
    ) -> str:
        """使用LLM生成结局叙事"""

        player_agent = world_state.get_agent(player_country)

        # 分析玩家的战略特征
        strategy_analysis = self._analyze_player_strategy(player_agent, world_state, player_country)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一位历史小说家，擅长将二战历史改编成引人入胜的故事。

请基于提供的游戏信息，创作一段精彩的历史叙事（600-900字）：

**叙事结构：**
1. **开篇**（10%）：简短回顾已发生的关键事件
2. **主体**（70%）：重点描写从当前时点到战争结束的虚构历史进程
   - 描绘各国接下来的命运走向
   - 想象关键战役、会议、转折点
   - 展现国际格局的演变
3. **结尾**（20%）：战后世界新秩序和各国的长远命运

**写作要求：**
- 使用史诗叙事风格，像在讲述真实历史
- 用国家名称，不要用"玩家"、"他"等代词
- 不要使用"第X回合"、"选择了"等游戏术语
- 不要简单列举发生了什么，而是讲述一个完整的故事
- 描绘具体的场景、人物、事件
- 重点在于**模拟未来**，而非复述过去

**禁止：**
- "玩家选择了..."
- "第一回合..."
- "他们决定..."
- 直接引用数据（"军事100"）
- 流水账式叙述

**示例风格：**
"1939年秋，欧洲的天空笼罩在战争的阴云之下。德意志帝国在占领波兰后，迅速将目光投向西欧...接下来的数年间，..."（而非"德国在第一回合选择了进攻波兰..."）"""),
            ("human", """游戏背景信息：
{game_summary}

{player_name}的战略特征：
{strategy_analysis}

结局触发：{trigger_reason}

请创作一个完整的历史故事，重点描写从1939年到战争结束的历史进程，以及战后的世界格局。""")
        ])

        chain = prompt | self.llm

        response = chain.invoke({
            "game_summary": game_summary,
            "strategy_analysis": strategy_analysis,
            "trigger_reason": trigger_reason,
            "player_name": player_agent.country_name
        })

        return response.content.strip()

    def _analyze_player_strategy(
        self,
        agent: "CountryAgent",
        world_state: WorldState,
        country_code: str
    ) -> str:
        """分析玩家的战略特征"""

        analysis_lines = []

        # 1. 行动历史分析
        if agent.action_history:
            actions = agent.action_history
            analysis_lines.append(f"总行动数：{len(actions)}")

            # 统计行动类型
            military_count = sum(1 for a in actions if any(k in a for k in ['军事', '进攻', '防御', '战争']))
            diplomatic_count = sum(1 for a in actions if any(k in a for k in ['外交', '协议', '谈判', '联盟']))
            economic_count = sum(1 for a in actions if any(k in a for k in ['经济', '生产', '工业', '资源']))

            analysis_lines.append(f"军事行动：{military_count}次")
            analysis_lines.append(f"外交行动：{diplomatic_count}次")
            analysis_lines.append(f"经济行动：{economic_count}次")

            # 判断主导战略
            if military_count > diplomatic_count and military_count > economic_count:
                analysis_lines.append("主导战略：军事扩张路线")
            elif diplomatic_count > military_count and diplomatic_count > economic_count:
                analysis_lines.append("主导战略：外交优先路线")
            elif economic_count > military_count and economic_count > diplomatic_count:
                analysis_lines.append("主导战略：经济发展路线")
            else:
                analysis_lines.append("主导战略：平衡发展路线")

            # 最近的行动
            recent = actions[-3:] if len(actions) >= 3 else actions
            analysis_lines.append(f"最近行动：{', '.join(recent)}")

        # 2. 外交状况
        allies = []
        enemies = []
        for other_country in world_state.agents.keys():
            if other_country != country_code:
                relation = world_state.get_relation(country_code, other_country)
                other_name = world_state.get_agent(other_country).country_name
                if relation > 0.3:
                    allies.append(other_name)
                elif relation < -0.5:
                    enemies.append(other_name)

        if allies:
            analysis_lines.append(f"盟友关系：与{', '.join(allies)}建立了友好关系")
        if enemies:
            analysis_lines.append(f"敌对关系：与{', '.join(enemies)}关系紧张")

        # 3. 资源状况（作为辅助）
        resources = agent.resources
        analysis_lines.append(
            f"最终状态：军事{resources.get('military', 100)}, "
            f"经济{resources.get('economic', 100)}, "
            f"外交{resources.get('diplomatic', 100)}"
        )

        return "\n".join(analysis_lines)

    def _generate_epilogue(
        self,
        world_state: WorldState,
        player_country: str
    ) -> Dict[str, str]:
        """生成各国的后续发展（使用LLM生成个性化内容）"""

        epilogue = {}

        for country, agent in world_state.agents.items():
            # 为每个国家生成个性化的后续发展
            epilogue_text = self._generate_country_epilogue(
                agent, world_state, country, country == player_country
            )
            epilogue[country] = epilogue_text

        return epilogue

    def _generate_country_epilogue(
        self,
        agent: "CountryAgent",
        world_state: WorldState,
        country_code: str,
        is_player: bool
    ) -> str:
        """为单个国家生成后续发展"""

        # 分析该国的特征
        resources = agent.resources
        military = resources.get('military', 100)
        economic = resources.get('economic', 100)

        # 分析行动历史
        action_summary = ""
        if agent.action_history:
            military_count = sum(1 for a in agent.action_history if any(k in a for k in ['军事', '进攻', '防御', '战争']))
            diplomatic_count = sum(1 for a in agent.action_history if any(k in a for k in ['外交', '协议', '谈判', '联盟']))
            economic_count = sum(1 for a in agent.action_history if any(k in a for k in ['经济', '生产', '工业', '资源']))

            if military_count > diplomatic_count and military_count > economic_count:
                action_summary = "采取了军事扩张战略"
            elif diplomatic_count > 0:
                action_summary = "注重外交斡旋"
            elif economic_count > 0:
                action_summary = "专注经济建设"

        # 外交关系
        allies = []
        enemies = []
        for other_country in world_state.agents.keys():
            if other_country != country_code:
                relation = world_state.get_relation(country_code, other_country)
                other_name = world_state.get_agent(other_country).country_name
                if relation > 0.3:
                    allies.append(other_name)
                elif relation < -0.5:
                    enemies.append(other_name)

        # 使用LLM生成个性化描述
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是历史学家，专门撰写二战后各国的命运。

请用1-2句话（50-80字）描述这个国家战后的发展和命运。

要求：
- 基于该国在战争中的表现和最终状态
- 描述要具体、生动，避免模板化
- 不要使用"该国"、"这个国家"等代词，直接用国家名
- 不要引用具体数值
- 描绘长远影响（几十年的视角）"""),
            ("human", """国家：{country_name}

战争期间表现：{action_summary}
最终军事状况：{military_status}
最终经济状况：{economic_status}
盟友关系：{allies}
敌对关系：{enemies}
是否为玩家国家：{is_player}

请描述这个国家战后的命运和发展。""")
        ])

        # 判断状态
        military_status = "强大" if military >= 120 else ("中等" if military >= 60 else "虚弱")
        economic_status = "繁荣" if economic >= 120 else ("稳定" if economic >= 60 else "困难")

        chain = prompt | self.llm

        try:
            response = chain.invoke({
                "country_name": agent.country_name,
                "action_summary": action_summary or "采取平衡发展策略",
                "military_status": military_status,
                "economic_status": economic_status,
                "allies": "、".join(allies) if allies else "无明显盟友",
                "enemies": "、".join(enemies) if enemies else "无明显敌对",
                "is_player": "是" if is_player else "否"
            })

            return response.content.strip()
        except Exception as e:
            # 如果LLM调用失败，使用简单的备用方案
            if military <= 20 or economic <= 20:
                return f"{agent.country_name}在战后陷入长期重建，需要数十年才能恢复元气。"
            elif military >= 150 and economic >= 150:
                return f"{agent.country_name}成为战后的超级大国，主导了新的世界秩序。"
            else:
                return f"{agent.country_name}在战后走上了复兴之路，逐步恢复国力。"

    def _determine_ending_type(
        self,
        world_state: WorldState,
        trigger_reason: str,
        player_country: str
    ) -> tuple[str, str]:
        """
        确定结局类型和胜利者

        综合考虑：
        1. 资源状态（但不是唯一标准）
        2. 外交关系网络
        3. 行动历史（战略选择）
        4. 回合结果趋势
        """

        player_agent = world_state.get_agent(player_country)

        # 检查是否有国家完全崩溃（明确的失败）
        for country, agent in world_state.agents.items():
            if agent.resources.get('military', 100) <= 0 or agent.resources.get('economic', 100) <= 0:
                if country == player_country:
                    return "defeat", None
                # 即使敌国崩溃，也不一定算胜利，要看整体情况

        # 评估玩家的战略得分
        player_score = self._calculate_strategic_score(player_agent, world_state, player_country)

        # 评估其他国家的平均得分
        other_scores = []
        for country, agent in world_state.agents.items():
            if country != player_country:
                score = self._calculate_strategic_score(agent, world_state, country)
                other_scores.append(score)

        avg_other_score = sum(other_scores) / len(other_scores) if other_scores else 0

        print(f"[结局判断] 玩家战略得分: {player_score:.1f}")
        print(f"[结局判断] 其他国家平均得分: {avg_other_score:.1f}")

        # 基于战略得分判断结局
        score_diff = player_score - avg_other_score

        if score_diff > 15:
            return "victory", player_country
        elif score_diff < -15:
            return "defeat", None
        else:
            return "historical", None

    def _calculate_strategic_score(
        self,
        agent: "CountryAgent",
        world_state: WorldState,
        country_code: str
    ) -> float:
        """
        计算战略得分（0-100）

        考虑多个维度：
        - 资源平衡性（30分）
        - 外交关系（25分）
        - 战略一致性（25分）
        - 行动多样性（20分）
        """
        score = 0.0

        # 1. 资源平衡性（30分）- 不只看总量，还看平衡
        resources = agent.resources
        military = resources.get('military', 100)
        economic = resources.get('economic', 100)
        diplomatic = resources.get('diplomatic', 100)

        # 资源总量（15分）
        total_resources = military + economic + diplomatic
        score += min(15, total_resources / 20)

        # 资源平衡性（15分）- 三项都不能太低
        min_resource = min(military, economic, diplomatic)
        if min_resource >= 80:
            score += 15
        elif min_resource >= 60:
            score += 10
        elif min_resource >= 40:
            score += 5

        # 2. 外交关系（25分）
        diplomatic_score = 0
        relation_count = 0

        for other_country in world_state.agents.keys():
            if other_country != country_code:
                relation = world_state.get_relation(country_code, other_country)
                relation_count += 1

                # 正面关系加分，负面关系减分
                if relation > 0.5:
                    diplomatic_score += 15  # 强盟友
                elif relation > 0:
                    diplomatic_score += 8   # 友好
                elif relation > -0.5:
                    diplomatic_score += 0   # 中立
                else:
                    diplomatic_score -= 5   # 敌对

        if relation_count > 0:
            score += min(25, max(0, diplomatic_score / relation_count * 25))

        # 3. 战略一致性（25分）- 分析行动历史
        if agent.action_history:
            actions = agent.action_history

            # 统计行动类型分布
            action_types = {}
            for action in actions:
                # 简单判断行动类型（基于关键词）
                if any(keyword in action for keyword in ['军事', '进攻', '防御', '部队', '战争']):
                    action_types['military'] = action_types.get('military', 0) + 1
                elif any(keyword in action for keyword in ['外交', '协议', '谈判', '联盟', '关系']):
                    action_types['diplomatic'] = action_types.get('diplomatic', 0) + 1
                elif any(keyword in action for keyword in ['经济', '生产', '工业', '资源', '贸易']):
                    action_types['economic'] = action_types.get('economic', 0) + 1

            total_actions = len(actions)
            if total_actions > 0:
                # 有明确战略方向（某一类型占主导但不是全部）加分
                if action_types:
                    max_type_count = max(action_types.values())
                    max_ratio = max_type_count / total_actions

                    if 0.4 <= max_ratio <= 0.7:  # 有主导战略但也有灵活性
                        score += 20
                    elif 0.3 <= max_ratio < 0.4 or 0.7 < max_ratio <= 0.8:
                        score += 12
                    else:
                        score += 5  # 过于分散或过于单一
                else:
                    score += 5

                # 行动数量加分（更活跃）
                score += min(5, total_actions / 2)

        # 4. 行动多样性（20分）- 不重复单一策略
        if agent.action_history:
            unique_actions = len(set(agent.action_history))
            diversity_ratio = unique_actions / len(agent.action_history)
            score += diversity_ratio * 20

        return min(100, score)

    def _collect_key_events(self, world_state: WorldState) -> List[str]:
        """收集关键历史事件"""
        key_events = []

        # 从所有Agent的行动历史中提取（混合时间顺序）
        # 收集每个国家的所有行动
        all_actions = []
        for country, agent in world_state.agents.items():
            if agent.action_history:
                for i, action in enumerate(agent.action_history):
                    all_actions.append({
                        'country': agent.country_name,
                        'action': action,
                        'turn': i + 1  # 估计回合数
                    })

        # 按回合排序（时间顺序）
        all_actions.sort(key=lambda x: x['turn'])

        # 选择最重要的事件（优先军事和外交）
        important_actions = []
        for action_info in all_actions:
            action = action_info['action']
            # 军事和外交行动优先
            if any(keyword in action for keyword in ['军事', '进攻', '防御', '战争', '外交', '协议', '联盟']):
                important_actions.append(action_info)
            elif len(important_actions) < 10:  # 确保至少有一些事件
                important_actions.append(action_info)

        # 限制数量，选择最多8个关键事件
        important_actions = important_actions[:8]

        # 格式化为字符串
        for action_info in important_actions:
            key_events.append(f"{action_info['country']}：{action_info['action']}")

        return key_events

    def _build_final_stats(self, world_state: WorldState) -> Dict[str, any]:
        """构建最终统计数据"""
        stats = {
            "total_turns": world_state.current_turn,
            "end_date": f"{world_state.current_year}年{world_state.current_month}月",
            "countries": {}
        }

        for country, agent in world_state.agents.items():
            stats["countries"][country] = {
                "name": agent.country_name,
                "resources": {
                    "military": agent.resources.get('military', 100),
                    "economic": agent.resources.get('economic', 100),
                    "diplomatic": agent.resources.get('diplomatic', 100)
                },
                "total_actions": len(agent.action_history)
            }

        return stats
