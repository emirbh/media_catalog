"""Tests for categories.py — categorize_file and CATEGORY_MAP coverage."""
from pathlib import Path

import pytest

from categories import ALL_CATEGORIES, CATEGORY_MAP, CATEGORY_OTHERS, categorize_file


class TestCategoryMap:
    def test_all_values_are_known_categories(self):
        for ext, cat in CATEGORY_MAP.items():
            assert cat in ALL_CATEGORIES, f"{ext} maps to unknown category '{cat}'"

    def test_all_keys_start_with_dot(self):
        for ext in CATEGORY_MAP:
            assert ext.startswith("."), f"Extension key '{ext}' missing leading dot"

    def test_all_keys_are_lowercase(self):
        for ext in CATEGORY_MAP:
            assert ext == ext.lower(), f"Extension key '{ext}' is not lowercase"


class TestImages:
    @pytest.mark.parametrize("ext", [
        ".jpg", ".jpeg", ".heic", ".heif", ".tiff", ".tif",
        ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng",
        ".orf", ".rw2", ".pef", ".srw",
    ])
    def test_camera_formats(self, tmp_path, ext):
        assert categorize_file(tmp_path / f"photo{ext}") == "images"


class TestScreenshots:
    @pytest.mark.parametrize("ext", [".png", ".gif", ".bmp", ".webp", ".svg", ".ico"])
    def test_raster_formats(self, tmp_path, ext):
        assert categorize_file(tmp_path / f"capture{ext}") == "screenshots"


class TestVideos:
    @pytest.mark.parametrize("ext", [
        ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv",
        ".webm", ".mts", ".m2ts", ".3gp", ".ts", ".vob", ".ogv",
        # MPEG-1/2 variants
        ".mpg", ".mpeg", ".mpv", ".m2v", ".m2p", ".mpe",
    ])
    def test_video_formats(self, tmp_path, ext):
        assert categorize_file(tmp_path / f"clip{ext}") == "videos"


class TestMusicFiles:
    @pytest.mark.parametrize("ext", [
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
        ".wma", ".opus", ".aiff", ".aif", ".alac", ".ape",
    ])
    def test_audio_formats(self, tmp_path, ext):
        assert categorize_file(tmp_path / f"track{ext}") == "music-files"


class TestDocuments:
    @pytest.mark.parametrize("ext", [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".txt", ".rtf", ".csv", ".md",
        ".pages", ".numbers", ".key", ".epub", ".mobi",
    ])
    def test_document_formats(self, tmp_path, ext):
        assert categorize_file(tmp_path / f"file{ext}") == "documents"


class TestWebPages:
    @pytest.mark.parametrize("ext", [
        ".html", ".htm", ".mhtml", ".mht", ".xhtml", ".webloc", ".url",
    ])
    def test_web_formats(self, tmp_path, ext):
        assert categorize_file(tmp_path / f"page{ext}") == "web-pages"


class TestOthers:
    def test_unknown_extension_returns_others(self, tmp_path):
        assert categorize_file(tmp_path / "file.xyz") == CATEGORY_OTHERS

    def test_no_extension_returns_others(self, tmp_path):
        assert categorize_file(tmp_path / "README") == CATEGORY_OTHERS

    def test_exe_returns_others(self, tmp_path):
        assert categorize_file(tmp_path / "setup.exe") == CATEGORY_OTHERS

    def test_zip_returns_others(self, tmp_path):
        assert categorize_file(tmp_path / "archive.zip") == CATEGORY_OTHERS

    def test_py_returns_others(self, tmp_path):
        assert categorize_file(tmp_path / "script.py") == CATEGORY_OTHERS


class TestCaseInsensitivity:
    def test_uppercase_extension(self, tmp_path):
        assert categorize_file(tmp_path / "photo.JPG") == "images"
        assert categorize_file(tmp_path / "clip.MP4") == "videos"
        assert categorize_file(tmp_path / "song.MP3") == "music-files"

    def test_mixed_case_extension(self, tmp_path):
        assert categorize_file(tmp_path / "photo.Jpg") == "images"
        assert categorize_file(tmp_path / "doc.Pdf") == "documents"

    def test_all_caps_extension(self, tmp_path):
        assert categorize_file(tmp_path / "RAW.CR2") == "images"
