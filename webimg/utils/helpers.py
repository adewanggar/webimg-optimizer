"""Utility and helper functions for webimg."""

import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

from webimg.config import SUPPORTED_INPUT_EXTENSIONS


def format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    return f"{size:.2f} {units[unit_idx]}"


def calculate_savings(original_size: int, new_size: int) -> Tuple[int, float]:
    """Calculate absolute byte difference and percentage saved.
    
    Returns:
        (saved_bytes, percent_saved)
    """
    if original_size <= 0:
        return 0, 0.0
    saved = original_size - new_size
    percent = (saved / original_size) * 100.0
    return saved, percent


def is_supported_image(path: Path) -> bool:
    """Check if file extension is among supported image formats."""
    return path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def collect_images(input_path: Path, recursive: bool = True) -> List[Path]:
    """Collect image paths from a single file or directory."""
    if not input_path.exists():
        return []

    if input_path.is_file():
        return [input_path] if is_supported_image(input_path) else []

    images: List[Path] = []
    pattern = "**/*" if recursive else "*"
    for item in input_path.glob(pattern):
        if is_supported_image(item):
            images.append(item)
    return sorted(images)


def resolve_output_path(
    input_path: Path,
    output_dir: Path,
    target_format: str,
    width: Optional[int] = None,
    relative_to: Optional[Path] = None,
) -> Path:
    """Determine output file path with optional width suffix and relative subfolder structure.
    
    Example:
        input: /images/sub/banner.png, width: 768, target_format: webp
        output: /output/sub/banner_768w.webp
    """
    stem = input_path.stem
    ext = target_format.lower().lstrip(".")
    if ext == "original":
        ext = input_path.suffix.lstrip(".")

    suffix = f"_{width}w" if width is not None else ""
    filename = f"{stem}{suffix}.{ext}"

    if relative_to and relative_to.is_dir() and input_path.is_relative_to(relative_to):
        rel_parent = input_path.relative_to(relative_to).parent
        dest_dir = output_dir / rel_parent
    else:
        dest_dir = output_dir

    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / filename


def wait_until_file_stable(file_path: Path, timeout: float = 3.0, interval: float = 0.3) -> bool:
    """Ensure a file being copied has finished writing by checking size stability."""
    start_time = time.time()
    last_size = -1
    while time.time() - start_time < timeout:
        try:
            if not file_path.exists():
                return False
            current_size = os.path.getsize(file_path)
            if current_size == last_size and current_size > 0:
                return True
            last_size = current_size
        except OSError:
            pass
        time.sleep(interval)
    return file_path.exists() and os.path.getsize(file_path) > 0
