"""Explicit-feedback genre profile feature engineering."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from backend.app.catalog.models import Track


def liked_genre_weights(tracks: Iterable[Track], liked_track_ids: Iterable[str]) -> dict[str, float]:
    """Build normalized genre weights; each liked track contributes one unit total."""
    by_id = {track.catalog_id: track for track in tracks}
    weights: defaultdict[str, float] = defaultdict(float)
    for track_id in set(liked_track_ids):
        track = by_id.get(track_id)
        if track is None or not track.genres:
            continue
        per_genre_weight = 1.0 / len(track.genres)
        for genre in track.genres:
            weights[genre.casefold()] += per_genre_weight
    total = sum(weights.values())
    return {genre: weight / total for genre, weight in sorted(weights.items())} if total else {}
