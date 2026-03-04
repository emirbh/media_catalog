"""Tests for models.py — FileRecord and ScanSummary."""
import pytest

from models import FileRecord, ScanSummary


class TestFileRecord:
    def test_to_dict_contains_all_fields(self, sample_record):
        d = sample_record.to_dict()
        assert d["hash"] == "abc123"
        assert d["source_locations"] == ["/src/photo.jpg"]
        assert d["destination_path"] == "/tgt/images/photo.jpg"
        assert d["category"] == "images"
        assert d["extension"] == ".jpg"
        assert d["date_taken"] == "2024-03-15"
        assert d["date_source"] == "exif"
        assert d["file_size_bytes"] == 1024
        assert d["cataloged_at"] == "2024-03-15T12:00:00"

    def test_source_locations_is_list(self, sample_record):
        d = sample_record.to_dict()
        assert isinstance(d["source_locations"], list)

    def test_from_dict_round_trips(self, sample_record):
        restored = FileRecord.from_dict(sample_record.to_dict())
        assert restored == sample_record

    def test_to_dict_is_plain_dict(self, sample_record):
        d = sample_record.to_dict()
        assert isinstance(d, dict)
        for k, v in d.items():
            if k == "source_locations":
                assert isinstance(v, list)
            else:
                assert isinstance(v, (str, int, float, bool, type(None)))

    def test_from_dict_missing_key_raises(self):
        incomplete = {"hash": "abc", "source_locations": ["/src"]}
        with pytest.raises(KeyError):
            FileRecord.from_dict(incomplete)

    # ── Backward compatibility ────────────────────────────────────────────────

    def test_backward_compat_original_path_key(self):
        """Old catalogs stored a single 'original_path' string."""
        old_dict = {
            "hash": "old",
            "original_path": "/src/photo.jpg",       # old single-string key
            "destination_path": "/tgt/images/photo.jpg",
            "category": "images",
            "extension": ".jpg",
            "date_taken": "2024-03-15",
            "date_source": "exif",
            "file_size_bytes": 512,
            "cataloged_at": "2024-03-15T00:00:00",
        }
        rec = FileRecord.from_dict(old_dict)
        assert rec.source_locations == ["/src/photo.jpg"]

    def test_backward_compat_media_type_key(self):
        """Old catalogs stored 'media_type' instead of 'category'."""
        old_dict = {
            "hash": "old",
            "original_path": "/src/photo.jpg",
            "destination_path": "/tgt/images/photo.jpg",
            "media_type": "image",
            "extension": ".jpg",
            "date_taken": "2024-03-15",
            "date_source": "exif",
            "file_size_bytes": 512,
            "cataloged_at": "2024-03-15T00:00:00",
        }
        rec = FileRecord.from_dict(old_dict)
        assert rec.category == "image"

    def test_category_key_preferred_over_media_type(self):
        d = {
            "hash": "x",
            "source_locations": ["/src/photo.jpg"],
            "destination_path": "/tgt/images/photo.jpg",
            "category": "images",
            "media_type": "image",   # both present → category wins
            "extension": ".jpg",
            "date_taken": "2024-03-15",
            "date_source": "exif",
            "file_size_bytes": 512,
            "cataloged_at": "2024-03-15T00:00:00",
        }
        rec = FileRecord.from_dict(d)
        assert rec.category == "images"

    def test_multiple_source_locations(self):
        rec = FileRecord(
            hash="multi",
            source_locations=["/drive1/photo.jpg", "/drive2/photo.jpg"],
            destination_path="/tgt/images/photo.jpg",
            category="images",
            extension=".jpg",
            date_taken="2024-01-01",
            date_source="exif",
            file_size_bytes=1024,
            cataloged_at="2024-01-01T00:00:00",
        )
        d = rec.to_dict()
        assert len(d["source_locations"]) == 2
        assert FileRecord.from_dict(d).source_locations == ["/drive1/photo.jpg", "/drive2/photo.jpg"]

    def test_video_record(self):
        rec = FileRecord(
            hash="deadbeef",
            source_locations=["/src/clip.mp4"],
            destination_path="/tgt/videos/clip.mp4",
            category="videos",
            extension=".mp4",
            date_taken="2023-07-04",
            date_source="mtime",
            file_size_bytes=52428800,
            cataloged_at="2023-07-04T08:00:00",
        )
        d = rec.to_dict()
        assert d["category"] == "videos"
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
