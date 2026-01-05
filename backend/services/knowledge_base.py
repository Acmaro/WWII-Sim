"""
RAG Knowledge Base Service

Uses FAISS for vector retrieval
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Optional
import faiss

from backend.core.models import HistoricalEvent, RAGResult
from backend.core.llm import get_embedding_model
from backend.core.config import settings


class KnowledgeBase:
    """RAG knowledge base"""

    def __init__(self, events_file: Optional[str] = None):
        """
        Initialize knowledge base

        Args:
            events_file: Historical events JSON file path
        """
        self.events_file = events_file or settings.HISTORICAL_EVENTS_FILE
        self.embeddings = get_embedding_model()

        # Data storage
        self.events: List[HistoricalEvent] = []
        self.texts: List[str] = []
        self.vectors: Optional[np.ndarray] = None
        self.index: Optional[faiss.Index] = None

        # Load data
        self._load_events()

    def _load_events(self):
        """Load historical events data"""
        events_path = Path(self.events_file)

        if not events_path.exists():
            print(f"Warning: Historical events file does not exist: {self.events_file}")
            return

        with open(events_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Parse events
        for event_data in data:
            try:
                event = HistoricalEvent(**event_data)
                self.events.append(event)

                # Build retrieval text
                text = self._format_event_for_retrieval(event)
                self.texts.append(text)

            except Exception as e:
                print(f"Failed to parse event: {e}")
                continue

        print(f"[OK] Loaded {len(self.events)} historical events")

    def _format_event_for_retrieval(self, event: HistoricalEvent) -> str:
        """
        Format event for retrieval

        Args:
            event: Historical event

        Returns:
            Formatted text
        """
        return (
            f"{event.year}/{event.month} "
            f"{event.name}: "
            f"{event.description}"
        )

    def build_index(self):
        """Build FAISS index"""
        if not self.texts:
            print("Warning: No data to build index")
            return

        print(f"Vectorizing {len(self.texts)} events...")

        # Batch vectorization
        embeddings_list = self.embeddings.embed_documents(self.texts)
        self.vectors = np.array(embeddings_list).astype('float32')

        print(f"Vector dimension: {self.vectors.shape}")

        # Create FAISS index (L2 distance)
        dimension = self.vectors.shape[1]
        self.index = faiss.IndexFlatL2(dimension)

        # Add vectors
        self.index.add(self.vectors)

        print(f"[OK] FAISS index built: {self.index.ntotal} vectors")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None
    ) -> List[RAGResult]:
        """
        Retrieve relevant events

        Args:
            query: Query text
            top_k: Number of results to return
            filters: Filter conditions (optional)

        Returns:
            Retrieval result list
        """
        if self.index is None:
            print("Warning: Index not built")
            return []

        # Vectorize query
        query_embedding = self.embeddings.embed_query(query)
        query_vector = np.array([query_embedding]).astype('float32')

        # FAISS retrieval
        distances, indices = self.index.search(query_vector, top_k)

        # Build results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= len(self.events):
                continue

            event = self.events[idx]
            distance = float(distances[0][i])

            # Apply filters (if any)
            if filters:
                if not self._apply_filters(event, filters):
                    continue

            # Calculate similarity score (smaller distance = more similar)
            score = 1.0 / (1.0 + distance)

            results.append(RAGResult(
                event=event,
                score=score,
                distance=distance
            ))

        return results

    def _apply_filters(self, event: HistoricalEvent, filters: dict) -> bool:
        """
        Apply filter conditions

        Args:
            event: Event
            filters: Filter conditions

        Returns:
            Whether it passes the filter
        """
        # Year filter
        if "year" in filters:
            if event.year != filters["year"]:
                return False

        # Country filter
        if "country" in filters:
            if event.country != filters["country"]:
                return False

        # Event type filter
        if "event_type" in filters:
            if event.event_type != filters["event_type"]:
                return False

        return True

    def get_event_by_id(self, event_id: str) -> Optional[HistoricalEvent]:
        """
        Get event by ID

        Args:
            event_id: Event ID

        Returns:
            Event object or None
        """
        for event in self.events:
            if event.id == event_id:
                return event
        return None

    def get_stats(self) -> dict:
        """
        Get knowledge base statistics

        Returns:
            Statistics dictionary
        """
        if not self.events:
            return {"total_events": 0}

        # Statistics by year
        year_counts = {}
        for event in self.events:
            year = event.year
            year_counts[year] = year_counts.get(year, 0) + 1

        # Statistics by type
        type_counts = {}
        for event in self.events:
            event_type = event.event_type
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

        # Statistics by country
        country_counts = {}
        for event in self.events:
            country = event.country
            country_counts[country] = country_counts.get(country, 0) + 1

        return {
            "total_events": len(self.events),
            "index_size": self.index.ntotal if self.index else 0,
            "vector_dimension": self.vectors.shape[1] if self.vectors is not None else 0,
            "year_distribution": year_counts,
            "type_distribution": type_counts,
            "country_distribution": country_counts
        }


# ============================================================================
# Global Knowledge Base Instance (Singleton)
# ============================================================================

_knowledge_base_instance: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """
    Get global knowledge base instance

    Returns:
        Knowledge base instance
    """
    global _knowledge_base_instance

    if _knowledge_base_instance is None:
        _knowledge_base_instance = KnowledgeBase()
        _knowledge_base_instance.build_index()

    return _knowledge_base_instance


# ============================================================================
# Utility Functions
# ============================================================================

def search_historical_events(
    query: str,
    top_k: int = 5,
    filters: Optional[dict] = None
) -> List[RAGResult]:
    """
    Search historical events (utility function)

    Args:
        query: Query text
        top_k: Number of results to return
        filters: Filter conditions

    Returns:
        Retrieval results
    """
    kb = get_knowledge_base()
    return kb.search(query, top_k=top_k, filters=filters)
