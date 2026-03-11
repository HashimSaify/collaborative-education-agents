"""
core/state_manager.py
----------------------
Session state management for the education agents pipeline.

The SessionState Pydantic model holds every piece of data produced
during a single user request, from the initial topic all the way to
the final writer output.  The StateManager class wraps it with
persistence (save/load JSON) and convenient update helpers.

State lifecycle:
    IDLE → RESEARCHING → RESEARCH_DONE → WRITING → COMPLETE / ERROR
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from core.handoff import ResearchHandoff
from config import STATE_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Pipeline Stage Enum ───────────────────────────────────────────────────────

class PipelineStage(str, Enum):
    IDLE           = "idle"
    RESEARCHING    = "researching"
    RESEARCH_DONE  = "research_done"
    WRITING        = "writing"
    COMPLETE       = "complete"
    ERROR          = "error"


# ── Session State Model ───────────────────────────────────────────────────────

class SessionState(BaseModel):
    """
    Immutable snapshot of the entire pipeline run for one user request.
    All fields are preserved to avoid information loss between agent steps.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this session."
    )

    # ── Input ─────────────────────────────────────────────────────────────────
    topic: str = Field(
        default="",
        description="The study topic provided by the user."
    )
    output_type: str = Field(
        default="study_guide",
        description="Requested output format (study_guide / summary / etc.)"
    )

    # ── Researcher output ─────────────────────────────────────────────────────
    researcher_raw_output: str = Field(
        default="",
        description="Raw text output from the Researcher Agent (before parsing)."
    )
    handoff: Optional[ResearchHandoff] = Field(
        default=None,
        description="Parsed and validated ResearchHandoff from the Researcher."
    )

    # ── Writer output ─────────────────────────────────────────────────────────
    writer_raw_output: str = Field(
        default="",
        description="Raw text output from the Writer Agent."
    )
    final_content: str = Field(
        default="",
        description="Cleaned and formatted final educational content."
    )

    # ── Pipeline tracking ─────────────────────────────────────────────────────
    stage: PipelineStage = Field(
        default=PipelineStage.IDLE,
        description="Current lifecycle stage of the pipeline."
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error description if stage == ERROR."
    )
    retry_count: int = Field(
        default=0,
        description="Number of overall retries attempted."
    )

    # ── Timing ────────────────────────────────────────────────────────────────
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When the session was created."
    )
    completed_at: Optional[str] = Field(
        default=None,
        description="When the pipeline completed (success or failure)."
    )

    model_config = {"arbitrary_types_allowed": True}


# ── State Manager ─────────────────────────────────────────────────────────────

class StateManager:
    """
    Manages a single SessionState throughout the pipeline lifecycle.

    Responsibilities:
      - Initialise state from user input
      - Update state at each pipeline stage
      - Persist state to a JSON file for traceability / debugging
      - Load state from a previous session (resume support)
    """

    def __init__(self, session_id: Optional[str] = None) -> None:
        if session_id:
            # Try to resume an existing session
            loaded = self._load(session_id)
            self.state: SessionState = loaded if loaded else SessionState()
        else:
            self.state = SessionState()

        logger.info("StateManager initialised | session_id=%s", self.state.session_id)

    # ── Initialise ────────────────────────────────────────────────────────────

    def initialise(self, topic: str, output_type: str = "study_guide") -> SessionState:
        """Set the initial user request and move to RESEARCHING stage."""
        self.state.topic = topic.strip()
        self.state.output_type = output_type
        self.state.stage = PipelineStage.RESEARCHING
        logger.info("Session started | topic='%s' | output_type=%s", topic, output_type)
        self._save()
        return self.state

    # ── Stage updates ─────────────────────────────────────────────────────────

    def set_researcher_output(self, raw_output: str, handoff: ResearchHandoff) -> None:
        """Store Researcher Agent results and advance stage."""
        self.state.researcher_raw_output = raw_output
        self.state.handoff = handoff
        self.state.stage = PipelineStage.RESEARCH_DONE
        logger.info(
            "Research complete | topic='%s' | handoff_valid=%s",
            self.state.topic,
            handoff.validation.is_complete,
        )
        self._save()

    def begin_writing(self) -> None:
        """Advance stage to WRITING."""
        self.state.stage = PipelineStage.WRITING
        logger.info("Writing stage started | session_id=%s", self.state.session_id)
        self._save()

    def set_writer_output(self, raw_output: str, final_content: str) -> None:
        """Store Writer Agent results and mark pipeline as COMPLETE."""
        self.state.writer_raw_output = raw_output
        self.state.final_content = final_content
        self.state.stage = PipelineStage.COMPLETE
        self.state.completed_at = datetime.now(timezone.utc).isoformat()
        if self.state.handoff:
            self.state.handoff.mark_complete()
        logger.info("Pipeline complete | session_id=%s", self.state.session_id)
        self._save()

    def set_error(self, message: str) -> None:
        """Record an error and mark the pipeline as failed."""
        self.state.error_message = message
        self.state.stage = PipelineStage.ERROR
        self.state.completed_at = datetime.now(timezone.utc).isoformat()
        if self.state.handoff:
            self.state.handoff.mark_failed()
        logger.error("Pipeline error | session_id=%s | %s", self.state.session_id, message)
        self._save()

    def increment_retry(self) -> None:
        """Increment the retry counter (used when handoff validation fails)."""
        self.state.retry_count += 1
        if self.state.handoff:
            self.state.handoff.retry_count = self.state.retry_count
        logger.warning(
            "Retry #%d | session_id=%s", self.state.retry_count, self.state.session_id
        )

    # ── Persistence ───────────────────────────────────────────────────────────

    def _state_path(self, session_id: Optional[str] = None) -> Path:
        sid = session_id or self.state.session_id
        return STATE_DIR / f"session_{sid}.json"

    def _save(self) -> None:
        """Persist the current state to disk as JSON."""
        try:
            path = self._state_path()
            path.write_text(
                self.state.model_dump_json(indent=2),
                encoding="utf-8",
            )
            logger.debug("State saved to %s", path)
        except OSError as exc:
            logger.warning("Could not save state: %s", exc)

    def _load(self, session_id: str) -> Optional[SessionState]:
        """Attempt to load a previous session from disk."""
        path = self._state_path(session_id)
        if not path.exists():
            logger.warning("No saved state found for session_id=%s", session_id)
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            state = SessionState.model_validate_json(raw)
            logger.info("Session resumed | session_id=%s", session_id)
            return state
        except Exception as exc:
            logger.error("Could not load state for session %s: %s", session_id, exc)
            return None

    def get_summary(self) -> dict:
        """Return a lightweight summary dict for display purposes."""
        return {
            "session_id": self.state.session_id,
            "topic": self.state.topic,
            "output_type": self.state.output_type,
            "stage": self.state.stage.value,
            "retry_count": self.state.retry_count,
            "started_at": self.state.started_at,
            "completed_at": self.state.completed_at,
            "error": self.state.error_message,
        }
