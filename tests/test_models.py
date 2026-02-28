"""Tests for models.py — FileRecord and ScanSummary."""
import pytest

from models import FileRecord, ScanSummary


class TestFileRecord:
    def test_to_dict_contains_all_fields(self, sample_record):
        d = sample_record.to_dict()
        assert d["hash"] == "abc123"
        assert d["original_path"] == "/src/photo.jpg"
        assert d["destination_path"] == "/tgt/images/2024/03/15/photo.jpg"
        assert d["media_type"] == "image"
        assert d["extension"] == ".jpg"
        assert d["date_taken"] == "2024-03-15"
        assert d["date_source"] == "exif"
        assert d["file_size_bytes"] == 1024
        assert d["cataloged_at"] == "2024-03-15T12:00:00"

    def test_from_dict_round_trips(self, sample_record):
        restored = FileRecord.from_dict(sample_record.to_dict())
        assert restored == sample_record

    def test_to_dict_is_plain_dict(self, sample_record):
        d = sample_record.to_dict()
        assert isinstance(d, dict)
        # All values must be JSON-primitive types
        for v in d.values():
            assert isinstance(v, (str, int, float, bool, type(None)))

    def test_from_dict_missing_key_raises(self):
        incomplete = {"hash": "abc", "original_path": "/src"}
        with pytest.raises(KeyError):
            FileRecord.from_dict(incomplete)

    def test_video_record(self):
        rec = FileRecord(
            hash="deadbeef",
            original_path="/src/clip.mp4",
            destination_path="/tgt/videos/2023/07/04/clip.mp4",
            media_type="video",
            extension=".mp4",
            date_taken="2023-07-04",
            date_source="mtime",
            file_size_bytes=52428800,
            cataloged_at="2023-07-04T08:00:00",
        )
        d = rec.to_dict()
        assert d["media_type"] == "video"
        assert FileRecord.from_dict(d).extension == ".mp4"


class TestScanSummary:
    def test_defaults_are_zero(self):
        s = ScanSummary(source_path="/mnt/drive")
        assert s.files_scanned == 0
        assert s.files_copied == 0
        assert s.files_skipped == 0
        assert s.files_errored == 0
        assert s.errors == []

    def test_source_path_stored(self):
        s = ScanSummary(source_path="/Volumes/SD")
        assert s.source_path == "/Volumes/SD"

    def test_errors_list_is_independent(self):
        """Each instance gets its own errors list (no shared mutable default)."""
        a = ScanSummary(source_path="/a")
        b = ScanSummary(source_path="/b")
        a.errors.append(("file.jpg", "oops"))
        assert b.errors == []

    def test_increment_counters(self):
        s = ScanSummary(source_path="/x")
        s.files_scanned += 5
        s.files_copied += 3
        s.files_skipped += 2
        assert s.files_scanned == 5
        assert s.files_copied == 3
        assert s.files_skipped == 2
