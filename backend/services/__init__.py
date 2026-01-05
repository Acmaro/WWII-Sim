"""
Services Module

Contains RAG knowledge base and other business services
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
