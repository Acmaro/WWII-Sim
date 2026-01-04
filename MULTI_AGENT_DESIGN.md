# WWIISim-v2 多Agent架构设计

> 三个国家作为独立Agent，玩家控制其中一个

---

## 1. 核心概念

### 1.1 设计理念

```
┌─────────────────────────────────────────────────────────────┐
│                      游戏世界 (World)                        │
│                                                              │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐   │
│  │  德国Agent  │      │  英国Agent  │      │  苏联Agent  │   │
│  │  (GER)     │      │  (UK)      │      │  (USSR)    │   │
│  │            │      │            │      │            │   │
│  │  🎮玩家控制 │      │  🤖AI控制   │      │  🤖AI控制   │   │
│  │            │      │            │      │            │   │
│  └─────┬──────┘      └─────┬──────┘      └─────┬──────┘   │
│        │                   │                   │           │
│        └───────────────────┴───────────────────┘           │
│                            ↓                                │
│                    ┌───────────────┐                        │
│                    │  世界状态      │                        │
│                    │  - 外交关系    │                        │
│                    │  - 军事态势    │                        │
│                    │  - 经济状况    │                        │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Agent特性

每个国家Agent具有：
- ✅ **独立决策能力**：基于LangGraph生成自己的行动选项
- ✅ **感知能力**：了解世界状态和其他国家行动
- ✅ **目标驱动**：有自己的战略目标（德国扩张、英国防御等）
- ✅ **交互能力**：行动会影响其他国家
- ✅ **控制模式切换**：可在"人类"和"AI"控制间切换

---

## 2. 系统架构

### 2.1 核心组件

```python
# backend/core/agent.py

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class ControlMode(str, Enum):
    """控制模式"""
    HUMAN = "human"      # 玩家控制
    AI = "ai"            # AI自动控制
    OBSERVER = "observer"  # 观察者（不参与）

class CountryAgent(BaseModel):
    """国家Agent"""
    country_code: str           # 国家代码（GER/UK/USSR）
    country_name: str           # 国家名称
    control_mode: ControlMode   # 控制模式

    # Agent状态
    objectives: List[str]       # 战略目标
    personality: dict           # 性格特征（激进/保守等）
    risk_tolerance: float       # 风险承受度 (0.0-1.0)

    # 当前状态
    current_year: int
    current_month: int
    resources: dict             # 资源（军事/经济/外交点数）

    # 决策历史
    action_history: List[str] = []

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
                "risk_tolerance": 0.7
            }
        }
```

### 2.2 世界状态管理

```python
# backend/core/world_state.py

class WorldState(BaseModel):
    """全局世界状态"""
    current_turn: int                    # 当前回合
    current_year: int
    current_month: int

    # 国家Agent
    agents: dict[str, CountryAgent]      # country_code -> Agent

    # 外交关系
    diplomatic_relations: dict[str, dict[str, float]]  # 国家间关系 (-1到1)
    # 示例: {"GER": {"UK": -0.8, "USSR": 0.2}}

    # 军事态势
    military_power: dict[str, float]     # 各国军力
    territories: dict[str, List[str]]    # 各国控制的领土

    # 经济状况
    economic_strength: dict[str, float]  # 各国经济实力

    # 重大事件
    major_events: List[str] = []         # 已发生的重大事件

    def get_agent(self, country: str) -> CountryAgent:
        """获取国家Agent"""
        return self.agents[country]

    def update_relations(self, country1: str, country2: str, delta: float):
        """更新外交关系"""
        if country1 not in self.diplomatic_relations:
            self.diplomatic_relations[country1] = {}

        current = self.diplomatic_relations[country1].get(country2, 0.0)
        new_value = max(-1.0, min(1.0, current + delta))
        self.diplomatic_relations[country1][country2] = new_value
```

### 2.3 回合制系统

```python
# backend/core/turn_system.py

class TurnPhase(str, Enum):
    """回合阶段"""
    PLANNING = "planning"          # 规划阶段（所有Agent生成选项）
    DECISION = "decision"          # 决策阶段（玩家/AI做出选择）
    EXECUTION = "execution"        # 执行阶段（处理所有行动）
    RESOLUTION = "resolution"      # 结算阶段（计算影响）

class TurnManager:
    """回合管理器"""

    def __init__(self, world_state: WorldState):
        self.world = world_state
        self.current_phase = TurnPhase.PLANNING
        self.pending_actions: dict[str, GameEvent] = {}  # country -> action

    async def execute_turn(self) -> TurnResult:
        """执行一个完整回合"""

        # 阶段1: 规划 - 为所有国家生成选项
        await self.planning_phase()

        # 阶段2: 决策 - 收集所有国家的选择
        await self.decision_phase()

        # 阶段3: 执行 - 同时执行所有行动
        await self.execution_phase()

        # 阶段4: 结算 - 计算相互影响
        result = await self.resolution_phase()

        # 推进时间
        self.advance_time()

        return result

    async def planning_phase(self):
        """规划阶段：为所有Agent生成选项"""
        for country_code, agent in self.world.agents.items():
            # 为该Agent生成选项（考虑世界状态）
            options = await self.generate_options_for_agent(agent)
            agent.pending_options = options

    async def decision_phase(self):
        """决策阶段：收集所有选择"""
        for country_code, agent in self.world.agents.items():
            if agent.control_mode == ControlMode.HUMAN:
                # 等待玩家选择（前端通过API提交）
                pass  # 通过事件或回调处理

            elif agent.control_mode == ControlMode.AI:
                # AI自动选择
                choice = await self.ai_make_choice(agent)
                self.pending_actions[country_code] = choice

    async def execution_phase(self):
        """执行阶段：同时处理所有行动"""
        # 所有国家的行动同时生效
        for country_code, action in self.pending_actions.items():
            await self.execute_action(country_code, action)

    async def resolution_phase(self) -> TurnResult:
        """结算阶段：计算交互影响"""
        conflicts = self.detect_conflicts()
        diplomatic_changes = self.calculate_diplomatic_impact()
        economic_changes = self.calculate_economic_impact()

        return TurnResult(
            conflicts=conflicts,
            diplomatic_changes=diplomatic_changes,
            economic_changes=economic_changes,
            major_events=self.world.major_events
        )

    async def ai_make_choice(self, agent: CountryAgent) -> GameEvent:
        """AI自动做出选择"""
        # 使用LLM评估每个选项的价值
        options = agent.pending_options

        # 构建评估提示词
        prompt = f"""
你是{agent.country_name}的决策AI。

【当前态势】
时间: {agent.current_year}年{agent.current_month}月
资源: {agent.resources}
战略目标: {', '.join(agent.objectives)}

【外交关系】
{self._format_relations(agent.country_code)}

【可选行动】
{self._format_options(options)}

【性格特征】
激进度: {agent.personality.get('aggression', 0.5)}
外交倾向: {agent.personality.get('diplomacy', 0.5)}
风险承受度: {agent.risk_tolerance}

请根据当前态势和性格特征，选择最符合战略目标的行动。
返回选择的行动ID。
"""
        # 调用LLM获取选择
        choice_id = await self.llm_select(prompt, options)
        return next(opt for opt in options if opt.id == choice_id)
```

---

## 3. Agent决策工作流

### 3.1 增强版事件生成工作流

```python
# backend/workflows/multi_agent_generation.py

class MultiAgentGenerationState(TypedDict):
    """多Agent事件生成状态"""
    # 当前Agent信息
    agent: CountryAgent

    # 世界状态
    world_state: WorldState

    # 其他Agent的最近行动
    other_agents_actions: dict[str, List[GameEvent]]

    # RAG上下文
    rag_context: str

    # 生成结果
    draft_events: BranchOptions | None
    quality_metrics: QualityMetrics | None
    final_events: BranchOptions | None

    # 计数器
    iterations: Annotated[int, operator.add]

class MultiAgentEventWorkflow(EventGenerationWorkflow):
    """多Agent事件生成工作流"""

    def retrieve_context(self, state: MultiAgentGenerationState):
        """检索上下文（增强版）"""
        agent = state["agent"]
        world = state["world_state"]

        # 1. RAG检索历史事件
        query = f"{agent.country_code} {agent.current_year}.{agent.current_month}"
        rag_results = self.knowledge_base.search(query, top_k=5)

        # 2. 添加世界状态上下文
        world_context = f"""
当前世界态势:
- 外交关系: {self._format_relations(agent, world)}
- 军事实力对比: {self._format_military(world)}
- 经济状况: {world.economic_strength}
"""

        # 3. 添加其他Agent的行动
        other_actions = state["other_agents_actions"]
        actions_context = "其他国家最近行动:\n"
        for country, actions in other_actions.items():
            if country != agent.country_code and actions:
                latest = actions[-1]
                actions_context += f"- {country}: {latest.name}\n"

        # 组合上下文
        state["rag_context"] = (
            self._format_rag_results(rag_results) +
            "\n\n" + world_context +
            "\n\n" + actions_context
        )

        return state

    def generate_draft(self, state: MultiAgentGenerationState):
        """生成草稿（考虑Agent性格）"""
        agent = state["agent"]

        prompt = ChatPromptTemplate.from_template("""
你是{country_name}的战略顾问AI。

【Agent性格特征】
激进度: {aggression} (0-1, 越高越倾向军事行动)
外交倾向: {diplomacy} (0-1, 越高越倾向外交手段)
经济重视度: {economic_focus} (0-1, 越高越重视经济发展)
风险承受度: {risk_tolerance} (0-1, 越高越敢冒险)

【战略目标】
{objectives}

【历史背景参考】
{rag_context}

【任务】
根据Agent的性格特征和战略目标，生成4个符合角色定位的行动选项。

【要求】
1. 选项类型分布应该符合Agent性格:
   - 激进型Agent: 更多 military 选项
   - 外交型Agent: 更多 diplomatic 选项
   - 经济型Agent: 更多 economic 选项

2. 风险程度应该匹配 risk_tolerance:
   - 高风险承受: 可以有大胆冒险的选项
   - 低风险承受: 选项应该更稳健保守

3. 每个选项必须:
   - 符合历史背景和当前态势
   - 考虑与其他国家的关系
   - 描述简洁（20-80字）

{format_instructions}

直接输出JSON。
""")

        chain = prompt | self.llm | self.parser

        draft = chain.invoke({
            "country_name": agent.country_name,
            "aggression": agent.personality.get("aggression", 0.5),
            "diplomacy": agent.personality.get("diplomacy", 0.5),
            "economic_focus": agent.personality.get("economic_focus", 0.5),
            "risk_tolerance": agent.risk_tolerance,
            "objectives": "\n".join(f"- {obj}" for obj in agent.objectives),
            "rag_context": state.get("rag_context", ""),
            "format_instructions": self.parser.get_format_instructions()
        })

        state["draft_events"] = draft
        state["iterations"] = 1
        return state
```

### 3.2 AI决策系统

```python
# backend/ai/decision_maker.py

class AIDecisionMaker:
    """AI决策系统"""

    def __init__(self, llm):
        self.llm = llm

    async def select_best_action(
        self,
        agent: CountryAgent,
        options: List[GameEvent],
        world_state: WorldState
    ) -> GameEvent:
        """选择最佳行动"""

        # 构建决策提示词
        prompt = ChatPromptTemplate.from_template("""
你是{country_name}的最高决策者AI。

【当前态势】
时间: {year}年{month}月
军事实力: {military_power}
经济实力: {economic_strength}

【外交关系】
{diplomatic_relations}

【战略目标】
{objectives}

【性格特征】
{personality}

【可选行动】
{options}

【评估标准】
1. 目标契合度: 行动是否有助于实现战略目标
2. 风险评估: 行动的潜在风险是否在承受范围内
3. 时机判断: 当前是否是执行该行动的最佳时机
4. 国际影响: 行动对外交关系的影响
5. 资源消耗: 行动所需资源是否充足

请分析每个选项，选择最优行动。

输出格式:
{{
  "selected_action_id": "行动ID",
  "reasoning": "选择理由（100字内）",
  "expected_outcome": "预期结果",
  "risk_level": 0.0-1.0
}}
""")

        # 格式化选项
        options_text = "\n".join([
            f"{i+1}. [{opt.event_type}] {opt.name} (ID: {opt.id})\n"
            f"   描述: {opt.description}\n"
            f"   历史可能性: {opt.likelihood:.1%}\n"
            for i, opt in enumerate(options)
        ])

        # 调用LLM
        response = await self.llm.ainvoke(
            prompt.format(
                country_name=agent.country_name,
                year=agent.current_year,
                month=agent.current_month,
                military_power=world_state.military_power[agent.country_code],
                economic_strength=world_state.economic_strength[agent.country_code],
                diplomatic_relations=self._format_relations(agent, world_state),
                objectives="\n".join(f"- {obj}" for obj in agent.objectives),
                personality=json.dumps(agent.personality, indent=2, ensure_ascii=False),
                options=options_text
            )
        )

        # 解析响应
        decision = json.loads(response.content)
        selected_id = decision["selected_action_id"]

        # 记录决策理由
        print(f"[AI决策] {agent.country_name} 选择: {selected_id}")
        print(f"  理由: {decision['reasoning']}")
        print(f"  风险: {decision['risk_level']:.1%}")

        return next(opt for opt in options if opt.id == selected_id)
```

---

## 4. API接口设计

### 4.1 新增端点

#### 启动多Agent游戏

```python
# POST /api/multi-agent/start

class MultiAgentStartRequest(BaseModel):
    player_country: Literal["GER", "UK", "USSR"]

    # 可选：自定义Agent配置
    agent_configs: Optional[dict[str, dict]] = None

class MultiAgentStartResponse(BaseModel):
    session_id: str
    world_state: WorldState
    player_agent: CountryAgent
    ai_agents: List[CountryAgent]
    message: str
```

#### 执行回合

```python
# POST /api/multi-agent/turn

class ExecuteTurnRequest(BaseModel):
    session_id: str

class ExecuteTurnResponse(BaseModel):
    turn_number: int
    phase: TurnPhase

    # 所有Agent的选项（包括玩家）
    agent_options: dict[str, List[GameEvent]]

    # AI Agent的自动选择
    ai_choices: dict[str, GameEvent]

    # 等待玩家选择
    waiting_for_player: bool
```

#### 玩家提交选择

```python
# POST /api/multi-agent/player-choice

class PlayerChoiceRequest(BaseModel):
    session_id: str
    choice_id: str

class PlayerChoiceResponse(BaseModel):
    success: bool
    turn_result: TurnResult  # 回合结果（所有国家的行动影响）
    next_turn_ready: bool
```

### 4.2 完整游戏流程

```python
# backend/api/multi_agent_server.py

@app.post("/api/multi-agent/start")
async def start_multi_agent_game(request: MultiAgentStartRequest):
    """启动多Agent游戏"""
    session_id = str(uuid.uuid4())

    # 创建三个Agent
    agents = {
        "GER": CountryAgent(
            country_code="GER",
            country_name="德国",
            control_mode=ControlMode.HUMAN if request.player_country == "GER" else ControlMode.AI,
            objectives=["占领波兰", "避免两线作战", "建立欧洲霸权"],
            personality={"aggression": 0.8, "diplomacy": 0.4, "economic_focus": 0.6},
            risk_tolerance=0.7,
            current_year=1939,
            current_month=9,
            resources={"military": 100, "economic": 80, "diplomatic": 50}
        ),
        "UK": CountryAgent(
            country_code="UK",
            country_name="英国",
            control_mode=ControlMode.HUMAN if request.player_country == "UK" else ControlMode.AI,
            objectives=["保卫本土", "维护海上霸权", "阻止德国扩张"],
            personality={"aggression": 0.4, "diplomacy": 0.7, "economic_focus": 0.6},
            risk_tolerance=0.5,
            current_year=1939,
            current_month=9,
            resources={"military": 90, "economic": 100, "diplomatic": 80}
        ),
        "USSR": CountryAgent(
            country_code="USSR",
            country_name="苏联",
            control_mode=ControlMode.HUMAN if request.player_country == "USSR" else ControlMode.AI,
            objectives=["扩大领土", "建立缓冲区", "避免与德国冲突"],
            personality={"aggression": 0.6, "diplomacy": 0.5, "economic_focus": 0.7},
            risk_tolerance=0.6,
            current_year=1939,
            current_month=9,
            resources={"military": 110, "economic": 70, "diplomatic": 60}
        )
    }

    # 创建世界状态
    world_state = WorldState(
        current_turn=1,
        current_year=1939,
        current_month=9,
        agents=agents,
        diplomatic_relations={
            "GER": {"UK": -0.8, "USSR": 0.2},
            "UK": {"GER": -0.8, "USSR": -0.3},
            "USSR": {"GER": 0.2, "UK": -0.3}
        },
        military_power={"GER": 100, "UK": 90, "USSR": 110},
        economic_strength={"GER": 80, "UK": 100, "USSR": 70}
    )

    # 创建回合管理器
    turn_manager = TurnManager(world_state)

    # 保存会话
    multi_agent_sessions[session_id] = {
        "world_state": world_state,
        "turn_manager": turn_manager
    }

    return MultiAgentStartResponse(
        session_id=session_id,
        world_state=world_state,
        player_agent=agents[request.player_country],
        ai_agents=[agent for code, agent in agents.items() if code != request.player_country],
        message=f"多Agent游戏开始！你控制{agents[request.player_country].country_name}"
    )


@app.post("/api/multi-agent/turn")
async def execute_turn(request: ExecuteTurnRequest):
    """执行回合（规划+AI决策）"""
    session = multi_agent_sessions[request.session_id]
    turn_manager = session["turn_manager"]

    # 规划阶段：为所有Agent生成选项
    await turn_manager.planning_phase()

    # AI决策阶段：AI Agent自动选择
    await turn_manager.decision_phase()

    # 收集所有选项
    agent_options = {}
    ai_choices = {}

    for country_code, agent in turn_manager.world.agents.items():
        agent_options[country_code] = agent.pending_options

        if agent.control_mode == ControlMode.AI:
            ai_choices[country_code] = turn_manager.pending_actions[country_code]

    return ExecuteTurnResponse(
        turn_number=turn_manager.world.current_turn,
        phase=turn_manager.current_phase,
        agent_options=agent_options,
        ai_choices=ai_choices,
        waiting_for_player=True
    )


@app.post("/api/multi-agent/player-choice")
async def player_choice(request: PlayerChoiceRequest):
    """玩家提交选择"""
    session = multi_agent_sessions[request.session_id]
    turn_manager = session["turn_manager"]
    world_state = turn_manager.world

    # 找到玩家控制的Agent
    player_agent = next(
        agent for agent in world_state.agents.values()
        if agent.control_mode == ControlMode.HUMAN
    )

    # 记录玩家选择
    player_action = next(
        opt for opt in player_agent.pending_options
        if opt.id == request.choice_id
    )
    turn_manager.pending_actions[player_agent.country_code] = player_action

    # 执行阶段：处理所有行动
    await turn_manager.execution_phase()

    # 结算阶段：计算影响
    turn_result = await turn_manager.resolution_phase()

    # 推进时间
    turn_manager.advance_time()

    return PlayerChoiceResponse(
        success=True,
        turn_result=turn_result,
        next_turn_ready=True
    )
```

---

## 5. 前端UI设计

### 5.1 多Agent界面布局

```
┌─────────────────────────────────────────────────────────────┐
│                     回合 3 - 1939年11月                      │
└─────────────────────────────────────────────────────────────┘

┌──────────────┬──────────────────────────────┬──────────────┐
│  德国 🎮      │        世界地图/态势         │   英国 🤖     │
│  (玩家控制)   │                              │   (AI控制)   │
│              │                              │              │
│ 军事: 100    │   ┌──────────────────┐      │ 军事: 90     │
│ 经济: 80     │   │                  │      │ 经济: 100    │
│ 外交: 50     │   │   [地图可视化]    │      │ 外交: 80     │
│              │   │                  │      │              │
│ 待选行动:     │   │  GER <---> UK    │      │ AI选择:      │
│ ⚔️ 华沙围攻   │   │  关系: -0.8      │      │ 🛡️ 加强防御   │
│ 🤝 苏德协调   │   │                  │      │              │
│ 🏭 工业动员   │   │  GER <---> USSR  │      │              │
│ 📢 宣传胜利   │   │  关系: +0.2      │      │              │
│              │   │                  │      │              │
│ [选择行动]    │   └──────────────────┘      │ [查看详情]    │
└──────────────┴──────────────────────────────┴──────────────┘

┌──────────────────────────────────────────────────────────────┐
│                     苏联 🤖 (AI控制)                         │
│  军事: 110  |  经济: 70  |  外交: 60                         │
│  AI选择: 🌾 巩固东线防务                                      │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                       回合事件日志                            │
│  • 德国选择: 华沙围攻 ⚔️                                      │
│  • 英国选择: 加强防御 🛡️                                      │
│  • 苏联选择: 巩固东线防务 🌾                                  │
│  • 外交影响: 德英关系 -0.8 → -0.9                             │
│  • 军事冲突: 德军攻占华沙，波兰抵抗减弱                        │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 前端JavaScript

```javascript
// 多Agent游戏状态
let multiAgentGame = {
    sessionId: null,
    worldState: null,
    playerCountry: null,
    currentTurn: 1,
    agentOptions: {},   // 所有Agent的选项
    aiChoices: {}       // AI Agent的选择
};

// 启动多Agent游戏
async function startMultiAgentGame(playerCountry) {
    const response = await fetch(`${API_BASE}/api/multi-agent/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_country: playerCountry })
    });

    const data = await response.json();

    multiAgentGame.sessionId = data.session_id;
    multiAgentGame.worldState = data.world_state;
    multiAgentGame.playerCountry = playerCountry;

    // 显示多Agent界面
    displayMultiAgentUI(data);

    // 执行第一个回合
    await executeTurn();
}

// 执行回合
async function executeTurn() {
    showGlobalLoading('正在生成所有国家的行动选项...');

    const response = await fetch(`${API_BASE}/api/multi-agent/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: multiAgentGame.sessionId })
    });

    const data = await response.json();

    multiAgentGame.agentOptions = data.agent_options;
    multiAgentGame.aiChoices = data.ai_choices;
    multiAgentGame.currentTurn = data.turn_number;

    hideGlobalLoading();

    // 显示所有Agent的选项
    displayAllAgentOptions(data);
}

// 显示所有Agent的选项
function displayAllAgentOptions(data) {
    // 玩家国家：显示可选择的按钮
    const playerOptions = data.agent_options[multiAgentGame.playerCountry];
    displayPlayerOptions(playerOptions);

    // AI国家：显示AI的自动选择
    for (const [country, choice] of Object.entries(data.ai_choices)) {
        displayAIChoice(country, choice);
    }

    // 显示"确认选择"按钮（等待玩家）
    showConfirmButton();
}

// 玩家提交选择
async function submitPlayerChoice(choiceId) {
    showGlobalLoading('处理所有国家的行动...');

    const response = await fetch(`${API_BASE}/api/multi-agent/player-choice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: multiAgentGame.sessionId,
            choice_id: choiceId
        })
    });

    const data = await response.json();

    hideGlobalLoading();

    // 显示回合结果
    displayTurnResult(data.turn_result);

    // 延迟后开始下一回合
    setTimeout(() => {
        executeTurn();
    }, 3000);
}

// 显示回合结果
function displayTurnResult(result) {
    const logContainer = document.getElementById('turnEventLog');

    let html = `<h3>回合 ${multiAgentGame.currentTurn} 结果</h3>`;

    // 显示所有国家的行动
    html += '<div class="all-actions">';
    for (const [country, action] of Object.entries(result.all_actions)) {
        html += `
            <div class="action-item ${country === multiAgentGame.playerCountry ? 'player' : 'ai'}">
                <span class="country-flag">${getCountryFlag(country)}</span>
                <span class="country-name">${getCountryName(country)}</span>
                <span class="action-name">${action.name}</span>
                <span class="action-type">${getTypeIcon(action.event_type)}</span>
            </div>
        `;
    }
    html += '</div>';

    // 显示外交影响
    if (result.diplomatic_changes.length > 0) {
        html += '<h4>外交影响</h4><ul>';
        result.diplomatic_changes.forEach(change => {
            html += `<li>${change.country1} 与 ${change.country2} 关系: ${change.old_value.toFixed(2)} → ${change.new_value.toFixed(2)}</li>`;
        });
        html += '</ul>';
    }

    // 显示冲突
    if (result.conflicts.length > 0) {
        html += '<h4>军事冲突</h4><ul>';
        result.conflicts.forEach(conflict => {
            html += `<li>${conflict.description}</li>`;
        });
        html += '</ul>';
    }

    logContainer.innerHTML = html;
}
```

---

## 6. 实现路线图

### 阶段1：核心多Agent系统（2-3天）

✅ **数据模型**
- CountryAgent 模型
- WorldState 模型
- TurnManager 类

✅ **基础工作流**
- MultiAgentEventWorkflow
- AIDecisionMaker

### 阶段2：回合制系统（2-3天）

✅ **回合管理**
- 四阶段回合系统
- 并行决策处理
- 交互影响计算

✅ **API端点**
- /api/multi-agent/start
- /api/multi-agent/turn
- /api/multi-agent/player-choice

### 阶段3：前端UI（2-3天）

✅ **多Agent界面**
- 三国并列显示
- AI选择可视化
- 回合事件日志

✅ **交互优化**
- 实时更新
- 动画效果
- 响应式布局

### 阶段4：高级特性（可选）

🔄 **外交系统**
- 条约签订
- 宣战/停战
- 联盟机制

🔄 **军事冲突**
- 战斗模拟
- 领土占领
- 资源争夺

🔄 **经济系统**
- 资源生产
- 贸易往来
- 制裁禁运

---

## 7. 示例场景

### 场景：1939年9月，波兰战役

**回合1开始**

**德国（玩家控制）：**
```
待选行动:
1. ⚔️ 华沙围攻 (军事)
   - 重炮轰击压缩华沙防御圈，步兵巷战清剿残敌
   - 风险: 高 | 预期: 占领华沙

2. 🤝 苏德协调 (外交)
   - 与苏联确认分界线，同步进攻避免冲突
   - 风险: 低 | 预期: 改善德苏关系

3. 🏭 工业动员 (经济)
   - 全国工业转向军工，快速补充装甲与弹药
   - 风险: 中 | 预期: 提升军事产能

4. 📢 宣传胜利 (政治)
   - 国内广播宣称速胜，强化民族团结与军心
   - 风险: 低 | 预期: 提升国内士气
```

**英国（AI自动选择）：**
```
AI决策分析中...

评估4个选项:
1. 🛡️ 加强防御 - 目标契合度: 0.9
2. 📻 宣战广播 - 目标契合度: 0.8
3. ⚓ 封锁海峡 - 目标契合度: 0.7
4. 💰 动员资源 - 目标契合度: 0.6

AI选择: 🛡️ 加强防御
理由: 当前首要任务是保卫本土，德军正在进攻波兰，
      需要加强防御准备，避免直接军事冲突。
```

**苏联（AI自动选择）：**
```
AI决策分析中...

评估4个选项:
1. 🌾 巩固东线防务 - 目标契合度: 0.85
2. 🤝 与德协商 - 目标契合度: 0.8
3. ⚔️ 进军波兰东部 - 目标契合度: 0.75
4. 🏭 工业扩张 - 目标契合度: 0.7

AI选择: 🌾 巩固东线防务
理由: 与德国保持中立协议，同时加强边境防御，
      为未来可能的冲突做准备。
```

**玩家做出选择：华沙围攻**

**回合结果：**
```
═══════════════════════════════════════════
回合 1 结果 - 1939年9月
═══════════════════════════════════════════

行动执行:
  🦅 德国: 华沙围攻 ⚔️
  🦁 英国: 加强防御 🛡️
  ⭐ 苏联: 巩固东线防务 🌾

外交影响:
  • 德国 <-> 英国: -0.8 → -0.9 (关系恶化)
  • 德国 <-> 苏联: +0.2 → +0.15 (轻微下降)

军事结果:
  • 德军成功占领华沙
  • 波兰政府流亡
  • 德国军事实力 +5

经济影响:
  • 德国消耗资源: 军事 -10
  • 英国动员成本: 经济 -5

重大事件:
  • 波兰战役基本结束
  • 英法正式对德宣战
  • 世界大战全面爆发
═══════════════════════════════════════════

时间推进: 1939年10月
下一回合准备中...
```

---

## 8. 总结

这个多Agent架构将游戏从"玩家 vs AI"升级为"玩家控制Agent vs 多个AI Agent"，实现了：

✅ **真实的多方博弈**：三个国家同时决策，相互影响
✅ **AI对手个性化**：每个AI Agent有独特性格和战略
✅ **动态世界演化**：世界状态根据所有国家行动实时变化
✅ **沉浸式体验**：玩家真正扮演一个国家的决策者

**下一步：** 开始实现阶段1的核心多Agent系统！

---

**文档版本：** 1.0.0
**创建日期：** 2025-01-30
