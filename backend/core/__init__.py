"""
Core Module

Contains data models, configuration and LLM factory
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
