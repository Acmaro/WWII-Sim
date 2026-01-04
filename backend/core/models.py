"""
核心数据模型 - 使用Pydantic实现类型安全

所有数据结构都使用Pydantic BaseModel，确保：
1. 类型安全和自动验证
2. IDE自动补全
3. 自动JSON序列化
4. 清晰的数据约束
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# 历史事件模型
# ============================================================================

class HistoricalEvent(BaseModel):
    """历史事件（用于知识库）"""
    id: str = Field(description="事件唯一ID")
    name: str = Field(description="事件名称", min_length=5, max_length=100)
    description: str = Field(description="事件描述", min_length=5)
    year: int = Field(description="年份", ge=1939, le=1945)
    month: Optional[int] = Field(description="月份", ge=1, le=12, default=None)
    country: str = Field(description="主要国家代码")
    event_type: Optional[Literal["military", "diplomatic", "economic", "political"]] = Field(
        description="事件类型",
        default=None
    )
    importance: float = Field(description="重要性评分", ge=0.0, le=1.0, default=0.5)
    participants: List[str] = Field(description="参与国家", default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "event_1939_09_01",
                "name": "德国入侵波兰",
                "description": "1939年9月1日，纳粹德国入侵波兰，标志着第二次世界大战欧洲战场的开始",
                "year": 1939,
                "month": 9,
                "country": "GER",
                "event_type": "military",
                "importance": 1.0,
                "participants": ["GER", "POL"]
            }
        }


# ============================================================================
# 游戏事件模型
# ============================================================================

class GameEvent(BaseModel):
    """游戏中的可选事件分支"""
    id: str = Field(description="事件ID")
    name: str = Field(description="事件名称", min_length=4, max_length=30)
    description: str = Field(description="详细描述", min_length=10, max_length=120)
    year: int = Field(description="发生年份", ge=1939, le=1945)
    month: int = Field(description="发生月份", ge=1, le=12)
    country: str = Field(description="行动国家")
    event_type: Literal["military", "diplomatic", "economic", "political"]
    likelihood: float = Field(description="历史可能性", ge=0.0, le=1.0)
    impact_score: int = Field(description="影响力评分", ge=-100, le=100, default=0)

    # 可选字段
    consequences: Optional[List[str]] = Field(
        description="可能后果",
        default_factory=list
    )
    prerequisites: Optional[List[str]] = Field(
        description="前置条件",
        default_factory=list
    )


class BranchOptions(BaseModel):
    """一组分支选项"""
    branches: List[GameEvent] = Field(
        description="可选分支",
        min_length=4,
        max_length=4
    )
    reasoning: str = Field(
        description="生成这些选项的推理过程",
        min_length=50
    )
    context_summary: str = Field(
        description="当前态势总结",
        min_length=20
    )
    generation_metadata: Optional[dict] = Field(
        description="生成元数据（迭代次数、质量评分等）",
        default_factory=dict
    )


# ============================================================================
# 游戏状态模型
# ============================================================================

class GameSession(BaseModel):
    """游戏会话"""
    session_id: str = Field(description="会话ID")
    player_country: str = Field(description="玩家国家")
    current_year: int = Field(description="当前年份", ge=1939, le=1945)
    current_month: int = Field(description="当前月份", ge=1, le=12)
    current_node_id: str = Field(description="当前节点ID")

    # 历史记录
    history: List[GameEvent] = Field(
        description="已发生事件",
        default_factory=list
    )

    # 游戏状态
    is_ended: bool = Field(description="游戏是否结束", default=False)
    ending_type: Optional[str] = Field(description="结束类型", default=None)

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# 战争积分模型
# ============================================================================

class CountryScore(BaseModel):
    """国家积分"""
    country: str = Field(description="国家代码")
    military_score: float = Field(description="军事积分", default=0.0)
    economic_score: float = Field(description="经济积分", default=0.0)
    diplomatic_score: float = Field(description="外交积分", default=0.0)
    morale_score: float = Field(description="士气积分", default=0.0)

    @property
    def total_score(self) -> float:
        """总积分"""
        return (
            self.military_score +
            self.economic_score +
            self.diplomatic_score +
            self.morale_score
        )


class WarScore(BaseModel):
    """战争态势评分"""
    allied_score: float = Field(description="盟军总分", default=0.0)
    axis_score: float = Field(description="轴心国总分", default=0.0)
    neutral_score: float = Field(description="中立国总分", default=0.0)

    country_scores: dict[str, CountryScore] = Field(
        description="各国详细积分",
        default_factory=dict
    )

    @property
    def score_differential(self) -> float:
        """分数差（盟军-轴心国）"""
        return self.allied_score - self.axis_score


# ============================================================================
# RAG相关模型
# ============================================================================

class RAGResult(BaseModel):
    """RAG检索结果"""
    event: HistoricalEvent = Field(description="检索到的事件")
    score: float = Field(description="相似度评分", ge=0.0, le=1.0)
    distance: float = Field(description="向量距离")


class RAGQuery(BaseModel):
    """RAG查询"""
    query_text: str = Field(description="查询文本")
    filters: Optional[dict] = Field(description="过滤条件", default_factory=dict)
    top_k: int = Field(description="返回结果数", default=5, ge=1, le=20)


# ============================================================================
# API请求/响应模型
# ============================================================================

class StartGameRequest(BaseModel):
    """开始游戏请求"""
    player_country: Literal["GER", "UK", "USSR", "USA", "JAP", "FRA", "ITA"]


class StartGameResponse(BaseModel):
    """开始游戏响应"""
    session_id: str
    start_node: GameEvent
    player_country: str
    country_info: Optional[dict] = None
    message: str = "游戏开始"


class GetBranchesRequest(BaseModel):
    """获取分支请求"""
    session_id: str
    current_node_id: str


class GetBranchesResponse(BaseModel):
    """获取分支响应"""
    branches: List[GameEvent]
    ending_probability: float = Field(ge=0.0, le=1.0)
    war_score: Optional[WarScore] = None

    # 如果游戏结束
    is_ended: bool = False
    ending: Optional[dict] = None


class MakeChoiceRequest(BaseModel):
    """做出选择请求"""
    session_id: str
    node_id: str
    choice_id: str


class MakeChoiceResponse(BaseModel):
    """做出选择响应"""
    current_node: str
    action_result: dict
    reaction_events: List[GameEvent] = Field(default_factory=list)
    war_score: Optional[WarScore] = None
    message: str = "选择成功"


# ============================================================================
# 质量评估模型
# ============================================================================

class QualityMetrics(BaseModel):
    """质量评估指标"""
    format_valid: float = Field(description="格式正确性", ge=0.0, le=1.0)
    diversity: float = Field(description="多样性", ge=0.0, le=1.0)
    consistency: float = Field(description="一致性", ge=0.0, le=1.0)
    historical_accuracy: float = Field(description="历史准确性", ge=0.0, le=1.0)

    @property
    def overall_score(self) -> float:
        """综合评分"""
        return (
            self.format_valid +
            self.diversity +
            self.consistency +
            self.historical_accuracy
        ) / 4.0


# ============================================================================
# 工作流状态模型（用于LangGraph）
# ============================================================================

class GenerationState(BaseModel):
    """事件生成工作流状态"""
    # 输入
    country: str
    year: int
    month: int
    history_summary: str = ""

    # 中间状态
    rag_context: str = ""
    draft_events: Optional[BranchOptions] = None
    quality_metrics: Optional[QualityMetrics] = None
    quality_score: float = 0.0

    # 输出
    final_events: Optional[BranchOptions] = None

    # 计数器
    iterations: int = 0

    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# 性能监控模型
# ============================================================================

class PerformanceMetrics(BaseModel):
    """性能指标"""
    llm_calls: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    total_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def average_time_per_call(self) -> float:
        """平均每次调用时间"""
        return self.total_time / self.llm_calls if self.llm_calls > 0 else 0.0
