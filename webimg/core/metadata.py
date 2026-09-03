"""Metadata and EXIF handling for privacy preservation and orientation normalization."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS


def normalize_orientation(image: Image.Image) -> Image.Image:
    """Apply EXIF orientation to pixel data so stripping EXIF does not rotate the image."""
    try:
        transposed = ImageOps.exif_transpose(image)
        return transposed if transposed is not None else image
    except Exception:
        return image


def prepare_metadata_for_save(
    image: Image.Image, keep_exif: bool = False
) -> Dict[str, Any]:
    """Prepare save parameters regarding EXIF and color profiles.
    
    If keep_exif is False (default), sensitive EXIF data is stripped.
    Color profile (ICC) is preserved if present to maintain accurate visual color.
    """
    save_kwargs: Dict[str, Any] = {}

    if keep_exif:
        raw_exif = image.info.get("exif")
        if raw_exif:
            save_kwargs["exif"] = raw_exif

    # Preserve ICC profile for color fidelity if present
    icc_profile = image.info.get("icc_profile")
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile

    return save_kwargs


def extract_metadata_summary(image_path: Path) -> Dict[str, Any]:
    """Extract human-readable metadata summary for the info command."""
    summary: Dict[str, Any] = {
        "format": "Unknown",
        "mode": "Unknown",
        "width": 0,
        "height": 0,
        "has_exif": False,
        "camera_make": None,
        "camera_model": None,
        "datetime": None,
        "has_gps": False,
        "gps_coords": None,
        "raw_tag_count": 0,
    }

    try:
        with Image.open(image_path) as img:
            summary["format"] = img.format or image_path.suffix.upper().lstrip(".")
            summary["mode"] = img.mode
            summary["width"] = img.width
            summary["height"] = img.height

            exif = img.getexif()
            if exif:
                summary["has_exif"] = True
                summary["raw_tag_count"] = len(exif)

                for tag_id, value in exif.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    if tag_name == "Make":
                        summary["camera_make"] = str(value).strip()
                    elif tag_name == "Model":
                        summary["camera_model"] = str(value).strip()
                    elif tag_name == "DateTime":
                        summary["datetime"] = str(value).strip()
                    elif tag_name == "GPSInfo":
                        summary["has_gps"] = True
                        # Parse GPS IFD if accessible
                        try:
                            gps_ifd = exif.get_ifd(0x8825)
                            if gps_ifd:
                                summary["gps_coords"] = _parse_gps(gps_ifd)
                        except Exception:
                            summary["gps_coords"] = "Present (Raw IFD)"

    except Exception as e:
        summary["error"] = str(e)

    return summary


def _parse_gps(gps_dict: Dict[int, Any]) -> Optional[str]:
    """Convert raw GPS IFD values to decimal degrees or readable coordinates."""
    try:
        lat_ref = gps_dict.get(1)
        lat_tuple = gps_dict.get(2)
        lon_ref = gps_dict.get(3)
        lon_tuple = gps_dict.get(4)

        if lat_tuple and lon_tuple:
            lat = _convert_to_degrees(lat_tuple)
            lon = _convert_to_degrees(lon_tuple)
            if lat_ref == "S":
                lat = -lat
            if lon_ref == "W":
                lon = -lon
            return f"{lat:.6f}, {lon:.6f}"
    except Exception:
        pass
    return "Present"


def _convert_to_degrees(value: Any) -> float:
    """Helper to convert degrees/minutes/seconds tuple to float degrees."""
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)
