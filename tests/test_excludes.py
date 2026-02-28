"""Tests for excludes.py — pattern matching, file loading, merging."""
from pathlib import Path

import pytest

from excludes import Excludes, build_excludes, load_exclude_file
from tests.conftest import make_file


# ── Excludes class ────────────────────────────────────────────────────────────

class TestExcludesEmpty:
    def test_no_patterns_is_empty(self):
        assert Excludes([]).is_empty()

    def test_only_comments_is_empty(self):
        assert Excludes(["# comment", "   # another"]).is_empty()

    def test_only_blank_lines_is_empty(self):
        assert Excludes(["", "  ", "\t"]).is_empty()

    def test_with_pattern_not_empty(self):
        assert not Excludes(["dqhelper"]).is_empty()


class TestExtensionPatterns:
    def test_star_dot_ext(self):
        ex = Excludes(["*.db"])
        assert ex.should_skip_file(Path("/any/path/data.db"))
        assert not ex.should_skip_file(Path("/any/path/data.jpg"))

    def test_leading_dot_shorthand(self):
        ex = Excludes([".tmp"])
        assert ex.should_skip_file(Path("cache.tmp"))
        assert not ex.should_skip_file(Path("cache.jpg"))

    def test_extension_case_insensitive(self):
        ex = Excludes(["*.DB"])
        assert ex.should_skip_file(Path("data.db"))
        assert ex.should_skip_file(Path("data.DB"))

    def test_multiple_extensions(self):
        ex = Excludes(["*.db", ".tmp", "*.log"])
        assert ex.should_skip_file(Path("x.db"))
        assert ex.should_skip_file(Path("x.tmp"))
        assert ex.should_skip_file(Path("x.log"))
        assert not ex.should_skip_file(Path("x.jpg"))

    def test_extension_does_not_affect_dirs(self):
        ex = Excludes(["*.db"])
        # Extension rules only apply via should_skip_file
        assert not ex.should_skip_dir(Path("mydir.db"))


class TestDirectoryPatterns:
    def test_exact_dir_name(self):
        ex = Excludes(["dqhelper"])
        assert ex.should_skip_dir(Path("dqhelper"))

    def test_nested_dir_matched_by_name(self):
        ex = Excludes(["dqhelper"])
        assert ex.should_skip_dir(Path("photos/dqhelper"))
        assert ex.should_skip_dir(Path("a/b/c/dqhelper"))

    def test_non_matching_dir(self):
        ex = Excludes(["dqhelper"])
        assert not ex.should_skip_dir(Path("photos"))
        assert not ex.should_skip_dir(Path("dqhelper_backup"))

    def test_trailing_slash_dir_only(self):
        ex = Excludes(["PRIVATE/"])
        assert ex.should_skip_dir(Path("PRIVATE"))
        assert ex.should_skip_dir(Path("SD/PRIVATE"))

    def test_trailing_slash_does_not_match_files(self):
        ex = Excludes(["PRIVATE/"])
        # PRIVATE/ was marked dir-only, so it won't appear in _file_patterns
        assert not ex.should_skip_file(Path("PRIVATE"))

    def test_plain_name_matches_both_dir_and_file(self):
        ex = Excludes(["junk"])
        assert ex.should_skip_dir(Path("junk"))
        assert ex.should_skip_file(Path("junk"))

    def test_slash_path_pattern(self):
        ex = Excludes(["logs/archive"])
        assert ex.should_skip_dir(Path("logs/archive"))
        assert not ex.should_skip_dir(Path("logs"))
        assert not ex.should_skip_dir(Path("archive"))

    def test_wildcard_in_dir_pattern(self):
        ex = Excludes(["tmp*"])
        assert ex.should_skip_dir(Path("tmp123"))
        assert ex.should_skip_dir(Path("tmpfiles"))
        assert not ex.should_skip_dir(Path("photos"))


class TestDescribe:
    def test_empty_returns_none_string(self):
        assert Excludes([]).describe() == "none"

    def test_extensions_listed(self):
        desc = Excludes(["*.db", ".tmp"]).describe()
        assert "extensions:" in desc
        assert ".db" in desc
        assert ".tmp" in desc

    def test_dirs_listed(self):
        desc = Excludes(["dqhelper", "MISC/"]).describe()
        assert "dirs/names:" in desc
        assert "dqhelper" in desc

    def test_combined_output(self):
        desc = Excludes(["*.db", "dqhelper"]).describe()
        assert "extensions:" in desc
        assert "dirs/names:" in desc


# ── load_exclude_file ─────────────────────────────────────────────────────────

class TestLoadExcludeFile:
    def test_reads_patterns(self, tmp_path):
        f = make_file(tmp_path / "exclude", b"dqhelper\n*.db\n")
        patterns = load_exclude_file(f)
        assert "dqhelper" in patterns
        assert "*.db" in patterns

    def test_strips_comments(self, tmp_path):
        f = make_file(tmp_path / "exclude", b"# skip this\ndqhelper\n")
        patterns = load_exclude_file(f)
        assert "# skip this" not in patterns
        assert "dqhelper" in patterns

    def test_strips_blank_lines(self, tmp_path):
        f = make_file(tmp_path / "exclude", b"\n\ndqhelper\n\n")
        patterns = load_exclude_file(f)
        assert "" not in patterns
        assert "dqhelper" in patterns

    def test_missing_file_returns_empty_list(self, tmp_path):
        patterns = load_exclude_file(tmp_path / "nonexistent")
        assert patterns == []

    def test_inline_comment_not_stripped(self, tmp_path):
        # Only full-line comments (leading #) are stripped; inline comments kept as-is
        f = make_file(tmp_path / "exclude", b"dqhelper # inline\n")
        patterns = load_exclude_file(f)
        assert any("dqhelper" in p for p in patterns)


# ── build_excludes ────────────────────────────────────────────────────────────

class TestBuildExcludes:
    def test_cli_patterns_applied(self, tmp_path):
        ex = build_excludes(["*.db"], exclude_file=tmp_path / "no_file")
        assert ex.should_skip_file(Path("data.db"))

    def test_file_patterns_applied(self, tmp_path):
        f = make_file(tmp_path / "exclude", b"dqhelper\n")
        ex = build_excludes([], exclude_file=f)
        assert ex.should_skip_dir(Path("dqhelper"))

    def test_file_and_cli_merged(self, tmp_path):
        f = make_file(tmp_path / "exclude", b"dqhelper\n")
        ex = build_excludes(["*.db"], exclude_file=f)
        assert ex.should_skip_dir(Path("dqhelper"))
        assert ex.should_skip_file(Path("data.db"))

    def test_missing_file_uses_only_cli(self, tmp_path):
        ex = build_excludes(["*.tmp"], exclude_file=tmp_path / "no_file")
        assert ex.should_skip_file(Path("x.tmp"))
        assert not ex.should_skip_file(Path("x.jpg"))
