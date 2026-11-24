from __future__ import annotations

import sqlite3

import pytest

from backend.app.catalog.database import import_tracks, initialize_database
from backend.app.catalog.models import Track
from backend.app.evaluation.feedback_replay import (
    EvaluationPlaylist,
    evaluate_temporal_replay,
    load_evaluation_playlists,
)
from backend.app.playlists.repository import ensure_session, save_feedback, save_playlist
from backend.app.recommendations.baseline import recommend


def fixture_tracks() -> list[Track]:
    return [
        Track("jazz", "Late Set", "Artist A", "Fixture", "jazz", "https://example.org/jazz", "CC0 1.0 Universal", "https://creativecommons.org/publicdomain/zero/1.0/", ("Jazz", "Instrumental"), True, "2026-11-21"),
        Track("ambient", "Still Waters", "Artist B", "Fixture", "ambient", "https://example.org/ambient", "CC0 1.0 Universal", "https://creativecommons.org/publicdomain/zero/1.0/", ("Ambient",), True, "2026-11-21"),
        Track("folk", "Open Road", "Artist C", "Fixture", "folk", "https://example.org/folk", "CC0 1.0 Universal", "https://creativecommons.org/publicdomain/zero/1.0/", ("Folk",), True, "2026-11-21"),
    ]


def test_temporal_replay_uses_prior_likes_and_only_explicit_test_judgments() -> None:
    tracks = fixture_tracks()
    playlists = [
        EvaluationPlaylist("session-1234", 1, "anything", ("jazz", "ambient"), {"jazz": "like"}),
        EvaluationPlaylist("session-1234", 2, "unmatched", ("jazz", "ambient", "folk"), {"jazz": "like", "ambient": "dislike", "folk": "skip"}),
        EvaluationPlaylist("short-1234", 1, "ambient", ("ambient",), {"ambient": "like"}),
    ]
    report = evaluate_temporal_replay(tracks, playlists, train_fraction=0.5, k=2)
    assert report.sessions_with_holdout == 1
    assert report.evaluated_playlists == 1
    assert report.explicit_judgments == 2
    assert report.positive_judgments == 1
    assert report.precision_at_k == pytest.approx(0.5)
    assert report.recall_at_k == pytest.approx(1.0)
    assert report.ndcg_at_k == pytest.approx(1.0)


def test_replay_reports_no_metrics_without_temporal_or_positive_labels() -> None:
    report = evaluate_temporal_replay(
        fixture_tracks(),
        [EvaluationPlaylist("session-1234", 1, "ambient", ("ambient",), {"ambient": "like"})],
    )
    assert report.evaluated_playlists == 0
    assert report.precision_at_k is None
    assert report.recall_at_k is None
    assert report.ndcg_at_k is None


def test_database_loader_uses_latest_feedback_event() -> None:
    tracks = fixture_tracks()
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_database(connection)
    import_tracks(connection, tracks)
    ensure_session(connection, "session-1234")
    results = recommend(tracks, "jazz", limit=2)
    playlist_id = save_playlist(connection, "session-1234", "jazz", results)
    jazz_id = next(result.track.catalog_id for result in results if result.track.catalog_id == "jazz")
    assert save_feedback(connection, "session-1234", playlist_id, jazz_id, "like")
    assert save_feedback(connection, "session-1234", playlist_id, jazz_id, "dislike")

    loaded = load_evaluation_playlists(connection)
    assert len(loaded) == 1
    assert loaded[0].judgments[jazz_id] == "dislike"


def test_replay_validates_split_and_cutoff() -> None:
    with pytest.raises(ValueError, match="train_fraction"):
        evaluate_temporal_replay(fixture_tracks(), [], train_fraction=1.0)
    with pytest.raises(ValueError, match="k"):
        evaluate_temporal_replay(fixture_tracks(), [], k=0)
