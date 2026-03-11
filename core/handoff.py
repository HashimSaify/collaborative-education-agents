"""
core/handoff.py
---------------
Pydantic models defining the structured hand-off contract between the
Researcher Agent and the Writer Agent.

The ResearchHandoff object is the single source of truth that travels
through the pipeline:

  Researcher Agent ──► ResearchHandoff ──► Writer Agent

This explicit schema enforces:
  - What fields must be present before the Writer starts
  - Validation status and completeness checks
  - Metadata for traceability (task_id, timestamps, status)
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ── Status Enum ───────────────────────────────────────────────────────────────

class HandoffStatus(str, Enum):
    """Tracks the lifecycle stage of a research handoff object."""
    PENDING           = "pending"             # Initialised, not yet populated
    RESEARCH_COMPLETE = "research_complete"   # Researcher has finished
    READY_FOR_WRITER  = "ready_for_writer"    # Validated, waiting for writer
    WRITING_COMPLETE  = "writing_complete"    # Writer has completed its task
    FAILED            = "failed"              # An unrecoverable error occurred


# ── Sub-models ────────────────────────────────────────────────────────────────

class ResourceItem(BaseModel):
    """Represents a single study resource recommended by the Researcher."""

    title: str = Field(
        ...,
        description="Name of the resource (book, article, video, website, etc.)"
    )
    resource_type: str = Field(
        ...,
        alias="type",
        description="Category: article | book | video | website | course | paper"
    )
    description: str = Field(
        ...,
        description="Brief description of what this resource covers."
    )
    url: Optional[str] = Field(
        default=None,
        description="Direct URL if available (can be None for books/offline resources)"
    )
    relevance: Optional[str] = Field(
        default=None,
        description="Why this resource is relevant to the topic."
    )

    model_config = {"populate_by_name": True}


class ValidationResult(BaseModel):
    """Captures the completeness validation result of a ResearchHandoff."""

    is_complete: bool = Field(
        default=False,
        description="True when all required fields are populated and valid."
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="List of field names that are empty or missing."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking issues (e.g. fewer than 3 resources found)."
    )
    validated_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of when validation was performed."
    )


# ── Primary Handoff Schema ────────────────────────────────────────────────────

class ResearchHandoff(BaseModel):
    """
    The inter-agent data contract passed from Researcher → Writer.

    This model is serialised to JSON after the Researcher Agent completes
    its task and is deserialised by the Orchestrator before being injected
    into the Writer Agent's task context.
    """

    # ── Identity / Traceability ───────────────────────────────────────────────
    task_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this research session."
    )
    topic: str = Field(
        ...,
        description="The original study topic as entered by the user."
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp when this handoff was created."
    )

    # ── Research Content ──────────────────────────────────────────────────────
    research_summary: str = Field(
        default="",
        description=(
            "A concise paragraph summarising the topic: what it is, "
            "why it matters, and its main branches / areas."
        )
    )
    key_concepts: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of the most important concepts / terms the "
            "student must understand. Aim for 6–12 items."
        )
    )
    detailed_notes: Optional[str] = Field(
        default=None,
        description=(
            "Expanded explanations for each key concept. "
            "The Researcher may include these as additional depth for the Writer."
        )
    )
    resources: list[ResourceItem] = Field(
        default_factory=list,
        description="Curated list of study resources (aim for 3–6)."
    )
    prerequisites: list[str] = Field(
        default_factory=list,
        description="Topics the student should know before studying this topic."
    )
    real_world_applications: list[str] = Field(
        default_factory=list,
        description="Practical or real-world uses of this topic."
    )

    # ── Instructions for Writer ───────────────────────────────────────────────
    writer_instructions: str = Field(
        default="",
        description=(
            "Specific instructions for the Writer Agent: output format, "
            "tone, depth level, and any special sections to include."
        )
    )
    output_type: str = Field(
        default="study_guide",
        description=(
            "Requested output format: study_guide | summary | "
            "revision_sheet | bullet_notes"
        )
    )

    # ── Pipeline Status ───────────────────────────────────────────────────────
    status: HandoffStatus = Field(
        default=HandoffStatus.PENDING,
        description="Current lifecycle stage of this handoff object."
    )
    retry_count: int = Field(
        default=0,
        description="Number of times the Researcher was retried due to validation failure."
    )

    # ── Validation ────────────────────────────────────────────────────────────
    validation: ValidationResult = Field(
        default_factory=ValidationResult,
        description="Result of the handoff completeness validation."
    )

    # ── Computed Validation ───────────────────────────────────────────────────
    @model_validator(mode="after")
    def _auto_validate(self) -> "ResearchHandoff":
        """
        Automatically computes the validation result whenever the model
        is constructed or updated.
        """
        missing: list[str] = []
        warnings: list[str] = []

        if not self.research_summary.strip():
            missing.append("research_summary")
        if not self.key_concepts:
            missing.append("key_concepts")
        if not self.writer_instructions.strip():
            missing.append("writer_instructions")

        if len(self.resources) < 3:
            warnings.append(
                f"Only {len(self.resources)} resource(s) found; 3–6 recommended."
            )
        if len(self.key_concepts) < 4:
            warnings.append(
                f"Only {len(self.key_concepts)} key concept(s); 6–12 recommended."
            )

        self.validation = ValidationResult(
            is_complete=len(missing) == 0,
            missing_fields=missing,
            warnings=warnings,
            validated_at=datetime.now(timezone.utc).isoformat(),
        )

        if self.validation.is_complete and self.status == HandoffStatus.PENDING:
            self.status = HandoffStatus.READY_FOR_WRITER

        return self

    def to_json_str(self) -> str:
        """Serialises the handoff to a pretty-printed JSON string."""
        return self.model_dump_json(indent=2, by_alias=True)

    @classmethod
    def from_json_str(cls, json_str: str) -> "ResearchHandoff":
        """Deserialises a ResearchHandoff from a JSON string."""
        return cls.model_validate_json(json_str)

    def mark_ready(self) -> None:
        """Marks the handoff as validated and ready for the Writer Agent."""
        if self.validation.is_complete:
            self.status = HandoffStatus.READY_FOR_WRITER

    def mark_complete(self) -> None:
        """Marks the handoff as fully processed (Writer done)."""
        self.status = HandoffStatus.WRITING_COMPLETE

    def mark_failed(self) -> None:
        """Marks the handoff as failed."""
        self.status = HandoffStatus.FAILED
