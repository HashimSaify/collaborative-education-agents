"""
utils/formatter.py
------------------
Output formatting helpers for the education agents system.

Uses the Rich library for beautiful terminal output and provides
functions to:
  - Print the handoff schema in a readable panel
  - Print the final educational content with section formatting
  - Save outputs to Markdown files in the outputs/ directory
  - Display pipeline status and session summaries
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.syntax import Syntax
from rich.text import Text

from config import OUTPUTS_DIR
from utils.logger import get_logger

logger = get_logger(__name__)

# Shared Rich console (used for all terminal output in the project)
console = Console()


class OutputFormatter:
    """
    Provides static methods to display and persist agent outputs.
    All terminal rendering uses Rich; all saved files are plain Markdown.
    """

    # ── Pipeline Banner ───────────────────────────────────────────────────────

    @staticmethod
    def print_banner() -> None:
        """Print the application startup banner."""
        banner = Text()
        banner.append("  Collaborative Education Agents\n", style="bold cyan")
        banner.append("  Multi-Agent Study Material Generator\n", style="dim cyan")
        banner.append("  Powered by CrewAI + OpenAI\n", style="dim")
        console.print(Panel(banner, border_style="cyan", padding=(1, 4)))

    @staticmethod
    def print_topic_start(topic: str, output_type: str) -> None:
        """Announce the start of a pipeline run."""
        console.print()
        console.print(
            f"[bold green]► Topic:[/bold green] [white]{topic}[/white]  "
            f"[bold]|[/bold]  "
            f"[bold green]Output:[/bold green] [white]{output_type.replace('_', ' ').title()}[/white]"
        )
        console.print()

    # ── Agent Status ──────────────────────────────────────────────────────────

    @staticmethod
    def print_agent_start(agent_name: str) -> None:
        """Show that an agent is beginning its task."""
        console.print(f"[bold yellow]⬡ {agent_name}[/bold yellow] is working...", end="\n")

    @staticmethod
    def print_agent_done(agent_name: str) -> None:
        """Show that an agent has completed its task."""
        console.print(f"[bold green]✔ {agent_name}[/bold green] finished.\n")

    # ── Handoff Display ───────────────────────────────────────────────────────

    @staticmethod
    def print_handoff(handoff) -> None:  # handoff: ResearchHandoff (avoid circular import)
        """Display the ResearchHandoff in a formatted table + JSON panel."""
        # Summary table
        table = Table(
            title="📋 Research Handoff Summary",
            box=box.ROUNDED,
            border_style="blue",
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("Task ID", handoff.task_id[:8] + "...")
        table.add_row("Topic", handoff.topic)
        table.add_row("Status", handoff.status.value)
        table.add_row("Output Type", handoff.output_type)
        table.add_row("Key Concepts", str(len(handoff.key_concepts)))
        table.add_row("Resources", str(len(handoff.resources)))
        table.add_row(
            "Validation",
            "✔ Complete" if handoff.validation.is_complete else "✘ Incomplete",
        )
        if handoff.validation.missing_fields:
            table.add_row("Missing Fields", ", ".join(handoff.validation.missing_fields))
        if handoff.validation.warnings:
            for w in handoff.validation.warnings:
                table.add_row("⚠ Warning", w)

        console.print(table)

        # Key concepts list
        if handoff.key_concepts:
            console.print("\n[bold cyan]Key Concepts:[/bold cyan]")
            for i, concept in enumerate(handoff.key_concepts, 1):
                console.print(f"  [dim]{i}.[/dim] {concept}")

        console.print()

    # ── Final Output Display ──────────────────────────────────────────────────

    @staticmethod
    def print_final_output(content: str, topic: str, output_type: str) -> None:
        """Render the final educational content as Rich Markdown."""
        title = f"📚 {output_type.replace('_', ' ').title()} — {topic}"
        console.print(Panel(
            Markdown(content),
            title=title,
            border_style="green",
            padding=(1, 2),
        ))

    # ── Session Summary ───────────────────────────────────────────────────────

    @staticmethod
    def print_session_summary(summary: dict) -> None:
        """Display a pipeline run summary table."""
        table = Table(title="Session Summary", box=box.SIMPLE, border_style="dim")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        for key, value in summary.items():
            if value is not None:
                table.add_row(key.replace("_", " ").title(), str(value))

        console.print(table)

    # ── Error Display ─────────────────────────────────────────────────────────

    @staticmethod
    def print_error(message: str) -> None:
        """Display an error message in a red panel."""
        console.print(Panel(
            f"[bold red]{message}[/bold red]",
            title="❌ Error",
            border_style="red",
        ))

    # ── File Persistence ──────────────────────────────────────────────────────

    @staticmethod
    def save_output(
        content: str,
        topic: str,
        output_type: str,
        session_id: str,
    ) -> Path:
        """
        Save the final educational content to a Markdown file.

        Returns the saved file path.
        """
        # Build a safe filename from the topic
        safe_topic = re.sub(r"[^\w\s-]", "", topic).strip().replace(" ", "_").lower()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{output_type}_{safe_topic}_{timestamp}.md"
        output_path = OUTPUTS_DIR / filename

        # Build the Markdown document
        header = (
            f"# {output_type.replace('_', ' ').title()} — {topic}\n\n"
            f"> Generated by Collaborative Education Agents  \n"
            f"> Session: `{session_id}`  \n"
            f"> Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n\n"
            f"---\n\n"
        )

        try:
            output_path.write_text(header + content, encoding="utf-8")
            logger.info("Output saved to %s", output_path)
            console.print(
                f"\n[dim]💾 Saved to:[/dim] [underline]{output_path}[/underline]\n"
            )
        except OSError as exc:
            logger.error("Failed to save output: %s", exc)

        return output_path

    @staticmethod
    def save_handoff_json(handoff, topic: str) -> Path:
        """Save the raw handoff JSON for inspection / debugging."""
        safe_topic = re.sub(r"[^\w\s-]", "", topic).strip().replace(" ", "_").lower()
        filename = f"handoff_{safe_topic}_{handoff.task_id[:8]}.json"
        path = OUTPUTS_DIR / filename
        try:
            path.write_text(handoff.to_json_str(), encoding="utf-8")
            logger.info("Handoff JSON saved to %s", path)
        except OSError as exc:
            logger.error("Failed to save handoff JSON: %s", exc)
        return path
