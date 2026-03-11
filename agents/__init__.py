"""
agents/
-------
Contains specialised CrewAI agent definitions:
  - ResearcherAgent: gathers and structures topic information
  - WriterAgent: converts research into polished educational content
"""

from .researcher import ResearcherAgent
from .writer import WriterAgent

__all__ = ["ResearcherAgent", "WriterAgent"]
