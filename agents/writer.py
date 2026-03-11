"""
agents/writer.py
-----------------
Defines the Writer Agent — strictly powered by Google Gemini.
"""

from textwrap import dedent
from crewai import Agent, Task
from langchain_google_genai import ChatGoogleGenerativeAI

import config
from core.handoff import ResearchHandoff
from utils.logger import get_logger

logger = get_logger(__name__)


# ── LLM Factory (Gemini Exclusive) ───────────────────────────────────────────

def _get_llm() -> ChatGoogleGenerativeAI:
    """Constructs the Gemini model instance."""
    return ChatGoogleGenerativeAI(
        model=config.GOOGLE_MODEL,
        google_api_key=config.GOOGLE_API_KEY,
        temperature=0.5,
    )


# ── Writer Agent ──────────────────────────────────────────────────────────────

class WriterAgent:
    """
    Wraps the CrewAI Agent and Task for the Writer role using Gemini.
    """

    ROLE = "Expert Educational Content Writer"

    GOAL = dedent("""
        Transform structured research data into high-quality educational content.
        Produce clear, well-organized Markdown material.
    """).strip()

    BACKSTORY = dedent("""
        You are an award-winning educational content writer. You excel at 
        simplifying complex academic topics into readable study guides.
    """).strip()

    # (Keeping the FORMAT_INSTRUCTIONS as they were, they are generic)
    FORMAT_INSTRUCTIONS = {
        "study_guide": "Create a COMPREHENSIVE STUDY GUIDE with sections: Overview, Prerequisites, Key Concepts, Applications, Resources, Questions.",
        "summary": "Create a SHORT SUMMARY: Definition, Why It Matters, Core Ideas.",
        "revision_sheet": "Create a REVISION SHEET: At a Glance, Must-Knows, Exam Questions.",
        "bullet_notes": "Create BULLET NOTES: Definition, Key Points, Terms, Facts.",
    }

    def _build_task_description(self, handoff: ResearchHandoff) -> str:
        format_instr = self.FORMAT_INSTRUCTIONS.get(handoff.output_type, self.FORMAT_INSTRUCTIONS["study_guide"])
        
        return dedent(f"""
            ## Task: Create Educational Content
            **Topic:** {handoff.topic}
            **Research Summary:** {handoff.research_summary}
            **Instructions:** {handoff.writer_instructions}
            
            **Output Format:** 
            {format_instr}
            
            Use Markdown, be student-friendly, and start immediately with the title.
        """).strip()

    def get_agent(self) -> Agent:
        return Agent(
            role=self.ROLE,
            goal=self.GOAL,
            backstory=self.BACKSTORY,
            llm=_get_llm(),
            allow_delegation=False,
            verbose=True,
            max_iter=config.WRITER_MAX_ITER,
        )

    def get_task(self, handoff: ResearchHandoff, agent: Agent) -> Task:
        return Task(
            description=self._build_task_description(handoff),
            agent=agent,
            expected_output=f"A well-formatted Markdown {handoff.output_type} about {handoff.topic}."
        )
