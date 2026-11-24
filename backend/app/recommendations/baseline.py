"""A transparent TF-IDF content retrieval baseline over track metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.app.catalog.models import Track

PREFERENCE_WEIGHT = 0.2
LIKED_PROFILE_WEIGHT = 0.2


@dataclass(frozen=True, slots=True)
class Recommendation:
    track: Track
    score: float
    content_similarity: float
    preference_match: float
    liked_genre_match: float
    reasons: tuple[str, ...]


def _metadata_text(track: Track) -> str:
    """Use descriptive catalog fields only; artist is omitted to avoid artist-name bias."""
    return " ".join((track.title, *track.genres))


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[\w'-]+", text, flags=re.UNICODE) if len(token) > 1}


def _explanation(
    track: Track,
    query: str,
    preferences: set[str],
    preference_match: float,
    liked_profile: Mapping[str, float],
) -> tuple[str, ...]:
    query_tokens = _tokens(query)
    matched_genres = [genre for genre in track.genres if _tokens(genre) & query_tokens]
    reasons: list[str] = []
    if matched_genres:
        reasons.append("Matches catalog genres: " + ", ".join(matched_genres))
    if _tokens(track.title) & query_tokens:
        reasons.append(f"Query terms appear in the title: {track.title}")
    preferred_matches = [genre for genre in track.genres if genre.casefold() in preferences]
    if preferred_matches:
        reasons.append("Matches preferred genres: " + ", ".join(preferred_matches))
    liked_matches = [genre for genre in track.genres if liked_profile.get(genre.casefold(), 0.0) > 0]
    if liked_matches:
        reasons.append("Matches genres from tracks you liked: " + ", ".join(liked_matches))
    if not reasons:
        if preference_match:
            reasons.append("Matches a selected genre preference")
        elif not query.strip():
            reasons.append("No descriptive prompt was supplied; ranked by selected genre preferences")
        else:
            reasons.append("No query terms matched this track's catalog metadata; shown as a fallback")
    return tuple(reasons)


def recommend(
    tracks: Iterable[Track],
    prompt: str,
    *,
    preferred_genres: Iterable[str] = (),
    disliked_track_ids: Iterable[str] = (),
    liked_genre_weights: Mapping[str, float] | None = None,
    limit: int = 10,
) -> list[Recommendation]:
    """Rank eligible tracks using cosine similarity plus explicit genre preference.

    Content similarity is TF-IDF cosine similarity between the prompt and each
    track's title/genre text. Preference match is the fraction of selected
    genres present on the track, weighted by ``PREFERENCE_WEIGHT``. A separate
    normalized liked-track genre profile is weighted by ``LIKED_PROFILE_WEIGHT``.
    Disliked tracks are excluded. Ties are resolved by catalog ID.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    catalog = sorted(list(tracks), key=lambda track: track.catalog_id)
    if not catalog:
        return []

    preferences = {genre.strip().casefold() for genre in preferred_genres if genre.strip()}
    profile = {
        genre.strip().casefold(): max(0.0, float(weight))
        for genre, weight in (liked_genre_weights or {}).items()
        if genre.strip()
    }
    profile_total = sum(profile.values())
    if profile_total:
        profile = {genre: weight / profile_total for genre, weight in profile.items()}
    disliked = set(disliked_track_ids)
    eligible = [track for track in catalog if track.catalog_id not in disliked]
    if not eligible:
        return []

    documents = [_metadata_text(track) for track in eligible]
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), token_pattern=r"(?u)\b[\w'-]+\b")
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError as error:
        if "empty vocabulary" not in str(error):
            raise
        similarities = [0.0] * len(eligible)
    else:
        query_vector = vectorizer.transform([prompt.strip()])
        similarities = cosine_similarity(query_vector, matrix).ravel().tolist()

    ranked: list[Recommendation] = []
    for track, similarity in zip(eligible, similarities, strict=True):
        preference_match = (
            sum(genre.casefold() in preferences for genre in track.genres) / len(preferences)
            if preferences
            else 0.0
        )
        liked_genre_match = sum(profile.get(genre.casefold(), 0.0) for genre in track.genres)
        score = (
            float(similarity)
            + PREFERENCE_WEIGHT * preference_match
            + LIKED_PROFILE_WEIGHT * liked_genre_match
        )
        ranked.append(
            Recommendation(
                track=track,
                score=score,
                content_similarity=float(similarity),
                preference_match=preference_match,
                liked_genre_match=liked_genre_match,
                reasons=_explanation(track, prompt, preferences, preference_match, profile),
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.track.catalog_id))
    return ranked[:limit]
