"""Tests for copier.py — path building, collision resolution, file copying."""
from datetime import datetime
from pathlib import Path

import pytest

from copier import build_destination_path, copy_file, resolve_collision
from tests.conftest import make_file


FIXED_DATE = datetime(2024, 3, 15, 10, 30, 0)


# ── build_destination_path ────────────────────────────────────────────────────

class TestBuildDestinationPath:
    def test_image_path_structure(self, tgt):
        result = build_destination_path(tgt, "image", FIXED_DATE, "photo.jpg")
        assert result == tgt / "images" / "2024" / "03" / "15" / "photo.jpg"

    def test_video_path_structure(self, tgt):
        result = build_destination_path(tgt, "video", FIXED_DATE, "clip.mp4")
        assert result == tgt / "videos" / "2024" / "03" / "15" / "clip.mp4"

    def test_zero_padded_month_and_day(self, tgt):
        date = datetime(2023, 1, 5)
        result = build_destination_path(tgt, "image", date, "img.jpg")
        assert result == tgt / "images" / "2023" / "01" / "05" / "img.jpg"

    def test_filename_preserved(self, tgt):
        result = build_destination_path(tgt, "image", FIXED_DATE, "IMG_0042.JPG")
        assert result.name == "IMG_0042.JPG"

    def test_different_dates_different_paths(self, tgt):
        d1 = datetime(2024, 1, 1)
        d2 = datetime(2024, 12, 31)
        p1 = build_destination_path(tgt, "image", d1, "x.jpg")
        p2 = build_destination_path(tgt, "image", d2, "x.jpg")
        assert p1 != p2

    def test_unknown_media_type_appends_s(self, tgt):
        # Fallback: unknown type → "unknowns/"
        result = build_destination_path(tgt, "unknown", FIXED_DATE, "file.xyz")
        assert result.parts[-5] == "unknowns"


# ── resolve_collision ─────────────────────────────────────────────────────────

class TestResolveCollision:
    def test_no_collision_returns_same_path(self, tmp_path):
        p = tmp_path / "photo.jpg"
        assert resolve_collision(p) == p

    def test_single_collision_appends_2(self, tmp_path):
        p = make_file(tmp_path / "photo.jpg")
        result = resolve_collision(p)
        assert result == tmp_path / "photo_2.jpg"

    def test_multiple_collisions_increments(self, tmp_path):
        make_file(tmp_path / "photo.jpg")
        make_file(tmp_path / "photo_2.jpg")
        result = resolve_collision(tmp_path / "photo.jpg")
        assert result == tmp_path / "photo_3.jpg"

    def test_suffix_preserved(self, tmp_path):
        p = make_file(tmp_path / "clip.mp4")
        result = resolve_collision(p)
        assert result.suffix == ".mp4"

    def test_no_extension_file(self, tmp_path):
        p = make_file(tmp_path / "README")
        result = resolve_collision(p)
        assert result == tmp_path / "README_2"

    def test_non_existent_path_returned_as_is(self, tmp_path):
        p = tmp_path / "new_photo.jpg"
        assert not p.exists()
        assert resolve_collision(p) == p


# ── copy_file ─────────────────────────────────────────────────────────────────

class TestCopyFile:
    def test_copies_content(self, tmp_path):
        src = make_file(tmp_path / "src" / "photo.jpg", b"image data")
        dest = tmp_path / "dst" / "photo.jpg"
        actual = copy_file(src, dest)
        assert actual.read_bytes() == b"image data"

    def test_creates_parent_directories(self, tmp_path):
        src = make_file(tmp_path / "src.jpg", b"data")
        dest = tmp_path / "deep" / "nested" / "dir" / "src.jpg"
        copy_file(src, dest)
        assert dest.exists()

    def test_returns_actual_destination(self, tmp_path):
        src = make_file(tmp_path / "photo.jpg", b"x")
        dest = tmp_path / "out" / "photo.jpg"
        result = copy_file(src, dest)
        assert result == dest

    def test_resolves_collision_automatically(self, tmp_path):
        src = make_file(tmp_path / "photo.jpg", b"new content")
        dest_dir = tmp_path / "out"
        existing = make_file(dest_dir / "photo.jpg", b"old content")
        result = copy_file(src, dest_dir / "photo.jpg")
        assert result == dest_dir / "photo_2.jpg"
        assert existing.read_bytes() == b"old content"   # original untouched
        assert result.read_bytes() == b"new content"

    def test_does_not_overwrite_existing(self, tmp_path):
        src = make_file(tmp_path / "photo.jpg", b"new")
        dest = make_file(tmp_path / "out" / "photo.jpg", b"original")
        copy_file(src, tmp_path / "out" / "photo.jpg")
        assert dest.read_bytes() == b"original"

    def test_copy_preserves_large_content(self, tmp_path):
        data = b"z" * (300 * 1024)  # 300 KB
        src = make_file(tmp_path / "big.jpg", data)
        dest = tmp_path / "out" / "big.jpg"
        copy_file(src, dest)
        assert dest.read_bytes() == data
