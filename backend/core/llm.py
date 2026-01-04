"""
LLM工厂和包装器

提供统一的LLM创建和管理接口
"""

from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from typing import Optional

from .config import settings, LLM_PRICING
from .custom_embeddings import LMStudioEmbeddings


class LLMFactory:
    """LLM工厂类"""

    @staticmethod
    def create_chat_llm(
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs
    ):
        """
        创建聊天LLM实例

        Args:
            provider: LLM提供商 ("openai" 或 "lm_studio")
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            LLM实例
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
            # LM Studio使用OpenAI兼容API
            return ChatOpenAI(
                model=settings.LM_STUDIO_MODEL,
                base_url=settings.LM_STUDIO_BASE_URL,
                api_key="lm-studio",  # LM Studio不需要真实API key
                temperature=temperature,
                **kwargs
            )

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def create_embedding_model(provider: Optional[str] = None):
        """
        创建Embedding模型实例

        Args:
            provider: Embedding提供商 ("openai", "ollama", 或 "lm_studio")

        Returns:
            Embedding模型实例
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
            # LM Studio使用自定义Embeddings类
            return LMStudioEmbeddings(
                base_url=settings.EMBEDDING_BASE_URL,
                model=settings.EMBEDDING_MODEL
            )

        else:
            raise ValueError(f"Unknown embedding provider: {provider}")


class CostCalculator:
    """成本计算器"""

    @staticmethod
    def calculate_cost(
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """
        计算LLM调用成本

        Args:
            model: 模型名称
            prompt_tokens: 输入token数
            completion_tokens: 输出token数

        Returns:
            成本（美元）
        """
        # 查找定价
        pricing = None
        for model_key, price in LLM_PRICING.items():
            if model_key in model:
                pricing = price
                break

        if pricing is None:
            # 未知模型，返回0
            return 0.0

        # 计算成本
        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]

        return prompt_cost + completion_cost


# ============================================================================
# 全局LLM实例（懒加载）
# ============================================================================

_llm_instance: Optional[ChatOpenAI] = None
_embedding_instance: Optional[OllamaEmbeddings] = None


def get_llm(temperature: Optional[float] = None):
    """
    获取全局LLM实例（单例模式）

    Args:
        temperature: 可选的温度参数，用于覆盖默认值

    Returns:
        LLM实例
    """
    global _llm_instance

    # 如果指定了temperature，创建新实例
    if temperature is not None:
        return LLMFactory.create_chat_llm(temperature=temperature)

    # 否则使用单例
    if _llm_instance is None:
        _llm_instance = LLMFactory.create_chat_llm()

    return _llm_instance


def get_embedding_model():
    """
    获取全局Embedding模型实例（单例模式）

    Returns:
        Embedding模型实例
    """
    global _embedding_instance

    if _embedding_instance is None:
        _embedding_instance = LLMFactory.create_embedding_model()

    return _embedding_instance


# ============================================================================
# 辅助函数
# ============================================================================

def estimate_tokens(text: str) -> int:
    """
    估算文本的token数（粗略估计）

    Args:
        text: 输入文本

    Returns:
        估算的token数
    """
    # 简单估算: 英文1 token ≈ 4 chars, 中文1 token ≈ 1.5 chars
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    other_chars = len(text) - chinese_chars

    return int(chinese_chars / 1.5 + other_chars / 4)
