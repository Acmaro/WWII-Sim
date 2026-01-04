"""
核心模块

包含数据模型、配置和LLM工厂
"""

from backend.core.models import (
    GameEvent,
    HistoricalEvent,
    BranchOptions,
    QualityMetrics,
    GameSession,
    StartGameRequest,
    StartGameResponse,
    GetBranchesRequest,
    GetBranchesResponse,
    MakeChoiceRequest,
    MakeChoiceResponse,
    RAGResult
)
from backend.core.config import settings
from backend.core.llm import get_llm, get_embedding_model

__all__ = [
    "GameEvent",
    "HistoricalEvent",
    "BranchOptions",
    "QualityMetrics",
    "GameSession",
    "StartGameRequest",
    "StartGameResponse",
    "GetBranchesRequest",
    "GetBranchesResponse",
    "MakeChoiceRequest",
    "MakeChoiceResponse",
    "RAGResult",
    "settings",
    "get_llm",
    "get_embedding_model"
]
