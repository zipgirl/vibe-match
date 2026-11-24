"""Generate a text-based playlist from the imported local catalog."""

import argparse
from pathlib import Path

from backend.app.catalog.database import connect, fetch_tracks
from .baseline import recommend


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/vibematch.sqlite"))
    parser.add_argument("--prompt", required=True, help="Text describing the desired sound or atmosphere")
    parser.add_argument("--preferred-genre", action="append", default=[], help="Preferred genre; repeatable")
    parser.add_argument("--disliked-track-id", action="append", default=[], help="Catalog ID to exclude; repeatable")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    with connect(args.db) as connection:
        tracks = fetch_tracks(connection)
    results = recommend(
        tracks,
        args.prompt,
        preferred_genres=args.preferred_genre,
        disliked_track_ids=args.disliked_track_id,
        limit=args.limit,
    )
    if not results:
        print("No eligible tracks found.")
        return
    for rank, result in enumerate(results, start=1):
        print(f"{rank}. {result.track.title} - {result.track.artist}")
        print(
            f"   score={result.score:.3f} "
            f"(content={result.content_similarity:.3f}, preferences={result.preference_match:.3f}, "
            f"liked-genres={result.liked_genre_match:.3f})"
        )
        for reason in result.reasons:
            print(f"   reason: {reason}")
        print(f"   source: {result.track.source_url}")


if __name__ == "__main__":
    main()
