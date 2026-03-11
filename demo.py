"""
demo.py
--------
End-to-end demonstration script for the Collaborative Education Agents system.

Runs the full research → write pipeline for three example topics and saves
all outputs to the outputs/ directory. Use this to verify the system works
correctly after setting up your API key.

Usage:
    python demo.py

What it does:
    1. Runs "Machine Learning Basics" → study_guide
    2. Runs "Photosynthesis" → revision_sheet
    3. Runs "DBMS Normalization" → bullet_notes
    4. Displays a final report of all results
    5. Validates that all handoffs parsed correctly

Requirements:
    - GOOGLE_API_KEY must be set in .env
    - GOOGLE_MODEL should be set (defaults to gemini-2.0-flash)
"""

import sys
import time
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel

import config
from core.orchestrator import EducationOrchestrator
from core.state_manager import PipelineStage
from utils.formatter import OutputFormatter
from utils.logger import setup_logger, get_logger

# Initialise logging
setup_logger()
logger = get_logger(__name__)
console = Console()


# ── Demo Scenarios ────────────────────────────────────────────────────────────

@dataclass
class DemoScenario:
    """Defines a single demo run."""
    name: str               # Display name for this demo
    topic: str              # Study topic
    output_type: str        # Output format


DEMO_SCENARIOS = [
    DemoScenario(
        name="Computer Science — AI/ML",
        topic="Machine Learning Basics",
        output_type="study_guide",
    ),
    DemoScenario(
        name="Biology — Life Sciences",
        topic="Photosynthesis",
        output_type="revision_sheet",
    ),
    DemoScenario(
        name="Database Systems",
        topic="DBMS Normalization",
        output_type="bullet_notes",
    ),
]


# ── Demo Result ───────────────────────────────────────────────────────────────

@dataclass
class DemoResult:
    """Captures the result of one demo scenario."""
    scenario: DemoScenario
    success: bool
    session_id: str
    content_length: int
    handoff_valid: bool
    duration_seconds: float
    error: Optional[str] = None
    output_file: Optional[str] = None


# ── Runner ────────────────────────────────────────────────────────────────────

def run_demo_scenario(
    orchestrator: EducationOrchestrator,
    scenario: DemoScenario,
) -> DemoResult:
    """
    Runs a single demo scenario and returns a DemoResult.
    Does not raise — captures failures into the result instead.
    """
    console.print(Panel(
        f"[bold white]Demo: {scenario.name}[/bold white]\n"
        f"Topic: [cyan]{scenario.topic}[/cyan]  |  "
        f"Output: [yellow]{scenario.output_type}[/yellow]",
        border_style="blue",
        padding=(0, 2),
    ))

    start_time = time.time()
    try:
        state_mgr = orchestrator.run(
            topic=scenario.topic,
            output_type=scenario.output_type,
            verbose=True,
        )
        duration = time.time() - start_time
        state = state_mgr.state

        # ── Validation checks ─────────────────────────────────────────────────
        assert state.stage == PipelineStage.COMPLETE, (
            f"Pipeline did not complete — stage is {state.stage}"
        )
        assert state.final_content, "Writer produced empty content"
        assert len(state.final_content) > 200, (
            f"Content too short ({len(state.final_content)} chars) — likely a failure"
        )

        # Save output to file
        saved_path = OutputFormatter.save_output(
            content=state.final_content,
            topic=scenario.topic,
            output_type=scenario.output_type,
            session_id=state.session_id,
        )

        # Save handoff JSON
        if state.handoff:
            OutputFormatter.save_handoff_json(state.handoff, scenario.topic)

        # Print preview (first 800 chars)
        preview = state.final_content[:800] + ("..." if len(state.final_content) > 800 else "")
        console.print(Panel(
            preview,
            title=f"Preview — {scenario.topic}",
            border_style="green",
            padding=(1, 2),
        ))

        return DemoResult(
            scenario=scenario,
            success=True,
            session_id=state.session_id,
            content_length=len(state.final_content),
            handoff_valid=state.handoff.validation.is_complete if state.handoff else False,
            duration_seconds=round(duration, 1),
            output_file=str(saved_path),
        )

    except (AssertionError, Exception) as exc:
        duration = time.time() - start_time
        error_msg = str(exc)
        logger.error("Demo scenario failed: %s | %s", scenario.topic, error_msg)
        OutputFormatter.print_error(f"Demo failed for '{scenario.topic}': {error_msg}")

        return DemoResult(
            scenario=scenario,
            success=False,
            session_id="N/A",
            content_length=0,
            handoff_valid=False,
            duration_seconds=round(duration, 1),
            error=error_msg,
        )


def print_demo_report(results: list[DemoResult]) -> None:
    """Display a formatted summary table of all demo results."""
    table = Table(
        title="📊 Demo Execution Report",
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#",             style="dim",   width=3)
    table.add_column("Topic",         style="white", min_width=25)
    table.add_column("Output Type",   style="yellow")
    table.add_column("Status",        style="bold")
    table.add_column("Handoff",       style="bold")
    table.add_column("Content",       style="cyan")
    table.add_column("Time (s)",      style="dim")

    passed = 0
    for i, result in enumerate(results, 1):
        status = "[green]✔ PASS[/green]" if result.success else "[red]✘ FAIL[/red]"
        handoff_ok = "[green]✔[/green]" if result.handoff_valid else "[red]✘[/red]"
        content = f"{result.content_length:,} chars" if result.success else "—"

        table.add_row(
            str(i),
            result.scenario.topic,
            result.scenario.output_type,
            status,
            handoff_ok,
            content,
            str(result.duration_seconds),
        )
        if result.success:
            passed += 1

    console.print()
    console.print(table)
    console.print()

    # Overall verdict
    total = len(results)
    if passed == total:
        console.print(
            f"[bold green]✔ All {total}/{total} demos passed![/bold green] "
            "The system is working correctly. 🎉"
        )
    else:
        failed = total - passed
        console.print(
            f"[bold yellow]⚠ {passed}/{total} demos passed, "
            f"{failed} failed.[/bold yellow] "
            "Check logs/education_agents.log for details."
        )

    console.print(
        f"\n[dim]Outputs saved to: {config.OUTPUTS_DIR}[/dim]\n"
    )


def main() -> int:
    """Run all demo scenarios and display the report. Returns exit code."""
    OutputFormatter.print_banner()

    # ── Config check ──────────────────────────────────────────────────────────
    config_errors = config.validate_config()
    if config_errors:
        for err in config_errors:
            OutputFormatter.print_error(err)
        console.print(
            "\n[yellow]Tip:[/yellow] Copy [bold].env.example[/bold] → [bold].env[/bold] "
            "and add your Google Gemini API key before running the demo.\n"
        )
        return 1

    console.print(
        Panel(
            f"[bold]Running {len(DEMO_SCENARIOS)} demo scenarios.[/bold]\n"
            "This will make API calls to Google Gemini and may take 1–3 minutes.",
            border_style="yellow",
            padding=(0, 2),
        )
    )

    # ── Create orchestrator (shared across all demos) ─────────────────────────
    orchestrator = EducationOrchestrator()
    results: list[DemoResult] = []

    for i, scenario in enumerate(DEMO_SCENARIOS, 1):
        console.print(f"\n[bold dim]── Scenario {i}/{len(DEMO_SCENARIOS)} ──[/bold dim]\n")
        result = run_demo_scenario(orchestrator, scenario)
        results.append(result)

        # Brief pause between API calls
        if i < len(DEMO_SCENARIOS):
            console.print("[dim]Waiting 3 seconds before next scenario...[/dim]")
            time.sleep(3)

    # ── Print final report ────────────────────────────────────────────────────
    print_demo_report(results)

    # Return non-zero if any scenario failed
    all_passed = all(r.success for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
