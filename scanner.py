from pathlib import Path
from typing import Generator, Tuple

from categories import categorize_file
from excludes import Excludes


CATALOG_FILENAME = "media_catalog.json"

_EMPTY_EXCLUDES = Excludes([])


def _is_hidden(path: Path) -> bool:
    """Return True if any component of the relative path starts with a dot."""
    return any(part.startswith(".") for part in path.parts)


def scan_directory(
    source_path: Path,
    excludes: Excludes = _EMPTY_EXCLUDES,
) -> Generator[Tuple[Path, str], None, None]:
    """
    Walk source_path recursively, yielding (file_path, category) for every
    non-hidden, non-zero, non-symlink file.  Unknown extensions land in the
    'others' category.  Hidden paths, symlinks, zero-byte files, the catalog
    JSON, and anything matched by excludes are silently skipped.
    """
    for file_path in source_path.rglob("*"):
        rel = file_path.relative_to(source_path)

        if _is_hidden(rel):
            continue

        # Directories are never yielded; just used for traversal
        if file_path.is_dir():
            continue

        if not file_path.is_file():
            continue

        if file_path.is_symlink():
            continue

        if file_path.name == CATALOG_FILENAME:
            continue

        # Skip files inside an excluded directory
        if rel.parent != Path(".") and excludes.should_skip_dir(rel.parent):
            continue

        # Skip directories matched by name anywhere in the relative path
        if excludes.should_skip_dir(rel):
            continue

        # Skip excluded files / extensions
        if excludes.should_skip_file(file_path):
            continue

        try:
            if file_path.stat().st_size == 0:
                continue
        except (PermissionError, FileNotFoundError, OSError):
            continue
        yield file_path, categorize_file(file_path)


def count_files(
    source_path: Path,
    excludes: Excludes = _EMPTY_EXCLUDES,
) -> int:
    """Count total files that would be processed."""
    return sum(1 for _ in scan_directory(source_path, excludes=excludes))
