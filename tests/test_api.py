from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api.app import create_app
from backend.app.catalog.database import connect, import_tracks, initialize_database
from backend.app.catalog.loader import load_tracks_csv

ROOT = Path(__file__).parents[1]
CATALOG = ROOT / "data" / "catalog" / "tracks.csv"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_path = tmp_path / "api.sqlite"
    connection = connect(database_path)
    try:
        with connection:
            initialize_database(connection)
            import_tracks(connection, load_tracks_csv(CATALOG))
    finally:
        connection.close()
    with TestClient(create_app(database_path)) as test_client:
        yield test_client


def test_text_playlist_preferences_and_feedback_round_trip(client: TestClient) -> None:
    session_id = "session-1234"
    assert client.get("/api/v1/health").json() == {"status": "ok"}

    genres = client.get("/api/v1/catalog/genres").json()
    assert "Ambient" in genres
    response = client.put(
        f"/api/v1/preferences/{session_id}",
        json={"preferred_genres": ["ambient", "Jazz"]},
    )
    assert response.status_code == 200
    assert response.json()["preferred_genres"] == ["Ambient", "Jazz"]

    playlist = client.post(
        "/api/v1/playlists",
        json={"session_id": session_id, "prompt": "ambient electronic", "limit": 3},
    )
    assert playlist.status_code == 200
    playlist_data = playlist.json()
    assert playlist_data["recommendations"][0]["title"] == "An Ocean in Outer Space"
    assert playlist_data["recommendations"][0]["reasons"]
    track_id = playlist_data["recommendations"][0]["catalog_id"]

    feedback = client.post(
        "/api/v1/feedback",
        json={
            "session_id": session_id,
            "playlist_id": playlist_data["playlist_id"],
            "catalog_id": track_id,
            "feedback_type": "dislike",
        },
    )
    assert feedback.status_code == 200

    regenerated = client.post(
        "/api/v1/playlists",
        json={"session_id": session_id, "prompt": "ambient electronic", "limit": 4},
    )
    assert regenerated.status_code == 200
    assert all(item["catalog_id"] != track_id for item in regenerated.json()["recommendations"])

    restored_feedback = client.post(
        "/api/v1/feedback",
        json={
            "session_id": session_id,
            "playlist_id": playlist_data["playlist_id"],
            "catalog_id": track_id,
            "feedback_type": "like",
        },
    )
    assert restored_feedback.status_code == 200
    restored = client.post(
        "/api/v1/playlists",
        json={"session_id": session_id, "prompt": "ambient electronic", "limit": 4},
    )
    assert any(item["catalog_id"] == track_id for item in restored.json()["recommendations"])
    liked_track = next(item for item in restored.json()["recommendations"] if item["catalog_id"] == track_id)
    assert liked_track["liked_genre_match"] > 0


def test_api_rejects_unknown_preferences_and_feedback_for_unseen_track(client: TestClient) -> None:
    session_id = "session-5678"
    unknown = client.put(
        f"/api/v1/preferences/{session_id}",
        json={"preferred_genres": ["Imaginary Genre"]},
    )
    assert unknown.status_code == 422

    playlist = client.post(
        "/api/v1/playlists",
        json={"session_id": session_id, "prompt": "jazz", "limit": 2},
    ).json()
    bad_feedback = client.post(
        "/api/v1/feedback",
        json={
            "session_id": session_id,
            "playlist_id": playlist["playlist_id"],
            "catalog_id": "not-in-this-playlist",
            "feedback_type": "like",
        },
    )
    assert bad_feedback.status_code == 404

    whitespace_prompt = client.post(
        "/api/v1/playlists",
        json={"session_id": session_id, "prompt": "   "},
    )
    assert whitespace_prompt.status_code == 422


def test_image_interpretation_uses_captioner_and_retains_no_image(client: TestClient) -> None:
    class FakeCaptioner:
        def caption(self, image: Image.Image) -> str:
            assert image.mode == "RGB"
            assert image.size == (16, 12)
            return "A quiet lake under a cloudy sky"

    client.app.state.image_captioner = FakeCaptioner()
    image_bytes = BytesIO()
    Image.new("RGB", (16, 12), color="navy").save(image_bytes, format="PNG")
    result = client.post(
        "/api/v1/images/interpret",
        files={"file": ("scene.png", image_bytes.getvalue(), "image/png")},
    )
    assert result.status_code == 200
    assert result.json() == {
        "caption": "A quiet lake under a cloudy sky",
        "review_required": True,
        "image_retained": False,
        "model_id": "Salesforce/blip-image-captioning-base",
    }

    rejected = client.post(
        "/api/v1/images/interpret",
        files={"file": ("not-image.txt", b"not image data", "text/plain")},
    )
    assert rejected.status_code == 415
