"""
RAG知识库服务

使用FAISS进行向量检索
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
    """RAG知识库"""

    def __init__(self, events_file: Optional[str] = None):
        """
        初始化知识库

        Args:
            events_file: 历史事件JSON文件路径
        """
        self.events_file = events_file or settings.HISTORICAL_EVENTS_FILE
        self.embeddings = get_embedding_model()

        # 数据存储
        self.events: List[HistoricalEvent] = []
        self.texts: List[str] = []
        self.vectors: Optional[np.ndarray] = None
        self.index: Optional[faiss.Index] = None

        # 加载数据
        self._load_events()

    def _load_events(self):
        """加载历史事件数据"""
        events_path = Path(self.events_file)

        if not events_path.exists():
            print(f"警告: 历史事件文件不存在: {self.events_file}")
            return

        with open(events_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 解析事件
        for event_data in data:
            try:
                event = HistoricalEvent(**event_data)
                self.events.append(event)

                # 构建检索文本
                text = self._format_event_for_retrieval(event)
                self.texts.append(text)

            except Exception as e:
                print(f"解析事件失败: {e}")
                continue

        print(f"[OK] 加载了 {len(self.events)} 个历史事件")

    def _format_event_for_retrieval(self, event: HistoricalEvent) -> str:
        """
        格式化事件用于检索

        Args:
            event: 历史事件

        Returns:
            格式化的文本
        """
        return (
            f"{event.year}年{event.month}月 "
            f"{event.name}: "
            f"{event.description}"
        )

    def build_index(self):
        """构建FAISS索引"""
        if not self.texts:
            print("警告: 没有数据可以建立索引")
            return

        print(f"正在向量化 {len(self.texts)} 个事件...")

        # 批量向量化
        embeddings_list = self.embeddings.embed_documents(self.texts)
        self.vectors = np.array(embeddings_list).astype('float32')

        print(f"向量维度: {self.vectors.shape}")

        # 创建FAISS索引 (L2距离)
        dimension = self.vectors.shape[1]
        self.index = faiss.IndexFlatL2(dimension)

        # 添加向量
        self.index.add(self.vectors)

        print(f"[OK] FAISS索引构建完成: {self.index.ntotal} 个向量")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None
    ) -> List[RAGResult]:
        """
        检索相关事件

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 过滤条件（可选）

        Returns:
            检索结果列表
        """
        if self.index is None:
            print("警告: 索引未构建")
            return []

        # 向量化查询
        query_embedding = self.embeddings.embed_query(query)
        query_vector = np.array([query_embedding]).astype('float32')

        # FAISS检索
        distances, indices = self.index.search(query_vector, top_k)

        # 构建结果
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= len(self.events):
                continue

            event = self.events[idx]
            distance = float(distances[0][i])

            # 应用过滤器（如果有）
            if filters:
                if not self._apply_filters(event, filters):
                    continue

            # 计算相似度分数 (距离越小越相似)
            score = 1.0 / (1.0 + distance)

            results.append(RAGResult(
                event=event,
                score=score,
                distance=distance
            ))

        return results

    def _apply_filters(self, event: HistoricalEvent, filters: dict) -> bool:
        """
        应用过滤条件

        Args:
            event: 事件
            filters: 过滤条件

        Returns:
            是否通过过滤
        """
        # 年份过滤
        if "year" in filters:
            if event.year != filters["year"]:
                return False

        # 国家过滤
        if "country" in filters:
            if event.country != filters["country"]:
                return False

        # 事件类型过滤
        if "event_type" in filters:
            if event.event_type != filters["event_type"]:
                return False

        return True

    def get_event_by_id(self, event_id: str) -> Optional[HistoricalEvent]:
        """
        根据ID获取事件

        Args:
            event_id: 事件ID

        Returns:
            事件对象或None
        """
        for event in self.events:
            if event.id == event_id:
                return event
        return None

    def get_stats(self) -> dict:
        """
        获取知识库统计信息

        Returns:
            统计信息字典
        """
        if not self.events:
            return {"total_events": 0}

        # 按年份统计
        year_counts = {}
        for event in self.events:
            year = event.year
            year_counts[year] = year_counts.get(year, 0) + 1

        # 按类型统计
        type_counts = {}
        for event in self.events:
            event_type = event.event_type
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

        # 按国家统计
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
# 全局知识库实例（单例）
# ============================================================================

_knowledge_base_instance: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """
    获取全局知识库实例

    Returns:
        知识库实例
    """
    global _knowledge_base_instance

    if _knowledge_base_instance is None:
        _knowledge_base_instance = KnowledgeBase()
        _knowledge_base_instance.build_index()

    return _knowledge_base_instance


# ============================================================================
# 便捷函数
# ============================================================================

def search_historical_events(
    query: str,
    top_k: int = 5,
    filters: Optional[dict] = None
) -> List[RAGResult]:
    """
    检索历史事件（便捷函数）

    Args:
        query: 查询文本
        top_k: 返回结果数
        filters: 过滤条件

    Returns:
        检索结果
    """
    kb = get_knowledge_base()
    return kb.search(query, top_k=top_k, filters=filters)
