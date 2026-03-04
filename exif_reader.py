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

# Only these extensions carry EXIF or QuickTime metadata that exifread can
# reliably decode.  Everything else (MPEG-1/2 streams, AVI, MKV, WMV, FLV …)
# has no standard EXIF container — skip straight to filesystem timestamps.
_EXIF_CAPABLE = frozenset({
    # Camera stills & RAW
    ".jpg", ".jpeg",
    ".heic", ".heif",
    ".tiff", ".tif",
    ".raw",
    ".cr2", ".cr3",
    ".nef", ".arw", ".dng",
    ".orf", ".rw2", ".pef", ".srw",
    # QuickTime / ISO-MP4 container (have a creation date atom)
    ".mov", ".mp4", ".m4v",
    ".3gp", ".mts", ".m2ts",
})

# Sentinel dates cameras write when their clock has never been set.
# Treated as "no valid date" — falls back to filesystem timestamps.
#   2000-12-31  — Apple/iOS QuickTime default (clock not set, QuickTime path)
#   2001-01-01  — Cocoa/NSDate reference epoch (iOS [NSDate date] zero-value);
#                 timezone shift of 2000-12-31 UTC can also produce this date
#   1904-01-01  — QuickTime epoch (time_t == 0 in 32-bit QuickTime)
#   1970-01-01  — Unix epoch; appears when QuickTime<->Unix time conversion
#                 produces zero (camera with unset clock on some Android/GoPro)
#   1980-01-01  — DOS/FAT epoch used by some Windows-based cameras
_NULL_DATES = frozenset({
    datetime(2000, 12, 31).date(),
    datetime(2001,  1,  1).date(),
    datetime(1970,  1,  1).date(),
    datetime(1904,  1,  1).date(),
    datetime(1980,  1,  1).date(),
})


def _is_null_timestamp(unix_ts: float) -> bool:
    """
    Return True if a Unix timestamp corresponds to a known null/sentinel date.
    Used to filter bad filesystem timestamps written by cameras with unset clocks.

    Non-positive timestamps (pre-Unix-epoch, e.g. 1904-01-01 stored as a
    negative value, or literal zero) are always treated as null.
    """
    if unix_ts <= 0:
        return True
    try:
        return datetime.fromtimestamp(unix_ts).date() in _NULL_DATES
    except (OSError, OverflowError, ValueError):
        return True   # unparseable → treat as null


def _parse_exif_date(raw_value: str) -> Optional[datetime]:
    """
    Parse an EXIF date string, returning None if the value is structurally
    invalid, zeroed, or a known camera-clock-not-set sentinel date.
    """
    try:
        dt = datetime.strptime(raw_value.strip(), EXIF_DATE_FORMAT)
        # Reject structurally impossible values
        if dt.year < 1970 or dt.month == 0 or dt.day == 0:
            return None
        # Reject known sentinel/epoch dates (device clock was never configured)
        if dt.date() in _NULL_DATES:
            return None
        return dt
    except (ValueError, AttributeError):
        return None


def get_date_from_exif(file_path: Path) -> Tuple[Optional[datetime], str]:
    """
    Attempt EXIF extraction using exifread.
    Only runs for extensions in _EXIF_CAPABLE; all others return (None, '')
    immediately so that filesystem timestamps are used instead.
    Returns (datetime, 'exif') on success, (None, '') on failure.
    """
    if not _EXIFREAD_AVAILABLE:
        return None, ""

    if file_path.suffix.lower() not in _EXIF_CAPABLE:
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

    Collects available timestamps (birthtime, ctime, mtime), validates them against
    known camera sentinel values, and returns the oldest valid date.
    """
    stat = file_path.stat()
    candidates = []

    # 1. st_birthtime is available on macOS/BSD and on Windows (Python 3.8+)
    birthtime = getattr(stat, "st_birthtime", None)
    if birthtime is not None and birthtime > 0 and not _is_null_timestamp(birthtime):
        candidates.append((birthtime, "birthtime"))

    # 2. st_ctime (inode change time on Linux, approximates creation otherwise)
    ctime = stat.st_ctime
    if ctime > 0 and not _is_null_timestamp(ctime):
        candidates.append((ctime, "ctime"))

    # 3. st_mtime (last modification time)
    mtime = stat.st_mtime
    if mtime > 0 and not _is_null_timestamp(mtime):
        candidates.append((mtime, "mtime"))

    if candidates:
        # Sort by timestamp ascending (oldest first)
        candidates.sort(key=lambda x: x[0])
        oldest_ts, source = candidates[0]
        return datetime.fromtimestamp(oldest_ts), source

    # Every filesystem timestamp is a null/sentinel — camera clock was never set.
    # Fall back to the current time (the moment the file is being imported).
    return datetime.now(), "import_time"


def get_media_date(file_path: Path) -> Tuple[datetime, str]:
    """
    Try EXIF first, then filesystem timestamps (birthtime → ctime → mtime).
    Always returns a valid (datetime, source_label) tuple.
    """
    dt, source = get_date_from_exif(file_path)
    if dt is not None:
        return dt, source
    return get_date_from_fs(file_path)
