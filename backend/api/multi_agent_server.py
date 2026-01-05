"""
Multi-Agent Game API Server
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
# Global State
# ============================================================================

multi_agent_sessions: Dict[str, Dict] = {}
knowledge_base = None
event_workflow = None
ai_decision_maker = None
ending_generator = None


# ============================================================================
# Request/Response Models
# ============================================================================

class MultiAgentStartRequest(BaseModel):
    """Multi-agent game start request"""
    player_country: Literal["GER", "UK", "USSR"]


class MultiAgentStartResponse(BaseModel):
    """Multi-agent game start response"""
    session_id: str
    world_state: WorldState
    player_agent: CountryAgent
    ai_agents: List[CountryAgent]
    message: str


class ExecuteTurnRequest(BaseModel):
    """Execute turn request"""
    session_id: str


class ExecuteTurnResponse(BaseModel):
    """Execute turn response"""
    turn_number: int
    phase: TurnPhase
    agent_options: Dict[str, List[GameEvent]]  # country -> options
    ai_choices: Dict[str, GameEvent]  # country -> choice
    waiting_for_player: bool


class PlayerChoiceRequest(BaseModel):
    """Player submit choice request"""
    session_id: str
    choice_id: str


class PlayerChoiceResponse(BaseModel):
    """Player submit choice response"""
    success: bool
    turn_result: TurnResult
    next_turn_ready: bool


# ============================================================================
# Lifecycle Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    global knowledge_base, event_workflow, ai_decision_maker, ending_generator

    print("="*70)
    print("Initializing multi-agent game server...")
    print("="*70)

    try:
        # Load knowledge base
        print("\n1. Loading knowledge base...")
        try:
            knowledge_base = get_knowledge_base()
            stats = knowledge_base.get_stats()
            print(f"   [OK] Loaded {stats['total_events']} historical events")
        except Exception as e:
            print(f"   [WARNING] Knowledge base loading failed: {e}")
            knowledge_base = None

        # Initialize workflow
        print("\n2. Initializing multi-agent event generation workflow...")
        event_workflow = MultiAgentEventWorkflow(knowledge_base=knowledge_base)
        print("   [OK] Multi-agent workflow ready")

        # Initialize AI decision system
        print("\n3. Initializing AI decision system...")
        llm = get_llm()
        ai_decision_maker = AIDecisionMaker(llm)
        print("   [OK] AI decision system ready")

        # Initialize ending generator
        print("\n4. Initializing ending generation system...")
        ending_generator = EndingGenerator(llm)
        print("   [OK] Ending generation system ready")

        print("\n" + "="*70)
        print("[SUCCESS] Multi-agent server initialization complete!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Initialization failed: {e}")
        import traceback
        traceback.print_exc()

    yield

    print("\nServer shutting down...")


# ============================================================================
# Create FastAPI Application
# ============================================================================

app = FastAPI(
    title="WWII Multi-Agent Simulation API",
    description="Multi-agent system based WWII simulation game API",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "WWII Multi-Agent Simulation API",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "Multi-agent parallel decision-making",
            "AI personalized decisions",
            "Turn-based system",
            "Dynamic world state"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check"""
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
    Start multi-agent game

    Create 3 country agents, player controls one, AI controls the rest
    """
    try:
        session_id = str(uuid.uuid4())

        # Create three agents
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

        # Create world state
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
                "GER": ["Germany mainland"],
                "UK": ["United Kingdom mainland"],
                "USSR": ["Soviet Union mainland"]
            }
        )

        # Create turn manager
        turn_manager = TurnManager(world_state)

        # Save session
        multi_agent_sessions[session_id] = {
            "world_state": world_state,
            "turn_manager": turn_manager,
            "player_country": request.player_country
        }

        # Collect AI agents
        ai_agents = [
            agent for code, agent in agents.items()
            if code != request.player_country
        ]

        print(f"\n[Game Start] Session {session_id}")
        print(f"  Player country: {request.player_country}")
        print(f"  AI countries: {[a.country_code for a in ai_agents]}")

        return MultiAgentStartResponse(
            session_id=session_id,
            world_state=world_state,
            player_agent=agents[request.player_country],
            ai_agents=ai_agents,
            message=f"Multi-agent game started! You control {agents[request.player_country].country_name}"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start game: {str(e)}")


@app.post("/api/multi-agent/turn", response_model=ExecuteTurnResponse)
async def execute_turn(request: ExecuteTurnRequest):
    """
    Execute turn

    Generate options for all agents, AI automatically chooses
    """
    if request.session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = multi_agent_sessions[request.session_id]
    turn_manager: TurnManager = session["turn_manager"]
    world_state: WorldState = turn_manager.get_world_state()

    try:
        print(f"\n[Turn Start] Turn {world_state.current_turn}")

        # Phase 1: Planning - Generate options for all agents (parallel)
        turn_manager.set_phase(TurnPhase.PLANNING)

        agent_options = {}

        print("\n  [Parallel] Generating options for all countries simultaneously...")

        # Prepare parallel tasks (using thread pool)
        def generate_for_one_agent(country_code: str, agent):
            if agent.control_mode == ControlMode.OBSERVER:
                return country_code, None

            # Collect action history from other agents
            other_actions = {
                other_country: other_agent.action_history
                for other_country, other_agent in world_state.agents.items()
                if other_country != country_code
            }

            # Generate options
            branch_options = event_workflow.generate_for_agent(
                agent=agent,
                world_state=world_state,
                other_actions=other_actions
            )

            return country_code, branch_options

        # Execute in parallel using thread pool
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

        # Process results
        for country_code, branch_options in results:
            if branch_options is None:
                continue

            agent = world_state.agents[country_code]
            if branch_options and branch_options.branches:
                agent.pending_options = branch_options.branches
                agent_options[country_code] = branch_options.branches
                print(f"    [OK] {agent.country_name}: Generated {len(branch_options.branches)} options")
            else:
                agent.pending_options = []
                agent_options[country_code] = []
                print(f"    [ERROR] {agent.country_name}: Generation failed")

        # Phase 2: Decision - AI automatically chooses
        turn_manager.set_phase(TurnPhase.DECISION)

        ai_choices = {}

        for country_code, agent in world_state.agents.items():
            if agent.control_mode == ControlMode.AI and agent.pending_options:
                # AI automatically decides
                choice = ai_decision_maker.select_best_action(
                    agent=agent,
                    options=agent.pending_options,
                    world_state=world_state
                )

                ai_choices[country_code] = choice
                turn_manager.record_action(country_code, choice)

                # Record AI's action to history
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
        raise HTTPException(status_code=500, detail=f"Failed to execute turn: {str(e)}")


@app.post("/api/multi-agent/player-choice", response_model=PlayerChoiceResponse)
async def player_choice(request: PlayerChoiceRequest):
    """
    Player submit choice

    Process player choice, execute resolution, advance time
    """
    if request.session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = multi_agent_sessions[request.session_id]
    turn_manager: TurnManager = session["turn_manager"]
    world_state: WorldState = turn_manager.get_world_state()
    player_country: str = session["player_country"]

    try:
        # Find player-controlled agent
        player_agent = world_state.get_agent(player_country)
        if not player_agent:
            raise HTTPException(status_code=404, detail="Player agent not found")

        # Find chosen action
        player_action = next(
            (opt for opt in player_agent.pending_options if opt.id == request.choice_id),
            None
        )

        if player_action is None:
            raise HTTPException(status_code=400, detail=f"Invalid choice ID: {request.choice_id}")

        print(f"\n[Player Choice] {player_country}: {player_action.name}")

        # Record player action
        turn_manager.record_action(player_country, player_action)
        player_agent.action_history.append(player_action.name)

        # Check if all countries have chosen
        if not turn_manager.has_all_actions():
            raise HTTPException(status_code=400, detail="Other countries have not chosen yet")

        # Phase 3: Execution
        turn_manager.set_phase(TurnPhase.EXECUTION)

        # Phase 4: Resolution
        turn_manager.set_phase(TurnPhase.RESOLUTION)
        turn_result = turn_manager.execute_resolution()

        # Advance time
        turn_manager.advance_time()

        # Clear pending actions
        turn_manager.clear_pending_actions()

        # Clear all agents' pending options
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
        raise HTTPException(status_code=500, detail=f"Failed to submit choice: {str(e)}")


@app.get("/api/multi-agent/world")
async def get_world_state(session_id: str):
    """Get world state"""
    if session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = multi_agent_sessions[session_id]
    world_state: WorldState = session["turn_manager"].get_world_state()

    return world_state.model_dump(mode='json')


class SimulateEndingRequest(BaseModel):
    """Simulate ending request"""
    session_id: str


@app.post("/api/multi-agent/simulate-ending", response_model=GameEnding)
async def simulate_ending(request: SimulateEndingRequest):
    """
    AI-driven ending generation

    Based on current game state, use AI to simulate remaining story and generate ending
    """
    if request.session_id not in multi_agent_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = multi_agent_sessions[request.session_id]
    world_state: WorldState = session["turn_manager"].get_world_state()
    player_country: str = session["player_country"]

    try:
        print(f"\n[Ending Generation] Generating ending for session {request.session_id}...")
        print(f"  Current turn: {world_state.current_turn}")
        print(f"  Current time: {world_state.current_year}/{world_state.current_month}")

        # Generate trigger reason
        trigger_reason = f"Player initiated game settlement ({world_state.current_year}/{world_state.current_month}, Turn {world_state.current_turn})"

        # Use AI to generate ending
        ending = ending_generator.generate_ending(
            world_state=world_state,
            trigger_reason=trigger_reason,
            player_country=player_country
        )

        print(f"  [OK] Ending generation complete")
        print(f"  Ending type: {ending.ending_type}")
        print(f"  Winner: {ending.winner or 'None'}")

        return ending

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate ending: {str(e)}")


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.multi_agent_server:app",
        host="0.0.0.0",
        port=8002,  # Use different port to avoid conflicts
        reload=False  # Disable reload in multi-agent mode
    )
