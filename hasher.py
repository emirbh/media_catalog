import hashlib
from pathlib import Path

CHUNK_SIZE = 65536  # 64 KB


def compute_sha256(file_path: Path) -> str:
    """Stream-read file and return hex SHA256 digest."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
    except OSError as e:
        raise OSError(f"Cannot read {file_path}: {e}") from e
    return h.hexdigest()


def compute_md5(file_path: Path) -> str:
    """Stream-read file and return hex MD5 digest."""
    h = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
    except OSError as e:
        raise OSError(f"Cannot read {file_path}: {e}") from e
    return h.hexdigest()


def compute_hash(file_path: Path, algo: str = "sha256") -> str:
    """Compute hash using the specified algorithm ('sha256' or 'md5')."""
    if algo == "md5":
        return compute_md5(file_path)
    return compute_sha256(file_path)
