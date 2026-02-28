from pathlib import Path
from typing import Generator, Optional, Tuple


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".webp", ".raw", ".cr2", ".nef", ".arw", ".dng",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv",
    ".flv", ".webm", ".mts", ".m2ts", ".3gp",
}

CATALOG_FILENAME = "media_catalog.json"


def classify_file(file_path: Path) -> Optional[str]:
    """Return 'image', 'video', or None based on file extension."""
    ext = file_path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def _is_hidden(path: Path) -> bool:
    """Return True if any component of the path starts with a dot."""
    return any(part.startswith(".") for part in path.parts)


def scan_directory(source_path: Path) -> Generator[Tuple[Path, str], None, None]:
    """
    Walk source_path recursively, yielding (file_path, media_type) for
    each image or video file. Skips hidden paths, symlinks, zero-byte
    files, and the catalog JSON file.
    """
    for file_path in source_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.is_symlink():
            continue
        if _is_hidden(file_path.relative_to(source_path)):
            continue
        if file_path.name == CATALOG_FILENAME:
            continue
        try:
            if file_path.stat().st_size == 0:
                continue
        except PermissionError:
            continue

        media_type = classify_file(file_path)
        if media_type is not None:
            yield file_path, media_type


def count_media_files(source_path: Path) -> int:
    """Count total media files in source_path for progress bar sizing."""
    total = 0
    for _ in scan_directory(source_path):
        total += 1
    return total
