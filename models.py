from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class FileRecord:
    hash: str
    original_path: str
    destination_path: str
    media_type: str          # "image" or "video"
    extension: str           # lowercase, e.g. ".jpg"
    date_taken: str          # ISO date "YYYY-MM-DD"
    date_source: str         # "exif" or "mtime"
    file_size_bytes: int
    cataloged_at: str        # ISO datetime of catalog insertion

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "original_path": self.original_path,
            "destination_path": self.destination_path,
            "media_type": self.media_type,
            "extension": self.extension,
            "date_taken": self.date_taken,
            "date_source": self.date_source,
            "file_size_bytes": self.file_size_bytes,
            "cataloged_at": self.cataloged_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "FileRecord":
        return FileRecord(
            hash=d["hash"],
            original_path=d["original_path"],
            destination_path=d["destination_path"],
            media_type=d["media_type"],
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
