from __future__ import annotations

import pytest

from backend.app.catalog.models import Track
from backend.app.recommendations.baseline import recommend
from backend.app.recommendations.profile import liked_genre_weights


def track(catalog_id: str, title: str, genres: tuple[str, ...]) -> Track:
    return Track(
        catalog_id=catalog_id,
        title=title,
        artist="Example Artist",
        source_name="Test Fixture",
        source_track_id=catalog_id,
        source_url="https://example.org/tracks/" + catalog_id,
        license="CC0 1.0 Universal",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        genres=genres,
        instrumental=True,
        source_checked_on="2026-11-21",
    )


@pytest.fixture
def tracks() -> list[Track]:
    return [
        track("ambient", "Soft Horizon", ("Ambient", "Electronic")),
        track("jazz", "Late Set", ("Jazz", "Instrumental")),
        track("folk", "Open Road", ("Folk", "Acoustic")),
    ]


def test_lexical_match_ranks_matching_genre_and_explains_it(tracks: list[Track]) -> None:
    results = recommend(tracks, "ambient electronic", limit=3)
    assert results[0].track.catalog_id == "ambient"
    assert results[0].content_similarity > results[1].content_similarity
    assert any("Ambient" in reason for reason in results[0].reasons)


def test_preferred_genre_adds_documented_score_component(tracks: list[Track]) -> None:
    results = recommend(tracks, "unmatched prompt", preferred_genres=["Jazz"], limit=3)
    jazz = next(result for result in results if result.track.catalog_id == "jazz")
    folk = next(result for result in results if result.track.catalog_id == "folk")
    assert jazz.preference_match == 1.0
    assert jazz.score == pytest.approx(0.2)
    assert jazz.score > folk.score
    assert any("preferred genres: Jazz" in reason for reason in jazz.reasons)


def test_disliked_tracks_are_excluded_and_ties_are_stable(tracks: list[Track]) -> None:
    first = recommend(tracks, "unknown word", disliked_track_ids=["ambient"], limit=5)
    second = recommend(list(reversed(tracks)), "unknown word", disliked_track_ids=["ambient"], limit=5)
    assert [result.track.catalog_id for result in first] == ["folk", "jazz"]
    assert [result.track.catalog_id for result in first] == [result.track.catalog_id for result in second]
    assert "fallback" in first[0].reasons[0]


def test_liked_track_genres_form_a_normalized_profile(tracks: list[Track]) -> None:
    profile = liked_genre_weights(tracks, ["ambient", "jazz", "unknown-id"])
    assert sum(profile.values()) == pytest.approx(1.0)
    results = recommend(tracks, "unmatched prompt", liked_genre_weights=profile, limit=3)
    jazz = next(result for result in results if result.track.catalog_id == "jazz")
    folk = next(result for result in results if result.track.catalog_id == "folk")
    assert jazz.liked_genre_match > 0
    assert jazz.score > folk.score
    assert any("genres from tracks you liked" in reason for reason in jazz.reasons)


def test_empty_catalog_and_invalid_limit(tracks: list[Track]) -> None:
    assert recommend([], "ambient") == []
    with pytest.raises(ValueError, match="limit"):
        recommend(tracks, "ambient", limit=0)
