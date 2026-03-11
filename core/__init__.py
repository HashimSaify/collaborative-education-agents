"""
core/
-----
Core infrastructure for the multi-agent education system:
  - handoff.py     : Pydantic schema for inter-agent data transfer
  - state_manager.py : Session state preservation
  - orchestrator.py  : Workflow coordination and CrewAI crew runner
"""

from .handoff import ResearchHandoff, ResourceItem, ValidationResult, HandoffStatus
from .state_manager import SessionState, StateManager
from .orchestrator import EducationOrchestrator

__all__ = [
    "ResearchHandoff",
    "ResourceItem",
    "ValidationResult",
    "HandoffStatus",
    "SessionState",
    "StateManager",
    "EducationOrchestrator",
]
