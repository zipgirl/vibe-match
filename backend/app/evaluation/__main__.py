"""Run a chronological replay over explicit user judgments in a SQLite database."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from backend.app.catalog.database import connect, fetch_tracks
from .feedback_replay import evaluate_temporal_replay, load_evaluation_playlists


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/vibematch.sqlite"))
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    with connect(args.db) as connection:
        tracks = fetch_tracks(connection)
        playlists = load_evaluation_playlists(connection)
    report = evaluate_temporal_replay(
        tracks,
        playlists,
        train_fraction=args.train_fraction,
        k=args.k,
    )
    print(json.dumps(asdict(report), indent=2))
    if report.evaluated_playlists == 0:
        print("No metrics produced: collect explicit feedback across at least two playlists per session.")


if __name__ == "__main__":
    main()
