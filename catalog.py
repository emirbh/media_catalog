#!/usr/bin/env python3
"""
media-catalog: Scan directories for all file types, copy them into a
categorised target structure, and maintain a persistent catalog to skip
duplicates across runs.

Output layout:
    <target>/images/photo.jpg
    <target>/videos/clip.mp4
    <target>/documents/report.pdf
    <target>/screenshots/capture.png
    <target>/music-files/song.mp3
    <target>/web-pages/page.html
    <target>/others/unknown.xyz

Usage:
    python catalog.py --source /Volumes/SD1 /Volumes/USB --target ~/MediaBackup
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from catalog_store import CatalogStore
from copier import build_destination_path, copy_file
from excludes import DEFAULT_EXCLUDE_FILE, Excludes, build_excludes
from exif_reader import get_media_date
from hasher import compute_hash
from models import FileRecord, ScanSummary
from scanner import count_files, scan_directory


# ── Core pipeline ─────────────────────────────────────────────────────────────

def process_source(
    source_path: Path,
    target_root: Path,
    store: CatalogStore,
    hash_algo: str,
    dry_run: bool,
    verbose: bool,
    excludes: Excludes,
) -> ScanSummary:
    """Full scan-and-copy pipeline for one source directory."""
    summary = ScanSummary(source_path=str(source_path))
    copies_since_save = 0

    for file_path, category in scan_directory(source_path, excludes=excludes):
        summary.files_scanned += 1

        try:
            file_hash = compute_hash(file_path, algo=hash_algo)

            if store.contains(file_hash):
                # Record this source path even though the file won't be re-copied
                store.add_location(file_hash, str(file_path))
                summary.files_skipped += 1
                if verbose:
                    print(f"  SKIP   {file_path}")
                continue

            date_taken, date_source = get_media_date(file_path)
            dest_path = build_destination_path(
                target_root, category, file_path.name
            )

            if not dry_run:
                actual_dest = copy_file(file_path, dest_path, date_taken=date_taken)
                record = FileRecord(
                    hash=file_hash,
                    source_locations=[str(file_path)],
                    destination_path=str(actual_dest),
                    category=category,
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
                print(f"  {action}  [{category}]  {file_path.name}")

        except Exception as e:
            summary.files_errored += 1
            summary.errors.append((str(file_path), str(e)))
            if verbose:
                print(f"  ERROR  {file_path}: {e}", file=sys.stderr)

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
    print("\n" + "=" * 48)
    print("  Media Catalog Summary")
    if dry_run:
        print("  (DRY RUN — no files were copied)")
    print("=" * 48)

    total_scanned = total_copied = total_skipped = total_errored = 0

    for s in summaries:
        print(f"\nSource  : {s.source_path}")
        print(f"  Scanned : {s.files_scanned:>7,} files")
        print(f"  Copied  : {s.files_copied:>7,} files")
        print(f"  Skipped : {s.files_skipped:>7,} files (already in catalog)")
        print(f"  Errors  : {s.files_errored:>7,} files")
        if s.errors:
            show = s.errors[:20]
            for path, msg in show:
                print(f"    ! {path}: {msg}")
            if len(s.errors) > 20:
                print(f"    … and {len(s.errors) - 20} more errors")
        total_scanned += s.files_scanned
        total_copied  += s.files_copied
        total_skipped += s.files_skipped
        total_errored += s.files_errored

    if len(summaries) > 1:
        print(f"\n{'─' * 48}")
        print("Totals")
        print(f"  Scanned : {total_scanned:>7,} files")
        print(f"  Copied  : {total_copied:>7,} files")
        print(f"  Skipped : {total_skipped:>7,} files")
        print(f"  Errors  : {total_errored:>7,} files")

    print(f"\nCatalog : {catalog_path}")
    print(f"Entries : {store.record_count():,} total cataloged files")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog.py",
        description=(
            "Scan source directories and copy files into a categorised target "
            "structure (images/, videos/, documents/, screenshots/, "
            "music-files/, web-pages/, others/). "
            "Duplicates are detected by content hash and skipped."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python catalog.py --source /Volumes/SD1 --target ~/Backup\n"
            "  python catalog.py --source /Volumes/SD1 /Volumes/USB --target ~/Backup --dry-run\n"
            "  python catalog.py --source /Volumes/GoPro --target ~/Backup --hash md5 --verbose\n"
            "  python catalog.py --source /Volumes/SD1 --target ~/Backup --exclude dqhelper *.db\n"
            "\n"
            "Exclude file format (one pattern per line, # = comment):\n"
            "  dqhelper     — skip any directory or file named 'dqhelper'\n"
            "  PRIVATE/     — skip directories named 'PRIVATE' only\n"
            "  *.db         — skip files with .db extension\n"
            "  .tmp         — same as *.tmp\n"
        ),
    )
    parser.add_argument(
        "--source", nargs="+", required=True, metavar="PATH",
        help="One or more source directories to scan (processed sequentially).",
    )
    parser.add_argument(
        "--target", required=True, metavar="PATH",
        help="Target root directory for categorised output.",
    )
    parser.add_argument(
        "--hash", choices=["sha256", "md5"], default="sha256", dest="hash_algo",
        help="Hash algorithm for duplicate detection (default: sha256).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be copied without making any changes.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print each file's action (COPY / SKIP / ERROR).",
    )
    parser.add_argument(
        "--catalog-path", metavar="PATH", default=None,
        help="Override the default catalog file location "
             "(default: TARGET/media_catalog.json).",
    )
    parser.add_argument(
        "--exclude", nargs="+", metavar="PATTERN", default=[],
        help=(
            "One or more patterns to exclude. Supports directory names "
            "(dqhelper), extensions (*.db or .db), and trailing-slash "
            "directory markers (PRIVATE/). Combined with the 'exclude' file."
        ),
    )
    parser.add_argument(
        "--exclude-file", metavar="PATH", default=None,
        help="Path to an exclude-patterns file "
             "(default: 'exclude' in the current directory).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Validate source paths
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
    catalog_path = (
        Path(args.catalog_path).expanduser().resolve()
        if args.catalog_path
        else CatalogStore.catalog_path_for(target_root)
    )

    # Build excludes (file + CLI patterns merged)
    exclude_file = (
        Path(args.exclude_file).expanduser().resolve()
        if args.exclude_file
        else Path.cwd() / DEFAULT_EXCLUDE_FILE
    )
    excludes = build_excludes(cli_patterns=args.exclude, exclude_file=exclude_file)
    if not excludes.is_empty():
        print(f"Excludes : {excludes.describe()}")

    # Load catalog
    store = CatalogStore(catalog_path)
    print(f"Catalog  : {catalog_path}  ({store.record_count():,} existing entries)")

    if args.dry_run:
        print("[DRY RUN] No files will be copied or catalog modified.")

    # Process each source directory
    summaries: List[ScanSummary] = []
    for source_path in sources:
        total = count_files(source_path, excludes=excludes)
        print(f"\nScanning : {source_path}  ({total:,} files found)")
        summary = process_source(
            source_path=source_path,
            target_root=target_root,
            store=store,
            hash_algo=args.hash_algo,
            dry_run=args.dry_run,
            verbose=args.verbose,
            excludes=excludes,
        )
        summaries.append(summary)

    print_summary(summaries, store, catalog_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
