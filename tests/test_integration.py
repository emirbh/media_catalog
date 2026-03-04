"""
Integration tests — end-to-end pipeline via process_source and the full
catalog machinery.  No CLI parsing is exercised here.
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from catalog import process_source
from catalog_store import CatalogStore
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
        excludes=excludes or Excludes([]),
    )
    return summary, store


# ── Basic copy — flat category structure ──────────────────────────────────────

class TestBasicCopy:
    def test_image_goes_to_images_folder(self, src, tgt):
        make_file(src / "photo.jpg", b"jpg data")
        _run(src, tgt)
        assert (tgt / "images" / "photo.jpg").exists()

    def test_video_goes_to_videos_folder(self, src, tgt):
        make_file(src / "clip.mp4", b"mp4 data")
        _run(src, tgt)
        assert (tgt / "videos" / "clip.mp4").exists()

    def test_document_goes_to_documents_folder(self, src, tgt):
        make_file(src / "report.pdf", b"pdf data")
        _run(src, tgt)
        assert (tgt / "documents" / "report.pdf").exists()

    def test_screenshot_goes_to_screenshots_folder(self, src, tgt):
        make_file(src / "capture.png", b"png data")
        _run(src, tgt)
        assert (tgt / "screenshots" / "capture.png").exists()

    def test_audio_goes_to_music_files_folder(self, src, tgt):
        make_file(src / "song.mp3", b"mp3 data")
        _run(src, tgt)
        assert (tgt / "music-files" / "song.mp3").exists()

    def test_html_goes_to_web_pages_folder(self, src, tgt):
        make_file(src / "page.html", b"html data")
        _run(src, tgt)
        assert (tgt / "web-pages" / "page.html").exists()

    def test_unknown_extension_goes_to_others(self, src, tgt):
        make_file(src / "mystery.xyz", b"unknown")
        _run(src, tgt)
        assert (tgt / "others" / "mystery.xyz").exists()

    def test_path_is_exactly_target_category_filename(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        _run(src, tgt)
        expected = tgt / "images" / "photo.jpg"
        assert expected.exists()
        # No extra date subdirectories
        assert expected.parent == tgt / "images"

    def test_mixed_types_split_correctly(self, src, tgt):
        make_file(src / "photo.jpg", b"img")
        make_file(src / "clip.mp4", b"vid")
        make_file(src / "report.pdf", b"doc")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 3
        assert (tgt / "images" / "photo.jpg").exists()
        assert (tgt / "videos" / "clip.mp4").exists()
        assert (tgt / "documents" / "report.pdf").exists()

    def test_file_content_intact_after_copy(self, src, tgt):
        payload = b"unique payload " + bytes(range(200))
        make_file(src / "photo.jpg", payload)
        _run(src, tgt)
        assert (tgt / "images" / "photo.jpg").read_bytes() == payload

    def test_recursive_source_scan(self, src, tgt):
        make_file(src / "a" / "b" / "photo.jpg", b"a")
        make_file(src / "clip.mp4", b"b")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 2

    def test_summary_scanned_count(self, src, tgt):
        make_file(src / "a.jpg", b"1")
        make_file(src / "b.mp4", b"2")
        make_file(src / "c.pdf", b"3")
        summary, _ = _run(src, tgt)
        assert summary.files_scanned == 3
        assert summary.files_copied == 3


# ── Duplicate detection ───────────────────────────────────────────────────────

class TestDuplicateDetection:
    def test_second_run_skips_all(self, src, tgt):
        make_file(src / "photo.jpg", b"same data")
        make_file(src / "clip.mp4", b"same video")

        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        s1 = process_source(src, tgt, store=store, hash_algo="sha256",
                             dry_run=False, verbose=False, excludes=Excludes([]))
        store.save()
        assert s1.files_copied == 2

        store2 = CatalogStore(catalog_path)
        s2 = process_source(src, tgt, store=store2, hash_algo="sha256",
                             dry_run=False, verbose=False, excludes=Excludes([]))
        assert s2.files_copied == 0
        assert s2.files_skipped == 2

    def test_identical_file_two_sources_copied_once(self, tmp_path, tgt):
        data = b"duplicate content"
        src1 = tmp_path / "src1"; src1.mkdir()
        src2 = tmp_path / "src2"; src2.mkdir()
        make_file(src1 / "photo.jpg", data)
        make_file(src2 / "photo.jpg", data)

        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)
        s1 = process_source(src1, tgt, store=store, hash_algo="sha256",
                             dry_run=False, verbose=False, excludes=Excludes([]))
        s2 = process_source(src2, tgt, store=store, hash_algo="sha256",
                             dry_run=False, verbose=False, excludes=Excludes([]))

        assert s1.files_copied == 1
        assert s2.files_skipped == 1
        assert len(list((tgt / "images").iterdir())) == 1

    def test_same_name_different_content_both_copied(self, tmp_path, tgt):
        src1 = tmp_path / "src1"; src1.mkdir()
        src2 = tmp_path / "src2"; src2.mkdir()
        make_file(src1 / "photo.jpg", b"content A")
        make_file(src2 / "photo.jpg", b"content B")

        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)
        process_source(src1, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))
        process_source(src2, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))

        jpgs = list((tgt / "images").iterdir())
        assert len(jpgs) == 2

    def test_catalog_persists_across_instances(self, src, tgt):
        make_file(src / "photo.jpg", b"persist me")
        catalog_path = tgt / "media_catalog.json"

        store = CatalogStore(catalog_path)
        process_source(src, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))
        store.save()

        store2 = CatalogStore(catalog_path)
        s2 = process_source(src, tgt, store=store2, hash_algo="sha256",
                             dry_run=False, verbose=False, excludes=Excludes([]))
        assert s2.files_skipped == 1


# ── Dry run ───────────────────────────────────────────────────────────────────

class TestDryRun:
    def test_no_files_written(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        _run(src, tgt, dry_run=True)
        assert not (tgt / "images").exists()

    def test_catalog_not_modified(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        _, store = _run(src, tgt, dry_run=True)
        assert store.record_count() == 0

    def test_counts_correct_in_dry_run(self, src, tgt):
        make_file(src / "a.jpg", b"1")
        make_file(src / "b.mp4", b"2")
        summary, _ = _run(src, tgt, dry_run=True)
        assert summary.files_scanned == 2
        assert summary.files_copied == 2   # "would copy"


# ── Excludes ──────────────────────────────────────────────────────────────────

class TestExcludesIntegration:
    def test_excluded_directory_not_copied(self, src, tgt):
        make_file(src / "dqhelper" / "photo.jpg", b"skip")
        make_file(src / "photos" / "keep.jpg", b"keep")
        summary, _ = _run(src, tgt, excludes=Excludes(["dqhelper"]))
        assert summary.files_copied == 1
        assert (tgt / "images" / "keep.jpg").exists()
        assert not (tgt / "images" / "photo.jpg").exists()

    def test_excluded_extension_not_copied(self, src, tgt):
        make_file(src / "photo.jpg", b"keep")
        make_file(src / "raw.dng", b"skip")
        summary, _ = _run(src, tgt, excludes=Excludes(["*.dng"]))
        assert summary.files_copied == 1
        assert (tgt / "images" / "photo.jpg").exists()
        assert not (tgt / "images" / "raw.dng").exists()

    def test_no_excludes_copies_all_types(self, src, tgt):
        make_file(src / "a.jpg", b"1")
        make_file(src / "b.mp4", b"2")
        make_file(src / "c.pdf", b"3")
        summary, _ = _run(src, tgt)
        assert summary.files_copied == 3


# ── Error resilience ──────────────────────────────────────────────────────────

class TestErrorResilience:
    def test_error_captured_not_raised(self, src, tgt):
        make_file(src / "photo.jpg", b"data")
        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        with patch("catalog.compute_hash", side_effect=OSError("disk error")):
            summary = process_source(src, tgt, store=store, hash_algo="sha256",
                                     dry_run=False, verbose=False,
                                     excludes=Excludes([]))

        assert summary.files_errored == 1
        assert summary.files_copied == 0
        assert "disk error" in summary.errors[0][1]

    def test_one_error_does_not_stop_other_files(self, src, tgt):
        make_file(src / "good.jpg", b"ok")
        make_file(src / "bad.jpg", b"fail")
        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        call_count = {"n": 0}
        real_hash = __import__("hasher").compute_hash

        def flaky_hash(path, algo="sha256"):
            call_count["n"] += 1
            if "bad" in str(path):
                raise OSError("read error")
            return real_hash(path, algo=algo)

        with patch("catalog.compute_hash", side_effect=flaky_hash):
            summary = process_source(src, tgt, store=store, hash_algo="sha256",
                                     dry_run=False, verbose=False,
                                     excludes=Excludes([]))

        assert summary.files_copied == 1
        assert summary.files_errored == 1


# ── Source location tracking ──────────────────────────────────────────────────

class TestSourceLocationTracking:
    def test_duplicate_across_sources_records_both_paths(self, tmp_path, tgt):
        """Same file found in two source dirs → both paths in source_locations."""
        data = b"identical content"
        src1 = tmp_path / "src1"; src1.mkdir()
        src2 = tmp_path / "src2"; src2.mkdir()
        make_file(src1 / "photo.jpg", data)
        make_file(src2 / "photo.jpg", data)

        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)
        process_source(src1, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))
        process_source(src2, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))
        store.save()

        store2 = CatalogStore(catalog_path)
        import hashlib
        h = hashlib.sha256(data).hexdigest()
        rec = store2.get(h)
        assert rec is not None
        assert str(src1 / "photo.jpg") in rec.source_locations
        assert str(src2 / "photo.jpg") in rec.source_locations

    def test_first_run_stores_single_source_location(self, src, tgt):
        make_file(src / "photo.jpg", b"unique content xyz")
        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)
        process_source(src, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))
        store.save()

        import hashlib
        h = hashlib.sha256(b"unique content xyz").hexdigest()
        rec = store.get(h)
        assert rec is not None
        assert len(rec.source_locations) == 1
        assert str(src / "photo.jpg") in rec.source_locations

    def test_same_source_rescanned_no_duplicate_paths(self, src, tgt):
        """Running the same source twice must not duplicate the location entry."""
        data = b"rescan me"
        make_file(src / "photo.jpg", data)
        catalog_path = tgt / "media_catalog.json"
        store = CatalogStore(catalog_path)

        process_source(src, tgt, store=store, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))
        store.save()

        store2 = CatalogStore(catalog_path)
        process_source(src, tgt, store=store2, hash_algo="sha256",
                       dry_run=False, verbose=False, excludes=Excludes([]))
        store2.save()

        import hashlib
        h = hashlib.sha256(data).hexdigest()
        rec = store2.get(h)
        assert rec.source_locations.count(str(src / "photo.jpg")) == 1
