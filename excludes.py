"""
Exclude rules for the media catalog scanner.

Patterns (from the 'exclude' file or --exclude CLI arg) support:
  dqhelper        — matches any directory or file named exactly 'dqhelper'
  *.db            — matches any file with that extension (fnmatch style)
  .tmp            — shorthand for *.tmp (leading dot, no *)
  PRIVATE/        — trailing slash forces directory-only match
  logs/archive    — slash-separated path segment match (relative to source root)

File format (one pattern per line):
  # lines starting with # are comments
  blank lines are ignored
"""

import fnmatch
from pathlib import Path
from typing import List, Set


DEFAULT_EXCLUDE_FILE = "exclude"


class Excludes:
    def __init__(self, patterns: List[str]) -> None:
        # Normalise and store patterns
        self._dir_patterns: List[str] = []   # match directory names / path segments
        self._file_patterns: List[str] = []  # match file names
        self._ext_set: Set[str] = set()      # fast extension lookup

        for raw in patterns:
            p = raw.strip()
            if not p or p.startswith("#"):
                continue

            # Trailing slash → directory only
            dir_only = p.endswith("/")
            p = p.rstrip("/")

            # Leading dot with no wildcard → extension shorthand  (.tmp → *.tmp)
            if p.startswith(".") and "*" not in p:
                self._ext_set.add(p.lower())
                continue

            # Wildcard extension pattern like *.db
            if p.startswith("*.") and "/" not in p:
                self._ext_set.add(p[1:].lower())  # store as ".db"
                continue

            if dir_only or "/" not in p:
                # Matches any path component (dir or file name)
                self._dir_patterns.append(p)
                if not dir_only:
                    self._file_patterns.append(p)
            else:
                # Contains slash → match relative path segment sequence
                self._dir_patterns.append(p)

    # ── Public API ────────────────────────────────────────────────────────────

    def is_empty(self) -> bool:
        return not (self._dir_patterns or self._file_patterns or self._ext_set)

    def should_skip_dir(self, rel_path: Path) -> bool:
        """
        Return True if a directory (given as path relative to source root)
        should be skipped entirely.
        """
        # Check each component of the relative path
        for part in rel_path.parts:
            for pattern in self._dir_patterns:
                if "/" not in pattern:
                    if fnmatch.fnmatch(part, pattern):
                        return True
                else:
                    # Slash pattern: match against the full relative string
                    if fnmatch.fnmatch(str(rel_path), pattern):
                        return True
        return False

    def should_skip_file(self, file_path: Path) -> bool:
        """Return True if a file should be excluded."""
        # Extension match
        if file_path.suffix.lower() in self._ext_set:
            return True

        # Name / pattern match
        for pattern in self._file_patterns:
            if fnmatch.fnmatch(file_path.name, pattern):
                return True

        return False

    def describe(self) -> str:
        """Human-readable summary of active rules."""
        parts = []
        if self._ext_set:
            parts.append("extensions: " + ", ".join(sorted(self._ext_set)))
        if self._dir_patterns:
            parts.append("dirs/names: " + ", ".join(self._dir_patterns))
        return "; ".join(parts) if parts else "none"


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_exclude_file(path: Path) -> List[str]:
    """Read patterns from a file, stripping comments and blank lines."""
    lines: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(stripped)
    except FileNotFoundError:
        pass  # Absence of the file is fine
    except OSError as e:
        print(f"Warning: could not read exclude file {path}: {e}")
    return lines


def build_excludes(
    cli_patterns: List[str],
    exclude_file: Path,
) -> Excludes:
    """
    Merge patterns from the exclude file and CLI --exclude args.
    CLI patterns take precedence in display order but matching is unified.
    """
    file_patterns = load_exclude_file(exclude_file)
    return Excludes(file_patterns + cli_patterns)
