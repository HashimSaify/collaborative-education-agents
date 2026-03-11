"""
main.py
--------
Main CLI entry point for the Collaborative Education Agents system.

Usage:
    # Interactive mode (prompts for topic):
    python main.py

    # Direct topic input:
    python main.py --topic "Machine Learning Basics"

    # With custom output type:
    python main.py --topic "Photosynthesis" --output-type summary

    # Resume a previous session:
    python main.py --session-id <session-id>

Output types: study_guide | summary | revision_sheet | bullet_notes
"""

import argparse
import sys

from rich.console import Console
from rich.prompt import Prompt, Confirm

import config
from config import OUTPUT_TYPES, DEFAULT_OUTPUT_TYPE
from core.orchestrator import EducationOrchestrator
from utils.formatter import OutputFormatter
from utils.logger import setup_logger, get_logger

# Initialise logging before anything else
setup_logger()
logger = get_logger(__name__)
console = Console()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="education-agents",
        description="Collaborative Education Agents — AI-powered study material generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Output Types:
  study_guide     Full multi-section study guide (default)
  summary         Short paragraph overview
  revision_sheet  Condensed bullet points for revision
  bullet_notes    Quick key-concept bullet notes

Examples:
  python main.py
  python main.py --topic "Machine Learning Basics"
  python main.py --topic "Photosynthesis" --output-type summary
  python main.py --topic "DBMS Normalization" --output-type revision_sheet
        """,
    )
    parser.add_argument(
        "--topic", "-t",
        type=str,
        default=None,
        help="Study topic to research and explain",
    )
    parser.add_argument(
        "--output-type", "-o",
        type=str,
        default=None,
        choices=OUTPUT_TYPES,
        dest="output_type",
        help=f"Type of educational content to generate (default: {DEFAULT_OUTPUT_TYPE})",
    )
    parser.add_argument(
        "--session-id", "-s",
        type=str,
        default=None,
        dest="session_id",
        help="Resume a previous session by its ID",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save output to a Markdown file",
    )
    parser.add_argument(
        "--no-handoff-display",
        action="store_true",
        help="Skip displaying the research handoff details",
    )
    return parser.parse_args()


def interactive_input() -> tuple[str, str]:
    """
    Interactively prompt for topic and output type if not provided via CLI.
    Returns (topic, output_type).
    """
    console.print("\n[bold cyan]Available Output Types:[/bold cyan]")
    type_descriptions = {
        "study_guide":    "Full multi-section study guide (recommended for deep learning)",
        "summary":        "Short overview paragraph (quick read)",
        "revision_sheet": "Condensed bullet points (exam prep)",
        "bullet_notes":   "Fast key-concept bullets (quick reference)",
    }
    for i, (ot, desc) in enumerate(type_descriptions.items(), 1):
        console.print(f"  [dim]{i}.[/dim] [bold]{ot}[/bold] — {desc}")

    topic = Prompt.ask("\n[bold green]Enter study topic[/bold green]")
    output_type = Prompt.ask(
        "[bold green]Choose output type[/bold green]",
        choices=OUTPUT_TYPES,
        default=DEFAULT_OUTPUT_TYPE,
    )
    return topic.strip(), output_type


def main() -> int:
    """Main entry point. Returns exit code (0 = success, 1 = error)."""
    # ── Display banner ────────────────────────────────────────────────────────
    OutputFormatter.print_banner()

    # ── Parse arguments ───────────────────────────────────────────────────────
    args = parse_args()

    # ── Get topic and output type ─────────────────────────────────────────────
    if args.topic:
        topic = args.topic.strip()
        output_type = args.output_type or DEFAULT_OUTPUT_TYPE
    else:
        topic, output_type = interactive_input()

    if not topic:
        OutputFormatter.print_error("Topic cannot be empty.")
        return 1

    # ── Validate config ───────────────────────────────────────────────────────
    config_errors = config.validate_config()
    if config_errors:
        for err in config_errors:
            OutputFormatter.print_error(err)
        console.print(
            "\n[yellow]Tip:[/yellow] Copy [bold].env.example[/bold] → [bold].env[/bold] "
            "and add your OpenAI API key.\n"
        )
        return 1

    # ── Run pipeline ──────────────────────────────────────────────────────────
    logger.info("Pipeline start | topic='%s' | output_type=%s", topic, output_type)

    try:
        orchestrator = EducationOrchestrator()
        state_mgr = orchestrator.run(
            topic=topic,
            output_type=output_type,
            session_id=args.session_id,
            verbose=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user.[/yellow]")
        return 1
    except Exception as exc:
        OutputFormatter.print_error(f"Pipeline failed: {exc}")
        logger.exception("Unhandled pipeline error")
        return 1

    # ── Display final content ─────────────────────────────────────────────────
    state = state_mgr.state

    if state.final_content:
        OutputFormatter.print_final_output(
            content=state.final_content,
            topic=topic,
            output_type=output_type,
        )
    else:
        OutputFormatter.print_error("No content was generated.")
        return 1

    # ── Save output to file ───────────────────────────────────────────────────
    if not args.no_save and state.final_content:
        OutputFormatter.save_output(
            content=state.final_content,
            topic=topic,
            output_type=output_type,
            session_id=state.session_id,
        )

        # Also save the handoff JSON for inspection
        if state.handoff and not args.no_handoff_display:
            OutputFormatter.save_handoff_json(state.handoff, topic)

    # ── Session summary ───────────────────────────────────────────────────────
    OutputFormatter.print_session_summary(state_mgr.get_summary())

    console.print("\n[bold green]✔ Done![/bold green] Happy studying! 📚\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
