from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.app import create_app
from backend.app.catalog.database import connect, initialize_database
from backend.app.catalog.loader import load_tracks_csv
from backend.app.catalog.seed import count_tracks, seed_catalog_if_empty

ROOT = Path(__file__).parents[1]
CATALOG = ROOT / "data" / "catalog" / "tracks.csv"


def test_startup_seeds_empty_database_from_catalog(tmp_path: Path) -> None:
    database_path = tmp_path / "seed.sqlite"
    with TestClient(create_app(database_path, CATALOG)) as client:
        genres = client.get("/api/v1/catalog/genres")
        assert genres.status_code == 200
        assert "Ambient" in genres.json()

    connection = connect(database_path)
    try:
        assert count_tracks(connection) == len(load_tracks_csv(CATALOG))
    finally:
        connection.close()


def test_seeding_is_skipped_when_tracks_already_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "existing.sqlite"
    connection = connect(database_path)
    try:
        initialize_database(connection)
        assert seed_catalog_if_empty(connection, CATALOG) > 0
        assert seed_catalog_if_empty(connection, CATALOG) == 0
    finally:
        connection.close()


def test_seed_reports_a_clear_error_when_catalog_is_missing(tmp_path: Path) -> None:
    connection = connect(tmp_path / "empty.sqlite")
    try:
        initialize_database(connection)
        with pytest.raises(FileNotFoundError, match="Catalog CSV not found"):
            seed_catalog_if_empty(connection, tmp_path / "missing.csv")
    finally:
        connection.close()
