"""Unit tests for webimg image converter and responsive generation."""

import tempfile
from pathlib import Path
import pytest
from PIL import Image

from webimg.config import OptimizationOptions
from webimg.core.converter import batch_optimize, process_single_image


@pytest.fixture
def sample_image_dir():
    """Create a temporary directory with sample images."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. Standard RGB JPEG (1000x800)
        img_rgb = Image.new("RGB", (1000, 800), color=(73, 109, 137))
        rgb_path = tmp_path / "sample.jpg"
        img_rgb.save(rgb_path, "JPEG", quality=90)

        # 2. Transparent RGBA PNG (500x500)
        img_rgba = Image.new("RGBA", (500, 500), color=(255, 0, 0, 128))
        rgba_path = tmp_path / "transparent.png"
        img_rgba.save(rgba_path, "PNG")

        # 3. Small PNG (200x200)
        img_small = Image.new("RGB", (200, 200), color=(0, 255, 0))
        small_path = tmp_path / "small.png"
        img_small.save(small_path, "PNG")

        # 4. Corrupt image file
        corrupt_path = tmp_path / "corrupt.jpg"
        corrupt_path.write_bytes(b"This is not a valid image file binary content.")

        # 5. Empty image file (0 bytes)
        empty_path = tmp_path / "empty.png"
        empty_path.write_bytes(b"")

        yield tmp_path


def test_convert_to_webp(sample_image_dir):
    """Test basic conversion to WebP."""
    input_file = sample_image_dir / "sample.jpg"
    out_dir = sample_image_dir / "out_webp"
    
    options = OptimizationOptions(formats=["webp"], quality=75)
    res = process_single_image(input_file, out_dir, options)

    assert res.success is True
    assert len(res.output_files) == 1
    assert res.output_files[0].suffix == ".webp"
    assert res.output_files[0].exists()
    assert res.total_output_bytes > 0


def test_convert_to_avif(sample_image_dir):
    """Test conversion to modern AVIF format."""
    input_file = sample_image_dir / "sample.jpg"
    out_dir = sample_image_dir / "out_avif"
    
    options = OptimizationOptions(formats=["avif"], quality=70)
    res = process_single_image(input_file, out_dir, options)

    assert res.success is True
    assert len(res.output_files) == 1
    assert res.output_files[0].suffix == ".avif"
    assert res.output_files[0].exists()
    assert res.total_output_bytes > 0


def test_multi_format_conversion(sample_image_dir):
    """Test simultaneous conversion to both WebP and AVIF."""
    input_file = sample_image_dir / "sample.jpg"
    out_dir = sample_image_dir / "out_multi"
    
    options = OptimizationOptions(formats=["webp", "avif"], quality=80)
    res = process_single_image(input_file, out_dir, options)

    assert res.success is True
    assert len(res.output_files) == 2
    extensions = {p.suffix for p in res.output_files}
    assert extensions == {".webp", ".avif"}


def test_responsive_widths_generation(sample_image_dir):
    """Test responsive variants generation without upscaling."""
    input_file = sample_image_dir / "sample.jpg"  # 1000x800
    out_dir = sample_image_dir / "out_variants"
    
    # Request 300, 768, 1200. Since original is 1000, 1200 is skipped.
    options = OptimizationOptions(
        formats=["webp"],
        widths=[300, 768, 1200],
        keep_original_size=True,
    )
    res = process_single_image(input_file, out_dir, options)

    assert res.success is True
    # Should produce: sample_300w.webp, sample_768w.webp, sample.webp (original 1000w)
    assert len(res.output_files) == 3
    file_names = {f.name for f in res.output_files}
    assert "sample_300w.webp" in file_names
    assert "sample_768w.webp" in file_names
    assert "sample.webp" in file_names

    # Verify actual image dimensions of generated files
    with Image.open(out_dir / "sample_300w.webp") as img:
        assert img.width == 300
        assert img.height == int(round((300 / 1000) * 800))  # 240

    with Image.open(out_dir / "sample_768w.webp") as img:
        assert img.width == 768
        assert img.height == int(round((768 / 1000) * 800))  # 614


def test_transparent_png_to_webp_preserves_alpha(sample_image_dir):
    """Test that transparent RGBA PNG retains alpha channel in WebP."""
    input_file = sample_image_dir / "transparent.png"
    out_dir = sample_image_dir / "out_alpha"

    options = OptimizationOptions(formats=["webp"])
    res = process_single_image(input_file, out_dir, options)

    assert res.success is True
    webp_path = res.output_files[0]
    with Image.open(webp_path) as img:
        assert img.mode == "RGBA"


def test_corrupt_file_handling(sample_image_dir):
    """Test graceful failure when processing a corrupt file."""
    input_file = sample_image_dir / "corrupt.jpg"
    out_dir = sample_image_dir / "out_corrupt"

    options = OptimizationOptions(formats=["webp"])
    res = process_single_image(input_file, out_dir, options)

    assert res.success is False
    assert res.error_message is not None
    assert "corrupt" in res.error_message.lower() or "unrecognized" in res.error_message.lower()


def test_empty_file_handling(sample_image_dir):
    """Test graceful failure when file is 0 bytes."""
    input_file = sample_image_dir / "empty.png"
    out_dir = sample_image_dir / "out_empty"

    options = OptimizationOptions(formats=["webp"])
    res = process_single_image(input_file, out_dir, options)

    assert res.success is False
    assert "0 bytes" in res.error_message.lower()


def test_batch_multiprocessing(sample_image_dir):
    """Test batch_optimize with ProcessPoolExecutor."""
    images = [
        sample_image_dir / "sample.jpg",
        sample_image_dir / "transparent.png",
        sample_image_dir / "small.png",
    ]
    out_dir = sample_image_dir / "out_batch"

    options = OptimizationOptions(formats=["webp"], quality=75)
    results = batch_optimize(images, out_dir, options, workers=2, show_progress=False)

    assert len(results) == 3
    for r in results:
        assert r.success is True
        assert len(r.output_files) == 1
        assert r.output_files[0].exists()
