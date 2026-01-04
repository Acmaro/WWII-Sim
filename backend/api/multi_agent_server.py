"""
多Agent游戏API服务器
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from typing import Dict, Literal, Optional, List

from pydantic import BaseModel

from backend.core.agent import (
    CountryAgent, WorldState, ControlMode,
    TurnPhase, TurnResult, GameEnding, PRESET_AGENTS
)
from backend.core.turn_manager import TurnManager
from backend.core.models import GameEvent
from backend.core.llm import get_llm
from backend.workflows.multi_agent_generation import MultiAgentEventWorkflow
from backend.ai.decision_maker import AIDecisionMaker
from backend.services.knowledge_base import get_knowledge_base
from backend.services.ending_generator import EndingGenerator


# ============================================================================
# 全局状态
# ============================================================================

multi_agent_sessions: Dict[str, Dict] = {}
knowledge_base = None
event_workflow = None
ai_decision_maker = None
ending_generator = None


# ============================================================================
# 请求/响应模型
# ============================================================================

class MultiAgentStartRequest(BaseModel):
    """启动多Agent游戏请求"""
    player_country: Literal["GER", "UK", "USSR"]


class MultiAgentStartResponse(BaseModel):
    """启动多Agent游戏响应"""
    session_id: str
    world_state: WorldState
    player_agent: CountryAgent
    ai_agents: List[CountryAgent]
    message: str


class ExecuteTurnRequest(BaseModel):
    """执行回合请求"""
    session_id: str


class ExecuteTurnResponse(BaseModel):
    """执行回合响应"""
    turn_number: int
    phase: TurnPhase
    agent_options: Dict[str, List[GameEvent]]  # country -> options
    ai_choices: Dict[str, GameEvent]  # country -> choice
    waiting_for_player: bool


class PlayerChoiceRequest(BaseModel):
    """玩家提交选择请求"""
    session_id: str
    choice_id: str


class PlayerChoiceResponse(BaseModel):
    """玩家提交选择响应"""
    success: bool
    turn_result: TurnResult
    next_turn_ready: bool


# ============================================================================
# 生命周期管理
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global knowledge_base, event_workflow, ai_decision_maker, ending_generator

    print("="*70)
    print("初始化多Agent游戏服务器...")
    print("="*70)

    try:
        # 加载知识库
        print("\n1. 加载知识库...")
        try:
            knowledge_base = get_knowledge_base()
            stats = knowledge_base.get_stats()
            print(f"   [OK] 加载了 {stats['total_events']} 个历史事件")
        except Exception as e:
            print(f"   [WARNING] 知识库加载失败: {e}")
            knowledge_base = None

        # 初始化工作流
        print("\n2. 初始化多Agent事件生成工作流...")
        event_workflow = MultiAgentEventWorkflow(knowledge_base=knowledge_base)
        print("   [OK] 多Agent工作流已就绪")

        # 初始化AI决策系统
        print("\n3. 初始化AI决策系统...")
        llm = get_llm()
        ai_decision_maker = AIDecisionMaker(llm)
        print("   [OK] AI决策系统已就绪")

        # 初始化结局生成器
        print("\n4. 初始化结局生成系统...")
        ending_generator = EndingGenerator(llm)
        print("   [OK] 结局生成系统已就绪")

        print("\n" + "="*70)
        print("[SUCCESS] 多Agent服务器初始化完成!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n[ERROR] 初始化失败: {e}")
        import traceback
        traceback.print_exc()

    yield

    print("\n服务器关闭中...")


# ============================================================================
# 创建FastAPI应用
# ============================================================================

app = FastAPI(
    title="WWII Multi-Agent Simulation API",
    description="基于多Agent系统的二战模拟游戏API",
    version="2.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API端点
# ============================================================================

@app.get("/")
async def root():
    """根端点"""
    return {
        "name": "WWII Multi-Agent Simulation API",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "多Agent并行决策",
            "AI个性化决策",
            "回合制系统",
            "动态世界状态"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "knowledge_base": knowledge_base is not None,
        "event_workflow": event_workflow is not None,
        "ai_decision_maker": ai_decision_maker is not None,
        "active_sessions": len(multi_agent_sessions)
    }


@app.post("/api/multi-agent/start", response_model=MultiAgentStartResponse)
async def start_multi_agent_game(request: MultiAgentStartRequest):
    """
    启动多Agent游戏

    创建3个国家Agent，玩家控制其中一个，AI控制其余
    """
    try:
        session_id = str(uuid.uuid4())

        # 创建三个Agent
        agents = {}
        for country_code in ["GER", "UK", "USSR"]:
            preset = PRESET_AGENTS[country_code]

            agent = CountryAgent(
                **preset,
                control_mode=(
                    ControlMode.HUMAN
                    if country_code == request.player_country
                    else ControlMode.AI
                ),
                current_year=1939,
                current_month=9
            )

            agents[country_code] = agent

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
            economic_strength={"GER": 80, "UK": 100, "USSR": 70},
            territories={
                "GER": ["德国本土"],
                "UK": ["英国本土"],
                "USSR": ["苏联本土"]
            }
        )

        # 创建回合管理器
        turn_manager = TurnManager(world_state)

        # 保存会话
        multi_agent_sessions[session_id] = {
            "world_state": world_state,
            "turn_manager": turn_manager,
            "player_country": request.player_country
        }

        # 收集AI Agent
        ai_agents = [
            agent for code, agent in agents.items()
            if code != request.player_country
        ]

        print(f"\n[游戏启动] 会话 {session_id}")
        print(f"  玩家国家: {request.player_country}")
        print(f"  AI国家: {[a.country_code for a in ai_agents]}")

        return MultiAgentStartResponse(
            session_id=session_id,
            world_state=world_state,
            player_agent=agents[request.player_country],
            ai_agents=ai_agents,
            message=f"多Agent游戏开始！你控制{agents[request.player_country].country_name}"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"启动游戏失败: {str(e)}")


@app.post("/api/multi-agent/turn", response_model=ExecuteTurnResponse)
async def execute_turn(request: ExecuteTurnRequest):
    """
    执行回合

    为所有Agent生成选项，AI自动选择
    """
    if request.session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = multi_agent_sessions[request.session_id]
    turn_manager: TurnManager = session["turn_manager"]
    world_state: WorldState = turn_manager.get_world_state()

    try:
        print(f"\n[回合开始] 回合 {world_state.current_turn}")

        # 阶段1: 规划 - 为所有Agent生成选项（并行）
        turn_manager.set_phase(TurnPhase.PLANNING)

        agent_options = {}

        print("\n  [并行] 为所有国家同时生成选项...")

        # 准备并行任务（使用线程池）
        def generate_for_one_agent(country_code: str, agent):
            if agent.control_mode == ControlMode.OBSERVER:
                return country_code, None

            # 收集其他Agent的行动历史
            other_actions = {
                other_country: other_agent.action_history
                for other_country, other_agent in world_state.agents.items()
                if other_country != country_code
            }

            # 生成选项
            branch_options = event_workflow.generate_for_agent(
                agent=agent,
                world_state=world_state,
                other_actions=other_actions
            )

            return country_code, branch_options

        # 使用线程池并行执行
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

        # 处理结果
        for country_code, branch_options in results:
            if branch_options is None:
                continue

            agent = world_state.agents[country_code]
            if branch_options and branch_options.branches:
                agent.pending_options = branch_options.branches
                agent_options[country_code] = branch_options.branches
                print(f"    [OK] {agent.country_name}: 生成了 {len(branch_options.branches)} 个选项")
            else:
                agent.pending_options = []
                agent_options[country_code] = []
                print(f"    [ERROR] {agent.country_name}: 生成失败")

        # 阶段2: 决策 - AI自动选择
        turn_manager.set_phase(TurnPhase.DECISION)

        ai_choices = {}

        for country_code, agent in world_state.agents.items():
            if agent.control_mode == ControlMode.AI and agent.pending_options:
                # AI自动决策
                choice = ai_decision_maker.select_best_action(
                    agent=agent,
                    options=agent.pending_options,
                    world_state=world_state
                )

                ai_choices[country_code] = choice
                turn_manager.record_action(country_code, choice)

                # 记录AI的行动到历史
                agent.action_history.append(choice.name)

        return ExecuteTurnResponse(
            turn_number=world_state.current_turn,
            phase=turn_manager.get_current_phase(),
            agent_options=agent_options,
            ai_choices=ai_choices,
            waiting_for_player=True
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"执行回合失败: {str(e)}")


@app.post("/api/multi-agent/player-choice", response_model=PlayerChoiceResponse)
async def player_choice(request: PlayerChoiceRequest):
    """
    玩家提交选择

    处理玩家选择，执行结算，推进时间
    """
    if request.session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = multi_agent_sessions[request.session_id]
    turn_manager: TurnManager = session["turn_manager"]
    world_state: WorldState = turn_manager.get_world_state()
    player_country: str = session["player_country"]

    try:
        # 找到玩家控制的Agent
        player_agent = world_state.get_agent(player_country)
        if not player_agent:
            raise HTTPException(status_code=404, detail="玩家Agent不存在")

        # 查找选择的行动
        player_action = next(
            (opt for opt in player_agent.pending_options if opt.id == request.choice_id),
            None
        )

        if player_action is None:
            raise HTTPException(status_code=400, detail=f"无效的选择ID: {request.choice_id}")

        print(f"\n[玩家选择] {player_country}: {player_action.name}")

        # 记录玩家行动
        turn_manager.record_action(player_country, player_action)
        player_agent.action_history.append(player_action.name)

        # 检查是否所有国家都已选择
        if not turn_manager.has_all_actions():
            raise HTTPException(status_code=400, detail="还有其他国家未选择")

        # 阶段3: 执行
        turn_manager.set_phase(TurnPhase.EXECUTION)

        # 阶段4: 结算
        turn_manager.set_phase(TurnPhase.RESOLUTION)
        turn_result = turn_manager.execute_resolution()

        # 推进时间
        turn_manager.advance_time()

        # 清空待处理行动
        turn_manager.clear_pending_actions()

        # 清空所有Agent的待选选项
        for agent in world_state.agents.values():
            agent.pending_options = []

        return PlayerChoiceResponse(
            success=True,
            turn_result=turn_result,
            next_turn_ready=True
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"提交选择失败: {str(e)}")


@app.get("/api/multi-agent/world")
async def get_world_state(session_id: str):
    """获取世界状态"""
    if session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = multi_agent_sessions[session_id]
    world_state: WorldState = session["turn_manager"].get_world_state()

    return world_state.model_dump(mode='json')


class SimulateEndingRequest(BaseModel):
    """模拟结局请求"""
    session_id: str


@app.post("/api/multi-agent/simulate-ending", response_model=GameEnding)
async def simulate_ending(request: SimulateEndingRequest):
    """
    AI驱动的结局生成

    基于当前游戏状态，使用AI模拟剩余的故事并生成结局
    """
    if request.session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = multi_agent_sessions[request.session_id]
    world_state: WorldState = session["turn_manager"].get_world_state()
    player_country: str = session["player_country"]

    try:
        print(f"\n[结局生成] 为会话 {request.session_id} 生成结局...")
        print(f"  当前回合: {world_state.current_turn}")
        print(f"  当前时间: {world_state.current_year}年{world_state.current_month}月")

        # 生成触发原因
        trigger_reason = f"玩家主动结算游戏（{world_state.current_year}年{world_state.current_month}月，第{world_state.current_turn}回合）"

        # 使用AI生成结局
        ending = ending_generator.generate_ending(
            world_state=world_state,
            trigger_reason=trigger_reason,
            player_country=player_country
        )

        print(f"  [OK] 结局生成完成")
        print(f"  结局类型: {ending.ending_type}")
        print(f"  胜利者: {ending.winner or '无'}")

        return ending

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成结局失败: {str(e)}")


# ============================================================================
# 运行服务器
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.multi_agent_server:app",
        host="0.0.0.0",
        port=8002,  # 使用不同端口避免冲突
        reload=False  # 多Agent模式下禁用reload
    )
