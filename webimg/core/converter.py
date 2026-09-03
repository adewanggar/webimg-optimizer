"""Core image conversion, compression, and batch multiprocessing engine."""

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PIL import Image, UnidentifiedImageError

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from webimg.config import OptimizationOptions, SingleFileResult
from webimg.core.metadata import normalize_orientation, prepare_metadata_for_save
from webimg.utils.helpers import resolve_output_path
from webimg.utils.logger import console, log_error, print_summary_table


def _prepare_image_mode_for_format(img: Image.Image, target_format: str) -> Image.Image:
    """Ensure color mode is compatible with target format."""
    target_format = target_format.lower()
    
    # Check if image has alpha transparency
    has_alpha = (
        img.mode in ("RGBA", "LA")
        or (img.mode == "P" and "transparency" in img.info)
    )

    if target_format in ("webp", "avif", "png"):
        if has_alpha and img.mode != "RGBA":
            return img.convert("RGBA")
        elif not has_alpha and img.mode not in ("RGB", "L"):
            return img.convert("RGB")
        return img

    if target_format in ("jpg", "jpeg"):
        # JPEG does not support transparency; composite on white background
        if has_alpha:
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[3])
            return background
        elif img.mode != "RGB":
            return img.convert("RGB")
        return img

    # Fallback to RGB if unknown mode (e.g. CMYK)
    if img.mode not in ("RGB", "RGBA", "L"):
        return img.convert("RGB")

    return img


def process_single_image(
    input_path: Path,
    output_dir: Path,
    options: OptimizationOptions,
    relative_to: Optional[Path] = None,
) -> SingleFileResult:
    """Process a single image file: resize, convert, compress, and strip metadata."""
    start_time = time.time()
    result = SingleFileResult(input_path=input_path)

    # Validate file existence and size
    try:
        if not input_path.exists():
            result.success = False
            result.error_message = "File does not exist"
            return result

        orig_size = os.path.getsize(input_path)
        result.original_size_bytes = orig_size
        if orig_size == 0:
            result.success = False
            result.error_message = "File is empty (0 bytes)"
            return result

    except (OSError, PermissionError) as e:
        result.success = False
        result.error_message = f"File access error: {e}"
        return result

    # Open and process image
    try:
        with Image.open(input_path) as img:
            # Correct orientation before stripping EXIF
            img = normalize_orientation(img)
            orig_w, orig_h = img.size

            # Resolve target formats
            resolved_formats: List[str] = []
            for fmt in options.formats:
                fmt_lower = fmt.lower()
                if fmt_lower == "all":
                    resolved_formats.extend(["webp", "avif"])
                elif fmt_lower == "original":
                    resolved_formats.append(input_path.suffix.lstrip(".").lower())
                else:
                    resolved_formats.append(fmt_lower)
            
            # Deduplicate preserving order
            seen_formats = set()
            target_formats = [f for f in resolved_formats if not (f in seen_formats or seen_formats.add(f))]

            # Resolve widths (avoid upscaling unless no variants exist)
            target_widths: List[Optional[int]] = []
            if options.widths:
                # Include smaller requested widths
                for w in sorted(set(options.widths)):
                    if w < orig_w:
                        target_widths.append(w)
                # Include original size if requested or if all widths are larger than original
                if options.keep_original_size or not target_widths:
                    target_widths.append(None)
            else:
                target_widths.append(None)

            # Process variants
            for target_format in target_formats:
                prepared_img = _prepare_image_mode_for_format(img, target_format)

                for w in target_widths:
                    if w is None:
                        variant_img = prepared_img
                    else:
                        new_h = max(1, int(round((w / orig_w) * orig_h)))
                        variant_img = prepared_img.resize((w, new_h), Image.Resampling.LANCZOS)

                    dest_file = resolve_output_path(
                        input_path=input_path,
                        output_dir=output_dir,
                        target_format=target_format,
                        width=w,
                        relative_to=relative_to,
                    )

                    # Prepare encoding parameters
                    save_kwargs = prepare_metadata_for_save(img, keep_exif=options.keep_exif)

                    if target_format == "webp":
                        save_kwargs["quality"] = options.quality
                        save_kwargs["method"] = min(6, max(0, options.effort))
                        save_kwargs["lossless"] = options.lossless
                    elif target_format == "avif":
                        save_kwargs["quality"] = options.quality
                    elif target_format in ("jpg", "jpeg"):
                        save_kwargs["quality"] = options.quality
                        save_kwargs["optimize"] = True
                        save_kwargs["progressive"] = True
                    elif target_format == "png":
                        save_kwargs["optimize"] = True

                    variant_img.save(dest_file, **save_kwargs)
                    result.output_files.append(dest_file)
                    result.total_output_bytes += os.path.getsize(dest_file)

        result.success = True

    except UnidentifiedImageError:
        result.success = False
        result.error_message = "Unrecognized or corrupted image format"
    except (OSError, PermissionError) as e:
        result.success = False
        result.error_message = f"I/O or Permission error: {e}"
    except Exception as e:
        result.success = False
        result.error_message = f"Processing error: {str(e)}"

    result.duration_seconds = time.time() - start_time
    return result


def _worker_wrapper(args_dict: dict) -> SingleFileResult:
    """Unpack serialized arguments for ProcessPoolExecutor."""
    # Ensure pillow-heif is registered in worker subprocess
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    input_path = Path(args_dict["input_path"])
    output_dir = Path(args_dict["output_dir"])
    relative_to = Path(args_dict["relative_to"]) if args_dict.get("relative_to") else None
    
    opts_data = args_dict["options"]
    options = OptimizationOptions(
        formats=opts_data["formats"],
        quality=opts_data["quality"],
        widths=opts_data["widths"],
        keep_original_size=opts_data["keep_original_size"],
        keep_exif=opts_data["keep_exif"],
        lossless=opts_data["lossless"],
        effort=opts_data["effort"],
        overwrite=opts_data["overwrite"],
    )
    return process_single_image(input_path, output_dir, options, relative_to)


def batch_optimize(
    images: List[Path],
    output_dir: Path,
    options: OptimizationOptions,
    workers: Optional[int] = None,
    relative_to: Optional[Path] = None,
    show_progress: bool = True,
    callback: Optional[Callable[[SingleFileResult], None]] = None,
) -> List[SingleFileResult]:
    """Process multiple images in parallel using multiprocessing ProcessPoolExecutor."""
    if not images:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    max_workers = workers if workers and workers > 0 else max(1, (os.cpu_count() or 1))
    
    # Serialize tasks for pickling across processes
    tasks = []
    options_dict = asdict(options)
    for img_path in images:
        tasks.append({
            "input_path": str(img_path),
            "output_dir": str(output_dir),
            "relative_to": str(relative_to) if relative_to else None,
            "options": options_dict,
        })

    results: List[SingleFileResult] = []
    total = len(tasks)

    if show_progress:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}[/bold blue]"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.completed}/{task.total} files[/cyan]"),
            TimeRemainingColumn(),
            console=console,
        )
        with progress:
            task_id = progress.add_task("Optimizing images...", total=total)
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_worker_wrapper, task): task for task in tasks}
                for future in as_completed(future_map):
                    res = future.result()
                    results.append(res)
                    if callback:
                        callback(res)
                    progress.advance(task_id, 1)
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(_worker_wrapper, task): task for task in tasks}
            for future in as_completed(future_map):
                res = future.result()
                results.append(res)
                if callback:
                    callback(res)

    return results
