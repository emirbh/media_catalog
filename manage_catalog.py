#!/usr/bin/env python3
"""
manage_catalog.py — Media catalog management utility.

Subcommands
-----------
find
    List catalog entries whose source files came from a named directory.

move-to-archive
    Move matching files (and their catalog entries) to a separate archive
    catalog.  The source catalog is updated to remove moved entries and the
    archive catalog is created/updated with the new locations.

Usage
-----
  python manage_catalog.py find \\
      --catalog <dir> --source-dir dqhelper [--verbose]

  python manage_catalog.py move-to-archive \\
      --source <dir> --archive <dir> --source-dir dqhelper [--dry-run] [--verbose]
"""

import argparse
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from catalog_store import CatalogStore
from copier import resolve_collision
from models import FileRecord


# ── Matching helpers ───────────────────────────────────────────────────────────

def _path_has_component(path_str: str, name: str) -> bool:
    """Return True if *name* is an exact path component of *path_str*."""
    return name in Path(path_str).parts


def find_by_source_dir(store: CatalogStore, dir_name: str) -> List[FileRecord]:
    """
    Return all FileRecords where at least one source_location path contains
    *dir_name* as an exact directory component (not a substring match).

    Example: dir_name="dqhelper" matches /Volumes/SD1/dqhelper/photo.jpg
             but NOT /Volumes/SD1/not_dqhelper/photo.jpg
    """
    results = []
    for entry in store._entries.values():
        record = FileRecord.from_dict(entry)
        if any(_path_has_component(loc, dir_name) for loc in record.source_locations):
            results.append(record)
    return results


# ── Move summary ───────────────────────────────────────────────────────────────

@dataclass
class MoveSummary:
    matched: int = 0
    moved: int = 0
    file_missing: int = 0   # on disk at expected path — catalog updated anyway
    errored: int = 0
    errors: List[Tuple[str, str]] = field(default_factory=list)


# ── Core move logic ────────────────────────────────────────────────────────────

def move_to_archive(
    records: List[FileRecord],
    source_root: Path,
    source_store: CatalogStore,
    archive_root: Path,
    archive_store: CatalogStore,
    dry_run: bool = False,
    verbose: bool = False,
) -> MoveSummary:
    """
    For each record:
      1. Locate the file at record.destination_path.
      2. Move it to archive_root / category / filename (collision-safe).
      3. Remove the entry from source_store.
      4. Add an updated entry (new destination_path) to archive_store.

    If the file is absent from disk the catalog entry is still transferred.
    Both stores are saved after all moves complete (or on dry-run, not at all).
    """
    summary = MoveSummary(matched=len(records))

    for record in records:
        src_file = Path(record.destination_path)
        archive_dest = archive_root / record.category / src_file.name

        try:
            if not dry_run:
                archive_dest.parent.mkdir(parents=True, exist_ok=True)
                archive_dest = resolve_collision(archive_dest)

                if src_file.exists():
                    shutil.move(str(src_file), archive_dest)
                    summary.moved += 1
                else:
                    summary.file_missing += 1
                    if verbose:
                        print(f"  WARN   file not on disk: {src_file}", file=sys.stderr)

                # Update record with new destination and transfer between catalogs
                updated = FileRecord(
                    hash=record.hash,
                    source_locations=record.source_locations,
                    destination_path=str(archive_dest),
                    category=record.category,
                    extension=record.extension,
                    date_taken=record.date_taken,
                    date_source=record.date_source,
                    file_size_bytes=record.file_size_bytes,
                    cataloged_at=record.cataloged_at,
                )
                del source_store._entries[record.hash]
                archive_store.add(updated)
            else:
                summary.moved += 1

            if verbose:
                action = "DRY-RUN" if dry_run else "MOVE"
                print(f"  {action}  {src_file.name}  →  {archive_dest}")

        except Exception as exc:
            summary.errored += 1
            summary.errors.append((str(src_file), str(exc)))
            print(f"  ERROR  {src_file}: {exc}", file=sys.stderr)

    if not dry_run:
        source_store.save()
        archive_store.save()

    return summary


# ── Subcommand: find ───────────────────────────────────────────────────────────

def cmd_find(args: argparse.Namespace) -> None:
    catalog_root = Path(args.catalog).expanduser().resolve()
    catalog_path = CatalogStore.catalog_path_for(catalog_root)
    store = CatalogStore(catalog_path)

    records = find_by_source_dir(store, args.source_dir)

    if not records:
        print(f"No entries found with source directory '{args.source_dir}'.")
        return

    print(f"Found {len(records)} entr{'y' if len(records) == 1 else 'ies'} "
          f"with source directory '{args.source_dir}':\n")

    for rec in records:
        print(f"  {rec.destination_path}")
        if args.verbose:
            for loc in rec.source_locations:
                print(f"    source: {loc}")


# ── Subcommand: move-to-archive ────────────────────────────────────────────────

def cmd_move_to_archive(args: argparse.Namespace) -> None:
    source_root  = Path(args.source).expanduser().resolve()
    archive_root = Path(args.archive).expanduser().resolve()

    if not source_root.is_dir():
        sys.exit(f"Error: source catalog directory does not exist: {source_root}")

    source_store  = CatalogStore(CatalogStore.catalog_path_for(source_root))
    archive_store = CatalogStore(CatalogStore.catalog_path_for(archive_root))

    records = find_by_source_dir(source_store, args.source_dir)

    if not records:
        print(f"No entries found with source directory '{args.source_dir}'. Nothing to do.")
        return

    print(f"Found {len(records)} entr{'y' if len(records) == 1 else 'ies'} "
          f"matching '{args.source_dir}'.")
    if args.dry_run:
        print("[DRY RUN] No files will be moved or catalogs modified.")

    if not args.dry_run:
        archive_root.mkdir(parents=True, exist_ok=True)

    summary = move_to_archive(
        records=records,
        source_root=source_root,
        source_store=source_store,
        archive_root=archive_root,
        archive_store=archive_store,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print(f"\n{'=' * 48}")
    print(f"  move-to-archive summary")
    print(f"{'=' * 48}")
    print(f"  Matched  : {summary.matched:>7,}")
    print(f"  Moved    : {summary.moved:>7,}")
    if summary.file_missing:
        print(f"  Missing  : {summary.file_missing:>7,}  (catalog updated, file was absent)")
    if summary.errored:
        print(f"  Errors   : {summary.errored:>7,}")
        for path, msg in summary.errors:
            print(f"    ! {path}: {msg}")
    print(f"\n  Source catalog  : {CatalogStore.catalog_path_for(source_root)}")
    print(f"  Archive catalog : {CatalogStore.catalog_path_for(archive_root)}")
    print()


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage_catalog.py",
        description="Manage and reorganise media catalogs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # List all files that came from a 'dqhelper' directory\n"
            "  python manage_catalog.py find --catalog ~/MediaBackup --source-dir dqhelper\n"
            "\n"
            "  # Move those files to an archive catalog\n"
            "  python manage_catalog.py move-to-archive \\\n"
            "      --source ~/MediaBackup --archive ~/MediaBackup/ARCHIVE \\\n"
            "      --source-dir dqhelper --dry-run\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── find ──
    p_find = sub.add_parser("find", help="List catalog entries from a named source directory.")
    p_find.add_argument("--catalog", required=True, metavar="DIR",
                        help="Catalog root directory (contains media_catalog.json).")
    p_find.add_argument("--source-dir", required=True, metavar="NAME",
                        help="Directory name to search for in source_locations.")
    p_find.add_argument("--verbose", action="store_true",
                        help="Also print source locations for each match.")

    # ── move-to-archive ──
    p_move = sub.add_parser(
        "move-to-archive",
        help="Move matching files and catalog entries to an archive catalog.",
    )
    p_move.add_argument("--source", required=True, metavar="DIR",
                        help="Source catalog root directory.")
    p_move.add_argument("--archive", required=True, metavar="DIR",
                        help="Archive catalog root directory (created if needed).")
    p_move.add_argument("--source-dir", required=True, metavar="NAME",
                        help="Move entries whose source_locations contain this directory name.")
    p_move.add_argument("--dry-run", action="store_true",
                        help="Show what would be moved without making any changes.")
    p_move.add_argument("--verbose", action="store_true",
                        help="Print each file as it is moved.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "find":
        cmd_find(args)
    elif args.command == "move-to-archive":
        cmd_move_to_archive(args)


if __name__ == "__main__":
    main()
