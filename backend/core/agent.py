"""
多Agent系统 - 国家Agent模型
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ControlMode(str, Enum):
    """控制模式"""
    HUMAN = "human"          # 玩家控制
    AI = "ai"                # AI自动控制
    OBSERVER = "observer"    # 观察者（不参与）


class CountryAgent(BaseModel):
    """国家Agent"""
    country_code: str = Field(description="国家代码（GER/UK/USSR）")
    country_name: str = Field(description="国家名称")
    control_mode: ControlMode = Field(description="控制模式")

    # Agent状态
    objectives: List[str] = Field(description="战略目标", default_factory=list)
    personality: Dict[str, float] = Field(
        description="性格特征（aggression/diplomacy/economic_focus）",
        default_factory=dict
    )
    risk_tolerance: float = Field(
        description="风险承受度 (0.0-1.0)",
        ge=0.0,
        le=1.0,
        default=0.5
    )

    # 当前状态
    current_year: int = Field(description="当前年份", ge=1939, le=1945)
    current_month: int = Field(description="当前月份", ge=1, le=12)
    resources: Dict[str, float] = Field(
        description="资源（military/economic/diplomatic）",
        default_factory=dict
    )

    # 决策历史
    action_history: List[str] = Field(
        description="历史行动ID列表",
        default_factory=list
    )

    # 待选选项（运行时）
    pending_options: List[Any] = Field(
        description="当前回合的待选选项",
        default_factory=list,
        exclude=True  # 不序列化
    )

    class Config:
        json_schema_extra = {
            "example": {
                "country_code": "GER",
                "country_name": "德国",
                "control_mode": "human",
                "objectives": [
                    "占领波兰",
                    "避免两线作战",
                    "建立欧洲霸权"
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
    """全局世界状态"""
    current_turn: int = Field(description="当前回合", default=1)
    current_year: int = Field(description="当前年份", ge=1939, le=1945)
    current_month: int = Field(description="当前月份", ge=1, le=12)

    # 国家Agent
    agents: Dict[str, CountryAgent] = Field(
        description="所有国家Agent (country_code -> Agent)",
        default_factory=dict
    )

    # 外交关系（-1敌对到1友好）
    diplomatic_relations: Dict[str, Dict[str, float]] = Field(
        description="外交关系矩阵",
        default_factory=dict
    )

    # 军事态势
    military_power: Dict[str, float] = Field(
        description="各国军力评分",
        default_factory=dict
    )

    # 控制的领土
    territories: Dict[str, List[str]] = Field(
        description="各国控制的领土列表",
        default_factory=dict
    )

    # 经济状况
    economic_strength: Dict[str, float] = Field(
        description="各国经济实力",
        default_factory=dict
    )

    # 重大事件
    major_events: List[str] = Field(
        description="已发生的重大事件",
        default_factory=list
    )

    # 创建时间
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

    def get_agent(self, country: str) -> Optional[CountryAgent]:
        """获取国家Agent"""
        return self.agents.get(country)

    def update_relations(self, country1: str, country2: str, delta: float):
        """更新外交关系"""
        if country1 not in self.diplomatic_relations:
            self.diplomatic_relations[country1] = {}

        current = self.diplomatic_relations[country1].get(country2, 0.0)
        new_value = max(-1.0, min(1.0, current + delta))
        self.diplomatic_relations[country1][country2] = new_value

        # 双向更新
        if country2 not in self.diplomatic_relations:
            self.diplomatic_relations[country2] = {}
        self.diplomatic_relations[country2][country1] = new_value

        self.last_updated = datetime.now()

    def get_relation(self, country1: str, country2: str) -> float:
        """获取两国关系"""
        return self.diplomatic_relations.get(country1, {}).get(country2, 0.0)

    def add_major_event(self, event: str):
        """添加重大事件"""
        self.major_events.append(event)
        self.last_updated = datetime.now()

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TurnPhase(str, Enum):
    """回合阶段"""
    PLANNING = "planning"          # 规划阶段（生成选项）
    DECISION = "decision"          # 决策阶段（玩家/AI选择）
    EXECUTION = "execution"        # 执行阶段（处理行动）
    RESOLUTION = "resolution"      # 结算阶段（计算影响）


class TurnResult(BaseModel):
    """回合结果"""
    turn_number: int = Field(description="回合编号")
    all_actions: Dict[str, Any] = Field(
        description="所有国家的行动",
        default_factory=dict
    )
    conflicts: List[Dict[str, Any]] = Field(
        description="军事冲突",
        default_factory=list
    )
    diplomatic_changes: List[Dict[str, Any]] = Field(
        description="外交关系变化",
        default_factory=list
    )
    economic_changes: List[Dict[str, Any]] = Field(
        description="经济变化",
        default_factory=list
    )
    major_events: List[str] = Field(
        description="本回合重大事件",
        default_factory=list
    )

    # 结局相关
    is_game_over: bool = Field(
        description="游戏是否结束",
        default=False
    )
    ending_trigger: Optional[str] = Field(
        description="结局触发原因",
        default=None
    )


class GameEnding(BaseModel):
    """游戏结局"""
    ending_type: str = Field(description="结局类型：victory/defeat/draw/historical")
    winner: Optional[str] = Field(description="胜利者国家代码", default=None)
    trigger_reason: str = Field(description="结局触发原因")

    # AI生成的结局叙事
    narrative: str = Field(description="结局故事叙述")
    epilogue: Dict[str, str] = Field(
        description="各国的后续发展",
        default_factory=dict
    )

    # 最终统计
    final_stats: Dict[str, Any] = Field(
        description="最终统计数据",
        default_factory=dict
    )
    key_events: List[str] = Field(
        description="关键历史事件回顾",
        default_factory=list
    )


# 预设Agent配置
PRESET_AGENTS = {
    "GER": {
        "country_code": "GER",
        "country_name": "德国",
        "objectives": [
            "占领波兰",
            "避免两线作战",
            "建立欧洲霸权"
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
        "country_name": "英国",
        "objectives": [
            "保卫本土",
            "维护海上霸权",
            "阻止德国扩张"
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
        "country_name": "苏联",
        "objectives": [
            "扩大领土",
            "建立缓冲区",
            "避免与德国冲突"
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
