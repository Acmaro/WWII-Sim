"""
LLM Factory and Wrapper

Provides unified LLM creation and management interface
"""

from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from typing import Optional

from .config import settings, LLM_PRICING
from .custom_embeddings import LMStudioEmbeddings


class LLMFactory:
    """LLM factory class"""

    @staticmethod
    def create_chat_llm(
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ):
        """
        Create chat LLM instance

        Args:
            provider: LLM provider ("openai" or "lm_studio")
            temperature: Temperature parameter
            **kwargs: Other parameters

        Returns:
            LLM instance
        """
        provider = provider or settings.LLM_PROVIDER
        temperature = temperature if temperature is not None else settings.OPENAI_TEMPERATURE

        if provider == "openai":
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=temperature,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
                **kwargs
            )

        elif provider == "lm_studio":
            # LM Studio uses OpenAI-compatible API
            return ChatOpenAI(
                model=settings.LM_STUDIO_MODEL,
                base_url=settings.LM_STUDIO_BASE_URL,
                api_key="lm-studio",  # LM Studio doesn't need real API key
                temperature=temperature,
                **kwargs
            )

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def create_embedding_model(provider: Optional[str] = None):
        """
        Create embedding model instance

        Args:
            provider: Embedding provider ("openai", "ollama", or "lm_studio")

        Returns:
            Embedding model instance
        """
        provider = provider or settings.EMBEDDING_PROVIDER

        if provider == "openai":
            return OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.OPENAI_API_KEY
            )

        elif provider == "ollama":
            return OllamaEmbeddings(
                model=settings.EMBEDDING_MODEL,
                base_url=settings.EMBEDDING_BASE_URL
            )

        elif provider == "lm_studio":
            # LM Studio uses custom Embeddings class
            return LMStudioEmbeddings(
                base_url=settings.EMBEDDING_BASE_URL,
                model=settings.EMBEDDING_MODEL
            )

        else:
            raise ValueError(f"Unknown embedding provider: {provider}")


class CostCalculator:
    """Cost calculator"""

    @staticmethod
    def calculate_cost(
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """
        Calculate LLM call cost

        Args:
            model: Model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Cost (USD)
        """
        # Look up pricing
        pricing = None
        for model_key, price in LLM_PRICING.items():
            if model_key in model:
                pricing = price
                break

        if pricing is None:
            # Unknown model, return 0
            return 0.0

        # Calculate cost
        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]

        return prompt_cost + completion_cost


# ============================================================================
# Global LLM Instances (lazy loading)
# ============================================================================

_llm_instance: Optional[ChatOpenAI] = None
_embedding_instance: Optional[OllamaEmbeddings] = None


def get_llm(temperature: Optional[float] = None):
    """
    Get global LLM instance (singleton pattern)

    Args:
        temperature: Optional temperature parameter to override default

    Returns:
        LLM instance
    """
    global _llm_instance

    # If temperature is specified, create new instance
    if temperature is not None:
        return LLMFactory.create_chat_llm(temperature=temperature)

    # Otherwise use singleton
    if _llm_instance is None:
        _llm_instance = LLMFactory.create_chat_llm()

    return _llm_instance


def get_embedding_model():
    """
    Get global embedding model instance (singleton pattern)

    Returns:
        Embedding model instance
    """
    global _embedding_instance

    if _embedding_instance is None:
        _embedding_instance = LLMFactory.create_embedding_model()

    return _embedding_instance


# ============================================================================
# Utility Functions
# ============================================================================

def estimate_tokens(text: str) -> int:
    """
    Estimate number of tokens in text (rough estimate)

    Args:
        text: Input text

    Returns:
        Estimated number of tokens
    """
    # Simple estimation: English 1 token ≈ 4 chars, Chinese 1 token ≈ 1.5 chars
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    other_chars = len(text) - chinese_chars

    return int(chinese_chars / 1.5 + other_chars / 4)
