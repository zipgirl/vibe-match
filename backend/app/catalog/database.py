"""SQLite schema and idempotent catalog import operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Track

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS tracks (
    catalog_id TEXT PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    source_track_id TEXT NOT NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    source_url TEXT NOT NULL,
    license TEXT NOT NULL,
    license_url TEXT NOT NULL,
    instrumental INTEGER NOT NULL CHECK (instrumental IN (0, 1)),
    source_checked_on TEXT NOT NULL,
    UNIQUE (source_id, source_track_id)
);
CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS track_genres (
    catalog_id TEXT NOT NULL REFERENCES tracks(catalog_id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id),
    PRIMARY KEY (catalog_id, genre_id)
);
CREATE TABLE IF NOT EXISTS anonymous_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS preferences (
    session_id TEXT PRIMARY KEY REFERENCES anonymous_sessions(session_id) ON DELETE CASCADE,
    preferred_genres_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES anonymous_sessions(session_id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id TEXT NOT NULL REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    rank INTEGER NOT NULL CHECK (rank > 0),
    catalog_id TEXT NOT NULL REFERENCES tracks(catalog_id),
    score REAL NOT NULL,
    content_similarity REAL NOT NULL,
    preference_match REAL NOT NULL,
    liked_genre_match REAL NOT NULL DEFAULT 0,
    reasons_json TEXT NOT NULL,
    PRIMARY KEY (playlist_id, rank),
    UNIQUE (playlist_id, catalog_id)
);
CREATE TABLE IF NOT EXISTS feedback_events (
    feedback_id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES anonymous_sessions(session_id) ON DELETE CASCADE,
    playlist_id TEXT NOT NULL REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    catalog_id TEXT NOT NULL REFERENCES tracks(catalog_id),
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('like', 'dislike', 'skip')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(
    database_path: str | Path,
    *,
    check_same_thread: bool = True,
) -> sqlite3.Connection:
    """Open a SQLite connection with named rows and foreign keys enabled.

    API request dependencies may hand a connection between worker threads, so
    the app opts out of SQLite's thread check for its per-request connections.
    """
    connection = sqlite3.connect(database_path, check_same_thread=check_same_thread)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    playlist_columns = {row["name"] for row in connection.execute("PRAGMA table_info(playlist_items)")}
    if "liked_genre_match" not in playlist_columns:
        connection.execute(
            "ALTER TABLE playlist_items ADD COLUMN liked_genre_match REAL NOT NULL DEFAULT 0"
        )


def import_tracks(connection: sqlite3.Connection, tracks: Iterable[Track]) -> int:
    """Upsert the supplied records atomically; return the number of tracks."""
    records = list(tracks)
    with connection:
        for track in records:
            connection.execute("INSERT OR IGNORE INTO sources(name) VALUES (?)", (track.source_name,))
            source_id = connection.execute(
                "SELECT id FROM sources WHERE name = ?", (track.source_name,)
            ).fetchone()["id"]
            connection.execute(
                """INSERT INTO tracks
                   (catalog_id, source_id, source_track_id, title, artist, source_url,
                    license, license_url, instrumental, source_checked_on)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(catalog_id) DO UPDATE SET
                     source_id=excluded.source_id, source_track_id=excluded.source_track_id,
                     title=excluded.title, artist=excluded.artist, source_url=excluded.source_url,
                     license=excluded.license, license_url=excluded.license_url,
                     instrumental=excluded.instrumental, source_checked_on=excluded.source_checked_on""",
                (
                    track.catalog_id,
                    source_id,
                    track.source_track_id,
                    track.title,
                    track.artist,
                    track.source_url,
                    track.license,
                    track.license_url,
                    int(track.instrumental),
                    track.source_checked_on,
                ),
            )
            connection.execute("DELETE FROM track_genres WHERE catalog_id = ?", (track.catalog_id,))
            for genre in track.genres:
                connection.execute("INSERT OR IGNORE INTO genres(name) VALUES (?)", (genre,))
                genre_id = connection.execute("SELECT id FROM genres WHERE name = ?", (genre,)).fetchone()["id"]
                connection.execute(
                    "INSERT INTO track_genres(catalog_id, genre_id) VALUES (?, ?)",
                    (track.catalog_id, genre_id),
                )
    return len(records)


def fetch_tracks(connection: sqlite3.Connection) -> list[Track]:
    """Return tracks and their genre metadata in stable catalog-ID order."""
    rows = connection.execute(
        """SELECT t.*, s.name AS source_name,
                  GROUP_CONCAT(g.name, '|') AS genres
           FROM tracks t
           JOIN sources s ON s.id = t.source_id
           JOIN track_genres tg ON tg.catalog_id = t.catalog_id
           JOIN genres g ON g.id = tg.genre_id
           GROUP BY t.catalog_id ORDER BY t.catalog_id"""
    ).fetchall()
    return [
        Track(
            catalog_id=row["catalog_id"], title=row["title"], artist=row["artist"],
            source_name=row["source_name"], source_track_id=row["source_track_id"],
            source_url=row["source_url"], license=row["license"], license_url=row["license_url"],
            genres=tuple(row["genres"].split("|")), instrumental=bool(row["instrumental"]),
            source_checked_on=row["source_checked_on"],
        )
        for row in rows
    ]
