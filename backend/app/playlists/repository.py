"""SQLite persistence for anonymous preferences, playlists, and feedback."""

from __future__ import annotations

import json
from uuid import uuid4

import sqlite3

from backend.app.recommendations.baseline import Recommendation


def ensure_session(connection: sqlite3.Connection, session_id: str) -> None:
    connection.execute("INSERT OR IGNORE INTO anonymous_sessions(session_id) VALUES (?)", (session_id,))


def get_preferred_genres(connection: sqlite3.Connection, session_id: str) -> list[str]:
    row = connection.execute(
        "SELECT preferred_genres_json FROM preferences WHERE session_id = ?", (session_id,)
    ).fetchone()
    return json.loads(row["preferred_genres_json"]) if row else []


def save_preferred_genres(
    connection: sqlite3.Connection,
    session_id: str,
    preferred_genres: list[str],
) -> None:
    ensure_session(connection, session_id)
    connection.execute(
        """INSERT INTO preferences(session_id, preferred_genres_json, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(session_id) DO UPDATE SET
             preferred_genres_json=excluded.preferred_genres_json,
             updated_at=CURRENT_TIMESTAMP""",
        (session_id, json.dumps(preferred_genres, ensure_ascii=False)),
    )


def get_disliked_track_ids(connection: sqlite3.Connection, session_id: str) -> list[str]:
    rows = connection.execute(
        """SELECT current.catalog_id
           FROM feedback_events AS current
           WHERE current.session_id = ?
             AND current.feedback_id = (
               SELECT MAX(previous.feedback_id)
               FROM feedback_events AS previous
               WHERE previous.session_id = current.session_id
                 AND previous.catalog_id = current.catalog_id
             )
             AND current.feedback_type = 'dislike'
           ORDER BY current.catalog_id""",
        (session_id,),
    ).fetchall()
    return [row["catalog_id"] for row in rows]


def get_liked_track_ids(connection: sqlite3.Connection, session_id: str) -> list[str]:
    rows = connection.execute(
        """SELECT current.catalog_id
           FROM feedback_events AS current
           WHERE current.session_id = ?
             AND current.feedback_id = (
               SELECT MAX(previous.feedback_id)
               FROM feedback_events AS previous
               WHERE previous.session_id = current.session_id
                 AND previous.catalog_id = current.catalog_id
             )
             AND current.feedback_type = 'like'
           ORDER BY current.catalog_id""",
        (session_id,),
    ).fetchall()
    return [row["catalog_id"] for row in rows]


def save_playlist(
    connection: sqlite3.Connection,
    session_id: str,
    prompt: str,
    recommendations: list[Recommendation],
) -> str:
    playlist_id = str(uuid4())
    ensure_session(connection, session_id)
    connection.execute(
        "INSERT INTO playlists(playlist_id, session_id, prompt) VALUES (?, ?, ?)",
        (playlist_id, session_id, prompt),
    )
    for rank, recommendation in enumerate(recommendations, start=1):
        connection.execute(
            """INSERT INTO playlist_items
               (playlist_id, rank, catalog_id, score, content_similarity, preference_match,
                liked_genre_match, reasons_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                playlist_id,
                rank,
                recommendation.track.catalog_id,
                recommendation.score,
                recommendation.content_similarity,
                recommendation.preference_match,
                recommendation.liked_genre_match,
                json.dumps(recommendation.reasons, ensure_ascii=False),
            ),
        )
    return playlist_id


def save_feedback(
    connection: sqlite3.Connection,
    session_id: str,
    playlist_id: str,
    catalog_id: str,
    feedback_type: str,
) -> bool:
    """Save feedback only for a track shown in that user's playlist."""
    row = connection.execute(
        """SELECT 1 FROM playlist_items item
           JOIN playlists playlist ON playlist.playlist_id = item.playlist_id
           WHERE item.playlist_id = ? AND item.catalog_id = ? AND playlist.session_id = ?""",
        (playlist_id, catalog_id, session_id),
    ).fetchone()
    if row is None:
        return False
    connection.execute(
        """INSERT INTO feedback_events(session_id, playlist_id, catalog_id, feedback_type)
           VALUES (?, ?, ?, ?)""",
        (session_id, playlist_id, catalog_id, feedback_type),
    )
    return True
