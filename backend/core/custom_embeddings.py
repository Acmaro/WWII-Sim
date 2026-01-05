"""
Custom Embeddings class for LM Studio
"""

import requests
from typing import List
from langchain_core.embeddings import Embeddings


class LMStudioEmbeddings(Embeddings):
    """LM Studio custom Embeddings implementation"""

    def __init__(self, base_url: str, model: str):
        """
        Initialize

        Args:
            base_url: LM Studio API address
            model: Model name
        """
        self.base_url = base_url.rstrip('/')
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Batch vectorize documents

        Args:
            texts: Text list

        Returns:
            Vector list
        """
        embeddings = []

        # Process one by one (avoid batch API issues)
        for text in texts:
            embedding = self.embed_query(text)
            embeddings.append(embedding)

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """
        Vectorize single query

        Args:
            text: Query text

        Returns:
            Vector
        """
        url = f"{self.base_url}/embeddings"

        payload = {
            "input": text,
            "model": self.model
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        data = response.json()

        # Extract embedding vector
        if "data" in data and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
        else:
            raise ValueError(f"No embedding data received from LM Studio: {data}")
