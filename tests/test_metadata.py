"""Unit tests for metadata stripping, orientation normalization, and EXIF extraction."""

import tempfile
from pathlib import Path
import pytest
from PIL import Image
from PIL.ExifTags import TAGS

from webimg.config import OptimizationOptions
from webimg.core.converter import process_single_image
from webimg.core.metadata import extract_metadata_summary


@pytest.fixture
def image_with_exif():
    """Create a temporary JPEG with mock EXIF metadata (Make, Model, Software)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        img_path = tmp_path / "with_exif.jpg"

        img = Image.new("RGB", (400, 300), color=(100, 150, 200))
        exif_obj = img.getexif()
        # 0x010F: Make, 0x0110: Model, 0x0131: Software
        exif_obj[0x010F] = "WebImgCamera"
        exif_obj[0x0110] = "Alpha999"
        exif_obj[0x0131] = "PrivacyTest1.0"
        
        img.save(img_path, "JPEG", exif=exif_obj)
        yield img_path


def test_strip_exif_by_default(image_with_exif):
    """Verify that by default, all EXIF metadata is stripped from optimized output."""
    out_dir = image_with_exif.parent / "out_stripped"
    
    options = OptimizationOptions(formats=["webp"], keep_exif=False)
    res = process_single_image(image_with_exif, out_dir, options)

    assert res.success is True
    output_file = res.output_files[0]
    
    with Image.open(output_file) as out_img:
        out_exif = out_img.getexif()
        # Should have 0 tags or no sensitive camera tags
        assert 0x010F not in out_exif
        assert 0x0110 not in out_exif
        assert 0x0131 not in out_exif


def test_keep_exif_flag(image_with_exif):
    """Verify that --keep-exif preserves EXIF tags when requested."""
    out_dir = image_with_exif.parent / "out_kept"
    
    options = OptimizationOptions(formats=["webp"], keep_exif=True)
    res = process_single_image(image_with_exif, out_dir, options)

    assert res.success is True
    output_file = res.output_files[0]

    with Image.open(output_file) as out_img:
        out_exif = out_img.getexif()
        assert out_exif.get(0x010F) == "WebImgCamera"
        assert out_exif.get(0x0110) == "Alpha999"


def test_extract_metadata_summary(image_with_exif):
    """Test reading metadata for info inspection."""
    summary = extract_metadata_summary(image_with_exif)
    assert summary["format"] == "JPEG"
    assert summary["width"] == 400
    assert summary["height"] == 300
    assert summary["has_exif"] is True
    assert summary["camera_make"] == "WebImgCamera"
    assert summary["camera_model"] == "Alpha999"
