"""Tests for manage_catalog.py — find, move-to-archive."""
import shutil
from pathlib import Path

import pytest

from catalog_store import CatalogStore
from manage_catalog import MoveSummary, find_by_source_dir, move_to_archive
from models import FileRecord
from tests.conftest import make_file


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_record(
    hash_val: str,
    source_locations: list,
    dest: str,
    category: str = "images",
) -> FileRecord:
    return FileRecord(
        hash=hash_val,
        source_locations=source_locations,
        destination_path=dest,
        category=category,
        extension=".jpg",
        date_taken="2024-06-01",
        date_source="exif",
        file_size_bytes=1024,
        cataloged_at="2024-06-01T00:00:00",
    )


def _load_store(catalog_root: Path) -> CatalogStore:
    return CatalogStore(CatalogStore.catalog_path_for(catalog_root))


# ── find_by_source_dir ────────────────────────────────────────────────────────

class TestFindBySourceDir:
    def test_finds_matching_record(self, tmp_path):
        store = _load_store(tmp_path)
        rec = _make_record(
            "abc", ["/Volumes/SD1/dqhelper/photo.jpg"], f"{tmp_path}/images/photo.jpg"
        )
        store.add(rec)
        results = find_by_source_dir(store, "dqhelper")
        assert len(results) == 1
        assert results[0].hash == "abc"

    def test_does_not_match_substring(self, tmp_path):
        """'notdqhelper' dir must NOT match a search for 'dqhelper'."""
        store = _load_store(tmp_path)
        rec = _make_record(
            "abc", ["/Volumes/SD1/notdqhelper/photo.jpg"], f"{tmp_path}/images/photo.jpg"
        )
        store.add(rec)
        assert find_by_source_dir(store, "dqhelper") == []

    def test_matches_any_source_location(self, tmp_path):
        """Record matches if ANY of its source_locations contains the dir."""
        store = _load_store(tmp_path)
        rec = _make_record(
            "abc",
            ["/Volumes/SD1/photos/photo.jpg", "/Volumes/SD2/dqhelper/photo.jpg"],
            f"{tmp_path}/images/photo.jpg",
        )
        store.add(rec)
        assert len(find_by_source_dir(store, "dqhelper")) == 1

    def test_returns_empty_when_no_match(self, tmp_path):
        store = _load_store(tmp_path)
        rec = _make_record("abc", ["/Volumes/SD1/photos/photo.jpg"], f"{tmp_path}/images/photo.jpg")
        store.add(rec)
        assert find_by_source_dir(store, "dqhelper") == []

    def test_returns_empty_on_empty_catalog(self, tmp_path):
        store = _load_store(tmp_path)
        assert find_by_source_dir(store, "dqhelper") == []

    def test_returns_multiple_matches(self, tmp_path):
        store = _load_store(tmp_path)
        for i in range(3):
            store.add(_make_record(
                f"hash{i}",
                [f"/Volumes/SD1/dqhelper/photo{i}.jpg"],
                f"{tmp_path}/images/photo{i}.jpg",
            ))
        store.add(_make_record("other", ["/Volumes/SD1/photos/x.jpg"], f"{tmp_path}/images/x.jpg"))
        results = find_by_source_dir(store, "dqhelper")
        assert len(results) == 3

    def test_nested_dir_matches(self, tmp_path):
        """dqhelper can appear anywhere in the path."""
        store = _load_store(tmp_path)
        rec = _make_record(
            "abc", ["/Volumes/SD1/DCIM/dqhelper/sub/photo.jpg"], f"{tmp_path}/images/photo.jpg"
        )
        store.add(rec)
        assert len(find_by_source_dir(store, "dqhelper")) == 1


# ── move_to_archive ───────────────────────────────────────────────────────────

class TestMoveToArchive:
    def _setup(self, tmp_path):
        """Create source + archive roots and a populated source catalog."""
        src_root = tmp_path / "source"
        arc_root = tmp_path / "archive"
        src_root.mkdir()

        src_store  = _load_store(src_root)
        arc_store  = _load_store(arc_root)
        return src_root, arc_root, src_store, arc_store

    def test_file_moved_to_archive(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)

        # Create the actual file in source
        src_file = make_file(src_root / "images" / "photo.jpg", b"data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        assert not src_file.exists()
        assert (arc_root / "images" / "photo.jpg").exists()

    def test_source_catalog_entry_removed(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        src_file = make_file(src_root / "images" / "photo.jpg", b"data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        reloaded = _load_store(src_root)
        assert not reloaded.contains("abc")

    def test_archive_catalog_entry_added(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        src_file = make_file(src_root / "images" / "photo.jpg", b"data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        reloaded = _load_store(arc_root)
        assert reloaded.contains("abc")

    def test_archive_destination_path_updated(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        src_file = make_file(src_root / "images" / "photo.jpg", b"data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        arc_rec = _load_store(arc_root).get("abc")
        assert arc_rec.destination_path == str(arc_root / "images" / "photo.jpg")

    def test_source_locations_preserved(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        src_file = make_file(src_root / "images" / "photo.jpg", b"data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg", "/SD2/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        arc_rec = _load_store(arc_root).get("abc")
        assert "/SD/dqhelper/photo.jpg" in arc_rec.source_locations
        assert "/SD2/dqhelper/photo.jpg" in arc_rec.source_locations

    def test_dry_run_does_not_move_file(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        src_file = make_file(src_root / "images" / "photo.jpg", b"data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store, dry_run=True)

        assert src_file.exists()
        assert not (arc_root / "images" / "photo.jpg").exists()

    def test_dry_run_does_not_modify_catalogs(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        src_file = make_file(src_root / "images" / "photo.jpg", b"data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)
        src_store.save()

        move_to_archive([rec], src_root, src_store, arc_root, arc_store, dry_run=True)

        # Source catalog still has the entry after dry-run
        assert _load_store(src_root).contains("abc")
        # Archive catalog was never created
        assert not CatalogStore.catalog_path_for(arc_root).exists()

    def test_missing_file_still_transfers_catalog_entry(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        # Record points to a file that doesn't exist on disk
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"],
                           str(src_root / "images" / "ghost.jpg"))
        src_store.add(rec)

        summary = move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        assert summary.file_missing == 1
        assert not _load_store(src_root).contains("abc")
        assert _load_store(arc_root).contains("abc")

    def test_collision_resolved_in_archive(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)

        # Pre-existing file in archive with same name
        make_file(arc_root / "images" / "photo.jpg", b"existing")

        src_file = make_file(src_root / "images" / "photo.jpg", b"new data")
        rec = _make_record("abc", ["/SD/dqhelper/photo.jpg"], str(src_file))
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        # Original archive file untouched, new file gets _2 suffix
        assert (arc_root / "images" / "photo.jpg").read_bytes() == b"existing"
        assert (arc_root / "images" / "photo_2.jpg").read_bytes() == b"new data"

    def test_summary_counts(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        f1 = make_file(src_root / "images" / "a.jpg", b"a")
        f2 = make_file(src_root / "images" / "b.jpg", b"b")
        r1 = _make_record("h1", ["/SD/dqhelper/a.jpg"], str(f1))
        r2 = _make_record("h2", ["/SD/dqhelper/b.jpg"], str(f2))
        src_store.add(r1); src_store.add(r2)

        summary = move_to_archive([r1, r2], src_root, src_store, arc_root, arc_store)

        assert summary.matched == 2
        assert summary.moved == 2
        assert summary.errored == 0

    def test_category_subdirectory_created_in_archive(self, tmp_path):
        src_root, arc_root, src_store, arc_store = self._setup(tmp_path)
        src_file = make_file(src_root / "videos" / "clip.mp4", b"video")
        rec = _make_record("abc", ["/SD/dqhelper/clip.mp4"], str(src_file), category="videos")
        src_store.add(rec)

        move_to_archive([rec], src_root, src_store, arc_root, arc_store)

        assert (arc_root / "videos" / "clip.mp4").exists()
