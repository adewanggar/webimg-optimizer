"""CLI interface for webimg using Typer and Rich."""

import sys
import time
from pathlib import Path
from typing import List, Optional

# Ensure UTF-8 stdout/stderr on Windows
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

import typer
from rich.table import Table

from webimg import __app_name__, __version__
from webimg.config import (
    PRESETS,
    OptimizationOptions,
    PresetChoice,
)
from webimg.core.converter import batch_optimize, process_single_image
from webimg.core.metadata import extract_metadata_summary
from webimg.core.watcher import start_watcher
from webimg.utils.helpers import collect_images, format_bytes, is_supported_image
from webimg.utils.logger import (
    console,
    log_error,
    log_info,
    log_success,
    log_warning,
    print_banner,
    print_summary_table,
)

app = typer.Typer(
    name=__app_name__,
    help="Smart Asset & Image Optimizer for Web/Social Media",
    add_completion=False,
    no_args_is_help=True,
)


def _parse_formats(raw_formats: List[str]) -> List[str]:
    """Parse format strings handling commas and multiple flags."""
    formats: List[str] = []
    for item in raw_formats:
        for part in item.split(","):
            cleaned = part.strip().lower()
            if cleaned:
                formats.append(cleaned)
    return formats if formats else ["webp"]


def _resolve_widths(widths_arg: Optional[str], preset: PresetChoice) -> List[int]:
    """Resolve target widths from comma-separated string and preset choice."""
    widths_set = set()

    # Apply preset widths if selected
    if preset != PresetChoice.NONE and preset.value in PRESETS:
        widths_set.update(PRESETS[preset.value])

    # Apply custom widths if provided
    if widths_arg:
        for part in widths_arg.split(","):
            cleaned = part.strip()
            if cleaned.isdigit() and int(cleaned) > 0:
                widths_set.add(int(cleaned))

    return sorted(list(widths_set))


@app.command()
def optimize(
    input_path: Path = typer.Argument(
        ...,
        help="Input image file or directory of images to optimize.",
        exists=True,
        readable=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory. Defaults to '<input>/optimized' or './optimized'.",
    ),
    format: List[str] = typer.Option(
        ["webp"],
        "-f",
        "--format",
        help="Output formats (webp, avif, all, original). Can be specified multiple times or comma-separated.",
    ),
    quality: int = typer.Option(
        80,
        "-q",
        "--quality",
        min=1,
        max=100,
        help="Compression quality (1-100). Default is 80.",
    ),
    widths: Optional[str] = typer.Option(
        None,
        "-w",
        "--widths",
        help="Comma-separated responsive variant widths in pixels (e.g. '300,768,1200').",
    ),
    preset: PresetChoice = typer.Option(
        PresetChoice.NONE,
        "-p",
        "--preset",
        help="Responsive preset: web (320, 768, 1200), social (1080, 1200), avatar (128, 256, 512), thumb (150, 300).",
    ),
    keep_exif: bool = typer.Option(
        False,
        "--keep-exif",
        help="Retain EXIF metadata (GPS, camera info). By default, EXIF is stripped for privacy.",
    ),
    workers: Optional[int] = typer.Option(
        None,
        "--workers",
        help="Number of concurrent worker processes. Defaults to CPU core count.",
    ),
    recursive: bool = typer.Option(
        True,
        "-r/--no-recursive",
        help="Recursively scan subdirectories for images.",
    ),
    lossless: bool = typer.Option(
        False,
        "--lossless",
        help="Use lossless compression (applicable to WebP).",
    ),
    effort: int = typer.Option(
        4,
        "--effort",
        min=0,
        max=6,
        help="Compression effort/CPU level (0-6). Higher produces smaller files at the cost of time.",
    ),
    no_orig: bool = typer.Option(
        False,
        "--no-orig",
        help="Skip generating original width if responsive widths or preset are specified.",
    ),
) -> None:
    """Batch optimize, convert, and resize images with parallel multiprocessing."""
    print_banner()

    resolved_formats = _parse_formats(format)
    resolved_widths = _resolve_widths(widths, preset)

    # Determine output directory
    if output is None:
        if input_path.is_file():
            output_dir = input_path.parent / "optimized"
        else:
            output_dir = input_path / "optimized"
    else:
        output_dir = output

    options = OptimizationOptions(
        formats=resolved_formats,
        quality=quality,
        widths=resolved_widths,
        keep_original_size=not (no_orig and len(resolved_widths) > 0),
        keep_exif=keep_exif,
        lossless=lossless,
        effort=effort,
    )

    # Collect images
    images = collect_images(input_path, recursive=recursive)
    # Exclude any images that are already inside the output directory
    images = [img for img in images if not img.resolve().is_relative_to(output_dir.resolve())]

    if not images:
        log_warning(f"No supported images found in: {input_path}")
        raise typer.Exit(code=0)

    log_info(
        f"Processing [bold cyan]{len(images)}[/bold cyan] images "
        f"-> Target Formats: [bold]{', '.join(resolved_formats)}[/bold] | "
        f"Quality: [bold]{quality}[/bold] | "
        f"Variants: [bold]{resolved_widths or 'Original size'}[/bold] | "
        f"Privacy: [bold]{'Keep EXIF' if keep_exif else 'Strip EXIF'}[/bold]"
    )

    start_time = time.time()
    relative_root = input_path if input_path.is_dir() else input_path.parent
    results = batch_optimize(
        images=images,
        output_dir=output_dir,
        options=options,
        workers=workers,
        relative_to=relative_root,
        show_progress=True,
    )
    elapsed = time.time() - start_time

    print_summary_table(results, elapsed)
    log_success(f"Optimized files saved to: [bold underline]{output_dir.resolve()}[/bold underline]")


@app.command()
def watch(
    input_dir: Path = typer.Argument(
        ...,
        help="Directory to monitor in real-time.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output directory. Defaults to '<input_dir>/optimized'.",
    ),
    format: List[str] = typer.Option(
        ["webp"],
        "-f",
        "--format",
        help="Output formats (webp, avif, all, original).",
    ),
    quality: int = typer.Option(
        80,
        "-q",
        "--quality",
        min=1,
        max=100,
        help="Compression quality (1-100).",
    ),
    widths: Optional[str] = typer.Option(
        None,
        "-w",
        "--widths",
        help="Comma-separated responsive variant widths (e.g. '300,768,1200').",
    ),
    preset: PresetChoice = typer.Option(
        PresetChoice.NONE,
        "-p",
        "--preset",
        help="Responsive preset (web, social, avatar, thumb).",
    ),
    keep_exif: bool = typer.Option(
        False,
        "--keep-exif",
        help="Retain EXIF metadata.",
    ),
    recursive: bool = typer.Option(
        True,
        "-r/--no-recursive",
        help="Monitor subdirectories recursively.",
    ),
    lossless: bool = typer.Option(
        False,
        "--lossless",
        help="Use lossless compression (WebP).",
    ),
    effort: int = typer.Option(
        4,
        "--effort",
        min=0,
        max=6,
        help="Compression effort (0-6).",
    ),
) -> None:
    """Run daemon folder watcher: monitor folder and optimize incoming images automatically."""
    print_banner()

    resolved_formats = _parse_formats(format)
    resolved_widths = _resolve_widths(widths, preset)

    output_dir = output or (input_dir / "optimized")

    options = OptimizationOptions(
        formats=resolved_formats,
        quality=quality,
        widths=resolved_widths,
        keep_original_size=True,
        keep_exif=keep_exif,
        lossless=lossless,
        effort=effort,
    )

    start_watcher(
        input_dir=input_dir,
        output_dir=output_dir,
        options=options,
        recursive=recursive,
    )


@app.command()
def info(
    image_path: Path = typer.Argument(
        ...,
        help="Path to image file to inspect.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Inspect image properties, color space, dimensions, and EXIF privacy exposure."""
    print_banner()

    if not is_supported_image(image_path):
        log_warning(f"File {image_path.name} may not be a standard supported image format.")

    summary = extract_metadata_summary(image_path)
    file_size = image_path.stat().st_size

    table = Table(
        title=f"Image Metadata Inspection: {image_path.name}",
        title_style="bold cyan",
        header_style="bold magenta",
        show_header=True,
    )
    table.add_column("Property", style="bold", width=24)
    table.add_column("Value")

    table.add_row("File Size", format_bytes(file_size))
    table.add_row("Format", str(summary.get("format")))
    table.add_row("Color Mode", str(summary.get("mode")))
    table.add_row("Dimensions", f"{summary.get('width')} x {summary.get('height')} px")
    table.add_row("EXIF Present", "[yellow]YES[/yellow]" if summary.get("has_exif") else "[green]NO[/green]")
    table.add_row("Total EXIF Tags", str(summary.get("raw_tag_count", 0)))
    table.add_row("Camera Make", str(summary.get("camera_make") or "[dim]None[/dim]"))
    table.add_row("Camera Model", str(summary.get("camera_model") or "[dim]None[/dim]"))
    table.add_row("Timestamp", str(summary.get("datetime") or "[dim]None[/dim]"))

    gps_val = summary.get("gps_coords")
    if summary.get("has_gps"):
        table.add_row("GPS Coordinates", f"[bold red]SENSITIVE: {gps_val}[/bold red]")
    else:
        table.add_row("GPS Coordinates", "[green]None (Clean)[/green]")

    console.print(table)


@app.command()
def version() -> None:
    """Display webimg version."""
    console.print(f"[bold cyan]{__app_name__}[/bold cyan] version [green]{__version__}[/green]")


if __name__ == "__main__":
    app()
