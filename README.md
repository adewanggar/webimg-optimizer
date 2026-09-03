# webimg: Smart Asset & Image Optimizer for Web/Social Media

A high-performance, modular Python CLI tool and daemon folder watcher built to optimize images (PNG, JPG, JPEG) into next-generation web formats (**WebP** and **AVIF**), automatically generate **responsive variants**, and **strip sensitive EXIF metadata** for privacy protection.

Powered by **multiprocessing (`concurrent.futures.ProcessPoolExecutor`)** to maximize throughput on multi-core CPUs.

---

## Key Features

- **Batch Compression & Format Conversion**:
  - Converts traditional formats (PNG, JPG, JPEG, BMP, TIFF) to modern web formats (**WebP** and **AVIF**).
  - Fine-grained visual quality control (`--quality 1-100`, `--lossless`, `--effort 0-6`).
  - Automatically handles transparency (RGBA) and color modes (CMYK -> RGB).

- **Responsive Variant Generator**:
  - Automatically generates standard web breakpoints (e.g. `300px`, `768px`, `1200px`) using high-fidelity Lanczos downscaling.
  - Built-in presets: `--preset web`, `--preset social`, `--preset avatar`, `--preset thumb`.
  - Smart aspect ratio preservation without upscaling smaller images.

- **Privacy & Metadata Stripping**:
  - Strips privacy-sensitive EXIF tags by default (GPS locations, camera make/model, timestamps, serial numbers).
  - Automatically transposes image pixels based on EXIF orientation prior to stripping, preventing upside-down or sideways photos.
  - Option to retain metadata when necessary via `--keep-exif`.

- **Real-Time Folder Watcher (Daemon Mode)**:
  - Continuously monitors an input directory using `watchdog`.
  - Automatically detects new or updated images, debounces write events, and exports optimized variants to the output directory.

- **Parallel Concurrency & Rich CLI UX**:
  - Multi-core processing using Python's `ProcessPoolExecutor`.
  - Visual terminal interface using `typer` and `rich` with live progress bars, file completion stats, and compression summary tables.

---

## Project Architecture

```
webimg-optimizer/
├── pyproject.toml              # PEP 621 packaging with 'webimg' CLI script entrypoint
├── requirements.txt            # Project dependencies (Pillow, pillow-heif, typer, rich, watchdog)
├── README.md                   # Full documentation and execution guide
├── tests/
│   ├── __init__.py
│   ├── test_converter.py       # Unit tests: WebP, AVIF, responsive sizing, corrupt files
│   ├── test_metadata.py        # Unit tests: EXIF stripping, --keep-exif, inspection
│   └── test_watcher.py         # Unit tests: Real-time watcher event handling
└── webimg/
    ├── __init__.py             # Package version and metadata
    ├── cli.py                  # Typer CLI application (optimize, watch, info, version)
    ├── config.py               # Enums, Presets, and configuration dataclasses
    ├── core/
    │   ├── __init__.py
    │   ├── converter.py        # Resizing, encoding, and multiprocessing pool executor
    │   ├── metadata.py         # EXIF extraction, orientation transposition, stripping
    │   └── watcher.py          # Watchdog file system event listener with debouncing
    └── utils/
        ├── __init__.py
        ├── helpers.py          # File scanners, format helpers, byte calculators
        └── logger.py           # Rich console logger, status badges, and summary tables
```

---

## Installation

### 1. Prerequisites
- Python 3.9 or higher.

### 2. Install Dependencies
Clone or navigate to the repository and install:

```bash
# Option A: Install directly via pip editable mode (registers the 'webimg' CLI executable)
pip install -e .

# Option B: Install dependencies from requirements.txt
pip install -r requirements.txt
```

> **Note for Windows Users**: If your Python Scripts directory is not in your system `PATH`, you can invoke the CLI using `python -m webimg.cli [COMMAND]` or add `%APPDATA%\Python\Python3xx\Scripts` to your environment variables.

---

## CLI Usage and Examples

### 1. Batch Optimize (`webimg optimize`)

Optimize a single file or an entire directory:

```bash
# Optimize all images in a folder to WebP (default quality 80)
webimg optimize ./assets/images/ -o ./dist/images/

# Convert images to both WebP and AVIF
webimg optimize ./photos/ -o ./optimized/ -f webp -f avif

# Generate responsive web variants (300px, 768px, 1200px) + original size
webimg optimize ./photos/ -o ./optimized/ -w 300,768,1200 -q 85

# Use a built-in preset (web, social, avatar, thumb)
webimg optimize ./photos/ -o ./optimized/ --preset web

# Retain EXIF metadata (disabled by default for privacy)
webimg optimize ./photos/ -o ./optimized/ --keep-exif

# Adjust concurrency workers (e.g. 4 workers)
webimg optimize ./photos/ -o ./optimized/ --workers 4
```

#### CLI Options for `optimize`:

| Option | Flag | Description | Default |
|---|---|---|---|
| `--output` | `-o` | Output destination directory | `<input>/optimized` |
| `--format` | `-f` | Target format (`webp`, `avif`, `all`, `original`) | `webp` |
| `--quality` | `-q` | Compression quality (1 - 100) | `80` |
| `--widths` | `-w` | Comma-separated variant widths in pixels (e.g. `300,768,1200`) | `None` |
| `--preset` | `-p` | Responsive preset (`none`, `web`, `social`, `avatar`, `thumb`) | `none` |
| `--keep-exif` | | Retain camera/GPS EXIF metadata | `False` (strips EXIF) |
| `--workers` | | Number of parallel worker processes | CPU core count |
| `--recursive` | `-r` | Recursively scan subdirectories | `True` |
| `--lossless` | | Enable lossless compression (WebP) | `False` |
| `--effort` | | Encoding effort level (0 to 6) | `4` |
| `--no-orig` | | Do not output original size if variant widths are set | `False` |

---

### 2. Real-Time Folder Watcher (`webimg watch`)

Start a background daemon that monitors an input directory for new or modified images and automatically processes them into the output directory:

```bash
# Watch a folder and output WebP variants automatically
webimg watch ./incoming_uploads/ -o ./cdn_assets/

# Watch with responsive variants and both WebP & AVIF formats
webimg watch ./incoming_uploads/ -o ./cdn_assets/ -f webp -f avif --preset web -q 82
```

- **Debouncing**: Prevents incomplete file processing while an image is still being copied or uploaded over the network.
- **Graceful Shutdown**: Stop the watcher anytime with `Ctrl + C`.

---

### 3. Metadata & Privacy Inspection (`webimg info`)

Inspect image dimensions, color mode, file size, and check whether sensitive EXIF metadata (camera model, GPS coordinates) is exposed:

```bash
webimg info ./photos/sample_camera.jpg
```

---

## Responsive Presets

| Preset | Target Widths (px) | Typical Use Case |
|---|---|---|
| `web` | `320`, `768`, `1200` | Standard responsive website layouts (mobile, tablet, desktop) |
| `social` | `1080`, `1200` | Social media feeds (Instagram, LinkedIn, Twitter/X landscape) |
| `avatar` | `128`, `256`, `512` | User profiles and thumbnails |
| `thumb` | `150`, `300` | Product listings and gallery thumbnails |

Generated filenames include the width suffix (e.g. `banner_300w.webp`, `banner_768w.webp`, `banner.webp`).

---

## Running Tests

Run the automated unit test suite with `pytest`:

```bash
python -m pytest tests/ -v
```

Tests cover:
- WebP and AVIF encoding fidelity
- Responsive resizing without upscaling
- Transparency (RGBA) preservation
- EXIF stripping vs `--keep-exif`
- Graceful handling of corrupted or zero-byte files
- Folder watcher event handling
- Multi-worker multiprocessing pool execution
