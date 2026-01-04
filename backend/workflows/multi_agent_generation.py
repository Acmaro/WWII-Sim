"""
多Agent事件生成工作流

基于原有EventGenerationWorkflow，增强以支持：
1. Agent性格特征影响生成
2. 世界状态上下文
3. 其他Agent行动考虑
"""

from typing import TypedDict, Annotated, Dict, List
import operator
from langchain.prompts import ChatPromptTemplate

from backend.workflows.event_generation import EventGenerationWorkflow
from backend.core.agent import CountryAgent, WorldState
from backend.core.models import BranchOptions, GameEvent


class MultiAgentGenerationState(TypedDict):
    """多Agent事件生成状态"""
    # 当前Agent信息
    agent: CountryAgent

    # 世界状态
    world_state: WorldState

    # 其他Agent的最近行动
    other_agents_actions: Dict[str, List[str]]  # country -> action names

    # 输入（继承自原workflow）
    country: str
    year: int
    month: int
    history_summary: str

    # 中间状态
    rag_context: str
    draft_events: BranchOptions | None
    quality_metrics: object | None  # QualityMetrics
    quality_score: float

    # 输出
    final_events: BranchOptions | None

    # 计数器
    iterations: Annotated[int, operator.add]


class MultiAgentEventWorkflow(EventGenerationWorkflow):
    """多Agent事件生成工作流"""

    def __init__(self, knowledge_base=None, llm=None):
        """初始化多Agent工作流"""
        # 调用父类初始化（但不使用其graph）
        super().__init__(knowledge_base, llm)
        # 构建自己的图
        self.graph = self._build_multi_agent_graph()

    def _build_multi_agent_graph(self):
        """构建多Agent工作流图"""
        from langgraph.graph import StateGraph, END

        workflow = StateGraph(MultiAgentGenerationState)

        # 添加节点（重用父类方法）
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("generate_draft", self.generate_draft)
        workflow.add_node("validate_quality", self.validate_quality)
        workflow.add_node("refine_events", self.refine_events)
        workflow.add_node("finalize", self.finalize)

        # 定义边
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "generate_draft")
        workflow.add_edge("generate_draft", "validate_quality")

        # 条件边
        workflow.add_conditional_edges(
            "validate_quality",
            self.should_refine,
            {
                "refine": "refine_events",
                "finalize": "finalize"
            }
        )

        workflow.add_edge("refine_events", "validate_quality")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    def generate_for_agent(
        self,
        agent: CountryAgent,
        world_state: WorldState,
        other_actions: Dict[str, List[str]] = None
    ) -> BranchOptions | None:
        """为特定Agent生成事件"""

        print(f"\n[多Agent工作流] 为 {agent.country_name} 生成事件...")

        # 准备初始状态
        initial_state = {
            "agent": agent,
            "world_state": world_state,
            "other_agents_actions": other_actions or {},
            "country": agent.country_code,
            "year": agent.current_year,
            "month": agent.current_month,
            "history_summary": self._build_agent_history(agent),
            "rag_context": "",
            "draft_events": None,
            "quality_metrics": None,
            "quality_score": 0.0,
            "final_events": None,
            "iterations": 0
        }

        # 执行工作流
        result = self.graph.invoke(initial_state)

        return result.get("final_events")

    def _build_agent_history(self, agent: CountryAgent) -> str:
        """构建Agent历史摘要"""
        if not agent.action_history:
            return "游戏开始"

        # 取最近3个行动
        recent = agent.action_history[-3:]
        return "最近行动: " + ", ".join(recent)

    def retrieve_context(self, state: MultiAgentGenerationState):
        """检索上下文（增强版）"""
        agent = state["agent"]
        world = state["world_state"]

        # 1. RAG检索历史事件
        query = f"{agent.country_code} {agent.current_year}.{agent.current_month}"
        rag_results = []

        if self.knowledge_base:
            try:
                rag_results = self.knowledge_base.search(query, top_k=5)
            except Exception as e:
                print(f"[RAG检索] 警告: {e}")

        # 2. 构建世界状态上下文
        world_context = self._build_world_context(agent, world)

        # 3. 其他Agent的行动
        other_actions_context = self._build_other_actions_context(
            agent,
            state["other_agents_actions"]
        )

        # 组合上下文
        context_parts = []

        # RAG历史
        if rag_results:
            context_parts.append("【历史事件参考】")
            for i, result in enumerate(rag_results, 1):
                event = result.event
                context_parts.append(
                    f"{i}. {event.year}.{event.month} - {event.name}\n"
                    f"   {event.description}"
                )

        # 世界状态
        context_parts.append(world_context)

        # 其他国家行动
        if other_actions_context:
            context_parts.append(other_actions_context)

        state["rag_context"] = "\n\n".join(context_parts)

        return state

    def _build_world_context(self, agent: CountryAgent, world: WorldState) -> str:
        """构建世界状态上下文"""
        lines = ["【当前世界态势】"]

        # 外交关系
        lines.append("外交关系:")
        for country, other_agent in world.agents.items():
            if country == agent.country_code:
                continue

            relation = world.get_relation(agent.country_code, country)
            status = self._relation_status(relation)
            lines.append(f"  与{other_agent.country_name}: {relation:+.2f} ({status})")

        # 军事实力对比
        lines.append("\n军事实力对比:")
        for country, power in world.military_power.items():
            lines.append(f"  {country}: {power}")

        return "\n".join(lines)

    def _build_other_actions_context(
        self,
        agent: CountryAgent,
        other_actions: Dict[str, List[str]]
    ) -> str:
        """构建其他Agent行动上下文"""
        if not other_actions:
            return ""

        lines = ["【其他国家最近行动】"]
        for country, actions in other_actions.items():
            if country != agent.country_code and actions:
                latest = actions[-1] if actions else "无记录"
                lines.append(f"  {country}: {latest}")

        return "\n".join(lines)

    def _relation_status(self, value: float) -> str:
        """关系状态"""
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

    def generate_draft(self, state: MultiAgentGenerationState):
        """生成草稿（考虑Agent性格）"""
        agent = state["agent"]

        prompt = ChatPromptTemplate.from_template("""
你是{country_name}的战略顾问AI。

【Agent性格特征】
激进度: {aggression} (0-1, 越高越倾向军事行动)
外交倾向: {diplomacy} (0-1, 越高越倾向外交手段)
经济重视度: {economic_focus} (0-1, 越高越重视经济发展)
风险承受度: {risk_tolerance} (0-1, 越高越敢冒险)

【战略目标】
{objectives}

【历史背景与当前态势】
{rag_context}

【任务】
根据Agent的性格特征和战略目标，生成4个符合角色定位的行动选项。

【要求】
1. **选项类型分布应符合Agent性格**:
   - 如果 aggression >= 0.7: 至少2个 military 选项
   - 如果 diplomacy >= 0.7: 至少2个 diplomatic 选项
   - 如果 economic_focus >= 0.7: 至少2个 economic 选项
   - 否则: 4种类型各1个（military, diplomatic, economic, political）

2. **风险程度匹配 risk_tolerance**:
   - 高风险承受(>0.6): 可以有大胆冒险的选项
   - 低风险承受(<0.4): 选项应该稳健保守

3. 每个选项必须:
   - 符合历史背景和当前态势
   - 考虑与其他国家的关系
   - 描述简洁（20-80字）
   - likelihood 评分合理（0.0-1.0）

{format_instructions}

直接输出JSON，不要添加markdown代码块标记或解释文字。
""")

        try:
            chain = prompt | self.llm | self.parser

            draft = chain.invoke({
                "country_name": agent.country_name,
                "aggression": agent.personality.get("aggression", 0.5),
                "diplomacy": agent.personality.get("diplomacy", 0.5),
                "economic_focus": agent.personality.get("economic_focus", 0.5),
                "risk_tolerance": agent.risk_tolerance,
                "objectives": "\n".join(f"- {obj}" for obj in agent.objectives),
                "rag_context": state.get("rag_context", ""),
                "format_instructions": self.parser.get_format_instructions()
            })

            state["draft_events"] = draft
            state["iterations"] = 1

        except Exception as e:
            print(f"[生成草稿] 失败: {e}")
            state["draft_events"] = None
            state["iterations"] = 1

        return state
