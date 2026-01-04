"""
服务模块

包含RAG知识库和其他业务服务
"""

from backend.services.knowledge_base import (
    KnowledgeBase,
    get_knowledge_base,
    search_historical_events
)

__all__ = [
    "KnowledgeBase",
    "get_knowledge_base",
    "search_historical_events"
]
