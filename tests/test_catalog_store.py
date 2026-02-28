"""Tests for catalog_store.py — CatalogStore CRUD, persistence, corruption."""
import json
from pathlib import Path

import pytest

from catalog_store import CATALOG_FILENAME, CatalogStore
from models import FileRecord


def _make_record(hash_val: str = "abc123", media_type: str = "image") -> FileRecord:
    return FileRecord(
        hash=hash_val,
        original_path=f"/src/{hash_val}.jpg",
        destination_path=f"/tgt/images/2024/01/01/{hash_val}.jpg",
        media_type=media_type,
        extension=".jpg",
        date_taken="2024-01-01",
        date_source="exif",
        file_size_bytes=512,
        cataloged_at="2024-01-01T00:00:00",
    )


# ── Initialisation ────────────────────────────────────────────────────────────

class TestInit:
    def test_new_store_is_empty(self, tmp_path):
        store = CatalogStore(tmp_path / "catalog.json")
        assert store.record_count() == 0

    def test_catalog_path_for(self, tmp_path):
        assert CatalogStore.catalog_path_for(tmp_path) == tmp_path / CATALOG_FILENAME

    def test_loads_existing_catalog(self, tmp_path):
        path = tmp_path / "catalog.json"
        store = CatalogStore(path)
        store.add(_make_record("hash1"))
        store.save()

        # Re-open from disk
        store2 = CatalogStore(path)
        assert store2.record_count() == 1
        assert store2.contains("hash1")

    def test_corrupted_json_starts_fresh(self, tmp_path):
        path = tmp_path / "catalog.json"
        path.write_text("{ not valid json !!!", encoding="utf-8")
        store = CatalogStore(path)   # must not raise
        assert store.record_count() == 0

    def test_empty_json_object_starts_fresh(self, tmp_path):
        path = tmp_path / "catalog.json"
        path.write_text("{}", encoding="utf-8")
        store = CatalogStore(path)
        assert store.record_count() == 0


# ── contains / add / get ──────────────────────────────────────────────────────

class TestContainsAddGet:
    def test_contains_false_for_unknown(self, tmp_path):
        store = CatalogStore(tmp_path / "c.json")
        assert not store.contains("unknown_hash")

    def test_contains_true_after_add(self, tmp_path):
        store = CatalogStore(tmp_path / "c.json")
        store.add(_make_record("myhash"))
        assert store.contains("myhash")

    def test_get_returns_none_for_unknown(self, tmp_path):
        store = CatalogStore(tmp_path / "c.json")
        assert store.get("nobody") is None

    def test_get_returns_record_after_add(self, tmp_path):
        store = CatalogStore(tmp_path / "c.json")
        rec = _make_record("xyz")
        store.add(rec)
        fetched = store.get("xyz")
        assert fetched == rec

    def test_record_count_increments(self, tmp_path):
        store = CatalogStore(tmp_path / "c.json")
        store.add(_make_record("h1"))
        store.add(_make_record("h2"))
        store.add(_make_record("h3"))
        assert store.record_count() == 3

    def test_add_same_hash_overwrites(self, tmp_path):
        store = CatalogStore(tmp_path / "c.json")
        rec1 = _make_record("dup")
        rec2 = FileRecord(
            hash="dup",
            original_path="/other.jpg",
            destination_path="/tgt/other.jpg",
            media_type="image",
            extension=".jpg",
            date_taken="2025-06-01",
            date_source="mtime",
            file_size_bytes=999,
            cataloged_at="2025-06-01T00:00:00",
        )
        store.add(rec1)
        store.add(rec2)
        # Hash collision → second write wins; count stays 1
        assert store.record_count() == 1
        assert store.get("dup").date_taken == "2025-06-01"


# ── save / persistence ────────────────────────────────────────────────────────

class TestSave:
    def test_save_creates_file(self, tmp_path):
        path = tmp_path / "catalog.json"
        store = CatalogStore(path)
        store.add(_make_record())
        store.save()
        assert path.exists()

    def test_saved_file_is_valid_json(self, tmp_path):
        path = tmp_path / "catalog.json"
        store = CatalogStore(path)
        store.add(_make_record("h1"))
        store.save()
        data = json.loads(path.read_text())
        assert "entries" in data
        assert "version" in data
        assert "h1" in data["entries"]

    def test_save_and_reload_preserves_all_fields(self, tmp_path):
        path = tmp_path / "catalog.json"
        store = CatalogStore(path)
        rec = _make_record("full_test")
        store.add(rec)
        store.save()

        store2 = CatalogStore(path)
        assert store2.get("full_test") == rec

    def test_save_updates_updated_at(self, tmp_path):
        path = tmp_path / "catalog.json"
        store = CatalogStore(path)
        store.save()
        data1 = json.loads(path.read_text())

        import time; time.sleep(1.1)
        store.save()
        data2 = json.loads(path.read_text())

        assert data2["updated_at"] >= data1["updated_at"]

    def test_no_tmp_file_left_after_save(self, tmp_path):
        path = tmp_path / "catalog.json"
        store = CatalogStore(path)
        store.save()
        assert not (tmp_path / "catalog.tmp").exists()

    def test_multiple_records_persisted(self, tmp_path):
        path = tmp_path / "catalog.json"
        store = CatalogStore(path)
        for i in range(10):
            store.add(_make_record(f"hash_{i}"))
        store.save()

        store2 = CatalogStore(path)
        assert store2.record_count() == 10
        for i in range(10):
            assert store2.contains(f"hash_{i}")

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "catalog.json"
        store = CatalogStore(path)
        store.save()
        assert path.exists()
