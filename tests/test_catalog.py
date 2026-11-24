from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from backend.app.catalog.database import fetch_tracks, import_tracks, initialize_database
from backend.app.catalog.loader import load_tracks_csv
from backend.app.catalog.models import CatalogValidationError

CATALOG = Path(__file__).parents[1] / "data" / "catalog" / "tracks.csv"


def test_checked_in_catalog_loads_with_provenance() -> None:
    tracks = load_tracks_csv(CATALOG)
    assert len(tracks) == 4
    assert all(track.source_url.startswith("https://") for track in tracks)
    assert all(track.license == "CC0 1.0 Universal" for track in tracks)
    assert all(track.genres for track in tracks)


def test_catalog_rejects_unapproved_license() -> None:
    with CATALOG.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    rows[0]["license"] = "CC BY-NC-ND"
    with TemporaryDirectory(prefix="vibematch-catalog-test-", dir=CATALOG.parents[2]) as directory:
        invalid_catalog = Path(directory) / "invalid.csv"
        with invalid_catalog.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        with pytest.raises(CatalogValidationError, match="not approved"):
            load_tracks_csv(invalid_catalog)


def test_sqlite_import_is_idempotent_and_round_trips_genres() -> None:
    tracks = load_tracks_csv(CATALOG)
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_database(connection)
    assert import_tracks(connection, tracks) == 4
    assert import_tracks(connection, tracks) == 4
    restored = fetch_tracks(connection)
    assert len(restored) == 4
    assert {track.catalog_id for track in restored} == {track.catalog_id for track in tracks}
    assert {track.title: track.genres for track in restored} == {
        track.title: track.genres for track in tracks
    }
