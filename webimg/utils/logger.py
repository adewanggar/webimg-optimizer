"""Rich-based logger and visual table reporter for webimg."""

import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from webimg.config import SingleFileResult
from webimg.utils.helpers import calculate_savings, format_bytes

# Ensure UTF-8 output encoding across Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(legacy_windows=False)
err_console = Console(stderr=True, legacy_windows=False)


def print_banner() -> None:
    """Print application banner."""
    title = Text("webimg: Smart Asset & Image Optimizer", style="bold cyan")
    subtitle = Text("Modern Web Formats (WebP/AVIF) | Responsive Variants | Privacy Stripping", style="dim")
    banner = Panel.fit(
        Text.assemble(title, "\n", subtitle),
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(banner)


def log_info(message: str) -> None:
    """Log an info message."""
    console.print(f"[bold blue][INFO][/bold blue] {message}")


def log_success(message: str) -> None:
    """Log a success message."""
    console.print(f"[bold green][SUCCESS][/bold green] {message}")


def log_warning(message: str) -> None:
    """Log a warning message."""
    console.print(f"[bold yellow][WARNING][/bold yellow] {message}")


def log_error(message: str) -> None:
    """Log an error message."""
    err_console.print(f"[bold red][ERROR][/bold red] {message}")


def print_summary_table(results: List[SingleFileResult], total_elapsed: float) -> None:
    """Print detailed summary table and statistics panel."""
    if not results:
        log_warning("No files were processed.")
        return

    table = Table(
        title="Optimization Results Summary",
        title_style="bold magenta",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("File", style="bold", overflow="ellipsis", max_width=30)
    table.add_column("Variants", justify="center")
    table.add_column("Original", justify="right")
    table.add_column("Optimized", justify="right")
    table.add_column("Savings", justify="right")
    table.add_column("Status", justify="center")

    total_orig = 0
    total_opt = 0
    success_count = 0
    fail_count = 0

    for res in results:
        if res.success:
            success_count += 1
            total_orig += res.original_size_bytes
            total_opt += res.total_output_bytes
            saved, pct = calculate_savings(res.original_size_bytes, res.total_output_bytes)

            if pct > 0:
                savings_str = f"[green]-{pct:.1f}%[/green]"
            elif pct < 0:
                savings_str = f"[yellow]+{abs(pct):.1f}%[/yellow]"
            else:
                savings_str = "[dim]0.0%[/dim]"

            status_str = "[green]SUCCESS[/green]"
            variants_str = str(len(res.output_files))
        else:
            fail_count += 1
            savings_str = "[dim]N/A[/dim]"
            status_str = f"[red]FAIL: {res.error_message or 'Unknown'}[/red]"
            variants_str = "0"

        table.add_row(
            res.input_path.name,
            variants_str,
            format_bytes(res.original_size_bytes),
            format_bytes(res.total_output_bytes) if res.success else "-",
            savings_str,
            status_str,
        )

    console.print(table)

    # Overall Summary Panel
    total_saved, total_pct = calculate_savings(total_orig, total_opt)
    speed = len(results) / total_elapsed if total_elapsed > 0 else 0.0

    summary_text = (
        f"[bold]Total Files:[/bold] {len(results)}  ([green]{success_count} succeeded[/green], [red]{fail_count} failed[/red])\n"
        f"[bold]Original Total Size:[/bold] {format_bytes(total_orig)}\n"
        f"[bold]Optimized Total Size:[/bold] {format_bytes(total_opt)}\n"
        f"[bold]Net Savings:[/bold] [bold green]{format_bytes(total_saved)} ({total_pct:.1f}%)[/bold green]\n"
        f"[bold]Duration:[/bold] {total_elapsed:.2f}s  ([cyan]{speed:.1f} files/sec[/cyan])"
    )

    console.print(
        Panel(
            summary_text,
            title="Optimization Overview",
            border_style="green" if fail_count == 0 else "yellow",
            padding=(1, 2),
        )
    )
