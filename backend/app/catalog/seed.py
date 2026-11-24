"""Seed an empty runtime database from the versioned application catalog."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .database import import_tracks
from .loader import load_tracks_csv


def count_tracks(connection: sqlite3.Connection) -> int:
    """Return the number of catalog tracks currently stored."""
    return int(connection.execute("SELECT COUNT(*) FROM tracks").fetchone()[0])


def seed_catalog_if_empty(
    connection: sqlite3.Connection,
    catalog_path: str | Path,
) -> int:
    """Import the checked-in catalog only when the database has no tracks.

    Returns the number of imported records, or zero when seeding is skipped.
    Existing databases are left untouched so local sessions and feedback are
    never replaced by a startup import.
    """
    if count_tracks(connection) > 0:
        return 0
    path = Path(catalog_path)
    if not path.is_file():
        raise FileNotFoundError(f"Catalog CSV not found: {path}")
    return import_tracks(connection, load_tracks_csv(path))
