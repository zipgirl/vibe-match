"""Import the checked-in application catalog into a local SQLite database."""

import argparse
from pathlib import Path

from .database import connect, import_tracks, initialize_database
from .loader import load_tracks_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("data/catalog/tracks.csv"))
    parser.add_argument("--db", type=Path, default=Path("data/vibematch.sqlite"))
    args = parser.parse_args()
    tracks = load_tracks_csv(args.csv)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with connect(args.db) as connection:
        initialize_database(connection)
        count = import_tracks(connection, tracks)
    print(f"Imported {count} catalog records into {args.db}")


if __name__ == "__main__":
    main()
