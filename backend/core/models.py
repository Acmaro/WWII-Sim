"""
Core Data Models - Type Safety with Pydantic

All data structures use Pydantic BaseModel, ensuring:
1. Type safety and automatic validation
2. IDE auto-completion
3. Automatic JSON serialization
4. Clear data constraints
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Historical Event Models
# ============================================================================

class HistoricalEvent(BaseModel):
    """Historical event (for knowledge base)"""
    id: str = Field(description="Unique event ID")
    name: str = Field(description="Event name", min_length=5, max_length=100)
    description: str = Field(description="Event description", min_length=5)
    year: int = Field(description="Year", ge=1939, le=1945)
    month: Optional[int] = Field(description="Month", ge=1, le=12, default=None)
    country: str = Field(description="Primary country code")
    event_type: Optional[Literal["military", "diplomatic", "economic", "political"]] = Field(
        description="Event type",
        default=None
    )
    importance: float = Field(description="Importance score", ge=0.0, le=1.0, default=0.5)
    participants: List[str] = Field(description="Participating countries", default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "event_1939_09_01",
                "name": "German Invasion of Poland",
                "description": "On September 1, 1939, Nazi Germany invaded Poland, marking the beginning of World War II in Europe",
                "year": 1939,
                "month": 9,
                "country": "GER",
                "event_type": "military",
                "importance": 1.0,
                "participants": ["GER", "POL"]
            }
        }


# ============================================================================
# Game Event Models
# ============================================================================

class GameEvent(BaseModel):
    """Playable event branch in the game"""
    id: str = Field(description="Event ID")
    name: str = Field(description="Event name", min_length=4, max_length=30)
    description: str = Field(description="Detailed description", min_length=10, max_length=120)
    year: int = Field(description="Occurrence year", ge=1939, le=1945)
    month: int = Field(description="Occurrence month", ge=1, le=12)
    country: str = Field(description="Acting country")
    event_type: Literal["military", "diplomatic", "economic", "political"]
    likelihood: float = Field(description="Historical likelihood", ge=0.0, le=1.0)
    impact_score: int = Field(description="Impact score", ge=-100, le=100, default=0)

    # Optional fields
    consequences: Optional[List[str]] = Field(
        description="Possible consequences",
        default_factory=list
    )
    prerequisites: Optional[List[str]] = Field(
        description="Prerequisites",
        default_factory=list
    )


class BranchOptions(BaseModel):
    """A set of branch options"""
    branches: List[GameEvent] = Field(
        description="Available branches",
        min_length=4,
        max_length=4
    )
    reasoning: str = Field(
        description="Reasoning process for generating these options",
        min_length=50
    )
    context_summary: str = Field(
        description="Current situation summary",
        min_length=20
    )
    generation_metadata: Optional[dict] = Field(
        description="Generation metadata (iterations, quality scores, etc.)",
        default_factory=dict
    )


# ============================================================================
# Game State Models
# ============================================================================

class GameSession(BaseModel):
    """Game session"""
    session_id: str = Field(description="Session ID")
    player_country: str = Field(description="Player country")
    current_year: int = Field(description="Current year", ge=1939, le=1945)
    current_month: int = Field(description="Current month", ge=1, le=12)
    current_node_id: str = Field(description="Current node ID")

    # History record
    history: List[GameEvent] = Field(
        description="Events that have occurred",
        default_factory=list
    )

    # Game state
    is_ended: bool = Field(description="Whether game has ended", default=False)
    ending_type: Optional[str] = Field(description="Ending type", default=None)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# War Score Models
# ============================================================================

class CountryScore(BaseModel):
    """Country score"""
    country: str = Field(description="Country code")
    military_score: float = Field(description="Military score", default=0.0)
    economic_score: float = Field(description="Economic score", default=0.0)
    diplomatic_score: float = Field(description="Diplomatic score", default=0.0)
    morale_score: float = Field(description="Morale score", default=0.0)

    @property
    def total_score(self) -> float:
        """Total score"""
        return (
            self.military_score +
            self.economic_score +
            self.diplomatic_score +
            self.morale_score
        )


class WarScore(BaseModel):
    """War situation score"""
    allied_score: float = Field(description="Allied total score", default=0.0)
    axis_score: float = Field(description="Axis total score", default=0.0)
    neutral_score: float = Field(description="Neutral total score", default=0.0)

    country_scores: dict[str, CountryScore] = Field(
        description="Detailed scores by country",
        default_factory=dict
    )

    @property
    def score_differential(self) -> float:
        """Score differential (Allied - Axis)"""
        return self.allied_score - self.axis_score


# ============================================================================
# RAG Related Models
# ============================================================================

class RAGResult(BaseModel):
    """RAG retrieval result"""
    event: HistoricalEvent = Field(description="Retrieved event")
    score: float = Field(description="Similarity score", ge=0.0, le=1.0)
    distance: float = Field(description="Vector distance")


class RAGQuery(BaseModel):
    """RAG query"""
    query_text: str = Field(description="Query text")
    filters: Optional[dict] = Field(description="Filter conditions", default_factory=dict)
    top_k: int = Field(description="Number of results to return", default=5, ge=1, le=20)


# ============================================================================
# API Request/Response Models
# ============================================================================

class StartGameRequest(BaseModel):
    """Start game request"""
    player_country: Literal["GER", "UK", "USSR", "USA", "JAP", "FRA", "ITA"]


class StartGameResponse(BaseModel):
    """Start game response"""
    session_id: str
    start_node: GameEvent
    player_country: str
    country_info: Optional[dict] = None
    message: str = "Game started"


class GetBranchesRequest(BaseModel):
    """Get branches request"""
    session_id: str
    current_node_id: str


class GetBranchesResponse(BaseModel):
    """Get branches response"""
    branches: List[GameEvent]
    ending_probability: float = Field(ge=0.0, le=1.0)
    war_score: Optional[WarScore] = None

    # If game has ended
    is_ended: bool = False
    ending: Optional[dict] = None


class MakeChoiceRequest(BaseModel):
    """Make choice request"""
    session_id: str
    node_id: str
    choice_id: str


class MakeChoiceResponse(BaseModel):
    """Make choice response"""
    current_node: str
    action_result: dict
    reaction_events: List[GameEvent] = Field(default_factory=list)
    war_score: Optional[WarScore] = None
    message: str = "Choice successful"


# ============================================================================
# Quality Assessment Models
# ============================================================================

class QualityMetrics(BaseModel):
    """Quality assessment metrics"""
    format_valid: float = Field(description="Format correctness", ge=0.0, le=1.0)
    diversity: float = Field(description="Diversity", ge=0.0, le=1.0)
    consistency: float = Field(description="Consistency", ge=0.0, le=1.0)
    historical_accuracy: float = Field(description="Historical accuracy", ge=0.0, le=1.0)

    @property
    def overall_score(self) -> float:
        """Overall score"""
        return (
            self.format_valid +
            self.diversity +
            self.consistency +
            self.historical_accuracy
        ) / 4.0


# ============================================================================
# Workflow State Models (for LangGraph)
# ============================================================================

class GenerationState(BaseModel):
    """Event generation workflow state"""
    # Input
    country: str
    year: int
    month: int
    history_summary: str = ""

    # Intermediate state
    rag_context: str = ""
    draft_events: Optional[BranchOptions] = None
    quality_metrics: Optional[QualityMetrics] = None
    quality_score: float = 0.0

    # Output
    final_events: Optional[BranchOptions] = None

    # Counter
    iterations: int = 0

    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# Performance Monitoring Models
# ============================================================================

class PerformanceMetrics(BaseModel):
    """Performance metrics"""
    llm_calls: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    total_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def average_time_per_call(self) -> float:
        """Average time per call"""
        return self.total_time / self.llm_calls if self.llm_calls > 0 else 0.0
