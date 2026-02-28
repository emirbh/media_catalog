from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

try:
    import exifread
    _EXIFREAD_AVAILABLE = True
except ImportError:
    _EXIFREAD_AVAILABLE = False

# EXIF tags checked in priority order
EXIF_DATE_TAGS = [
    "EXIF DateTimeOriginal",
    "EXIF DateTimeDigitized",
    "Image DateTime",
]

# QuickTime/video date tags
VIDEO_DATE_TAGS = [
    "QuickTime Creation Date",
    "QuickTime:CreateDate",
]

EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"


def _parse_exif_date(raw_value: str) -> Optional[datetime]:
    """Parse an EXIF date string, returning None if invalid or zeroed."""
    try:
        dt = datetime.strptime(raw_value.strip(), EXIF_DATE_FORMAT)
        # Guard against cameras writing zeroed dates
        if dt.year < 1970 or dt.month == 0 or dt.day == 0:
            return None
        return dt
    except (ValueError, AttributeError):
        return None


def get_date_from_exif(file_path: Path) -> Tuple[Optional[datetime], str]:
    """
    Attempt EXIF extraction using exifread.
    Returns (datetime, 'exif') on success, (None, '') on failure.
    """
    if not _EXIFREAD_AVAILABLE:
        return None, ""

    try:
        with open(file_path, "rb") as f:
            tags = exifread.process_file(f, stop_tag="DateTimeOriginal", details=False)

        # Try image EXIF tags first
        for tag_name in EXIF_DATE_TAGS:
            if tag_name in tags:
                dt = _parse_exif_date(str(tags[tag_name]))
                if dt is not None:
                    return dt, "exif"

        # Try video/QuickTime tags
        for tag_name in VIDEO_DATE_TAGS:
            if tag_name in tags:
                dt = _parse_exif_date(str(tags[tag_name]))
                if dt is not None:
                    return dt, "exif"

        # Re-read without stop_tag to catch more tags for videos
        with open(file_path, "rb") as f:
            tags = exifread.process_file(f, details=False)

        for tag_name in EXIF_DATE_TAGS + VIDEO_DATE_TAGS:
            if tag_name in tags:
                dt = _parse_exif_date(str(tags[tag_name]))
                if dt is not None:
                    return dt, "exif"

    except Exception:
        pass

    return None, ""


def get_date_from_fs(file_path: Path) -> Tuple[datetime, str]:
    """
    Return the earliest reliable filesystem timestamp with a source label.

    Priority:
      1. st_birthtime  — true creation time (macOS, BSD, Windows via Python)
      2. st_ctime      — inode change time (Linux fallback; approximates creation)
      3. st_mtime      — last modification time (final fallback)
    """
    stat = file_path.stat()

    # st_birthtime is available on macOS/BSD and on Windows (Python 3.8+)
    birthtime = getattr(stat, "st_birthtime", None)
    if birthtime is not None and birthtime > 0:
        return datetime.fromtimestamp(birthtime), "birthtime"

    # st_ctime on Linux is inode change time, not true creation time,
    # but it is still earlier than mtime for freshly written files.
    ctime = stat.st_ctime
    mtime = stat.st_mtime
    if ctime <= mtime:
        return datetime.fromtimestamp(ctime), "ctime"

    return datetime.fromtimestamp(mtime), "mtime"


def get_media_date(file_path: Path) -> Tuple[datetime, str]:
    """
    Try EXIF first, then filesystem timestamps (birthtime → ctime → mtime).
    Always returns a valid (datetime, source_label) tuple.
    """
    dt, source = get_date_from_exif(file_path)
    if dt is not None:
        return dt, source
    return get_date_from_fs(file_path)
