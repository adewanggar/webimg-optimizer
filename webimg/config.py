"""Configuration models, presets, and constants for webimg."""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

SUPPORTED_INPUT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".avif",
    ".bmp",
    ".tiff",
    ".tif",
}

PRESETS: Dict[str, List[int]] = {
    "web": [320, 768, 1200],
    "social": [1080, 1200],
    "avatar": [128, 256, 512],
    "thumb": [150, 300],
}


class OutputFormat(str, Enum):
    WEBP = "webp"
    AVIF = "avif"
    ALL = "all"
    ORIGINAL = "original"


class PresetChoice(str, Enum):
    NONE = "none"
    WEB = "web"
    SOCIAL = "social"
    AVATAR = "avatar"
    THUMB = "thumb"


@dataclass
class OptimizationOptions:
    formats: List[str] = field(default_factory=lambda: ["webp"])
    quality: int = 80
    widths: List[int] = field(default_factory=list)
    keep_original_size: bool = True
    keep_exif: bool = False
    lossless: bool = False
    effort: int = 4
    overwrite: bool = True


@dataclass
class SingleFileResult:
    input_path: Path
    output_files: List[Path] = field(default_factory=list)
    original_size_bytes: int = 0
    total_output_bytes: int = 0
    success: bool = True
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
