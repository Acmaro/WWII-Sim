"""
FastAPI Server

Provides RESTful API interface
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from typing import Dict

from backend.core.models import (
    StartGameRequest, StartGameResponse,
    GetBranchesRequest, GetBranchesResponse,
    MakeChoiceRequest, MakeChoiceResponse,
    GameSession, GameEvent
)
from backend.core.config import settings
from backend.workflows.event_generation import create_event_generation_workflow
from backend.services.knowledge_base import get_knowledge_base


# ============================================================================
# Global State
# ============================================================================

# Game session storage
sessions: Dict[str, GameSession] = {}

# Knowledge base and workflow
knowledge_base = None
event_workflow = None


# ============================================================================
# Lifecycle Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    global knowledge_base, event_workflow

    # Initialize on startup
    print("="*70)
    print("Initializing WWIISim-v2 server...")
    print("="*70)

    try:
        # Initialize knowledge base
        print("\n1. Loading knowledge base...")
        try:
            knowledge_base = get_knowledge_base()
            stats = knowledge_base.get_stats()
            print(f"   [OK] Loaded {stats['total_events']} historical events")
            print(f"   [OK] Vector dimension: {stats['vector_dimension']}")
        except Exception as kb_error:
            print(f"   [WARNING] Knowledge base loading failed: {kb_error}")
            print("   [WARNING] Running in non-RAG mode")
            knowledge_base = None

        # Initialize workflow
        print("\n2. Initializing event generation workflow...")
        event_workflow = create_event_generation_workflow(knowledge_base)
        print("   [OK] LangGraph workflow ready")

        print("\n" + "="*70)
        print("[SUCCESS] Server initialization complete!")
        print(f"API address: http://{settings.API_HOST}:{settings.API_PORT}")
        if knowledge_base is None:
            print("[WARNING] RAG features disabled (knowledge base not loaded)")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Initialization failed: {e}")
        import traceback
        traceback.print_exc()

    yield

    # Cleanup on shutdown
    print("\nServer shutting down...")


# ============================================================================
# Create FastAPI Application
# ============================================================================

app = FastAPI(
    title="WWII Simulation API v2",
    description="WWII simulation game API based on LangGraph and LangChain",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False when using wildcard origin
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
        "name": "WWII Simulation API v2",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "LangGraph intelligent workflow",
            "Pydantic type safety",
            "Automatic iterative optimization",
            "RAG knowledge retrieval"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "knowledge_base": knowledge_base is not None,
        "event_workflow": event_workflow is not None,
        "active_sessions": len(sessions)
    }


@app.post("/api/start", response_model=StartGameResponse)
async def start_game(request: StartGameRequest):
    """
    Start new game

    Create game session and return initial event
    """
    try:
        # Create session ID
        session_id = str(uuid.uuid4())

        # Create initial event
        start_event = GameEvent(
            id=f"start_{request.player_country}",
            name=f"The Dawn of War for {request.player_country}",
            description="On September 1, 1939, World War II officially began, plunging the entire world into the flames of war. As the supreme decision-maker of your nation, you will guide this country through the torrents of war, where every decision will affect the fate of the nation and the course of history.",
            year=settings.GAME_START_YEAR,
            month=settings.GAME_START_MONTH,
            country=request.player_country,
            event_type="political",
            likelihood=1.0,
            impact_score=0
        )

        # Create session
        session = GameSession(
            session_id=session_id,
            player_country=request.player_country,
            current_year=settings.GAME_START_YEAR,
            current_month=settings.GAME_START_MONTH,
            current_node_id=start_event.id,
            history=[start_event]
        )

        # Save session
        sessions[session_id] = session

        return StartGameResponse(
            session_id=session_id,
            start_node=start_event,
            player_country=request.player_country,
            country_info={},  # TODO: Add detailed country information
            message=f"Game started! You will play as the decision-maker of {request.player_country}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start game: {str(e)}")


@app.post("/api/branches", response_model=GetBranchesResponse)
async def get_branches(request: GetBranchesRequest):
    """
    Get branch options

    Use LangGraph workflow to generate event branches
    """
    # Validate session
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.session_id]

    try:
        # Build history summary
        history_summary = _build_history_summary(session.history)

        # Use LangGraph workflow to generate branches
        print(f"\nGenerating branches: {session.player_country} {session.current_year}.{session.current_month}")

        branch_options = event_workflow.generate(
            country=session.player_country,
            year=session.current_year,
            month=session.current_month,
            history_summary=history_summary
        )

        if branch_options is None:
            raise HTTPException(status_code=500, detail="Generation failed")

        # Display generation metadata
        metadata = branch_options.generation_metadata
        if metadata:
            print(f"   Iterations: {metadata.get('iterations', 0)}")
            print(f"   Quality score: {metadata.get('quality_score', 0):.1%}")

        return GetBranchesResponse(
            branches=branch_options.branches,
            ending_probability=0.0,  # TODO: Implement war point system
            is_ended=False
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate branches: {str(e)}")


@app.post("/api/choose")
async def make_choice(request: MakeChoiceRequest):
    """
    Make choice

    Record player choice and update game state
    """
    # Validate session
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[request.session_id]

    try:
        # TODO: Validate choice_id validity

        # Update state
        session.current_node_id = request.choice_id

        # Advance time (simplified version)
        session.current_month += 1
        if session.current_month > 12:
            session.current_month = 1
            session.current_year += 1

        # TODO: Add chosen event to history

        # Create result node
        result_node = GameEvent(
            id=f"result_{request.choice_id}_{session.current_year}_{session.current_month}",
            name=f"Action Result for {session.player_country}",
            description=f"Your chosen action has begun execution. Decision-makers of {session.player_country} are fully pursuing this strategic policy, and subsequent effects will gradually emerge. The international situation is also undergoing subtle changes.",
            year=session.current_year,
            month=session.current_month,
            country=session.player_country,
            event_type="political",
            likelihood=1.0,
            impact_score=0
        )

        return {
            "success": True,
            "current_node": result_node.id,
            "result_node": result_node.model_dump(),
            "action_result": {
                "outcome": "Complete success",
                "result_description": f"Your chosen action has begun execution. {session.player_country} is fully pursuing this strategic policy.",
                "success_score": 0.85,
                "consequences": [
                    "International relations undergo subtle changes",
                    "Domestic public opinion reacts positively to this decision"
                ],
                "impacts": [
                    {"country": session.player_country, "effect": "Domestic morale boosted", "severity": "Moderate"},
                    {"country": "ALL", "effect": "International relations undergo subtle changes", "severity": "Minor"}
                ],
                "impact": {
                    "military": 5,
                    "diplomatic": 3,
                    "economic": 2
                }
            },
            "reaction_nodes": [],
            "world_state": {},
            "message": "Choice successful"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Choice failed: {str(e)}")


@app.get("/api/status")
async def get_status(session_id: str):
    """Get game status"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    return {
        "session_id": session.session_id,
        "player_country": session.player_country,
        "current_year": session.current_year,
        "current_month": session.current_month,
        "total_events": len(session.history),
        "is_ended": session.is_ended
    }


@app.get("/api/kb/stats")
async def get_kb_stats():
    """Get knowledge base statistics"""
    if knowledge_base is None:
        raise HTTPException(status_code=503, detail="Knowledge base not initialized")

    return knowledge_base.get_stats()


# ============================================================================
# Utility Functions
# ============================================================================

def _build_history_summary(history: list[GameEvent]) -> str:
    """Build history summary"""
    if not history:
        return "Game start"

    # Take the most recent 3 events
    recent = history[-3:]
    parts = []

    for event in recent:
        parts.append(
            f"{event.year}.{event.month} - {event.name}"
        )

    return "\n".join(parts)


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD
    )
