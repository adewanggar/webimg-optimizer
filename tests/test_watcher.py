"""Test real-time folder watcher and event handling."""

import tempfile
import time
from pathlib import Path
from PIL import Image

from webimg.config import OptimizationOptions
from webimg.core.watcher import ImageWatcherHandler


def test_watcher_handler_processes_new_file():
    """Verify ImageWatcherHandler handles new file creation events."""
    with tempfile.TemporaryDirectory() as in_dir, tempfile.TemporaryDirectory() as out_dir:
        in_path = Path(in_dir)
        out_path = Path(out_dir)

        options = OptimizationOptions(formats=["webp"], quality=75)
        handler = ImageWatcherHandler(
            input_dir=in_path,
            output_dir=out_path,
            options=options,
            debounce_seconds=0.1,
        )

        # Create image inside input directory
        test_file = in_path / "watched_photo.png"
        img = Image.new("RGB", (300, 300), color=(20, 150, 80))
        img.save(test_file, "PNG")

        # Manually trigger handler or test internal logic
        handler._handle_file(test_file)

        # Check output
        expected_output = out_path / "watched_photo.webp"
        assert expected_output.exists()
        assert expected_output.stat().st_size > 0
