"""
LangGraph事件生成工作流

使用StateGraph实现自动迭代优化的事件生成流程：
检索 → 生成 → 验证 → [优化循环] → 完成
"""

from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser

from backend.core.models import BranchOptions, QualityMetrics, GameEvent
from backend.core.llm import get_llm
from backend.core.config import settings


# ============================================================================
# 状态定义
# ============================================================================

class EventGenerationState(TypedDict):
    """事件生成工作流状态"""
    # 输入
    country: str
    year: int
    month: int
    history_summary: str

    # 中间状态
    rag_context: str
    draft_events: BranchOptions | None
    quality_metrics: QualityMetrics | None
    quality_score: float

    # 输出
    final_events: BranchOptions | None

    # 计数器（累加）
    iterations: Annotated[int, operator.add]


# ============================================================================
# 事件生成工作流类
# ============================================================================

class EventGenerationWorkflow:
    """事件生成工作流"""

    def __init__(self, knowledge_base=None, llm=None):
        """
        初始化工作流

        Args:
            knowledge_base: RAG知识库（可选）
            llm: LLM实例（可选，默认使用全局实例）
        """
        self.knowledge_base = knowledge_base
        self.llm = llm or get_llm()
        self.parser = PydanticOutputParser(pydantic_object=BranchOptions)

        # 构建工作流图
        self.graph = self._build_graph()

    def _build_graph(self):
        """构建LangGraph工作流"""

        workflow = StateGraph(EventGenerationState)

        # 添加节点
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("generate_draft", self.generate_draft)
        workflow.add_node("validate_quality", self.validate_quality)
        workflow.add_node("refine_events", self.refine_events)
        workflow.add_node("finalize", self.finalize)

        # 定义边
        workflow.set_entry_point("retrieve_context")
        workflow.add_edge("retrieve_context", "generate_draft")
        workflow.add_edge("generate_draft", "validate_quality")

        # 条件边：根据质量决定路径
        workflow.add_conditional_edges(
            "validate_quality",
            self.should_refine,
            {
                "refine": "refine_events",
                "finalize": "finalize"
            }
        )

        # 优化后重新验证
        workflow.add_edge("refine_events", "validate_quality")

        # 完成后结束
        workflow.add_edge("finalize", END)

        return workflow.compile()

    # ------------------------------------------------------------------------
    # 节点实现
    # ------------------------------------------------------------------------

    def retrieve_context(self, state: EventGenerationState) -> EventGenerationState:
        """
        节点1: RAG检索历史背景

        从知识库检索相关历史事件，作为生成的上下文
        """
        if self.knowledge_base is None:
            state["rag_context"] = "（知识库未配置）"
            return state

        query = f"{state['country']} {state['year']}.{state['month']}"

        try:
            results = self.knowledge_base.search(query, top_k=5)

            # 格式化上下文
            context_parts = []
            for i, result in enumerate(results, 1):
                event = result.event  # RAGResult是Pydantic对象
                score = result.score
                context_parts.append(
                    f"{i}. {event.year}.{event.month} - "
                    f"{event.name} (相关度: {score:.2f})\n"
                    f"   {event.description}"
                )

            state["rag_context"] = "\n\n".join(context_parts)

        except Exception as e:
            print(f"RAG检索失败: {e}")
            state["rag_context"] = "（检索失败）"

        return state

    def generate_draft(self, state: EventGenerationState) -> EventGenerationState:
        """
        节点2: 生成事件草稿

        使用LLM生成初始事件选项
        """
        # 构建提示词
        prompt = ChatPromptTemplate.from_template(
            """你是一位精通二战历史的专家和游戏设计师。

【历史背景参考】
{rag_context}

【当前游戏态势】
国家: {country}
时间: {year}年{month}月
历史: {history_summary}

【任务】
为{country}生成4个不同的战略选项。

【要求】
1. 4个选项类型必须完全不同:
   - military (军事)
   - diplomatic (外交)
   - economic (经济)
   - political (政治)

2. 每个选项必须:
   - 符合历史背景和当前态势
   - 具有明确的行动和预期结果
   - likelihood评分合理（0.0-1.0）
   - 描述简洁（20-80字，越短越好）

3. 选项应该涵盖不同的战略方向:
   - 激进进攻型
   - 稳健扩张型
   - 防御巩固型
   - 外交政治型

4. reasoning字段说明为什么这些选项合理且多样

{format_instructions}

直接输出JSON，不要添加markdown代码块标记或解释文字。
"""
        )

        try:
            # 构建chain
            chain = prompt | self.llm | self.parser

            # 调用
            draft = chain.invoke({
                "country": state["country"],
                "year": state["year"],
                "month": state["month"],
                "history_summary": state.get("history_summary", "游戏开始"),
                "rag_context": state.get("rag_context", ""),
                "format_instructions": self.parser.get_format_instructions()
            })

            state["draft_events"] = draft
            state["iterations"] = 1  # 累加计数

        except Exception as e:
            print(f"生成失败: {e}")
            # 创建空占位
            state["draft_events"] = None
            state["iterations"] = 1

        return state

    def validate_quality(self, state: EventGenerationState) -> EventGenerationState:
        """
        节点3: 质量验证

        多维度评估生成质量
        """
        if state["draft_events"] is None:
            state["quality_score"] = 0.0
            state["quality_metrics"] = QualityMetrics(
                format_valid=0.0,
                diversity=0.0,
                consistency=0.0,
                historical_accuracy=0.0
            )
            return state

        events = state["draft_events"]

        # 评估各维度
        metrics = QualityMetrics(
            format_valid=self._check_format(events),
            diversity=self._check_diversity(events),
            consistency=self._check_consistency(events, state),
            historical_accuracy=self._check_historical(events)
        )

        state["quality_metrics"] = metrics
        state["quality_score"] = metrics.overall_score

        return state

    def refine_events(self, state: EventGenerationState) -> EventGenerationState:
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
            return state

        # 识别问题
        issues = []
        if metrics.format_valid < 0.8:
            issues.append("格式不完整或不规范")
        if metrics.diversity < 0.8:
            issues.append("选项类型不够多样，存在重复类型")
        if metrics.consistency < 0.8:
            issues.append("时间或国家信息不一致")
        if metrics.historical_accuracy < 0.8:
            issues.append("历史可能性评分不合理")

        if not issues:
            return state

        # 构建改进提示词
        prompt = ChatPromptTemplate.from_template(
            """以下事件存在质量问题，请改进。

【原始事件】
{draft_events}

【发现的问题】
{issues}

【改进要求】
1. 如果类型不够多样: 确保4个选项类型完全不同（military, diplomatic, economic, political各一个）
2. 如果一致性不足: 检查year={year}, month={month}, country={country}是否正确
3. 如果历史准确性不足: 调整likelihood评分，使其更符合历史实际

保持其他高质量的部分不变。

{format_instructions}

直接输出改进后的JSON。
"""
        )

        try:
            chain = prompt | self.llm | self.parser

            improved = chain.invoke({
                "draft_events": state["draft_events"].model_dump_json(indent=2),
                "issues": "\n".join(f"- {issue}" for issue in issues),
                "year": state["year"],
                "month": state["month"],
                "country": state["country"],
                "format_instructions": self.parser.get_format_instructions()
            })

            state["draft_events"] = improved
            state["iterations"] = 1  # 累加

        except Exception as e:
            print(f"优化失败: {e}")
            state["iterations"] = 1

        return state

    def finalize(self, state: EventGenerationState) -> EventGenerationState:
        """
        节点5: 最终确认

        标记完成并保存最终结果
        """
        if state["draft_events"] is not None:
            # 添加元数据
            state["draft_events"].generation_metadata = {
                "iterations": state.get("iterations", 0),
                "quality_score": state.get("quality_score", 0.0),
                "quality_metrics": state["quality_metrics"].model_dump() if state.get("quality_metrics") else None
            }

        state["final_events"] = state["draft_events"]
        return state

    # ------------------------------------------------------------------------
    # 条件判断
    # ------------------------------------------------------------------------

    def should_refine(self, state: EventGenerationState) -> str:
        """
        决定是否需要优化

        Returns:
            "refine" - 继续优化
            "finalize" - 完成
        """
        quality = state.get("quality_score", 0.0)
        iterations = state.get("iterations", 0)

        # 质量达标
        if quality >= settings.QUALITY_THRESHOLD:
            return "finalize"

        # 迭代次数过多
        if iterations >= settings.MAX_GENERATION_RETRIES:
            return "finalize"

        # 需要优化
        return "refine"

    # ------------------------------------------------------------------------
    # 质量检查辅助方法
    # ------------------------------------------------------------------------

    def _check_format(self, events: BranchOptions) -> float:
        """检查格式正确性"""
        if len(events.branches) == 4:
            return 1.0
        return len(events.branches) / 4.0

    def _check_diversity(self, events: BranchOptions) -> float:
        """检查多样性（类型不应重复）"""
        if not events.branches:
            return 0.0

        types = [e.event_type for e in events.branches]
        unique_types = len(set(types))

        # 期望4种不同类型
        return unique_types / 4.0

    def _check_consistency(self, events: BranchOptions, state: EventGenerationState) -> float:
        """检查一致性（时间、国家）"""
        if not events.branches:
            return 0.0

        score = 1.0
        for event in events.branches:
            # 时间一致性
            if event.year != state["year"] or event.month != state["month"]:
                score -= 0.25

        return max(0.0, score)

    def _check_historical(self, events: BranchOptions) -> float:
        """检查历史准确性（likelihood合理性）"""
        if not events.branches:
            return 0.0

        # 检查likelihood是否在合理范围
        likelihoods = [e.likelihood for e in events.branches]
        avg = sum(likelihoods) / len(likelihoods)

        # 平均应该在0.3-0.8之间
        if 0.3 <= avg <= 0.8:
            return 0.9
        else:
            return 0.6

    # ------------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------------

    def generate(
        self,
        country: str,
        year: int,
        month: int,
        history_summary: str = ""
    ) -> BranchOptions | None:
        """
        生成事件分支

        Args:
            country: 国家代码
            year: 年份
            month: 月份
            history_summary: 历史摘要

        Returns:
            生成的分支选项
        """
        # 准备初始状态
        initial_state = {
            "country": country,
            "year": year,
            "month": month,
            "history_summary": history_summary or "游戏开始",
            "iterations": 0,
            "quality_score": 0.0
        }

        # 执行工作流
        result = self.graph.invoke(initial_state)

        return result.get("final_events")


# ============================================================================
# 便捷函数
# ============================================================================

def create_event_generation_workflow(knowledge_base=None) -> EventGenerationWorkflow:
    """
    创建事件生成工作流实例

    Args:
        knowledge_base: RAG知识库（可选）

    Returns:
        工作流实例
    """
    return EventGenerationWorkflow(knowledge_base=knowledge_base)
