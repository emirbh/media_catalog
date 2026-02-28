"""Tests for hasher.py — SHA-256, MD5, dispatch."""
import hashlib

import pytest

from hasher import compute_hash, compute_md5, compute_sha256
from tests.conftest import make_file


class TestComputeSha256:
    def test_known_content(self, tmp_path):
        data = b"hello media catalog"
        f = make_file(tmp_path / "test.bin", data)
        expected = hashlib.sha256(data).hexdigest()
        assert compute_sha256(f) == expected

    def test_empty_file_has_known_hash(self, tmp_path):
        f = make_file(tmp_path / "empty.bin", b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_sha256(f) == expected

    def test_different_content_gives_different_hash(self, tmp_path):
        f1 = make_file(tmp_path / "a.bin", b"aaa")
        f2 = make_file(tmp_path / "b.bin", b"bbb")
        assert compute_sha256(f1) != compute_sha256(f2)

    def test_same_content_gives_same_hash(self, tmp_path):
        data = b"identical content"
        f1 = make_file(tmp_path / "a.bin", data)
        f2 = make_file(tmp_path / "b.bin", data)
        assert compute_sha256(f1) == compute_sha256(f2)

    def test_missing_file_raises_oserror(self, tmp_path):
        with pytest.raises(OSError):
            compute_sha256(tmp_path / "nonexistent.bin")

    def test_large_content_chunked_correctly(self, tmp_path):
        # 200 KB — forces multiple 64 KB chunk reads
        data = b"x" * (200 * 1024)
        f = make_file(tmp_path / "large.bin", data)
        expected = hashlib.sha256(data).hexdigest()
        assert compute_sha256(f) == expected


class TestComputeMd5:
    def test_known_content(self, tmp_path):
        data = b"hello md5"
        f = make_file(tmp_path / "test.bin", data)
        expected = hashlib.md5(data).hexdigest()
        assert compute_md5(f) == expected

    def test_missing_file_raises_oserror(self, tmp_path):
        with pytest.raises(OSError):
            compute_md5(tmp_path / "gone.bin")


class TestComputeHash:
    def test_dispatches_to_sha256_by_default(self, tmp_path):
        data = b"dispatch test"
        f = make_file(tmp_path / "f.bin", data)
        assert compute_hash(f) == hashlib.sha256(data).hexdigest()

    def test_dispatches_to_sha256_explicit(self, tmp_path):
        data = b"sha256 explicit"
        f = make_file(tmp_path / "f.bin", data)
        assert compute_hash(f, algo="sha256") == hashlib.sha256(data).hexdigest()

    def test_dispatches_to_md5(self, tmp_path):
        data = b"md5 dispatch"
        f = make_file(tmp_path / "f.bin", data)
        assert compute_hash(f, algo="md5") == hashlib.md5(data).hexdigest()

    def test_sha256_and_md5_differ(self, tmp_path):
        data = b"same content"
        f = make_file(tmp_path / "f.bin", data)
        assert compute_hash(f, algo="sha256") != compute_hash(f, algo="md5")
