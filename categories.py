"""
File categorisation for the media catalog.

Every known extension maps to one of these category names (which become the
top-level folder names in the target directory):

    images        — camera photos and RAW files
    videos        — all video formats
    screenshots   — non-camera raster images (PNG, GIF, BMP, WebP …)
    documents     — office docs, PDFs, plain text, spreadsheets …
    web-pages     — saved HTML pages and related formats
    music-files   — audio recordings
    others        — anything not matched above
"""

from pathlib import Path

CATEGORY_MAP: dict[str, str] = {
    # ── Images (camera photos + RAW) ─────────────────────────────────────────
    ".jpg":  "images",
    ".jpeg": "images",
    ".heic": "images",
    ".heif": "images",
    ".tiff": "images",
    ".tif":  "images",
    ".raw":  "images",
    ".cr2":  "images",
    ".cr3":  "images",
    ".nef":  "images",
    ".arw":  "images",
    ".dng":  "images",
    ".orf":  "images",
    ".rw2":  "images",
    ".pef":  "images",
    ".srw":  "images",

    # ── Screenshots / non-camera rasters ────────────────────────────────────
    ".png":  "screenshots",
    ".gif":  "screenshots",
    ".bmp":  "screenshots",
    ".webp": "screenshots",
    ".svg":  "screenshots",
    ".ico":  "screenshots",

    # ── Videos ───────────────────────────────────────────────────────────────
    ".mp4":  "videos",
    ".mov":  "videos",
    ".avi":  "videos",
    ".mkv":  "videos",
    ".m4v":  "videos",
    ".wmv":  "videos",
    ".flv":  "videos",
    ".webm": "videos",
    ".mts":  "videos",
    ".m2ts": "videos",
    ".3gp":  "videos",
    ".ts":   "videos",
    ".vob":  "videos",
    ".ogv":  "videos",
    # MPEG-1/2 variants
    ".mpg":  "videos",
    ".mpeg": "videos",
    ".mpv":  "videos",
    ".m2v":  "videos",
    ".m2p":  "videos",
    ".mpe":  "videos",

    # ── Music ────────────────────────────────────────────────────────────────
    ".mp3":  "music-files",
    ".wav":  "music-files",
    ".flac": "music-files",
    ".aac":  "music-files",
    ".ogg":  "music-files",
    ".m4a":  "music-files",
    ".wma":  "music-files",
    ".opus": "music-files",
    ".aiff": "music-files",
    ".aif":  "music-files",
    ".alac": "music-files",
    ".ape":  "music-files",

    # ── Documents ────────────────────────────────────────────────────────────
    ".pdf":   "documents",
    ".doc":   "documents",
    ".docx":  "documents",
    ".xls":   "documents",
    ".xlsx":  "documents",
    ".ppt":   "documents",
    ".pptx":  "documents",
    ".odt":   "documents",
    ".ods":   "documents",
    ".odp":   "documents",
    ".txt":   "documents",
    ".rtf":   "documents",
    ".csv":   "documents",
    ".md":    "documents",
    ".pages": "documents",
    ".numbers": "documents",
    ".key":   "documents",
    ".epub":  "documents",
    ".mobi":  "documents",

    # ── Web pages ────────────────────────────────────────────────────────────
    ".html":  "web-pages",
    ".htm":   "web-pages",
    ".mhtml": "web-pages",
    ".mht":   "web-pages",
    ".xhtml": "web-pages",
    ".webloc": "web-pages",
    ".url":   "web-pages",
}

# The fallback bucket for unrecognised extensions
CATEGORY_OTHERS = "others"

# All valid category names (used for validation in tests)
ALL_CATEGORIES = frozenset(CATEGORY_MAP.values()) | {CATEGORY_OTHERS}


def categorize_file(file_path: Path) -> str:
    """
    Return the category name for file_path based on its extension.
    Returns CATEGORY_OTHERS ("others") for unrecognised extensions.
    Comparison is always case-insensitive.
    """
    return CATEGORY_MAP.get(file_path.suffix.lower(), CATEGORY_OTHERS)
