"""Tests for exif_reader.py — date parsing, filesystem fallback, get_media_date."""
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from exif_reader import (
    _EXIF_CAPABLE,
    _is_null_timestamp,
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

    # ── Null / sentinel camera dates ──────────────────────────────────────────

    def test_apple_quicktime_null_date_rejected(self):
        """2000-12-31 is the Apple/iOS 'clock not set' sentinel in .MOV files."""
        assert _parse_exif_date("2000:12:31 00:00:00") is None

    def test_apple_null_date_with_nonzero_time_rejected(self):
        """Time component doesn't rescue a null date."""
        assert _parse_exif_date("2000:12:31 10:30:00") is None

    def test_cocoa_nsdate_epoch_rejected(self):
        """2001-01-01 is the Cocoa/NSDate reference epoch (iOS NSDate zero-value)."""
        assert _parse_exif_date("2001:01:01 00:00:00") is None

    def test_cocoa_nsdate_epoch_nonzero_time_rejected(self):
        """Time component doesn't rescue the NSDate epoch."""
        assert _parse_exif_date("2001:01:01 08:00:00") is None

    def test_unix_epoch_rejected(self):
        """1970-01-01 is the Unix epoch; appears on cameras with unset clocks."""
        assert _parse_exif_date("1970:01:01 00:00:00") is None

    def test_quicktime_epoch_rejected(self):
        """1904-01-01 is time_t=0 in 32-bit QuickTime."""
        assert _parse_exif_date("1904:01:01 00:00:00") is None

    def test_dos_fat_epoch_rejected(self):
        """1980-01-01 is the DOS/FAT epoch used by some cameras."""
        assert _parse_exif_date("1980:01:01 00:00:00") is None

    def test_valid_date_near_null_not_rejected(self):
        """2000-12-30 is a real date, not a sentinel."""
        dt = _parse_exif_date("2000:12:30 15:00:00")
        assert dt is not None
        assert dt.year == 2000

    def test_valid_date_after_nsdate_epoch_not_rejected(self):
        """2001-01-02 is a legitimate date, not a sentinel."""
        dt = _parse_exif_date("2001:01:02 09:00:00")
        assert dt is not None
        assert dt.year == 2001 and dt.month == 1 and dt.day == 2

    def test_valid_recent_date(self):
        dt = _parse_exif_date("2023:07:04 08:15:30")
        assert dt == datetime(2023, 7, 4, 8, 15, 30)


# ── _is_null_timestamp ───────────────────────────────────────────────────────

class TestIsNullTimestamp:
    def test_normal_timestamp_is_not_null(self):
        # 2023-06-15 12:00:00 UTC — well away from any sentinel
        assert not _is_null_timestamp(1_686_830_400.0)

    def test_zero_is_null(self):
        # Explicit zero is always null (pre-epoch)
        assert _is_null_timestamp(0.0)

    def test_negative_is_null(self):
        # Negative timestamps (pre-Unix-epoch) are always null
        assert _is_null_timestamp(-1.0)

    def test_apple_null_date_timestamp_is_null(self):
        # 2001-01-01 00:00:00 UTC → 978307200.
        # In any UTC offset -12..+12 this local date is 2000-12-31 or 2001-01-01,
        # both of which are in _NULL_DATES.
        import calendar
        ts = float(calendar.timegm((2001, 1, 1, 0, 0, 0, 0, 0, 0)))
        assert _is_null_timestamp(ts) is True

    def test_unix_epoch_noon_is_null(self):
        # 1970-01-01 12:00:00 UTC — still resolves to 1970-01-01 in any timezone
        import calendar
        ts = float(calendar.timegm((1970, 1, 1, 12, 0, 0, 0, 0, 0)))
        assert _is_null_timestamp(ts) is True


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

    def test_null_mtime_falls_back_to_import_time(self, tmp_path):
        """If every filesystem timestamp is a sentinel, return current time."""
        f = make_file(tmp_path / "photo.jpg")
        # 2001-01-01 00:00:00 UTC
        import calendar
        null_ts = float(calendar.timegm((2001, 1, 1, 0, 0, 0, 0, 0, 0)))
        stat_mock = MagicMock(spec=["st_birthtime", "st_ctime", "st_mtime"])
        del stat_mock.st_birthtime
        stat_mock.st_ctime = null_ts
        stat_mock.st_mtime = null_ts
        before = datetime.now()
        with patch.object(Path, "stat", return_value=stat_mock):
            dt, label = get_date_from_fs(f)
        after = datetime.now()
        assert label == "import_time"
        assert before <= dt <= after

    def test_null_birthtime_skipped_uses_mtime(self, tmp_path):
        """A null birthtime must be skipped; valid mtime should still be used."""
        f = make_file(tmp_path / "photo.jpg")
        import calendar
        null_ts  = float(calendar.timegm((2001, 1, 1, 0, 0, 0, 0, 0, 0)))
        valid_ts = 1_700_000_000.0  # 2023-11-14
        stat_mock = MagicMock()
        stat_mock.st_birthtime = null_ts
        stat_mock.st_ctime = valid_ts
        stat_mock.st_mtime = valid_ts
        with patch.object(Path, "stat", return_value=stat_mock):
            dt, label = get_date_from_fs(f)
        assert label in ("ctime", "mtime")
        assert abs(dt.timestamp() - valid_ts) < 2

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

    def test_oldest_valid_timestamp_is_chosen(self, tmp_path):
        """When multiple valid timestamps exist, the oldest one must be chosen."""
        f = make_file(tmp_path / "photo.jpg")
        stat_mock = MagicMock(spec=["st_birthtime", "st_ctime", "st_mtime"])
        # Set them in different orders to ensure it's not just checking one first
        stat_mock.st_birthtime = 1_700_000_200.0  # Newest
        stat_mock.st_ctime     = 1_700_000_100.0  # Middle
        stat_mock.st_mtime     = 1_700_000_000.0  # Oldest

        with patch("exif_reader.Path.stat", return_value=stat_mock):
            with patch("exif_reader.getattr", side_effect=lambda o, a, d=None: getattr(o, a, d)):
                _, label = get_date_from_fs(f)
        assert label == "mtime"

    def test_ctime_used_when_oldest(self, tmp_path):
        f = make_file(tmp_path / "photo.jpg")
        stat_mock = MagicMock(spec=["st_birthtime", "st_ctime", "st_mtime"])
        stat_mock.st_birthtime = 1_700_000_200.0  # Newest
        stat_mock.st_ctime     = 1_700_000_000.0  # Oldest
        stat_mock.st_mtime     = 1_700_000_100.0  # Middle
        
        with patch("exif_reader.Path.stat", return_value=stat_mock):
            with patch("exif_reader.getattr", side_effect=lambda o, a, d=None: getattr(o, a, d)):
                _, label = get_date_from_fs(f)
        assert label == "ctime"
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

    # ── EXIF-capable whitelist ─────────────────────────────────────────────────

    @pytest.mark.parametrize("ext", [".mpg", ".mpeg", ".mpv", ".m2v", ".avi",
                                      ".mkv", ".wmv", ".flv", ".webm"])
    def test_non_exif_capable_skips_exifread(self, tmp_path, ext):
        """Extensions not in _EXIF_CAPABLE must never call exifread."""
        f = make_file(tmp_path / f"clip{ext}", b"fake content")
        with patch("exif_reader._EXIFREAD_AVAILABLE", True), \
             patch("exif_reader.exifread.process_file") as mock_proc:
            dt, source = get_date_from_exif(f)
        mock_proc.assert_not_called()
        assert dt is None
        assert source == ""

    def test_exif_capable_set_includes_jpg(self):
        assert ".jpg" in _EXIF_CAPABLE

    def test_exif_capable_set_includes_mov(self):
        assert ".mov" in _EXIF_CAPABLE

    def test_exif_capable_set_excludes_mpg(self):
        assert ".mpg" not in _EXIF_CAPABLE

    def test_exif_capable_set_excludes_mpeg(self):
        assert ".mpeg" not in _EXIF_CAPABLE


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

    @pytest.mark.parametrize("ext", [".mpg", ".mpeg", ".mpv", ".m2v"])
    def test_mpg_uses_filesystem_date(self, tmp_path, ext):
        """MPEG streams have no EXIF — must fall back to filesystem timestamps."""
        f = make_file(tmp_path / f"movie{ext}", b"fake mpeg stream")
        with patch("exif_reader._EXIFREAD_AVAILABLE", True), \
             patch("exif_reader.exifread.process_file") as mock_proc:
            dt, source = get_media_date(f)
        mock_proc.assert_not_called()
        assert isinstance(dt, datetime)
        assert source in ("birthtime", "ctime", "mtime")
