"""
Integration tests — end-to-end pipeline via process_source and the full
catalog machinery. No CLI parsing is exercised here; that is kept separate
to allow fast, isolated testing of the core logic.
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from catalog_store import CatalogStore
from catalog import process_source
from excludes import Excludes
from tests.conftest import make_file


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(
    src: Path,
    tgt: Path,
    *,
    excludes: Excludes = None,
    dry_run: bool = False,
    verbose: bool = False,
):
    """Run process_source with a fresh catalog and return (summary, store)."""
    catalog_path = tgt / "media_catalog.json"
    store = CatalogStore(catalog_path)
    summary = process_source(
        source_path=src,
        target_root=tgt,
        store=store,
        hash_algo="sha256",
        dry_run=dry_run,
        verbose=verbose,
        use_progress=False,
        excludes=excludes or Excludes([]),
    )
    return summary, store


def _image_files(tgt: Path) -> list[Path]:
    return sorted((tgt / "images").rglob("*") if (tgt / "images").exists() else [])


def _video_files(tgt: Path) -> list[Path]:
    return sorted((tgt / "videos").rglob("*") if (tgt / "videos").exists() else [])


# ── Basic copy ────────────────────────────────────────────────────────────────

class TestBasicCopy:
    def test_image_copied_to_images_subtree(self, src, tgt):
        make_file(src / "photo.jpg", b"jpg data")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 1
        assert summary.files_errored == 0
        images = list((tgt / "images").rglob("*.jpg"))
        assert len(images) == 1

    def test_video_copied_to_videos_subtree(self, src, tgt):
        make_file(src / "clip.mp4", b"mp4 data")
        _run(src, tgt)
        videos = list((tgt / "videos").rglob("*.mp4"))
        assert len(videos) == 1

    def test_mixed_media_split_correctly(self, src, tgt):
        make_file(src / "photo.jpg", b"img")
        make_file(src / "clip.mp4", b"vid")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 2
        assert len(list((tgt / "images").rglob("*.jpg"))) == 1
        assert len(list((tgt / "videos").rglob("*.mp4"))) == 1

    def test_date_based_directory_structure(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        tag_mock = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
        tag_mock.__str__ = lambda self: "2024:06:15 10:00:00"
        fake_tags = {"EXIF DateTimeOriginal": tag_mock}

        with patch("exif_reader._EXIFREAD_AVAILABLE", True), \
             patch("exif_reader.exifread.process_file", return_value=fake_tags):
            _run(src, tgt)

        # Verify YYYY/MM/DD folder structure under images/
        expected = tgt / "images" / "2024" / "06" / "15" / "photo.jpg"
        assert expected.exists()

    def test_non_media_files_not_copied(self, src, tgt):
        make_file(src / "photo.jpg", b"img")
        make_file(src / "notes.txt", b"text")
        make_file(src / "data.db", b"db")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 1
        assert summary.files_scanned == 1

    def test_file_content_intact_after_copy(self, src, tgt):
        payload = b"unique image payload " + bytes(range(256))
        make_file(src / "photo.jpg", payload)
        _run(src, tgt)
        copied = list((tgt / "images").rglob("*.jpg"))[0]
        assert copied.read_bytes() == payload

    def test_recursive_source_scan(self, src, tgt):
        make_file(src / "2024" / "03" / "photo.jpg", b"a")
        make_file(src / "2023" / "clip.mp4", b"b")
        make_file(src / "raw.cr2", b"c")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 3


# ── Duplicate detection ───────────────────────────────────────────────────────

class TestDuplicateDetection:
    def test_second_run_skips_all(self, src, tgt):
        make_file(src / "photo.jpg", b"same data")
        make_file(src / "clip.mp4", b"same video")

        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        # First run
        s1 = process_source(src, tgt, store=store, hash_algo="sha256",
                             dry_run=False, verbose=False, use_progress=False,
                             excludes=Excludes([]))
        store.save()
        assert s1.files_copied == 2

        # Second run — reload catalog
        store2 = CatalogStore(catalog_path)
        s2 = process_source(src, tgt, store=store2, hash_algo="sha256",
                             dry_run=False, verbose=False, use_progress=False,
                             excludes=Excludes([]))
        assert s2.files_copied == 0
        assert s2.files_skipped == 2

    def test_identical_file_in_two_sources_copied_once(self, tmp_path, tgt):
        data = b"duplicate content"
        src1 = tmp_path / "src1"
        src2 = tmp_path / "src2"
        src1.mkdir(); src2.mkdir()
        make_file(src1 / "photo.jpg", data)
        make_file(src2 / "photo.jpg", data)   # same content, same name

        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        s1 = process_source(src1, tgt, store=store, hash_algo="sha256",
                             dry_run=False, verbose=False, use_progress=False,
                             excludes=Excludes([]))
        s2 = process_source(src2, tgt, store=store, hash_algo="sha256",
                             dry_run=False, verbose=False, use_progress=False,
                             excludes=Excludes([]))

        assert s1.files_copied == 1
        assert s2.files_skipped == 1
        assert len(list((tgt / "images").rglob("*.jpg"))) == 1

    def test_same_name_different_content_both_copied(self, tmp_path, tgt):
        src1 = tmp_path / "src1"; src1.mkdir()
        src2 = tmp_path / "src2"; src2.mkdir()
        make_file(src1 / "photo.jpg", b"content A")
        make_file(src2 / "photo.jpg", b"content B")

        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        process_source(src1, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, use_progress=False,
                       excludes=Excludes([]))
        process_source(src2, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, use_progress=False,
                       excludes=Excludes([]))

        # Both copied; second one gets _2 suffix
        jpgs = list((tgt / "images").rglob("*.jpg"))
        assert len(jpgs) == 2

    def test_catalog_persists_across_instances(self, src, tgt):
        make_file(src / "photo.jpg", b"persist me")
        catalog_path = tgt / "media_catalog.json"

        store = CatalogStore(catalog_path)
        process_source(src, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, use_progress=False,
                       excludes=Excludes([]))
        store.save()

        # New store instance loaded from disk
        store2 = CatalogStore(catalog_path)
        s2 = process_source(src, tgt, store=store2, hash_algo="sha256",
                             dry_run=False, verbose=False, use_progress=False,
                             excludes=Excludes([]))
        assert s2.files_skipped == 1


# ── Dry run ───────────────────────────────────────────────────────────────────

class TestDryRun:
    def test_no_files_copied_in_dry_run(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        summary, store = _run(src, tgt, dry_run=True)
        assert summary.files_copied == 1    # counted as "would copy"
        assert not (tgt / "images").exists()

    def test_catalog_not_modified_in_dry_run(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        _, store = _run(src, tgt, dry_run=True)
        assert store.record_count() == 0

    def test_dry_run_counts_scanned(self, src, tgt):
        make_file(src / "a.jpg", b"1")
        make_file(src / "b.mp4", b"2")
        make_file(src / "c.txt", b"3")   # not media
        summary, _ = _run(src, tgt, dry_run=True)
        assert summary.files_scanned == 2


# ── Excludes ──────────────────────────────────────────────────────────────────

class TestExcludesIntegration:
    def test_excluded_directory_not_copied(self, src, tgt):
        make_file(src / "dqhelper" / "photo.jpg", b"skip me")
        make_file(src / "photos" / "keep.jpg", b"keep me")
        summary, _ = _run(src, tgt, excludes=Excludes(["dqhelper"]))
        assert summary.files_copied == 1
        assert summary.files_scanned == 1

    def test_excluded_extension_not_copied(self, src, tgt):
        make_file(src / "photo.jpg", b"keep")
        make_file(src / "raw.dng", b"skip")
        summary, _ = _run(src, tgt, excludes=Excludes(["*.dng"]))
        assert summary.files_copied == 1
        copied = list((tgt / "images").rglob("*.*"))
        assert all(f.suffix != ".dng" for f in copied)

    def test_no_excludes_copies_everything(self, src, tgt):
        make_file(src / "a.jpg", b"1")
        make_file(src / "b.dng", b"2")
        make_file(src / "c.mp4", b"3")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 3


# ── Summary counters ──────────────────────────────────────────────────────────

class TestSummaryCounters:
    def test_scanned_includes_all_media(self, src, tgt):
        make_file(src / "a.jpg", b"1")
        make_file(src / "b.mp4", b"2")
        summary, _ = _run(src, tgt)
        assert summary.files_scanned == 2

    def test_error_captured_not_raised(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        with patch("catalog.compute_hash", side_effect=OSError("disk error")):
            summary = process_source(src, tgt, store=store, hash_algo="sha256",
                                     dry_run=False, verbose=False, use_progress=False,
                                     excludes=Excludes([]))

        assert summary.files_errored == 1
        assert summary.files_copied == 0
        assert len(summary.errors) == 1
        assert "disk error" in summary.errors[0][1]

    def test_skipped_not_counted_as_copied(self, src, tgt):
        data = b"same"
        make_file(src / "photo.jpg", data)
        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        process_source(src, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, use_progress=False,
                       excludes=Excludes([]))
        store.save()

        store2 = CatalogStore(catalog_path)
        s2 = process_source(src, tgt, store=store2, hash_algo="sha256",
                             dry_run=False, verbose=False, use_progress=False,
                             excludes=Excludes([]))
        assert s2.files_skipped == 1
        assert s2.files_copied == 0
