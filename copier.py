import shutil
from datetime import datetime
from pathlib import Path

MEDIA_TYPE_DIRS = {
    "image": "images",
    "video": "videos",
}

MAX_COLLISION_ATTEMPTS = 999


def build_destination_path(
    target_root: Path,
    media_type: str,
    date_taken: datetime,
    original_filename: str,
) -> Path:
    """
    Construct: target_root / images|videos / YYYY / MM / DD / filename
    Example: /backup/images/2024/03/15/IMG_0042.jpg
    """
    type_dir = MEDIA_TYPE_DIRS.get(media_type, media_type + "s")
    return (
        target_root
        / type_dir
        / date_taken.strftime("%Y")
        / date_taken.strftime("%m")
        / date_taken.strftime("%d")
        / original_filename
    )


def resolve_collision(dest_path: Path) -> Path:
    """
    If dest_path exists, append _2, _3, ... to stem until a free path is found.
    Raises RuntimeError after MAX_COLLISION_ATTEMPTS.
    """
    if not dest_path.exists():
        return dest_path

    stem = dest_path.stem
    suffix = dest_path.suffix
    parent = dest_path.parent

    for counter in range(2, MAX_COLLISION_ATTEMPTS + 2):
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(
        f"Could not resolve filename collision after {MAX_COLLISION_ATTEMPTS} "
        f"attempts for: {dest_path}"
    )


def copy_file(source_path: Path, dest_path: Path) -> Path:
    """
    Create parent directories and copy source to dest (preserving timestamps).
    Resolves filename collisions automatically.
    Returns the actual destination path used.
    """
    dest_path = resolve_collision(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)
    return dest_path
