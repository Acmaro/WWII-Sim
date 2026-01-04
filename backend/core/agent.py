"""
Multi-Agent System - Country Agent Models
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ControlMode(str, Enum):
    """Control mode"""
    HUMAN = "human"          # Player controlled
    AI = "ai"                # AI controlled
    OBSERVER = "observer"    # Observer (non-participant)


class CountryAgent(BaseModel):
    """Country agent"""
    country_code: str = Field(description="Country code (GER/UK/USSR)")
    country_name: str = Field(description="Country name")
    control_mode: ControlMode = Field(description="Control mode")

    # Agent state
    objectives: List[str] = Field(description="Strategic objectives", default_factory=list)
    personality: Dict[str, float] = Field(
        description="Personality traits (aggression/diplomacy/economic_focus)",
        default_factory=dict
    )
    risk_tolerance: float = Field(
        description="Risk tolerance (0.0-1.0)",
        ge=0.0,
        le=1.0,
        default=0.5
    )

    # Current state
    current_year: int = Field(description="Current year", ge=1939, le=1945)
    current_month: int = Field(description="Current month", ge=1, le=12)
    resources: Dict[str, float] = Field(
        description="Resources (military/economic/diplomatic)",
        default_factory=dict
    )

    # Decision history
    action_history: List[str] = Field(
        description="Historical action ID list",
        default_factory=list
    )

    # Pending options (runtime)
    pending_options: List[Any] = Field(
        description="Pending options for current turn",
        default_factory=list,
        exclude=True  # Not serialized
    )

    class Config:
        json_schema_extra = {
            "example": {
                "country_code": "GER",
                "country_name": "Germany",
                "control_mode": "human",
                "objectives": [
                    "Occupy Poland",
                    "Avoid two-front war",
                    "Establish European hegemony"
                ],
                "personality": {
                    "aggression": 0.8,
                    "diplomacy": 0.4,
                    "economic_focus": 0.6
                },
                "risk_tolerance": 0.7,
                "current_year": 1939,
                "current_month": 9,
                "resources": {
                    "military": 100,
                    "economic": 80,
                    "diplomatic": 50
                }
            }
        }


class WorldState(BaseModel):
    """Global world state"""
    current_turn: int = Field(description="Current turn", default=1)
    current_year: int = Field(description="Current year", ge=1939, le=1945)
    current_month: int = Field(description="Current month", ge=1, le=12)

    # Country agents
    agents: Dict[str, CountryAgent] = Field(
        description="All country agents (country_code -> Agent)",
        default_factory=dict
    )

    # Diplomatic relations (-1 hostile to 1 friendly)
    diplomatic_relations: Dict[str, Dict[str, float]] = Field(
        description="Diplomatic relations matrix",
        default_factory=dict
    )

    # Military situation
    military_power: Dict[str, float] = Field(
        description="Military power scores by country",
        default_factory=dict
    )

    # Controlled territories
    territories: Dict[str, List[str]] = Field(
        description="Territory lists controlled by each country",
        default_factory=dict
    )

    # Economic situation
    economic_strength: Dict[str, float] = Field(
        description="Economic strength by country",
        default_factory=dict
    )

    # Major events
    major_events: List[str] = Field(
        description="Major events that have occurred",
        default_factory=list
    )

    # Creation time
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

    def get_agent(self, country: str) -> Optional[CountryAgent]:
        """Get country agent"""
        return self.agents.get(country)

    def update_relations(self, country1: str, country2: str, delta: float):
        """Update diplomatic relations"""
        if country1 not in self.diplomatic_relations:
            self.diplomatic_relations[country1] = {}

        current = self.diplomatic_relations[country1].get(country2, 0.0)
        new_value = max(-1.0, min(1.0, current + delta))
        self.diplomatic_relations[country1][country2] = new_value

        # Bidirectional update
        if country2 not in self.diplomatic_relations:
            self.diplomatic_relations[country2] = {}
        self.diplomatic_relations[country2][country1] = new_value

        self.last_updated = datetime.now()

    def get_relation(self, country1: str, country2: str) -> float:
        """Get relationship between two countries"""
        return self.diplomatic_relations.get(country1, {}).get(country2, 0.0)

    def add_major_event(self, event: str):
        """Add major event"""
        self.major_events.append(event)
        self.last_updated = datetime.now()

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TurnPhase(str, Enum):
    """Turn phase"""
    PLANNING = "planning"          # Planning phase (generate options)
    DECISION = "decision"          # Decision phase (player/AI choice)
    EXECUTION = "execution"        # Execution phase (process actions)
    RESOLUTION = "resolution"      # Resolution phase (calculate impact)


class TurnResult(BaseModel):
    """Turn result"""
    turn_number: int = Field(description="Turn number")
    all_actions: Dict[str, Any] = Field(
        description="Actions by all countries",
        default_factory=dict
    )
    conflicts: List[Dict[str, Any]] = Field(
        description="Military conflicts",
        default_factory=list
    )
    diplomatic_changes: List[Dict[str, Any]] = Field(
        description="Diplomatic relation changes",
        default_factory=list
    )
    economic_changes: List[Dict[str, Any]] = Field(
        description="Economic changes",
        default_factory=list
    )
    major_events: List[str] = Field(
        description="Major events this turn",
        default_factory=list
    )

    # Ending related
    is_game_over: bool = Field(
        description="Whether game has ended",
        default=False
    )
    ending_trigger: Optional[str] = Field(
        description="Reason for ending trigger",
        default=None
    )


class GameEnding(BaseModel):
    """Game ending"""
    ending_type: str = Field(description="Ending type: victory/defeat/draw/historical")
    winner: Optional[str] = Field(description="Winner country code", default=None)
    trigger_reason: str = Field(description="Reason for ending trigger")

    # AI-generated ending narrative
    narrative: str = Field(description="Ending story narrative")
    epilogue: Dict[str, str] = Field(
        description="Subsequent development of each country",
        default_factory=dict
    )

    # Final statistics
    final_stats: Dict[str, Any] = Field(
        description="Final statistical data",
        default_factory=dict
    )
    key_events: List[str] = Field(
        description="Key historical events review",
        default_factory=list
    )


# Preset Agent configurations
PRESET_AGENTS = {
    "GER": {
        "country_code": "GER",
        "country_name": "Germany",
        "objectives": [
            "Occupy Poland",
            "Avoid two-front war",
            "Establish European hegemony"
        ],
        "personality": {
            "aggression": 0.8,
            "diplomacy": 0.4,
            "economic_focus": 0.6
        },
        "risk_tolerance": 0.7,
        "resources": {
            "military": 100,
            "economic": 80,
            "diplomatic": 50
        }
    },
    "UK": {
        "country_code": "UK",
        "country_name": "United Kingdom",
        "objectives": [
            "Defend the homeland",
            "Maintain naval supremacy",
            "Prevent German expansion"
        ],
        "personality": {
            "aggression": 0.4,
            "diplomacy": 0.7,
            "economic_focus": 0.6
        },
        "risk_tolerance": 0.5,
        "resources": {
            "military": 90,
            "economic": 100,
            "diplomatic": 80
        }
    },
    "USSR": {
        "country_code": "USSR",
        "country_name": "Soviet Union",
        "objectives": [
            "Expand territory",
            "Establish buffer zones",
            "Avoid conflict with Germany"
        ],
        "personality": {
            "aggression": 0.6,
            "diplomacy": 0.5,
            "economic_focus": 0.7
        },
        "risk_tolerance": 0.6,
        "resources": {
            "military": 110,
            "economic": 70,
            "diplomatic": 60
        }
    }
}
