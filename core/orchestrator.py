"""
core/orchestrator.py
---------------------
The EducationOrchestrator is the central coordinator of the multi-agent
education pipeline. It is responsible for:

  1. Validating configuration before the pipeline starts
  2. Initialising the Researcher and Writer agents
  3. Running the CrewAI sequential workflow (Researcher → Writer)
  4. Parsing and validating the inter-agent ResearchHandoff
  5. Retrying the research task if validation fails
  6. Updating the SessionState at every stage transition
  7. Formatting and returning the final educational output

WORKFLOW:
    User Input
        └─► Orchestrator.run(topic, output_type)
                ├─► ResearcherAgent.get_task() ──► Crew.kickoff()
                │       └─► raw_output ──► parse_output() ──► ResearchHandoff
                │               └─► validate handoff (retry if invalid)
                ├─► WriterAgent.get_task(handoff) ──► Crew.kickoff()
                │       └─► final_content (Markdown string)
                └─► SessionState.set_writer_output() ──► return result
"""

from __future__ import annotations

import time
from typing import Optional

from crewai import Crew, Process

import config
from agents.researcher import ResearcherAgent
from agents.writer import WriterAgent
from core.handoff import ResearchHandoff, HandoffStatus
from core.state_manager import StateManager, PipelineStage
from utils.formatter import OutputFormatter
from utils.logger import get_logger

logger = get_logger(__name__)


class EducationOrchestrator:
    """
    Coordinates the complete multi-agent education content pipeline.

    Usage:
        orchestrator = EducationOrchestrator()
        result = orchestrator.run(topic="Machine Learning Basics",
                                  output_type="study_guide")
        print(result.final_content)
    """

    def __init__(self) -> None:
        # Instantiate agent definition classes (not CrewAI agents yet)
        self._researcher_def = ResearcherAgent()
        self._writer_def = WriterAgent()
        logger.info("EducationOrchestrator initialised")

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        topic: str,
        output_type: str = config.DEFAULT_OUTPUT_TYPE,
        session_id: Optional[str] = None,
        verbose: bool = True,
    ) -> StateManager:
        """
        Execute the full research → write pipeline for a given topic.

        Args:
            topic:       The study topic (e.g. "Machine Learning Basics")
            output_type: One of study_guide | summary | revision_sheet | bullet_notes
            session_id:  Optional — resume a previous session from disk
            verbose:     Whether to print Rich-formatted progress to terminal

        Returns:
            The StateManager whose .state contains all pipeline data including
            .state.final_content (the finished educational content).
        """
        # ── Validate config first ─────────────────────────────────────────────
        config_errors = config.validate_config()
        if config_errors:
            for err in config_errors:
                OutputFormatter.print_error(err)
            raise RuntimeError(f"Configuration errors: {config_errors}")

        # ── Validate output type ──────────────────────────────────────────────
        if output_type not in config.OUTPUT_TYPES:
            logger.warning(
                "Unknown output_type '%s' — defaulting to 'study_guide'", output_type
            )
            output_type = config.DEFAULT_OUTPUT_TYPE

        # ── Initialise state ──────────────────────────────────────────────────
        state_mgr = StateManager(session_id=session_id)
        state_mgr.initialise(topic=topic, output_type=output_type)

        if verbose:
            OutputFormatter.print_topic_start(topic, output_type)

        # ── Run pipeline ──────────────────────────────────────────────────────
        try:
            handoff = self._run_researcher(state_mgr, topic, output_type, verbose)
            self._run_writer(state_mgr, handoff, verbose)
        except Exception as exc:
            state_mgr.set_error(str(exc))
            if verbose:
                OutputFormatter.print_error(f"Pipeline failed: {exc}")
            logger.exception("Pipeline error for topic='%s'", topic)
            raise

        return state_mgr

    # ── Private: Researcher Stage ─────────────────────────────────────────────

    def _run_researcher(
        self,
        state_mgr: StateManager,
        topic: str,
        output_type: str,
        verbose: bool,
    ) -> ResearchHandoff:
        """
        Runs the Researcher Agent and returns a validated ResearchHandoff.
        Retries up to HANDOFF_RETRY_LIMIT times if validation fails.
        """
        if verbose:
            OutputFormatter.print_agent_start("Researcher Agent")

        max_retries = config.HANDOFF_RETRY_LIMIT
        last_error: Optional[str] = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                state_mgr.increment_retry()
                logger.info("Retry attempt %d for topic='%s'", attempt, topic)
                time.sleep(2)  # Brief delay before retry

            try:
                raw_output = self._run_researcher_crew(topic, output_type)
                handoff = ResearcherAgent.parse_output(raw_output, topic, output_type)

                if handoff.validation.is_complete:
                    # ── Handoff is valid — store and proceed ──────────────────
                    state_mgr.set_researcher_output(raw_output, handoff)
                    if verbose:
                        OutputFormatter.print_agent_done("Researcher Agent")
                        OutputFormatter.print_handoff(handoff)
                    return handoff
                else:
                    last_error = (
                        f"Handoff validation failed: "
                        f"missing fields = {handoff.validation.missing_fields}"
                    )
                    logger.warning(last_error)

                    if attempt == max_retries:
                        # Last attempt — log a warning but continue with partial handoff
                        logger.warning(
                            "Max retries reached. Proceeding with partial handoff."
                        )
                        if verbose:
                            OutputFormatter.print_error(
                                f"⚠ Partial research output (missing: "
                                f"{handoff.validation.missing_fields}). "
                                f"Continuing with partial data."
                            )
                        state_mgr.set_researcher_output(raw_output, handoff)
                        return handoff

            except Exception as exc:
                last_error = str(exc)
                logger.error("Researcher Agent error (attempt %d): %s", attempt, exc)
                if attempt == max_retries:
                    raise RuntimeError(
                        f"Researcher Agent failed after {max_retries + 1} attempts: {last_error}"
                    ) from exc

        # Should not reach here but satisfies type checker
        raise RuntimeError(f"Researcher Agent failed: {last_error}")

    def _run_researcher_crew(self, topic: str, output_type: str) -> str:
        """Creates and kicks off a single-agent CrewAI crew for the Researcher."""
        agent = self._researcher_def.get_agent()
        task = self._researcher_def.get_task(topic, output_type, agent)

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,  # We handle our own progress display
        )

        result = crew.kickoff()
        # CrewAI returns a CrewOutput object; extract string
        return str(result.raw) if hasattr(result, "raw") else str(result)

    # ── Private: Writer Stage ─────────────────────────────────────────────────

    def _run_writer(
        self,
        state_mgr: StateManager,
        handoff: ResearchHandoff,
        verbose: bool,
    ) -> None:
        """Runs the Writer Agent and stores the final content in state."""
        state_mgr.begin_writing()
        if verbose:
            OutputFormatter.print_agent_start("Writer Agent")

        agent = self._writer_def.get_agent()
        task = self._writer_def.get_task(handoff, agent)

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        raw_output = str(result.raw) if hasattr(result, "raw") else str(result)
        final_content = raw_output.strip()

        state_mgr.set_writer_output(raw_output, final_content)

        if verbose:
            OutputFormatter.print_agent_done("Writer Agent")

        logger.info(
            "Writer complete | topic='%s' | output_type=%s | length=%d chars",
            handoff.topic,
            handoff.output_type,
            len(final_content),
        )
