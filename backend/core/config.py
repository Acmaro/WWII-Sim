"""
配置管理

集中管理所有配置项，支持环境变量覆盖
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # ========================================================================
    # LLM配置
    # ========================================================================

    # OpenAI配置
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.6
    OPENAI_MAX_TOKENS: int = 2000

    # LM Studio配置（本地LLM）
    LM_STUDIO_BASE_URL: str = "http://localhost:11434"
    LM_STUDIO_MODEL: str = "qwen2.5:14b"
    LM_STUDIO_TEMPERATURE: float = 0.6

    # LLM提供商选择
    LLM_PROVIDER: str = "lm_studio"  # "openai" 或 "lm_studio"

    # ========================================================================
    # Embedding配置
    # ========================================================================

    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_PROVIDER: str = "ollama"  # "openai" 或 "ollama"
    EMBEDDING_BASE_URL: str = "http://localhost:11434"

    # ========================================================================
    # FAISS配置
    # ========================================================================

    FAISS_INDEX_PATH: str = "data/faiss_index"
    FAISS_USE_GPU: bool = False

    # ========================================================================
    # 游戏配置
    # ========================================================================

    # 国家配置
    AVAILABLE_COUNTRIES: list[str] = ["GER", "UK", "USSR", "USA", "JAP", "FRA", "ITA"]
    DEFAULT_COUNTRY: str = "GER"

    # 时间配置
    GAME_START_YEAR: int = 1939
    GAME_START_MONTH: int = 9
    GAME_END_YEAR: int = 1945
    GAME_END_MONTH: int = 8

    # 生成配置
    NUM_BRANCHES: int = 4
    MAX_GENERATION_RETRIES: int = 3
    QUALITY_THRESHOLD: float = 0.85

    # ========================================================================
    # 性能配置
    # ========================================================================

    # 缓存配置
    ENABLE_CACHE: bool = True
    CACHE_SIZE: int = 1000
    CACHE_TTL: int = 3600  # 秒

    # 批处理配置
    BATCH_SIZE: int = 32

    # 并发配置
    MAX_CONCURRENT_REQUESTS: int = 10

    # ========================================================================
    # API配置
    # ========================================================================

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True

    # CORS配置
    CORS_ORIGINS: list[str] = ["http://localhost:5500", "http://127.0.0.1:5500"]

    # ========================================================================
    # 数据路径
    # ========================================================================

    DATA_DIR: str = "data"
    HISTORICAL_EVENTS_FILE: str = "data/historical_events.json"
    COUNTRY_TEMPLATES_DIR: str = "data/countries"

    # ========================================================================
    # 日志配置
    # ========================================================================

    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    VERBOSE: bool = False

    # ========================================================================
    # LangSmith配置（可选）
    # ========================================================================

    LANGCHAIN_TRACING_V2: str = "false"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "wwii-simulation-v2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()


# ============================================================================
# 常量定义
# ============================================================================

# 国家阵营
ALLIED_COUNTRIES = ["UK", "USA", "USSR", "FRA"]
AXIS_COUNTRIES = ["GER", "JAP", "ITA"]
NEUTRAL_COUNTRIES = []  # 可扩展

# 事件类型
EVENT_TYPES = ["military", "diplomatic", "economic", "political"]

# 质量评分权重
QUALITY_WEIGHTS = {
    "format_valid": 0.3,
    "diversity": 0.25,
    "consistency": 0.25,
    "historical_accuracy": 0.2
}

# LLM定价（用于成本计算，单位：$/1K tokens）
LLM_PRICING = {
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    "lm_studio": {"prompt": 0.0, "completion": 0.0}  # 本地免费
}
