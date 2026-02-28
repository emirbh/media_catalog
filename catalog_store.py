import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import FileRecord

CATALOG_FILENAME = "media_catalog.json"
CATALOG_VERSION = "1.0"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CatalogStore:
    """
    Manages a JSON catalog at target_root/media_catalog.json.

    Schema:
    {
      "version": "1.0",
      "created_at": "<ISO datetime>",
      "updated_at": "<ISO datetime>",
      "entries": { "<sha256>": { ...FileRecord fields... } }
    }

    Entries are keyed by hash for O(1) duplicate lookup.
    """

    def __init__(self, catalog_path: Path) -> None:
        self._path = catalog_path
        self._entries: dict[str, dict] = {}
        self._metadata: dict = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entries = data.get("entries", {})
                self._metadata = {
                    "version": data.get("version", CATALOG_VERSION),
                    "created_at": data.get("created_at", _now_iso()),
                    "updated_at": data.get("updated_at", _now_iso()),
                }
            except (json.JSONDecodeError, OSError):
                # Corrupted catalog — start fresh
                self._entries = {}
                self._metadata = {
                    "version": CATALOG_VERSION,
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                }
        else:
            self._entries = {}
            self._metadata = {
                "version": CATALOG_VERSION,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }

    def contains(self, file_hash: str) -> bool:
        """Return True if hash is already cataloged."""
        return file_hash in self._entries

    def add(self, record: FileRecord) -> None:
        """Insert a new FileRecord keyed by its hash."""
        self._entries[record.hash] = record.to_dict()

    def get(self, file_hash: str) -> Optional[FileRecord]:
        """Return the FileRecord for a hash, or None."""
        entry = self._entries.get(file_hash)
        if entry is None:
            return None
        return FileRecord.from_dict(entry)

    def record_count(self) -> int:
        """Return total number of cataloged entries."""
        return len(self._entries)

    def save(self) -> None:
        """
        Atomically write catalog to disk.
        Writes to a .tmp file first, then renames to avoid corruption.
        """
        self._metadata["updated_at"] = _now_iso()
        data = {
            **self._metadata,
            "entries": self._entries,
        }
        tmp_path = self._path.with_suffix(".tmp")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self._path)

    @staticmethod
    def catalog_path_for(target_root: Path) -> Path:
        return target_root / CATALOG_FILENAME
