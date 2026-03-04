from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class FileRecord:
    hash: str
    source_locations: List[str]  # every source path where this file has been found
    destination_path: str
    category: str            # "images", "videos", "documents", "screenshots", etc.
    extension: str           # lowercase, e.g. ".jpg"
    date_taken: str          # ISO date "YYYY-MM-DD" (from EXIF or filesystem)
    date_source: str         # "exif", "birthtime", "ctime", or "mtime"
    file_size_bytes: int
    cataloged_at: str        # ISO datetime of first catalog insertion

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "source_locations": self.source_locations,
            "destination_path": self.destination_path,
            "category": self.category,
            "extension": self.extension,
            "date_taken": self.date_taken,
            "date_source": self.date_source,
            "file_size_bytes": self.file_size_bytes,
            "cataloged_at": self.cataloged_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "FileRecord":
        # Backward-compat: old catalogs stored a single "original_path" string
        if "source_locations" in d:
            locations = d["source_locations"]
        elif "original_path" in d:
            locations = [d["original_path"]]
        else:
            locations = []

        return FileRecord(
            hash=d["hash"],
            source_locations=locations,
            destination_path=d["destination_path"],
            # Backward-compat: old catalogs used "media_type" key
            category=d.get("category") or d.get("media_type", "others"),
            extension=d["extension"],
            date_taken=d["date_taken"],
            date_source=d["date_source"],
            file_size_bytes=d["file_size_bytes"],
            cataloged_at=d["cataloged_at"],
        )


@dataclass
class ScanSummary:
    source_path: str
    files_scanned: int = 0
    files_copied: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    errors: List[Tuple[str, str]] = field(default_factory=list)
