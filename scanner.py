from pathlib import Path
from typing import Generator, Optional, Tuple

from excludes import Excludes


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".webp", ".raw", ".cr2", ".nef", ".arw", ".dng",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv",
    ".flv", ".webm", ".mts", ".m2ts", ".3gp",
}

CATALOG_FILENAME = "media_catalog.json"

_EMPTY_EXCLUDES = Excludes([])


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


def scan_directory(
    source_path: Path,
    excludes: Excludes = _EMPTY_EXCLUDES,
) -> Generator[Tuple[Path, str], None, None]:
    """
    Walk source_path recursively, yielding (file_path, media_type) for
    each image or video file. Skips hidden paths, symlinks, zero-byte
    files, the catalog JSON file, and anything matched by excludes.
    """
    for file_path in source_path.rglob("*"):
        rel = file_path.relative_to(source_path)

        # Skip hidden paths
        if _is_hidden(rel):
            continue

        # Skip excluded directories early (avoids descending into them)
        if file_path.is_dir():
            if excludes.should_skip_dir(rel):
                # Mark all children as pruned by not yielding; rglob will
                # still visit them, so we skip at the file level too.
                pass
            continue

        if not file_path.is_file():
            continue
        if file_path.is_symlink():
            continue
        if file_path.name == CATALOG_FILENAME:
            continue

        # Skip files whose parent directory is excluded
        if rel.parent != Path(".") and excludes.should_skip_dir(rel.parent):
            continue

        # Skip excluded files / extensions
        if excludes.should_skip_file(file_path):
            continue

        try:
            if file_path.stat().st_size == 0:
                continue
        except PermissionError:
            continue

        media_type = classify_file(file_path)
        if media_type is not None:
            yield file_path, media_type


def count_media_files(
    source_path: Path,
    excludes: Excludes = _EMPTY_EXCLUDES,
) -> int:
    """Count total media files in source_path for progress bar sizing."""
    total = 0
    for _ in scan_directory(source_path, excludes=excludes):
        total += 1
    return total
