"""Tests for scanner.py — scan_directory, count_files."""
from pathlib import Path

import pytest

from categories import CATEGORY_OTHERS
from excludes import Excludes
from scanner import count_files, scan_directory
from tests.conftest import make_file


# ── scan_directory ────────────────────────────────────────────────────────────

class TestScanDirectory:
    def test_yields_images_with_correct_category(self, src):
        make_file(src / "photo.jpg")
        make_file(src / "raw.cr2")
        results = dict(scan_directory(src))
        assert results[src / "photo.jpg"] == "images"
        assert results[src / "raw.cr2"] == "images"

    def test_yields_videos_with_correct_category(self, src):
        make_file(src / "clip.mp4")
        results = dict(scan_directory(src))
        assert results[src / "clip.mp4"] == "videos"

    def test_yields_documents(self, src):
        make_file(src / "report.pdf")
        results = dict(scan_directory(src))
        assert results[src / "report.pdf"] == "documents"

    def test_yields_screenshots(self, src):
        make_file(src / "capture.png")
        results = dict(scan_directory(src))
        assert results[src / "capture.png"] == "screenshots"

    def test_yields_music_files(self, src):
        make_file(src / "track.mp3")
        results = dict(scan_directory(src))
        assert results[src / "track.mp3"] == "music-files"

    def test_yields_web_pages(self, src):
        make_file(src / "index.html")
        results = dict(scan_directory(src))
        assert results[src / "index.html"] == "web-pages"

    def test_yields_others_for_unknown_extension(self, src):
        make_file(src / "mystery.xyz")
        results = dict(scan_directory(src))
        assert results[src / "mystery.xyz"] == CATEGORY_OTHERS

    def test_yields_all_file_types(self, src):
        make_file(src / "photo.jpg")
        make_file(src / "clip.mp4")
        make_file(src / "report.pdf")
        make_file(src / "song.mp3")
        make_file(src / "page.html")
        make_file(src / "weird.xyz")
        results = list(scan_directory(src))
        assert len(results) == 6

    def test_recurses_into_subdirectories(self, src):
        make_file(src / "2024" / "03" / "photo.jpg")
        make_file(src / "archive" / "clip.mp4")
        results = list(scan_directory(src))
        assert len(results) == 2

    def test_skips_hidden_files(self, src):
        make_file(src / ".hidden.jpg")
        results = list(scan_directory(src))
        assert results == []

    def test_skips_hidden_directories(self, src):
        make_file(src / ".Spotlight-V100" / "photo.jpg")
        results = list(scan_directory(src))
        assert results == []

    def test_skips_zero_byte_files(self, src):
        make_file(src / "empty.jpg", b"")
        results = list(scan_directory(src))
        assert results == []

    def test_skips_catalog_json(self, src):
        make_file(src / "media_catalog.json", b"{}")
        results = list(scan_directory(src))
        assert results == []

    def test_skips_symlinks(self, src, tmp_path):
        real = make_file(tmp_path / "real.jpg")
        link = src / "link.jpg"
        link.symlink_to(real)
        results = list(scan_directory(src))
        assert results == []

    def test_empty_directory(self, src):
        assert list(scan_directory(src)) == []

    def test_skips_file_deleted_during_scan(self, src):
        from unittest.mock import patch
        f = make_file(src / "photo.jpg")
        
        # Simulate the file being deleted right before stat() is called for size validation
        original_stat = Path.stat
        call_count = 0
        def mock_stat(self, **kwargs):
            nonlocal call_count
            if self == f:
                call_count += 1
                # Fail on the 4th stat() call, which corresponds to file_path.stat().st_size
                # is_dir() -> is_file() -> is_symlink() -> stat().st_size
                if call_count >= 4:
                    raise FileNotFoundError(f"No such file or directory: '{self}'")
            return original_stat(self, **kwargs)
            
        with patch.object(Path, "stat", mock_stat):
            results = list(scan_directory(src))
        assert results == []

    def test_exclude_directory_by_name(self, src):
        make_file(src / "dqhelper" / "photo.jpg")
        make_file(src / "photos" / "other.jpg")
        ex = Excludes(["dqhelper"])
        results = list(scan_directory(src, excludes=ex))
        assert len(results) == 1
        assert results[0][0] == src / "photos" / "other.jpg"

    def test_exclude_nested_directory(self, src):
        make_file(src / "DCIM" / "PRIVATE" / "secret.jpg")
        make_file(src / "DCIM" / "100MEDIA" / "photo.jpg")
        ex = Excludes(["PRIVATE/"])
        results = list(scan_directory(src, excludes=ex))
        assert len(results) == 1
        assert "PRIVATE" not in str(results[0][0])

    def test_exclude_file_extension(self, src):
        make_file(src / "photo.jpg")
        make_file(src / "raw.dng")
        ex = Excludes(["*.dng"])
        results = list(scan_directory(src, excludes=ex))
        assert len(results) == 1
        assert results[0][0].suffix == ".jpg"

    def test_no_excludes_yields_all(self, src):
        make_file(src / "a.jpg")
        make_file(src / "b.mp4")
        make_file(src / "c.pdf")
        assert len(list(scan_directory(src))) == 3


# ── count_files ────────────────────────────────────────────────────────────────

class TestCountFiles:
    def test_counts_all_file_types(self, src):
        make_file(src / "a.jpg")
        make_file(src / "b.mp4")
        make_file(src / "c.txt")
        make_file(src / "d.xyz")
        assert count_files(src) == 4

    def test_empty_directory(self, src):
        assert count_files(src) == 0

    def test_respects_excludes(self, src):
        make_file(src / "a.jpg")
        make_file(src / "skip" / "b.jpg")
        ex = Excludes(["skip"])
        assert count_files(src, excludes=ex) == 1
