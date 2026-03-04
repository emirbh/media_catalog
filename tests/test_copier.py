"""Tests for copier.py — path building, collision resolution, file copying,
and timestamp preservation."""
import calendar
import os
import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from copier import build_destination_path, copy_file, preserve_timestamps, resolve_collision
from tests.conftest import make_file

# 2001-01-01 00:00:00 UTC — a known null/sentinel timestamp
_NULL_TS = float(calendar.timegm((2001, 1, 1, 0, 0, 0, 0, 0, 0)))


# ── build_destination_path ────────────────────────────────────────────────────

class TestBuildDestinationPath:
    def test_image_path_structure(self, tgt):
        result = build_destination_path(tgt, "images", "photo.jpg")
        assert result == tgt / "images" / "photo.jpg"

    def test_video_path_structure(self, tgt):
        result = build_destination_path(tgt, "videos", "clip.mp4")
        assert result == tgt / "videos" / "clip.mp4"

    def test_documents_path_structure(self, tgt):
        result = build_destination_path(tgt, "documents", "report.pdf")
        assert result == tgt / "documents" / "report.pdf"

    def test_screenshots_path_structure(self, tgt):
        result = build_destination_path(tgt, "screenshots", "capture.png")
        assert result == tgt / "screenshots" / "capture.png"

    def test_music_files_path_structure(self, tgt):
        result = build_destination_path(tgt, "music-files", "song.mp3")
        assert result == tgt / "music-files" / "song.mp3"

    def test_web_pages_path_structure(self, tgt):
        result = build_destination_path(tgt, "web-pages", "page.html")
        assert result == tgt / "web-pages" / "page.html"

    def test_others_path_structure(self, tgt):
        result = build_destination_path(tgt, "others", "mystery.xyz")
        assert result == tgt / "others" / "mystery.xyz"

    def test_filename_preserved_exactly(self, tgt):
        result = build_destination_path(tgt, "images", "IMG_0042.JPG")
        assert result.name == "IMG_0042.JPG"

    def test_path_depth_is_two_levels(self, tgt):
        result = build_destination_path(tgt, "images", "photo.jpg")
        # target/category/filename → exactly 2 levels below target_root
        assert result.parent.parent == tgt


# ── resolve_collision ─────────────────────────────────────────────────────────

class TestResolveCollision:
    def test_no_collision_returns_same_path(self, tmp_path):
        p = tmp_path / "photo.jpg"
        assert resolve_collision(p) == p

    def test_single_collision_appends_2(self, tmp_path):
        make_file(tmp_path / "photo.jpg")
        result = resolve_collision(tmp_path / "photo.jpg")
        assert result == tmp_path / "photo_2.jpg"

    def test_multiple_collisions_increments(self, tmp_path):
        make_file(tmp_path / "photo.jpg")
        make_file(tmp_path / "photo_2.jpg")
        result = resolve_collision(tmp_path / "photo.jpg")
        assert result == tmp_path / "photo_3.jpg"

    def test_suffix_preserved(self, tmp_path):
        make_file(tmp_path / "clip.mp4")
        result = resolve_collision(tmp_path / "clip.mp4")
        assert result.suffix == ".mp4"

    def test_no_extension_file(self, tmp_path):
        make_file(tmp_path / "README")
        result = resolve_collision(tmp_path / "README")
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
        existing = make_file(tmp_path / "out" / "photo.jpg", b"old content")
        result = copy_file(src, tmp_path / "out" / "photo.jpg")
        assert result == tmp_path / "out" / "photo_2.jpg"
        assert existing.read_bytes() == b"old content"
        assert result.read_bytes() == b"new content"

    def test_does_not_overwrite_existing(self, tmp_path):
        src = make_file(tmp_path / "photo.jpg", b"new")
        dest = make_file(tmp_path / "out" / "photo.jpg", b"original")
        copy_file(src, tmp_path / "out" / "photo.jpg")
        assert dest.read_bytes() == b"original"

    def test_copy_preserves_large_content(self, tmp_path):
        data = b"z" * (300 * 1024)
        src = make_file(tmp_path / "big.jpg", data)
        dest = tmp_path / "out" / "big.jpg"
        copy_file(src, dest)
        assert dest.read_bytes() == data

    def test_mtime_preserved_after_copy(self, tmp_path):
        src = make_file(tmp_path / "photo.jpg", b"data")
        os.utime(src, (1_700_000_000.0, 1_700_000_000.0))
        dest = tmp_path / "out" / "photo.jpg"
        copy_file(src, dest)
        assert abs(dest.stat().st_mtime - 1_700_000_000.0) < 2


# ── preserve_timestamps ───────────────────────────────────────────────────────

class TestPreserveTimestamps:
    def test_mtime_copied_to_dest(self, tmp_path):
        src = make_file(tmp_path / "src.jpg", b"data")
        os.utime(src, (1_600_000_000.0, 1_600_000_000.0))
        dest = make_file(tmp_path / "dst.jpg", b"data")
        preserve_timestamps(dest, src)
        assert abs(dest.stat().st_mtime - 1_600_000_000.0) < 2

    def test_null_mtime_not_copied_to_dest(self, tmp_path):
        """A sentinel mtime from a camera with unset clock must not be stamped."""
        src = make_file(tmp_path / "src.jpg", b"data")
        dest = make_file(tmp_path / "dst.jpg", b"data")
        # Record dest mtime before the call (it's a real recent timestamp)
        dest_mtime_before = dest.stat().st_mtime

        stat_mock = MagicMock()
        stat_mock.st_mtime = _NULL_TS
        stat_mock.st_birthtime = _NULL_TS
        with patch("copier.Path.stat", return_value=stat_mock):
            preserve_timestamps(dest, src)

        # dest mtime must NOT have been overwritten with the null timestamp
        assert abs(dest.stat().st_mtime - _NULL_TS) > 60, (
            "null mtime was stamped onto the destination"
        )

    def test_valid_mtime_still_copied(self, tmp_path):
        """A real mtime must still be applied after the sentinel guard."""
        valid_ts = 1_700_000_000.0  # 2023-11-14
        src = make_file(tmp_path / "src.jpg", b"data")
        dest = make_file(tmp_path / "dst.jpg", b"data")
        os.utime(src, (valid_ts, valid_ts))
        preserve_timestamps(dest, src)
        assert abs(dest.stat().st_mtime - valid_ts) < 2

    @pytest.mark.skipif(
        platform.system() != "Darwin",
        reason="birthtime only available on macOS",
    )
    def test_birthtime_copied_on_macos(self, tmp_path):
        src = make_file(tmp_path / "src.jpg", b"data")
        dest = make_file(tmp_path / "dst.jpg", b"data")
        preserve_timestamps(dest, src)
        src_birth = src.stat().st_birthtime
        dst_birth = dest.stat().st_birthtime
        assert abs(dst_birth - src_birth) < 2

    @pytest.mark.skipif(
        platform.system() != "Darwin",
        reason="birthtime only settable on macOS",
    )
    def test_birthtime_pinned_to_mtime_when_source_birthtime_null(self, tmp_path):
        """If source birthtime is a sentinel, dest birthtime must be set to mtime
        so creation is never newer than modification date."""
        valid_ts = 1_700_000_000.0   # 2023-11-14
        src = make_file(tmp_path / "src.jpg", b"data")
        dest = make_file(tmp_path / "dst.jpg", b"data")

        stat_mock = MagicMock()
        stat_mock.st_mtime    = valid_ts
        stat_mock.st_birthtime = _NULL_TS   # sentinel birthtime

        with patch("copier.Path.stat", return_value=stat_mock):
            preserve_timestamps(dest, src)

        dest_stat = dest.stat()
        # mtime set correctly
        assert abs(dest_stat.st_mtime - valid_ts) < 2
        # birthtime must not be newer than mtime
        assert dest_stat.st_birthtime <= dest_stat.st_mtime + 1

    def test_explicit_date_taken_overrides_source_timestamps(self, tmp_path):
        from datetime import datetime
        src = make_file(tmp_path / "src.jpg", b"data")
        dest = make_file(tmp_path / "dst.jpg", b"data")
        
        # Source has a completely different timestamp
        os.utime(src, (1_600_000_000.0, 1_600_000_000.0))
        
        # We explicitly supply a date_taken
        dt_taken = datetime(2025, 1, 1, 12, 0, 0)
        preserve_timestamps(dest, src, date_taken=dt_taken)
        
        dest_stat = dest.stat()
        expected_ts = dt_taken.timestamp()
        
        assert abs(dest_stat.st_mtime - expected_ts) < 2
        
        if platform.system() == "Darwin":
            assert abs(dest_stat.st_birthtime - expected_ts) < 2
