# WWIISim-v2 多Agent系统架构与工作流程文档

> **版本**: 2.0
> **最后更新**: 2026-01-02
> **作者**: Claude AI

---

## 目录

1. [系统架构概述](#系统架构概述)
2. [核心组件说明](#核心组件说明)
3. [LangGraph的作用与实现](#langgraph的作用与实现)
4. [完整工作流程](#完整工作流程)
5. [关键技术细节](#关键技术细节)
6. [数据流与状态管理](#数据流与状态管理)

---

## 系统架构概述

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层 (Frontend)                     │
│                    multi_agent.html/js                       │
│  - 国家选择界面                                              │
│  - 回合操作界面                                              │
│  - 结局显示界面                                              │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST API
┌────────────────────▼────────────────────────────────────────┐
│                    API层 (FastAPI)                           │
│                multi_agent_server.py                         │
│  - /api/multi-agent/start      启动游戏                     │
│  - /api/multi-agent/turn       执行回合                     │
│  - /api/multi-agent/player-choice 玩家选择                  │
│  - /api/multi-agent/simulate-ending 生成结局                │
└────────────┬───────────────┬──────────────┬─────────────────┘
             │               │              │
┌────────────▼──────┐ ┌──────▼─────┐ ┌─────▼──────────────┐
│  核心逻辑层        │ │ AI决策层    │ │  工作流层          │
│  (Core Logic)     │ │ (AI)        │ │  (Workflows)       │
│                   │ │             │ │                    │
│ - TurnManager     │ │ - AI        │ │ - LangGraph        │
│ - CountryAgent    │ │   Decision  │ │   事件生成工作流   │
│ - WorldState      │ │   Maker     │ │ - Ending           │
│                   │ │             │ │   Generator        │
└────────┬──────────┘ └─────────────┘ └──────┬─────────────┘
         │                                    │
┌────────▼────────────────────────────────────▼─────────────┐
│                    服务层 (Services)                       │
│  - KnowledgeBase (RAG) - 515个历史事件                    │
│  - LLM Service - LangChain + LM Studio                    │
└────────────────────────────────────────────────────────────┘
```

### 技术栈

- **后端框架**: FastAPI + Uvicorn
- **AI框架**: LangChain + LangGraph
- **LLM**: LM Studio (本地qwen3-vl-8b)
- **向量数据库**: FAISS
- **Embedding**: nomic-embed-text-v1.5
- **前端**: 原生HTML/CSS/JavaScript
- **数据验证**: Pydantic v2

---

## 核心组件说明

### 1. CountryAgent (国家Agent)

**文件位置**: `backend/core/agent.py`

```python
class CountryAgent(BaseModel):
    """代表一个国家的智能体"""

    # 基本信息
    country_code: str              # 国家代码 (GER/UK/USSR)
    country_name: str              # 国家名称
    control_mode: ControlMode      # HUMAN/AI/OBSERVER

    # 性格参数 (影响AI决策)
    personality: Dict[str, float] = {
        "aggression": 0.7,         # 侵略性 (0-1)
        "diplomacy": 0.5,          # 外交倾向
        "economic_focus": 0.6,     # 经济关注度
        "risk_tolerance": 0.8      # 风险容忍度
    }

    # 资源状态
    resources: Dict[str, float] = {
        "military": 100.0,         # 军事资源
        "economic": 100.0,         # 经济资源
        "diplomatic": 100.0        # 外交资源
    }

    # 战略目标
    strategic_goals: List[str]     # 如 ["扩张领土", "确保海权"]

    # 行动历史
    action_history: List[str]      # 记录所有历史行动
    pending_options: List[GameEvent] # 当前回合的待选项
```

**核心特性**:
- 每个Agent独立拥有性格、资源、目标
- AI Agent根据性格参数做出符合其特点的决策
- 行动历史用于结局生成和战略分析

### 2. WorldState (世界状态)

**文件位置**: `backend/core/agent.py`

```python
class WorldState(BaseModel):
    """全局游戏状态"""

    # 时间状态
    current_turn: int              # 当前回合数
    current_year: int              # 当前年份
    current_month: int             # 当前月份

    # 所有国家Agent
    agents: Dict[str, CountryAgent]  # country_code -> Agent

    # 外交关系网络
    diplomatic_relations: Dict[str, Dict[str, float]]
    # 例: {"GER": {"UK": -0.8, "USSR": 0.2}}
    # 范围: -1.0 (敌对) 到 1.0 (盟友)

    # 军事与经济实力
    military_power: Dict[str, int]
    economic_strength: Dict[str, int]

    # 领土控制
    territories: Dict[str, List[str]]
```

**关键方法**:
- `get_agent(country: str)`: 获取指定国家的Agent
- `get_relation(c1: str, c2: str)`: 获取两国关系
- `update_relations(c1, c2, delta)`: 更新外交关系（双向）

### 3. TurnManager (回合管理器)

**文件位置**: `backend/core/turn_manager.py`

```python
class TurnManager:
    """管理回合流程的四个阶段"""

    def __init__(self, world_state: WorldState):
        self.world = world_state
        self.current_phase = TurnPhase.PLANNING
        self.pending_actions: Dict[str, GameEvent] = {}
```

**四个回合阶段**:

1. **PLANNING** (规划): 为所有国家生成选项
2. **DECISION** (决策): AI选择，玩家等待输入
3. **EXECUTION** (执行): 处理所有行动
4. **RESOLUTION** (结算): 计算影响，更新状态

**关键方法**:
- `execute_resolution()`: 执行结算逻辑
- `_detect_conflicts()`: 检测军事冲突
- `_calculate_diplomatic_impact()`: 计算外交影响
- `_calculate_economic_impact()`: 计算资源变化
- `_check_game_ending()`: 检查7种结局条件
- `advance_time()`: 推进时间和回合数

---

## LangGraph的作用与实现

### LangGraph是什么？

**LangGraph** 是 LangChain 生态系统中的一个工作流编排框架，用于构建**有状态的、多步骤的AI应用**。

在本项目中，LangGraph用于实现**事件生成工作流**，确保生成的历史事件：
1. 符合历史真实性
2. 匹配国家性格
3. 具有高质量和多样性
4. 能够自动迭代优化

### LangGraph在项目中的架构

**文件位置**: `backend/workflows/event_generation.py` 和 `multi_agent_generation.py`

```python
from langgraph.graph import StateGraph, END

class EventGenerationWorkflow:
    """使用LangGraph构建的事件生成工作流"""

    def __init__(self, knowledge_base, llm):
        self.knowledge_base = knowledge_base
        self.llm = llm
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建状态图"""
        workflow = StateGraph(GenerationState)

        # 添加节点（处理步骤）
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("generate_draft", self.generate_draft)
        workflow.add_node("validate_quality", self.validate_quality)
        workflow.add_node("refine_events", self.refine_events)
        workflow.add_node("finalize", self.finalize)

        # 设置入口点
        workflow.set_entry_point("retrieve_context")

        # 添加边（流程控制）
        workflow.add_edge("retrieve_context", "generate_draft")
        workflow.add_edge("generate_draft", "validate_quality")

        # 条件边：根据质量决定是否重新生成
        workflow.add_conditional_edges(
            "validate_quality",
            self._should_refine,  # 决策函数
            {
                "refine": "refine_events",    # 质量不达标
                "finalize": "finalize"         # 质量达标
            }
        )

        workflow.add_edge("refine_events", "generate_draft")
        workflow.add_edge("finalize", END)

        return workflow.compile()
```

### LangGraph工作流详解

#### 工作流状态定义

```python
class GenerationState(TypedDict):
    """工作流的状态"""

    # 输入
    country_code: str
    current_year: int
    current_month: int
    agent_personality: Dict[str, float]
    world_state: Dict

    # 中间状态
    historical_context: List[HistoricalEvent]  # RAG检索结果
    draft_events: List[Dict]                   # 初稿事件
    quality_score: float                        # 质量评分
    iteration_count: int                        # 迭代次数

    # 输出
    final_events: List[GameEvent]              # 最终事件
```

#### 节点1: retrieve_context (检索历史上下文)

```python
def retrieve_context(self, state: GenerationState) -> GenerationState:
    """使用RAG检索相关历史事件"""

    # 构建查询
    query = f"{state['current_year']}年 {state['country_code']} 历史事件"

    # FAISS向量搜索
    relevant_events = self.knowledge_base.search(
        query=query,
        top_k=5,
        filters={"year": state['current_year']}
    )

    state["historical_context"] = relevant_events
    return state
```

**作用**: 从515个真实历史事件中检索相关内容，为LLM提供上下文。

#### 节点2: generate_draft (生成初稿)

```python
def generate_draft(self, state: GenerationState) -> GenerationState:
    """使用LLM生成初稿事件"""

    # 构建Prompt
    prompt = f"""
    基于以下历史背景，为{state['country_code']}生成4个可能的行动选项。

    历史背景：
    {format_historical_context(state['historical_context'])}

    国家性格：
    - 侵略性: {state['agent_personality']['aggression']}
    - 外交倾向: {state['agent_personality']['diplomacy']}

    要求：
    1. 符合历史真实性
    2. 反映国家性格特点
    3. 包含4种类型：军事、外交、经济、政治
    4. 每个选项要有明确的后果
    """

    # 调用LLM
    response = self.llm.invoke(prompt)

    # 解析响应
    draft_events = parse_llm_response(response.content)

    state["draft_events"] = draft_events
    state["iteration_count"] = state.get("iteration_count", 0) + 1

    return state
```

**作用**: 结合历史上下文和国家性格，生成4个候选事件。

#### 节点3: validate_quality (质量验证)

```python
def validate_quality(self, state: GenerationState) -> GenerationState:
    """验证生成事件的质量"""

    events = state["draft_events"]

    # 评分维度
    scores = {
        "format_valid": check_format(events),           # 格式正确性
        "diversity": calculate_diversity(events),        # 多样性
        "consistency": check_consistency(                # 一致性
            events,
            state['agent_personality']
        ),
        "historical_accuracy": check_history(            # 历史准确性
            events,
            state['historical_context']
        )
    }

    # 计算总分 (0-100)
    total_score = sum(scores.values()) / len(scores) * 100

    state["quality_score"] = total_score

    return state
```

**质量标准**:
- **格式正确性**: 所有必需字段完整
- **多样性**: 4个选项类型不同
- **一致性**: 符合国家性格
- **历史准确性**: 与真实历史相符

**阈值**: 85分以上通过，否则重新生成

#### 条件判断: _should_refine

```python
def _should_refine(self, state: GenerationState) -> str:
    """决定是否需要重新生成"""

    # 质量达标
    if state["quality_score"] >= 85.0:
        return "finalize"

    # 迭代次数过多，放弃优化
    if state["iteration_count"] >= 3:
        return "finalize"

    # 需要重新生成
    return "refine"
```

**迭代策略**:
- 质量 ≥ 85分 → 通过
- 迭代 ≥ 3次 → 强制通过（避免无限循环）
- 其他情况 → 重新生成

#### 节点4: refine_events (优化事件)

```python
def refine_events(self, state: GenerationState) -> GenerationState:
    """根据质量反馈优化事件"""

    # 分析问题
    feedback = analyze_quality_issues(
        state["draft_events"],
        state["quality_score"]
    )

    # 添加反馈到下一轮生成
    state["refinement_feedback"] = feedback

    # 返回到 generate_draft 节点
    return state
```

**作用**: 分析质量不达标的原因，为下一轮生成提供反馈。

#### 节点5: finalize (最终输出)

```python
def finalize(self, state: GenerationState) -> GenerationState:
    """转换为最终格式"""

    final_events = []

    for draft in state["draft_events"]:
        event = GameEvent(
            id=generate_unique_id(),
            name=draft["name"],
            event_type=draft["type"],
            description=draft["description"],
            year=state["current_year"],
            month=state["current_month"],
            country=state["country_code"]
        )
        final_events.append(event)

    state["final_events"] = final_events

    return state
```

**作用**: 将验证通过的事件转换为Pydantic模型。

### LangGraph的优势

1. **可视化流程**: 状态图清晰展示工作流
2. **状态管理**: 自动管理中间状态
3. **条件路由**: 根据质量动态决定流程
4. **迭代优化**: 自动循环直到达标
5. **可调试**: 每个节点独立测试

### 多Agent扩展版本

**文件位置**: `backend/workflows/multi_agent_generation.py`

```python
class MultiAgentEventWorkflow(EventGenerationWorkflow):
    """多Agent版本，增加了国家间互动考虑"""

    def generate_for_agent(
        self,
        agent: CountryAgent,
        world_state: WorldState,
        other_actions: Dict[str, List[str]]  # 其他国家的历史行动
    ) -> BranchResponse:
        """为单个Agent生成事件，考虑其他国家的影响"""

        # 构建增强的状态
        state = {
            "country_code": agent.country_code,
            "agent_personality": agent.personality,
            "world_state": world_state.model_dump(),
            "other_actions": other_actions,  # 新增：其他国家行动
            # ...
        }

        # 运行LangGraph工作流
        result = self.graph.invoke(state)

        return BranchResponse(
            branches=result["final_events"],
            ending_probability=0.0,
            war_score=None
        )
```

**多Agent特性**:
- 考虑其他国家的历史行动
- 生成时避免重复或冲突
- 更好的国际互动性

---

## 完整工作流程

### 阶段1: 游戏启动

```
用户选择国家 (例: GER)
    ↓
POST /api/multi-agent/start
    ↓
multi_agent_server.start_multi_agent_game()
    │
    ├─ 创建3个CountryAgent
    │   ├─ GER (HUMAN控制)
    │   │   └─ personality: {aggression: 0.8, ...}
    │   ├─ UK (AI控制)
    │   │   └─ personality: {aggression: 0.6, ...}
    │   └─ USSR (AI控制)
    │       └─ personality: {aggression: 0.7, ...}
    │
    ├─ 创建WorldState
    │   ├─ current_turn = 1
    │   ├─ current_year = 1939
    │   ├─ current_month = 9
    │   └─ diplomatic_relations = {
    │       "GER": {"UK": -0.8, "USSR": 0.2},
    │       ...
    │   }
    │
    └─ 创建TurnManager
        └─ current_phase = PLANNING
    ↓
返回 session_id, world_state, agents
    ↓
前端初始化游戏界面
```

### 阶段2: 回合执行 (Planning Phase)

```
前端自动调用
    ↓
POST /api/multi-agent/turn
    ↓
TurnManager.set_phase(PLANNING)
    ↓
并行生成选项 (ThreadPoolExecutor)
    │
    ├─────────────────┬─────────────────┬─────────────────┐
    │                 │                 │                 │
Thread 1          Thread 2          Thread 3
generate_for      generate_for      generate_for
GER               UK                USSR
    │                 │                 │
    ▼                 ▼                 ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ LangGraph   │ │ LangGraph   │ │ LangGraph   │
│ Workflow    │ │ Workflow    │ │ Workflow    │
├─────────────┤ ├─────────────┤ ├─────────────┤
│ 1.retrieve  │ │ 1.retrieve  │ │ 1.retrieve  │
│   context   │ │   context   │ │   context   │
│   ↓         │ │   ↓         │ │   ↓         │
│ 2.generate  │ │ 2.generate  │ │ 2.generate  │
│   draft     │ │   draft     │ │   draft     │
│   ↓         │ │   ↓         │ │   ↓         │
│ 3.validate  │ │ 3.validate  │ │ 3.validate  │
│   quality   │ │   quality   │ │   quality   │
│   ↓         │ │   ↓         │ │   ↓         │
│ [循环优化]  │ │ [循环优化]  │ │ [循环优化]  │
│   ↓         │ │   ↓         │ │   ↓         │
│ 4.finalize  │ │ 4.finalize  │ │ 4.finalize  │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┴───────────────┘
                       │
                       ▼
            await asyncio.gather(*tasks)
                       │
                       ▼
        每个国家获得4个选项
                       │
                       ▼
        agent.pending_options = branches
```

**并发优化**:
- 使用 `ThreadPoolExecutor` 真正并发
- 3个国家同时生成，速度提升3倍
- 从原来的9-15秒优化到3-5秒

### 阶段3: AI决策 (Decision Phase)

```
TurnManager.set_phase(DECISION)
    ↓
遍历所有AI控制的Agent
    ↓
for country_code, agent in world_state.agents.items():
    if agent.control_mode == ControlMode.AI:
        ↓
        AIDecisionMaker.select_best_action()
            │
            ├─ 输入: agent.pending_options (4个选项)
            │
            ├─ 为每个选项评分
            │   ├─ 基础分: random(0.3, 0.7)
            │   ├─ 性格匹配:
            │   │   └─ if option.type == "military":
            │   │       score += aggression * 0.2
            │   └─ 历史准确性: +0.1
            │
            ├─ 选择得分最高的选项
            │
            └─ 返回: best_action
        ↓
        turn_manager.record_action(country_code, choice)
        agent.action_history.append(choice.name)  # 记录历史
        ↓
        ai_choices[country_code] = choice
    ↓
返回前端: {ai_choices, agent_options, waiting_for_player: true}
```

**AI决策示例**:

```python
选项列表:
1. 军事: "进攻波兰" - 基础分0.5 + 侵略性0.8*0.2 = 0.66
2. 外交: "与苏联谈判" - 基础分0.4 + 外交0.5*0.2 = 0.50
3. 经济: "工业动员" - 基础分0.6 + 经济0.6*0.2 = 0.72  ← 选中
4. 政治: "内部整顿" - 基础分0.45
```

### 阶段4: 玩家选择

```
前端显示选项
    ↓
玩家点击选择
    ↓
selectOption(optionId)
    ↓
玩家点击"确认选择"
    ↓
POST /api/multi-agent/player-choice
    ↓
multi_agent_server.player_choice()
    │
    ├─ 查找玩家选择的行动
    │
    ├─ turn_manager.record_action(player_country, action)
    ├─ agent.action_history.append(action.name)
    │
    ├─ 检查是否所有国家都已选择
    │   └─ turn_manager.has_all_actions()
    │
    └─ 继续到EXECUTION阶段
```

### 阶段5: 执行与结算 (Execution & Resolution)

```
TurnManager.set_phase(EXECUTION)
    ↓
TurnManager.set_phase(RESOLUTION)
    ↓
TurnManager.execute_resolution()
    │
    ├─ 1. 收集所有行动
    │   └─ all_actions = {country: action for ...}
    │
    ├─ 2. 检测冲突
    │   └─ _detect_conflicts()
    │       └─ if 多个国家都进行军事行动:
    │           conflicts.append({...})
    │
    ├─ 3. 计算外交影响
    │   └─ _calculate_diplomatic_impact()
    │       ├─ for 每个行动:
    │       │   ├─ if type == "military":
    │       │   │   └─ 降低与所有国家的关系 (-0.1)
    │       │   └─ if type == "diplomatic":
    │       │       └─ 提升与所有国家的关系 (+0.05)
    │       └─ world_state.update_relations(双向更新)
    │
    ├─ 4. 计算经济影响
    │   └─ _calculate_economic_impact()
    │       ├─ if type == "military":
    │       │   └─ military -= 10
    │       └─ if type == "economic":
    │           └─ economic += 5
    │
    ├─ 5. 检查游戏结局
    │   └─ _check_game_ending()
    │       ├─ 时间 >= 1945.5? → 结束
    │       ├─ 回合 >= 100? → 结束
    │       ├─ military == 0? → 崩溃
    │       ├─ economic == 0? → 崩溃
    │       ├─ military >= 250? → 霸权
    │       ├─ 全面战争? → 资源枯竭
    │       └─ 外交孤立? → 结束
    │
    └─ 6. 创建TurnResult
        └─ is_game_over, ending_trigger
    ↓
turn_manager.advance_time()
    ├─ current_month += 1
    ├─ if current_month > 12:
    │   ├─ current_month = 1
    │   └─ current_year += 1
    └─ current_turn += 1
    ↓
返回: TurnResult
```

### 阶段6: 结局生成 (可选)

```
用户点击"查看结局" 或 自动触发
    ↓
POST /api/multi-agent/simulate-ending
    ↓
EndingGenerator.generate_ending()
    │
    ├─ 1. 计算战略得分
    │   ├─ _calculate_strategic_score(玩家)
    │   │   ├─ 资源平衡性: 30分
    │   │   │   ├─ 资源总量: min(15, total/20)
    │   │   │   └─ 资源平衡: min_resource判断
    │   │   ├─ 外交关系: 25分
    │   │   │   ├─ 盟友(>0.5): +15分
    │   │   │   ├─ 友好(>0): +8分
    │   │   │   └─ 敌对(<-0.5): -5分
    │   │   ├─ 战略一致性: 25分
    │   │   │   └─ 分析行动类型分布
    │   │   └─ 行动多样性: 20分
    │   │       └─ unique/total * 20
    │   │
    │   └─ _calculate_strategic_score(其他国家)
    │       └─ 计算平均分
    │
    ├─ 2. 判断结局类型
    │   ├─ 得分差 > 15 → victory
    │   ├─ 得分差 < -15 → defeat
    │   └─ 其他 → historical
    │
    ├─ 3. 生成主叙事 (LLM)
    │   └─ _generate_narrative()
    │       ├─ 分析玩家战略特征
    │       │   ├─ 行动类型统计
    │       │   ├─ 判断主导战略
    │       │   └─ 盟友/敌人关系
    │       │
    │       └─ LLM Prompt:
    │           "你是历史小说家，创作600-900字的史诗叙事
    │            - 10%回顾过去
    │            - 70%模拟未来历史
    │            - 20%战后格局
    │            禁止使用游戏术语，重点在未来..."
    │
    ├─ 4. 生成各国后续 (LLM)
    │   └─ _generate_epilogue()
    │       └─ for 每个国家:
    │           └─ _generate_country_epilogue()
    │               └─ LLM生成50-80字个性化描述
    │
    ├─ 5. 收集关键事件
    │   └─ _collect_key_events()
    │       ├─ 从所有国家action_history收集
    │       ├─ 按时间排序
    │       └─ 优先军事和外交事件
    │
    └─ 6. 构建最终统计
        └─ _build_final_stats()
            └─ 回合数、资源、行动数等
    ↓
返回: GameEnding
    ├─ ending_type
    ├─ narrative (史诗故事)
    ├─ epilogue (各国命运)
    ├─ key_events
    └─ final_stats
    ↓
前端显示结局界面
```

---

## 关键技术细节

### 1. RAG (检索增强生成)

**实现**: `backend/services/knowledge_base.py`

```python
class KnowledgeBase:
    """基于FAISS的历史事件知识库"""

    def __init__(self):
        # 加载515个历史事件
        events = load_json("data/historical_events.json")

        # 使用Embedding模型转换为向量
        embeddings = HuggingFaceEmbeddings(
            model_name="nomic-ai/nomic-embed-text-v1.5"
        )

        # 创建FAISS向量库
        self.vectorstore = FAISS.from_documents(
            documents=events,
            embedding=embeddings
        )

    def search(self, query: str, top_k: int = 5):
        """语义搜索相关历史事件"""
        return self.vectorstore.similarity_search(
            query,
            k=top_k
        )
```

**工作原理**:
1. 将515个历史事件转换为768维向量
2. 使用FAISS构建索引（支持快速相似度搜索）
3. 查询时，将查询文本也转换为向量
4. 计算余弦相似度，返回Top-K结果

**优势**:
- 语义搜索而非关键词匹配
- 毫秒级搜索速度
- 支持复杂查询

### 2. 并发事件生成

**实现**: `backend/api/multi_agent_server.py`

```python
# 使用线程池并发执行
import asyncio
from concurrent.futures import ThreadPoolExecutor

loop = asyncio.get_event_loop()
with ThreadPoolExecutor(max_workers=3) as executor:
    tasks = [
        loop.run_in_executor(
            executor,
            generate_for_one_agent,
            country_code,
            agent
        )
        for country_code, agent in world_state.agents.items()
    ]
    results = await asyncio.gather(*tasks)
```

**性能对比**:
- 顺序执行: 3 × 5秒 = 15秒
- 并发执行: max(5秒) = 5秒
- **提升3倍速度**

### 3. 智能结局判断

**不仅看数值，综合评估**:

```python
战略得分 =
    资源平衡性(30%) +
    外交关系(25%) +
    战略一致性(25%) +
    行动多样性(20%)

结局判定:
    if 玩家得分 - 平均得分 > 15: 胜利
    elif 玩家得分 - 平均得分 < -15: 失败
    else: 历史结局
```

**示例**:

```
玩家德国:
- 资源: 军120, 经80, 外100 → 平衡分25/30
- 外交: 与英国敌对, 与苏联友好 → 15/25
- 战略: 60%军事, 30%外交, 10%经济 → 20/25
- 多样性: 8种不同行动 / 10次 = 16/20
总分: 76分

其他国家平均: 58分

结果: 76 - 58 = +18 > 15 → 胜利
```

### 4. 历史叙事生成

**改进的Prompt工程**:

```python
# 禁止游戏术语
禁止词: ["玩家", "第X回合", "选择了", "他们"]

# 强调故事性
要求:
- 史诗叙事风格
- 具体场景描写
- 70%模拟未来
- 使用国家名称

# 结构化输出
10% - 简短回顾已发生的事件
70% - 详细模拟接下来的历史进程
20% - 战后世界格局
```

**效果对比**:

改进前:
> "第一回合，玩家选择了外交施压..."

改进后:
> "1939年秋，德意志帝国展开了精心策划的外交攻势。柏林与莫斯科的秘密会谈持续数月，最终达成了震惊世界的互不侵犯条约。接下来的数年间..."

---

## 数据流与状态管理

### 数据流图

```
用户输入
    ↓
HTTP请求 → FastAPI → API端点
    ↓
业务逻辑层
    ├─ TurnManager (状态管理)
    ├─ CountryAgent (Agent状态)
    └─ WorldState (全局状态)
    ↓
AI处理层
    ├─ LangGraph Workflow → LLM → RAG
    ├─ AIDecisionMaker → LLM
    └─ EndingGenerator → LLM
    ↓
数据返回 → JSON → 前端渲染
```

### 状态持久化

**会话管理**:

```python
# 全局会话字典
multi_agent_sessions: Dict[str, Dict] = {
    "session_id_123": {
        "world_state": WorldState(...),
        "turn_manager": TurnManager(...),
        "player_country": "GER"
    }
}
```

**生命周期**:
- 游戏启动: 创建session
- 每回合: 读取和更新session
- 结局生成: 读取session
- 服务器重启: session丢失（内存存储）

**扩展方案**:
- 使用Redis持久化session
- 定期保存到数据库
- 支持断线重连

### 性能优化总结

1. **并发生成**: ThreadPoolExecutor (3x提速)
2. **向量搜索**: FAISS (毫秒级检索)
3. **质量控制**: LangGraph自动迭代
4. **缓存机制**: LLM响应缓存（可扩展）
5. **异步API**: FastAPI原生异步支持

---

## 总结

### LangGraph的核心价值

1. **流程可视化**: 状态图清晰展示工作流
2. **自动迭代**: 质量不达标自动重试
3. **状态管理**: 统一管理中间状态
4. **可扩展性**: 轻松添加新节点
5. **可调试性**: 每个节点独立测试

### 系统特点

- ✅ **真多Agent**: 每个国家独立决策
- ✅ **AI个性化**: 基于性格参数
- ✅ **历史真实**: RAG检索515事件
- ✅ **质量保证**: 自动迭代优化
- ✅ **智能结局**: 综合战略评分
- ✅ **史诗叙事**: AI生成完整故事

### 技术栈优势

- **LangChain + LangGraph**: 强大的AI工作流
- **FAISS**: 高效的向量检索
- **FastAPI**: 高性能异步API
- **Pydantic**: 严格的类型验证
- **LM Studio**: 本地部署，数据安全

---

**文档版本**: v2.0
**更新日期**: 2026-01-02
**维护者**: Claude AI

如有疑问，请参考代码注释或提Issue。
