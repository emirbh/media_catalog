"""Tests for exif_reader.py — date parsing, filesystem fallback, get_media_date."""
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from exif_reader import (
    _parse_exif_date,
    get_date_from_exif,
    get_date_from_fs,
    get_media_date,
)
from tests.conftest import make_file


# ── _parse_exif_date ──────────────────────────────────────────────────────────

class TestParseExifDate:
    def test_valid_date_string(self):
        dt = _parse_exif_date("2024:03:15 10:30:00")
        assert dt == datetime(2024, 3, 15, 10, 30, 0)

    def test_strips_whitespace(self):
        dt = _parse_exif_date("  2024:03:15 10:30:00  ")
        assert dt is not None
        assert dt.year == 2024

    def test_zeroed_year_returns_none(self):
        assert _parse_exif_date("0000:00:00 00:00:00") is None

    def test_year_before_1970_returns_none(self):
        assert _parse_exif_date("1969:12:31 23:59:59") is None

    def test_invalid_format_returns_none(self):
        assert _parse_exif_date("not-a-date") is None
        assert _parse_exif_date("2024/03/15") is None
        assert _parse_exif_date("") is None

    def test_zero_month_returns_none(self):
        assert _parse_exif_date("2024:00:15 10:00:00") is None

    def test_zero_day_returns_none(self):
        assert _parse_exif_date("2024:03:00 10:00:00") is None

    def test_valid_recent_date(self):
        dt = _parse_exif_date("2023:07:04 08:15:30")
        assert dt == datetime(2023, 7, 4, 8, 15, 30)


# ── get_date_from_fs ──────────────────────────────────────────────────────────

class TestGetDateFromFs:
    def test_returns_datetime_and_label(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg")
        dt, label = get_date_from_fs(f)
        assert isinstance(dt, datetime)
        assert label in ("birthtime", "ctime", "mtime")

    def test_datetime_is_recent(self, tmp_path):
        before = datetime.now()
        f = make_file(tmp_path / "photo.jpg")
        dt, _ = get_date_from_fs(f)
        after = datetime.now()
        assert before <= dt <= after

    def test_birthtime_preferred_on_macos(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg")
        stat = f.stat()
        if hasattr(stat, "st_birthtime"):
            _, label = get_date_from_fs(f)
            assert label == "birthtime"
        else:
            pytest.skip("st_birthtime not available on this platform")

    def test_ctime_used_when_no_birthtime(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg")
        stat_mock = MagicMock()
        stat_mock.st_birthtime = None   # simulate no birthtime
        stat_mock.st_ctime = 1_700_000_000.0
        stat_mock.st_mtime = 1_700_000_100.0  # mtime > ctime
        with patch.object(Path, "stat", return_value=stat_mock):
            _, label = get_date_from_fs(f)
        assert label == "ctime"

    def test_mtime_used_when_ctime_greater(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg")
        stat_mock = MagicMock(spec=[
            "st_birthtime", "st_ctime", "st_mtime",
        ])
        del stat_mock.st_birthtime        # AttributeError → getattr returns None
        stat_mock.st_ctime = 1_700_000_200.0  # ctime > mtime → use mtime
        stat_mock.st_mtime = 1_700_000_100.0
        with patch("exif_reader.Path.stat", return_value=stat_mock):
            with patch("exif_reader.getattr", side_effect=lambda o, a, d=None: d):
                _, label = get_date_from_fs(f)
        # On platforms without birthtime and where ctime > mtime, mtime is used
        assert label in ("ctime", "mtime")


# ── get_date_from_exif ────────────────────────────────────────────────────────

class TestGetDateFromExif:
    def test_returns_none_for_non_image(self, tmp_path):
        f = make_file(tmp_path / "data.bin", b"not an image")
        dt, source = get_date_from_exif(f)
        # Either no EXIF found (None, "") or exifread not installed
        assert dt is None

    def test_returns_exif_date_when_available(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg", b"fake jpeg")
        tag_mock = MagicMock()
        tag_mock.__str__ = lambda self: "2024:06:01 14:00:00"
        fake_tags = {"EXIF DateTimeOriginal": tag_mock}

        with patch("exif_reader._EXIFREAD_AVAILABLE", True), \
             patch("exif_reader.exifread.process_file", return_value=fake_tags):
            dt, source = get_date_from_exif(f)

        assert dt == datetime(2024, 6, 1, 14, 0, 0)
        assert source == "exif"

    def test_falls_through_to_second_tag(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg", b"fake jpeg")
        tag_mock = MagicMock()
        tag_mock.__str__ = lambda self: "2023:11:11 09:00:00"
        # Only DateTimeDigitized is present
        fake_tags = {"EXIF DateTimeDigitized": tag_mock}

        with patch("exif_reader._EXIFREAD_AVAILABLE", True), \
             patch("exif_reader.exifread.process_file", return_value=fake_tags):
            dt, source = get_date_from_exif(f)

        assert dt == datetime(2023, 11, 11, 9, 0, 0)
        assert source == "exif"

    def test_returns_none_when_exifread_unavailable(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg")
        with patch("exif_reader._EXIFREAD_AVAILABLE", False):
            dt, source = get_date_from_exif(f)
        assert dt is None
        assert source == ""

    def test_exception_in_exifread_returns_none(self, tmp_path):
        f = make_file(tmp_path / "corrupt.jpg", b"garbage")
        with patch("exif_reader._EXIFREAD_AVAILABLE", True), \
             patch("exif_reader.exifread.process_file", side_effect=Exception("boom")):
            dt, source = get_date_from_exif(f)
        assert dt is None


# ── get_media_date ────────────────────────────────────────────────────────────

class TestGetMediaDate:
    def test_falls_back_to_fs_when_no_exif(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg", b"no exif here")
        dt, source = get_media_date(f)
        assert isinstance(dt, datetime)
        assert source in ("birthtime", "ctime", "mtime")

    def test_prefers_exif_over_fs(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg")
        tag_mock = MagicMock()
        tag_mock.__str__ = lambda self: "2020:01:01 00:00:00"
        fake_tags = {"EXIF DateTimeOriginal": tag_mock}

        with patch("exif_reader._EXIFREAD_AVAILABLE", True), \
             patch("exif_reader.exifread.process_file", return_value=fake_tags):
            dt, source = get_media_date(f)

        assert dt == datetime(2020, 1, 1)
        assert source == "exif"

    def test_always_returns_valid_datetime(self, tmp_path):
        f = make_file(tmp_path / "video.mp4", b"fake")
        dt, source = get_media_date(f)
        assert dt is not None
        assert isinstance(dt, datetime)
        assert source != ""
