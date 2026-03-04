import ctypes
import ctypes.util
import os
import platform
import shutil
from pathlib import Path

from exif_reader import _is_null_timestamp

MAX_COLLISION_ATTEMPTS = 999


# ── Path building ─────────────────────────────────────────────────────────────

def build_destination_path(
    target_root: Path,
    category: str,
    original_filename: str,
) -> Path:
    """
    Construct: target_root / category / original_filename
    Example: /backup/images/IMG_0042.jpg
             /backup/documents/report.pdf
    """
    return target_root / category / original_filename


# ── Collision resolution ──────────────────────────────────────────────────────

def resolve_collision(dest_path: Path) -> Path:
    """
    If dest_path already exists, append _2, _3, … to the stem until a free
    path is found.  Raises RuntimeError after MAX_COLLISION_ATTEMPTS.
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


# ── Timestamp preservation ────────────────────────────────────────────────────

def _set_birthtime_macos(path: Path, birthtime: float) -> None:
    """
    Set the file creation time (birthtime) on macOS using setattrlist(2).
    Failure is non-fatal and silently ignored.
    """
    try:
        ATTR_BIT_MAP_COUNT = 5
        ATTR_CMN_CRTIME = 0x00000200
        FSOPT_NOFOLLOW = 0x00000001

        class _AttrList(ctypes.Structure):
            _fields_ = [
                ("bitmapcount", ctypes.c_ushort),
                ("reserved",    ctypes.c_ushort),
                ("commonattr",  ctypes.c_uint32),
                ("volattr",     ctypes.c_uint32),
                ("dirattr",     ctypes.c_uint32),
                ("fileattr",    ctypes.c_uint32),
                ("forkattr",    ctypes.c_uint32),
            ]

        class _Timespec(ctypes.Structure):
            _fields_ = [
                ("tv_sec",  ctypes.c_long),
                ("tv_nsec", ctypes.c_long),
            ]

        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)

        al = _AttrList()
        al.bitmapcount = ATTR_BIT_MAP_COUNT
        al.commonattr  = ATTR_CMN_CRTIME

        ts = _Timespec()
        ts.tv_sec  = int(birthtime)
        ts.tv_nsec = int((birthtime % 1) * 1_000_000_000)

        libc.setattrlist(
            str(path).encode("utf-8"),
            ctypes.byref(al),
            ctypes.byref(ts),
            ctypes.sizeof(ts),
            FSOPT_NOFOLLOW,
        )
    except Exception:
        pass  # non-fatal


def preserve_timestamps(dest_path: Path, source_path: Path, date_taken=None) -> None:
    """
    Stamp dest_path with the timestamps.

    Rules:
    - If date_taken is provided, use its timestamp for both mtime and birthtime.
    - Otherwise, extract mtime from source_path.
        - If source mtime is a null/sentinel, skip everything (keep copy-time).
    - Set dest mtime via os.utime().
    - On macOS also set dest birthtime using either the date_taken timestamp,
      the source's birthtime, or pinning to mtime.
    """
    if date_taken is not None:
        target_ts = date_taken.timestamp()
        target_mtime = target_ts
        target_birthtime = target_ts
    else:
        stat = source_path.stat()
        mtime = stat.st_mtime
        if _is_null_timestamp(mtime):
            # Every source timestamp is bad — keep the copy-time stamp.
            return
        target_mtime = mtime
        
        if platform.system() == "Darwin":
            birthtime = getattr(stat, "st_birthtime", None)
            if birthtime and birthtime > 0 and not _is_null_timestamp(birthtime):
                target_birthtime = birthtime
            else:
                target_birthtime = mtime

    # Apply mtime on all platforms (atime = mtime to avoid leaking access time).
    os.utime(dest_path, (target_mtime, target_mtime))

    # macOS: also set birthtime so creation is never newer than modification.
    if platform.system() == "Darwin":
        if 'target_birthtime' in locals():
            _set_birthtime_macos(dest_path, target_birthtime)


# ── File copy ─────────────────────────────────────────────────────────────────

def copy_file(source_path: Path, dest_path: Path, date_taken=None) -> Path:
    """
    Copy source_path to dest_path, creating parent directories as needed.
    Resolves filename collisions automatically.
    Preserves both mtime and (on macOS) birthtime from the source, or overrides
    them with date_taken if provided.
    Returns the actual destination path used.
    """
    dest_path = resolve_collision(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)      # copies content + basic timestamps
    preserve_timestamps(dest_path, source_path, date_taken=date_taken)  # restore birthtime on macOS
    return dest_path
