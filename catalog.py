#!/usr/bin/env python3
"""
media-catalog: Scan directories for images and videos, copy them to a
dated target structure, and maintain a persistent catalog to skip duplicates.

Usage:
    python catalog.py --source /Volumes/SD1 /Volumes/USB --target ~/MediaBackup
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from catalog_store import CatalogStore
from copier import build_destination_path, copy_file
from exif_reader import get_media_date
from hasher import compute_hash
from models import FileRecord, ScanSummary
from scanner import count_media_files, scan_directory

try:
    from tqdm import tqdm
    _TQDM_AVAILABLE = True
except ImportError:
    _TQDM_AVAILABLE = False


# ── Progress helpers ──────────────────────────────────────────────────────────

class _NoOpBar:
    """Minimal tqdm-compatible no-op for --no-progress mode."""
    def __init__(self, *args, **kwargs):
        pass

    def update(self, n=1):
        pass

    def set_postfix(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _make_bar(total: int, desc: str, use_progress: bool):
    if use_progress and _TQDM_AVAILABLE:
        return tqdm(total=total, unit="file", desc=desc, ncols=80)
    return _NoOpBar()


# ── Core pipeline ─────────────────────────────────────────────────────────────

def process_source(
    source_path: Path,
    target_root: Path,
    store: CatalogStore,
    hash_algo: str,
    dry_run: bool,
    verbose: bool,
    use_progress: bool,
) -> ScanSummary:
    """Full scan-and-copy pipeline for one source directory."""
    summary = ScanSummary(source_path=str(source_path))

    if use_progress:
        print(f"\nCounting files in {source_path} ...")
    total = count_media_files(source_path)

    copies_since_save = 0

    with _make_bar(total, desc=str(source_path.name), use_progress=use_progress) as bar:
        for file_path, media_type in scan_directory(source_path):
            summary.files_scanned += 1
            bar.update(1)
            bar.set_postfix(
                copied=summary.files_copied,
                skipped=summary.files_skipped,
            )

            try:
                file_hash = compute_hash(file_path, algo=hash_algo)

                if store.contains(file_hash):
                    summary.files_skipped += 1
                    if verbose:
                        print(f"  SKIP  {file_path}")
                    continue

                date_taken, date_source = get_media_date(file_path)
                dest_path = build_destination_path(
                    target_root, media_type, date_taken, file_path.name
                )

                if not dry_run:
                    actual_dest = copy_file(file_path, dest_path)
                    record = FileRecord(
                        hash=file_hash,
                        original_path=str(file_path),
                        destination_path=str(actual_dest),
                        media_type=media_type,
                        extension=file_path.suffix.lower(),
                        date_taken=date_taken.strftime("%Y-%m-%d"),
                        date_source=date_source,
                        file_size_bytes=file_path.stat().st_size,
                        cataloged_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    store.add(record)
                    copies_since_save += 1
                    if copies_since_save >= 50:
                        store.save()
                        copies_since_save = 0

                summary.files_copied += 1
                if verbose:
                    action = "DRY-RUN" if dry_run else "COPY"
                    print(f"  {action}  {file_path}  →  {dest_path}")

            except Exception as e:
                summary.files_errored += 1
                summary.errors.append((str(file_path), str(e)))
                if verbose:
                    print(f"  ERROR {file_path}: {e}", file=sys.stderr)

    # Save after finishing each source
    if not dry_run:
        store.save()

    return summary


# ── Output ────────────────────────────────────────────────────────────────────

def print_summary(
    summaries: List[ScanSummary],
    store: CatalogStore,
    catalog_path: Path,
    dry_run: bool,
) -> None:
    print("\n" + "=" * 44)
    print("  Media Catalog Summary")
    if dry_run:
        print("  (DRY RUN — no files were copied)")
    print("=" * 44)

    total_scanned = total_copied = total_skipped = total_errored = 0

    for s in summaries:
        print(f"\nSource: {s.source_path}")
        print(f"  Scanned : {s.files_scanned:>6,} files")
        print(f"  Copied  : {s.files_copied:>6,} files")
        print(f"  Skipped : {s.files_skipped:>6,} files (already in catalog)")
        print(f"  Errors  : {s.files_errored:>6,} files")
        if s.errors:
            show = s.errors if len(s.errors) <= 20 else s.errors[:20]
            for path, msg in show:
                print(f"    ! {path}: {msg}")
            if len(s.errors) > 20:
                print(f"    ... and {len(s.errors) - 20} more errors")
        total_scanned += s.files_scanned
        total_copied += s.files_copied
        total_skipped += s.files_skipped
        total_errored += s.files_errored

    if len(summaries) > 1:
        print(f"\n{'─' * 44}")
        print("Totals")
        print(f"  Scanned : {total_scanned:>6,} files")
        print(f"  Copied  : {total_copied:>6,} files")
        print(f"  Skipped : {total_skipped:>6,} files")
        print(f"  Errors  : {total_errored:>6,} files")

    print(f"\nCatalog : {catalog_path}")
    print(f"Entries : {store.record_count():,} total cataloged files")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog.py",
        description=(
            "Scan source directories for images and videos, copy them to a "
            "dated target structure (images/YYYY/MM/DD/ and videos/YYYY/MM/DD/), "
            "and skip duplicates using content hashing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python catalog.py --source /Volumes/SD1 --target ~/MediaBackup\n"
            "  python catalog.py --source /Volumes/SD1 /Volumes/USB --target ~/MediaBackup --dry-run\n"
            "  python catalog.py --source /Volumes/GoPro --target ~/MediaBackup --hash md5 --verbose\n"
        ),
    )
    parser.add_argument(
        "--source",
        nargs="+",
        required=True,
        metavar="PATH",
        help="One or more source directories to scan (processed sequentially).",
    )
    parser.add_argument(
        "--target",
        required=True,
        metavar="PATH",
        help="Target root directory for organized output.",
    )
    parser.add_argument(
        "--hash",
        choices=["sha256", "md5"],
        default="sha256",
        dest="hash_algo",
        help="Hash algorithm for duplicate detection (default: sha256).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be copied without making any changes.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each file's action (COPY / SKIP / ERROR).",
    )
    parser.add_argument(
        "--catalog-path",
        metavar="PATH",
        default=None,
        help="Override the default catalog file location (default: TARGET/media_catalog.json).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars (useful when piping output to log files).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve and validate source paths
    sources: List[Path] = []
    for raw in args.source:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            parser.error(f"Source path does not exist: {p}")
        if not p.is_dir():
            parser.error(f"Source path is not a directory: {p}")
        sources.append(p)

    # Resolve target
    target_root = Path(args.target).expanduser().resolve()
    if not args.dry_run:
        target_root.mkdir(parents=True, exist_ok=True)
    elif not target_root.exists():
        print(f"[dry-run] Target would be created: {target_root}")

    # Resolve catalog path
    if args.catalog_path:
        catalog_path = Path(args.catalog_path).expanduser().resolve()
    else:
        catalog_path = CatalogStore.catalog_path_for(target_root)

    use_progress = not args.no_progress

    # Load catalog
    store = CatalogStore(catalog_path)
    print(f"Catalog: {catalog_path}  ({store.record_count():,} existing entries)")

    if args.dry_run:
        print("[DRY RUN] No files will be copied or catalog modified.")

    # Process each source
    summaries: List[ScanSummary] = []
    for source_path in sources:
        print(f"\nScanning: {source_path}")
        summary = process_source(
            source_path=source_path,
            target_root=target_root,
            store=store,
            hash_algo=args.hash_algo,
            dry_run=args.dry_run,
            verbose=args.verbose,
            use_progress=use_progress,
        )
        summaries.append(summary)

    print_summary(summaries, store, catalog_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
