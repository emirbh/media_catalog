"""
Shared fixtures for the media-catalog test suite.
"""
import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from models import FileRecord


# ── File-creation helpers ─────────────────────────────────────────────────────

def make_file(path: Path, content: bytes = b"dummy content") -> Path:
    """Create a file with the given content; create parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def make_image(path: Path, content: bytes = b"fake jpeg data") -> Path:
    return make_file(path, content)


def make_video(path: Path, content: bytes = b"fake mp4 data") -> Path:
    return make_file(path, content)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def src(tmp_path: Path) -> Path:
    """Empty source directory."""
    d = tmp_path / "source"
    d.mkdir()
    return d


@pytest.fixture
def tgt(tmp_path: Path) -> Path:
    """Empty target directory."""
    d = tmp_path / "target"
    d.mkdir()
    return d


@pytest.fixture
def sample_record() -> FileRecord:
    return FileRecord(
        hash="abc123",
        original_path="/src/photo.jpg",
        destination_path="/tgt/images/2024/03/15/photo.jpg",
        media_type="image",
        extension=".jpg",
        date_taken="2024-03-15",
        date_source="exif",
        file_size_bytes=1024,
        cataloged_at="2024-03-15T12:00:00",
    )


@pytest.fixture
def fixed_date() -> datetime:
    return datetime(2024, 3, 15, 10, 30, 0)
