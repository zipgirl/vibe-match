"""Temporal offline replay over explicitly judged playlist impressions."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Literal, Mapping

from backend.app.catalog.models import Track
from backend.app.evaluation.metrics import ndcg_at_k, precision_at_k, recall_at_k
from backend.app.recommendations.baseline import recommend
from backend.app.recommendations.profile import liked_genre_weights

Judgment = Literal["like", "dislike", "skip"]


@dataclass(frozen=True, slots=True)
class EvaluationPlaylist:
    session_id: str
    sequence: int
    prompt: str
    candidate_track_ids: tuple[str, ...]
    judgments: Mapping[str, Judgment]


@dataclass(frozen=True, slots=True)
class ReplayMetrics:
    sessions_with_holdout: int
    evaluated_playlists: int
    explicit_judgments: int
    positive_judgments: int
    precision_at_k: float | None
    recall_at_k: float | None
    ndcg_at_k: float | None


def load_evaluation_playlists(connection: sqlite3.Connection) -> list[EvaluationPlaylist]:
    """Load saved slates and each item's latest explicit feedback state."""
    playlist_rows = connection.execute(
        """SELECT rowid AS sequence, playlist_id, session_id, prompt
           FROM playlists ORDER BY session_id, rowid"""
    ).fetchall()
    item_rows = connection.execute(
        """SELECT playlist_id, catalog_id FROM playlist_items ORDER BY playlist_id, rank"""
    ).fetchall()
    feedback_rows = connection.execute(
        """SELECT current.playlist_id, current.catalog_id, current.feedback_type
           FROM feedback_events AS current
           WHERE current.feedback_id = (
             SELECT MAX(previous.feedback_id)
             FROM feedback_events AS previous
             WHERE previous.playlist_id = current.playlist_id
               AND previous.catalog_id = current.catalog_id
           )"""
    ).fetchall()
    candidates: defaultdict[str, list[str]] = defaultdict(list)
    judgments: defaultdict[str, dict[str, Judgment]] = defaultdict(dict)
    for row in item_rows:
        candidates[row["playlist_id"]].append(row["catalog_id"])
    for row in feedback_rows:
        judgments[row["playlist_id"]][row["catalog_id"]] = row["feedback_type"]
    return [
        EvaluationPlaylist(
            session_id=row["session_id"],
            sequence=row["sequence"],
            prompt=row["prompt"],
            candidate_track_ids=tuple(candidates[row["playlist_id"]]),
            judgments=judgments[row["playlist_id"]],
        )
        for row in playlist_rows
    ]


def evaluate_temporal_replay(
    tracks: list[Track],
    playlists: list[EvaluationPlaylist],
    *,
    train_fraction: float = 0.7,
    k: int = 5,
) -> ReplayMetrics:
    """Evaluate later explicitly judged slate items using earlier likes only.

    Sessions are split independently by playlist insertion sequence. For each
    held-out playlist, the profile is built only from the session's training
    playlists. Unjudged and skipped candidates are excluded from the evaluated
    slate rather than being silently treated as negative feedback.
    """
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between 0 and 1")
    if k < 1:
        raise ValueError("k must be at least 1")
    tracks_by_id = {track.catalog_id: track for track in tracks}
    sessions: defaultdict[str, list[EvaluationPlaylist]] = defaultdict(list)
    for playlist in playlists:
        sessions[playlist.session_id].append(playlist)

    precision_values: list[float] = []
    recall_values: list[float] = []
    ndcg_values: list[float] = []
    explicit_count = 0
    positive_count = 0
    split_sessions = 0

    for session_playlists in sessions.values():
        ordered = sorted(session_playlists, key=lambda playlist: playlist.sequence)
        if len(ordered) < 2:
            continue
        train_size = min(len(ordered) - 1, max(1, int(len(ordered) * train_fraction)))
        training, held_out = ordered[:train_size], ordered[train_size:]
        split_sessions += 1
        last_action_by_track: dict[str, Judgment] = {}
        for playlist in training:
            for track_id, action in playlist.judgments.items():
                last_action_by_track[track_id] = action

        liked_ids = [track_id for track_id, action in last_action_by_track.items() if action == "like"]
        disliked_ids = [track_id for track_id, action in last_action_by_track.items() if action == "dislike"]
        profile = liked_genre_weights(tracks, liked_ids)

        for playlist in held_out:
            judged = {
                track_id: action
                for track_id, action in playlist.judgments.items()
                if action in {"like", "dislike"}
                and track_id in playlist.candidate_track_ids
                and track_id in tracks_by_id
            }
            relevant_ids = {track_id for track_id, action in judged.items() if action == "like"}
            if not judged or not relevant_ids:
                continue
            ranked = recommend(
                tracks,
                playlist.prompt,
                liked_genre_weights=profile,
                disliked_track_ids=disliked_ids,
                limit=len(tracks),
            )
            judged_set = set(judged)
            judged_ranking = [result.track.catalog_id for result in ranked if result.track.catalog_id in judged_set]
            precision_values.append(precision_at_k(judged_ranking, relevant_ids, k))
            recall_values.append(recall_at_k(judged_ranking, relevant_ids, k))
            ndcg_values.append(ndcg_at_k(judged_ranking, relevant_ids, k))
            explicit_count += len(judged)
            positive_count += len(relevant_ids)

    return ReplayMetrics(
        sessions_with_holdout=split_sessions,
        evaluated_playlists=len(precision_values),
        explicit_judgments=explicit_count,
        positive_judgments=positive_count,
        precision_at_k=mean(precision_values) if precision_values else None,
        recall_at_k=mean(recall_values) if recall_values else None,
        ndcg_at_k=mean(ndcg_values) if ndcg_values else None,
    )
