"""
Workflows Module

Contains LangGraph workflow definitions
"""

from backend.workflows.event_generation import (
    EventGenerationWorkflow,
    create_event_generation_workflow
)

__all__ = [
    "EventGenerationWorkflow",
    "create_event_generation_workflow"
]
