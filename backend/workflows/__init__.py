"""
工作流模块

包含LangGraph工作流定义
"""

from backend.workflows.event_generation import (
    EventGenerationWorkflow,
    create_event_generation_workflow
)

__all__ = [
    "EventGenerationWorkflow",
    "create_event_generation_workflow"
]
