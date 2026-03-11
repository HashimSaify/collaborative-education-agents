"""
agents/researcher.py
---------------------
Defines the Researcher Agent — strictly powered by Google Gemini.
"""

import json
import re
from textwrap import dedent

from crewai import Agent, Task
from langchain_google_genai import ChatGoogleGenerativeAI

import config
from core.handoff import ResearchHandoff, ResourceItem
from utils.logger import get_logger

logger = get_logger(__name__)


# ── LLM Factory (Gemini Exclusive) ───────────────────────────────────────────

def _get_llm() -> ChatGoogleGenerativeAI:
    """Constructs the Gemini model instance."""
    return ChatGoogleGenerativeAI(
        model=config.GOOGLE_MODEL,
        google_api_key=config.GOOGLE_API_KEY,
        temperature=0.3,
    )


# ── Researcher Agent ──────────────────────────────────────────────────────────

class ResearcherAgent:
    """
    Wraps the CrewAI Agent and Task for the Researcher role using Gemini.
    """

    ROLE = "Expert Educational Researcher"

    GOAL = dedent("""
        Conduct thorough academic research on the given study topic and
        produce a comprehensive, machine-readable structured output.
        All output must be formatted as a valid JSON object matching the
        ResearchHandoff schema exactly.
    """).strip()

    BACKSTORY = dedent("""
        You are a senior academic researcher specialist. Your hallmark is 
        your ability to break any complex topic into digestible, well-organised 
        study material for students. You output precise JSON data.
    """).strip()

    @staticmethod
    def _build_task_description(topic: str, output_type: str) -> str:
        return dedent(f"""
            ## Task: Research the Study Topic

            **Topic:** {topic}
            **Requested Output Type:** {output_type}

            ### Your Job
            Research the topic "{topic}" thoroughly and produce a structured
            JSON output following the ResearchHandoff schema below.

            ### Output Schema (JSON)
            {{
              "task_id": "auto-generated-uuid",
              "topic": "{topic}",
              "research_summary": "A 3-5 sentence paragraph explaining the topic.",
              "key_concepts": [
                "Concept 1 — brief 1-line explanation",
                "... (6 to 12 concepts total)"
              ],
              "detailed_notes": "Expanded explanations of each key concept.",
              "resources": [
                {{
                  "title": "Resource name",
                  "type": "article | book | video | website",
                  "description": "Why it is useful",
                  "url": "https://...",
                  "relevance": "Why relevant"
                }}
              ],
              "prerequisites": ["Prereq 1"],
              "real_world_applications": ["App 1"],
              "writer_instructions": "Detailed instructions for the Writer Agent for '{output_type}'.",
              "output_type": "{output_type}",
              "status": "ready_for_writer"
            }}

            ### CRITICAL
            Return ONLY valid JSON. No preamble, no postamble, no markdown fences.
        """).strip()

    def get_agent(self) -> Agent:
        return Agent(
            role=self.ROLE,
            goal=self.GOAL,
            backstory=self.BACKSTORY,
            llm=_get_llm(),
            allow_delegation=False,
            verbose=True,
            max_iter=config.RESEARCHER_MAX_ITER,
        )

    def get_task(self, topic: str, output_type: str, agent: Agent) -> Task:
        return Task(
            description=self._build_task_description(topic, output_type),
            agent=agent,
            expected_output="A valid JSON object matching the ResearchHandoff schema."
        )

    @staticmethod
    def parse_output(raw_output: str, topic: str, output_type: str) -> ResearchHandoff:
        logger.info("Parsing Researcher output | topic='%s'", topic)
        cleaned = raw_output.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
            return _build_handoff_from_dict(data, topic, output_type)
        except:
            match = re.search(r"\{[\s\S]*\}", raw_output)
            if match:
                try:
                    data = json.loads(match.group())
                    return _build_handoff_from_dict(data, topic, output_type)
                except: pass

        return ResearchHandoff(
            topic=topic,
            output_type=output_type,
            research_summary="Research could not be parsed.",
            key_concepts=["Fallback concept"],
            writer_instructions=f"Create a {output_type} based on the topic: {topic}"
        )

def _build_handoff_from_dict(data: dict, topic: str, output_type: str) -> ResearchHandoff:
    raw_resources = data.get("resources", [])
    resources: list[ResourceItem] = []
    for r in raw_resources:
        if isinstance(r, dict):
            resources.append(ResourceItem(
                title=r.get("title", "Resource"),
                type=r.get("type", "article"),
                description=r.get("description", ""),
                url=r.get("url"),
                relevance=r.get("relevance"),
            ))

    return ResearchHandoff(
        topic=data.get("topic", topic),
        research_summary=data.get("research_summary", ""),
        key_concepts=data.get("key_concepts", []),
        detailed_notes=data.get("detailed_notes"),
        resources=resources,
        prerequisites=data.get("prerequisites", []),
        real_world_applications=data.get("real_world_applications", []),
        writer_instructions=data.get("writer_instructions", ""),
        output_type=data.get("output_type", output_type),
    )
