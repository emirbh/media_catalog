"""Tests for scanner.py — classify_file, scan_directory, count_media_files."""
from pathlib import Path

import pytest

from excludes import Excludes
from scanner import classify_file, count_media_files, scan_directory
from tests.conftest import make_file


# ── classify_file ─────────────────────────────────────────────────────────────

class TestClassifyFile:
    @pytest.mark.parametrize("ext", [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".heic", ".heif", ".webp", ".raw", ".cr2", ".nef", ".arw", ".dng",
    ])
    def test_image_extensions(self, tmp_path, ext):
        assert classify_file(tmp_path / f"photo{ext}") == "image"

    @pytest.mark.parametrize("ext", [
        ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv",
        ".flv", ".webm", ".mts", ".m2ts", ".3gp",
    ])
    def test_video_extensions(self, tmp_path, ext):
        assert classify_file(tmp_path / f"clip{ext}") == "video"

    def test_unknown_extension_returns_none(self, tmp_path):
        assert classify_file(tmp_path / "doc.pdf") is None
        assert classify_file(tmp_path / "data.db") is None
        assert classify_file(tmp_path / "script.py") is None

    def test_case_insensitive(self, tmp_path):
        assert classify_file(tmp_path / "photo.JPG") == "image"
        assert classify_file(tmp_path / "clip.MP4") == "video"
        assert classify_file(tmp_path / "photo.Jpg") == "image"

    def test_no_extension(self, tmp_path):
        assert classify_file(tmp_path / "README") is None


# ── scan_directory ─────────────────────────────────────────────────────────────

class TestScanDirectory:
    def test_yields_images(self, src):
        make_file(src / "photo.jpg")
        make_file(src / "raw.cr2")
        results = list(scan_directory(src))
        paths = [p for p, _ in results]
        types = [t for _, t in results]
        assert src / "photo.jpg" in paths
        assert src / "raw.cr2" in paths
        assert all(t == "image" for t in types)

    def test_yields_videos(self, src):
        make_file(src / "clip.mp4")
        make_file(src / "movie.mov")
        results = list(scan_directory(src))
        types = {t for _, t in results}
        assert types == {"video"}

    def test_yields_mixed_media(self, src):
        make_file(src / "photo.jpg")
        make_file(src / "clip.mp4")
        results = list(scan_directory(src))
        assert len(results) == 2
        assert {t for _, t in results} == {"image", "video"}

    def test_ignores_non_media_files(self, src):
        make_file(src / "photo.jpg")
        make_file(src / "notes.txt")
        make_file(src / "data.db")
        results = list(scan_directory(src))
        assert len(results) == 1

    def test_recurses_into_subdirectories(self, src):
        make_file(src / "2024" / "03" / "photo.jpg")
        make_file(src / "2023" / "clip.mp4")
        results = list(scan_directory(src))
        assert len(results) == 2

    def test_skips_hidden_files(self, src):
        make_file(src / ".hidden.jpg")
        results = list(scan_directory(src))
        assert results == []

    def test_skips_hidden_directories(self, src):
        make_file(src / ".Spotlight-V100" / "photo.jpg")
        make_file(src / ".DS_Store_dir" / "clip.mp4")
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
        make_file(src / "thumb.db")   # db is not a media ext, already skipped
        make_file(src / "raw.dng")
        ex = Excludes(["*.dng"])
        results = list(scan_directory(src, excludes=ex))
        assert len(results) == 1
        assert results[0][0].suffix == ".jpg"

    def test_no_excludes_yields_all(self, src):
        make_file(src / "a.jpg")
        make_file(src / "b.mp4")
        make_file(src / "c.cr2")
        assert len(list(scan_directory(src))) == 3


# ── count_media_files ─────────────────────────────────────────────────────────

class TestCountMediaFiles:
    def test_counts_correctly(self, src):
        make_file(src / "a.jpg")
        make_file(src / "b.mp4")
        make_file(src / "c.txt")   # not counted
        assert count_media_files(src) == 2

    def test_empty_directory(self, src):
        assert count_media_files(src) == 0

    def test_respects_excludes(self, src):
        make_file(src / "a.jpg")
        make_file(src / "skip" / "b.jpg")
        ex = Excludes(["skip"])
        assert count_media_files(src, excludes=ex) == 1
