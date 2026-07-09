"""
One-off migration: move pre-versioning file content into the versioned layout.

Before file versioning, content was stored flat at
``DATA_DIR/<identity>/files/<file_id>``. The current code expects
``DATA_DIR/<identity>/files/<file_id>/<version_id>`` plus a ``file_versions``
row. For each flat file this script creates a version-1 FileVersion row and
moves the content into place.

Idempotent: already-migrated files (directories) and files that already have
version rows are skipped. Run while the server is stopped or idle:

    python scripts/migrate_file_versions.py [--data-dir /data]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from box_mock.models import File, FileVersion


def migrate_identity(identity_dir: Path) -> None:
    """Migrate all flat content files for one identity directory."""
    files_dir = identity_dir / "files"
    if not files_dir.is_dir():
        return

    engine = create_engine(f"sqlite:///{identity_dir}/box.db")
    session = sessionmaker(bind=engine)()
    try:
        for path in sorted(files_dir.iterdir()):
            if path.is_dir():
                continue  # already in versioned layout

            file_id = path.name
            file = session.get(File, file_id)
            if file is None:
                print(f"  SKIP {identity_dir.name}/{file_id}: no files row")
                continue
            if file.versions:
                print(f"  SKIP {identity_dir.name}/{file_id}: already has versions")
                continue

            content = path.read_bytes()
            version = FileVersion(
                file_id=file.id,
                version_number=1,
                name=file.name,
                size=len(content),
                sha1=hashlib.sha1(content).hexdigest(),
                created_at=file.created_at,
                modified_at=file.created_at,
            )
            session.add(version)
            session.flush()

            # The flat file and its target directory share a name.
            tmp = path.with_name(f"{file_id}.migrating")
            path.rename(tmp)
            path.mkdir()
            tmp.rename(path / version.id)
            session.commit()
            print(f"  OK   {identity_dir.name}/{file_id} -> {version.id} ({file.name})")
    finally:
        session.close()
        engine.dispose()


def migrate(data_dir: Path) -> None:
    """Migrate every identity under *data_dir*."""
    for identity_dir in sorted(data_dir.iterdir()):
        if identity_dir.is_dir() and (identity_dir / "box.db").exists():
            print(f"Identity: {identity_dir.name}")
            migrate_identity(identity_dir)


def main() -> None:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("/data"),
        help="Root data directory (default: /data)",
    )
    args = parser.parse_args()
    migrate(args.data_dir)


if __name__ == "__main__":
    main()
