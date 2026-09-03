"""Real-time folder watcher and daemon service using watchdog."""

import os
import time
import threading
from pathlib import Path
from typing import Dict, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from webimg.config import OptimizationOptions
from webimg.core.converter import process_single_image
from webimg.utils.helpers import (
    calculate_savings,
    format_bytes,
    is_supported_image,
    wait_until_file_stable,
)
from webimg.utils.logger import (
    console,
    log_error,
    log_info,
    log_success,
    log_warning,
)


class ImageWatcherHandler(FileSystemEventHandler):
    """Event handler that detects new or updated image files and triggers optimization."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        options: OptimizationOptions,
        debounce_seconds: float = 1.5,
    ):
        super().__init__()
        self.input_dir = input_dir.resolve()
        self.output_dir = output_dir.resolve()
        self.options = options
        self.debounce_seconds = debounce_seconds
        self._last_processed: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _is_event_applicable(self, path: Path) -> bool:
        """Check if file should be processed."""
        if not path.is_file():
            return False

        # Ignore files within output directory
        try:
            if path.resolve().is_relative_to(self.output_dir):
                return False
        except (ValueError, AttributeError):
            pass

        # Ignore temporary and hidden files
        name = path.name
        if name.startswith((".", "~$", "#")) or name.endswith((".tmp", ".crdownload", ".part", ".swp")):
            return False

        return is_supported_image(path)

    def _handle_file(self, file_path: Path) -> None:
        """Debounce and process a detected image."""
        path_str = str(file_path.resolve())
        now = time.time()

        with self._lock:
            last_time = self._last_processed.get(path_str, 0)
            if now - last_time < self.debounce_seconds:
                return
            self._last_processed[path_str] = now

        # Wait for file to finish copying/downloading
        if not wait_until_file_stable(file_path):
            log_warning(f"[WATCH] Skipping incomplete or unreadable file: {file_path.name}")
            return

        log_info(f"[WATCH] New image detected: [bold]{file_path.name}[/bold]")
        
        # Process image
        result = process_single_image(
            input_path=file_path,
            output_dir=self.output_dir,
            options=self.options,
            relative_to=self.input_dir,
        )

        if result.success:
            saved, pct = calculate_savings(result.original_size_bytes, result.total_output_bytes)
            savings_str = f"-{pct:.1f}%" if pct > 0 else f"+{abs(pct):.1f}%"
            log_success(
                f"[WATCH] [green]Generated {len(result.output_files)} variants[/green] for [bold]{file_path.name}[/bold] "
                f"({format_bytes(result.original_size_bytes)} -> {format_bytes(result.total_output_bytes)}, "
                f"[bold cyan]{savings_str}[/bold cyan])"
            )
        else:
            log_error(f"[WATCH] Failed to process {file_path.name}: {result.error_message}")

    def on_created(self, event: FileSystemEvent) -> None:
        path = Path(event.src_path)
        if self._is_event_applicable(path):
            self._handle_file(path)

    def on_modified(self, event: FileSystemEvent) -> None:
        path = Path(event.src_path)
        if self._is_event_applicable(path):
            self._handle_file(path)


def start_watcher(
    input_dir: Path,
    output_dir: Path,
    options: OptimizationOptions,
    recursive: bool = True,
) -> None:
    """Start watchdog observer daemon to monitor a directory for new images."""
    input_path = input_dir.resolve()
    output_path = output_dir.resolve()

    if not input_path.exists():
        log_error(f"Input directory does not exist: {input_path}")
        return

    output_path.mkdir(parents=True, exist_ok=True)

    event_handler = ImageWatcherHandler(
        input_dir=input_path,
        output_dir=output_path,
        options=options,
    )

    observer = Observer()
    observer.schedule(event_handler, str(input_path), recursive=recursive)
    observer.start()

    console.print(
        f"\n[bold green]Folder Watcher Active[/bold green]\n"
        f"  - [cyan]Watching:[/cyan]  {input_path}\n"
        f"  - [cyan]Output to:[/cyan] {output_path}\n"
        f"  - [cyan]Formats:[/cyan]   {', '.join(options.formats)}\n"
        f"  - [cyan]Quality:[/cyan]   {options.quality}\n"
        f"  - [cyan]Variants:[/cyan]  {options.widths or 'Original size only'}\n"
        f"  - [cyan]EXIF:[/cyan]      {'Keep' if options.keep_exif else 'Stripped (Privacy Protected)'}\n"
        f"\n[dim yellow]Drop images into the watched directory. Press Ctrl+C to stop.[/dim yellow]\n"
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping folder watcher...[/yellow]")
        observer.stop()
    observer.join()
    console.print("[green]Watcher stopped cleanly.[/green]")
