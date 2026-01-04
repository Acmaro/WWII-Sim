"""
FastAPI服务器

提供RESTful API接口
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
# 全局状态
# ============================================================================

# 游戏会话存储
sessions: Dict[str, GameSession] = {}

# 知识库和工作流
knowledge_base = None
event_workflow = None


# ============================================================================
# 生命周期管理
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global knowledge_base, event_workflow

    # 启动时初始化
    print("="*70)
    print("初始化WWIISim-v2服务器...")
    print("="*70)

    try:
        # 初始化知识库
        print("\n1. 加载知识库...")
        try:
            knowledge_base = get_knowledge_base()
            stats = knowledge_base.get_stats()
            print(f"   [OK] 加载了 {stats['total_events']} 个历史事件")
            print(f"   [OK] 向量维度: {stats['vector_dimension']}")
        except Exception as kb_error:
            print(f"   [WARNING] 知识库加载失败: {kb_error}")
            print("   [WARNING] 将在无RAG模式下运行")
            knowledge_base = None

        # 初始化工作流
        print("\n2. 初始化事件生成工作流...")
        event_workflow = create_event_generation_workflow(knowledge_base)
        print("   [OK] LangGraph工作流已就绪")

        print("\n" + "="*70)
        print("[SUCCESS] 服务器初始化完成!")
        print(f"API地址: http://{settings.API_HOST}:{settings.API_PORT}")
        if knowledge_base is None:
            print("[WARNING] RAG功能已禁用（知识库未加载）")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n[ERROR] 初始化失败: {e}")
        import traceback
        traceback.print_exc()

    yield

    # 关闭时清理
    print("\n服务器关闭中...")


# ============================================================================
# 创建FastAPI应用
# ============================================================================

app = FastAPI(
    title="WWII Simulation API v2",
    description="基于LangGraph和LangChain的二战模拟游戏API",
    version="2.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源
    allow_credentials=False,  # 使用通配符源时必须为False
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
        "name": "WWII Simulation API v2",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "LangGraph智能工作流",
            "Pydantic类型安全",
            "自动迭代优化",
            "RAG知识检索"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "knowledge_base": knowledge_base is not None,
        "event_workflow": event_workflow is not None,
        "active_sessions": len(sessions)
    }


@app.post("/api/start", response_model=StartGameResponse)
async def start_game(request: StartGameRequest):
    """
    开始新游戏

    创建游戏会话并返回初始事件
    """
    try:
        # 创建会话ID
        session_id = str(uuid.uuid4())

        # 创建初始事件
        start_event = GameEvent(
            id=f"start_{request.player_country}",
            name=f"{request.player_country}国家的战争开端时刻",
            description="1939年9月1日，第二次世界大战正式爆发，全世界陷入战火之中。作为国家的最高决策者，你将引导这个国家在战争的洪流中前进，每一个决策都将影响国家的命运和历史的走向。",
            year=settings.GAME_START_YEAR,
            month=settings.GAME_START_MONTH,
            country=request.player_country,
            event_type="political",
            likelihood=1.0,
            impact_score=0
        )

        # 创建会话
        session = GameSession(
            session_id=session_id,
            player_country=request.player_country,
            current_year=settings.GAME_START_YEAR,
            current_month=settings.GAME_START_MONTH,
            current_node_id=start_event.id,
            history=[start_event]
        )

        # 保存会话
        sessions[session_id] = session

        return StartGameResponse(
            session_id=session_id,
            start_node=start_event,
            player_country=request.player_country,
            country_info={},  # TODO: 添加国家详细信息
            message=f"游戏开始！你将扮演{request.player_country}的决策者"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动游戏失败: {str(e)}")


@app.post("/api/branches", response_model=GetBranchesResponse)
async def get_branches(request: GetBranchesRequest):
    """
    获取分支选项

    使用LangGraph工作流生成事件分支
    """
    # 验证会话
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = sessions[request.session_id]

    try:
        # 构建历史摘要
        history_summary = _build_history_summary(session.history)

        # 使用LangGraph工作流生成分支
        print(f"\n生成分支: {session.player_country} {session.current_year}.{session.current_month}")

        branch_options = event_workflow.generate(
            country=session.player_country,
            year=session.current_year,
            month=session.current_month,
            history_summary=history_summary
        )

        if branch_options is None:
            raise HTTPException(status_code=500, detail="生成失败")

        # 显示生成元数据
        metadata = branch_options.generation_metadata
        if metadata:
            print(f"   迭代次数: {metadata.get('iterations', 0)}")
            print(f"   质量评分: {metadata.get('quality_score', 0):.1%}")

        return GetBranchesResponse(
            branches=branch_options.branches,
            ending_probability=0.0,  # TODO: 实现战争积分系统
            is_ended=False
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成分支失败: {str(e)}")


@app.post("/api/choose")
async def make_choice(request: MakeChoiceRequest):
    """
    做出选择

    记录玩家选择并更新游戏状态
    """
    # 验证会话
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    session = sessions[request.session_id]

    try:
        # TODO: 验证choice_id有效性

        # 更新状态
        session.current_node_id = request.choice_id

        # 推进时间（简化版）
        session.current_month += 1
        if session.current_month > 12:
            session.current_month = 1
            session.current_year += 1

        # TODO: 添加选择的事件到历史

        # 创建结果节点
        result_node = GameEvent(
            id=f"result_{request.choice_id}_{session.current_year}_{session.current_month}",
            name=f"{session.player_country}的行动结果",
            description=f"你选择的行动已经开始执行。{session.player_country}的决策者们正在全力推进这一战略方针，后续的影响将逐步显现。国际局势也在随之发生微妙的变化。",
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
                "outcome": "完全成功",
                "result_description": f"你选择的行动已经开始执行。{session.player_country}正在全力推进这一战略方针。",
                "success_score": 0.85,
                "consequences": [
                    "国际关系发生微妙变化",
                    "国内舆论对此决策反应积极"
                ],
                "impacts": [
                    {"country": session.player_country, "effect": "国内士气提升", "severity": "中等"},
                    {"country": "ALL", "effect": "国际关系发生微妙变化", "severity": "轻微"}
                ],
                "impact": {
                    "military": 5,
                    "diplomatic": 3,
                    "economic": 2
                }
            },
            "reaction_nodes": [],
            "world_state": {},
            "message": "选择成功"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"选择失败: {str(e)}")


@app.get("/api/status")
async def get_status(session_id: str):
    """获取游戏状态"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

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
    """获取知识库统计信息"""
    if knowledge_base is None:
        raise HTTPException(status_code=503, detail="知识库未初始化")

    return knowledge_base.get_stats()


# ============================================================================
# 辅助函数
# ============================================================================

def _build_history_summary(history: list[GameEvent]) -> str:
    """构建历史摘要"""
    if not history:
        return "游戏开始"

    # 取最近3个事件
    recent = history[-3:]
    parts = []

    for event in recent:
        parts.append(
            f"{event.year}.{event.month} - {event.name}"
        )

    return "\n".join(parts)


# ============================================================================
# 运行服务器
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD
    )
