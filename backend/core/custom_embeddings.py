"""
自定义Embeddings类，用于LM Studio
"""

import requests
from typing import List
from langchain_core.embeddings import Embeddings


class LMStudioEmbeddings(Embeddings):
    """LM Studio自定义Embeddings实现"""

    def __init__(self, base_url: str, model: str):
        """
        初始化

        Args:
            base_url: LM Studio API地址
            model: 模型名称
        """
        self.base_url = base_url.rstrip('/')
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化文档

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        embeddings = []

        # 逐个处理（避免批量API问题）
        for text in texts:
            embedding = self.embed_query(text)
            embeddings.append(embedding)

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        向量化单个查询

        Args:
            text: 查询文本

        Returns:
            向量
        """
        url = f"{self.base_url}/embeddings"

        payload = {
            "input": text,
            "model": self.model
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        data = response.json()

        # 提取embedding向量
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
        else:
            raise ValueError(f"No embedding data received from LM Studio: {data}")
