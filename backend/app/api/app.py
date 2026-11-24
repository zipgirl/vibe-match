"""FastAPI endpoints for anonymous text-based playlist generation."""

from __future__ import annotations

import logging
import re
from io import BytesIO
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Generator, Literal

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from backend.app.catalog.database import connect, fetch_tracks, initialize_database
from backend.app.catalog.seed import seed_catalog_if_empty
from backend.app.inference.image_captioning import BlipLocalCaptioner, ImageModelUnavailable
from backend.app.playlists.repository import (
    ensure_session,
    get_disliked_track_ids,
    get_liked_track_ids,
    get_preferred_genres,
    save_feedback,
    save_playlist,
    save_preferred_genres,
)
from backend.app.recommendations.baseline import Recommendation, recommend
from backend.app.recommendations.profile import liked_genre_weights

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "tracks.csv"
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
LOGGER = logging.getLogger(__name__)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlaylistRequest(APIModel):
    session_id: str = Field(min_length=8, max_length=64)
    prompt: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class PreferenceRequest(APIModel):
    preferred_genres: list[str] = Field(default_factory=list, max_length=30)


class PreferenceResponse(APIModel):
    session_id: str
    preferred_genres: list[str]


class TrackRecommendation(APIModel):
    catalog_id: str
    title: str
    artist: str
    source_url: str
    license: str
    license_url: str
    genres: list[str]
    score: float
    content_similarity: float
    preference_match: float
    liked_genre_match: float
    reasons: list[str]


class PlaylistResponse(APIModel):
    playlist_id: str
    prompt: str
    recommendations: list[TrackRecommendation]


class FeedbackRequest(APIModel):
    session_id: str = Field(min_length=8, max_length=64)
    playlist_id: str = Field(min_length=1, max_length=64)
    catalog_id: str = Field(min_length=1, max_length=200)
    feedback_type: Literal["like", "dislike", "skip"]


class FeedbackResponse(APIModel):
    saved: bool


class HealthResponse(APIModel):
    status: Literal["ok"]


class ImageInterpretationResponse(APIModel):
    caption: str
    review_required: Literal[True] = True
    image_retained: Literal[False] = False
    model_id: str


def _validate_session_id(session_id: str) -> str:
    if not SESSION_PATTERN.fullmatch(session_id):
        raise HTTPException(status_code=422, detail="session_id must contain 8-64 letters, numbers, '_' or '-'")
    return session_id


def _track_recommendation(result: Recommendation) -> TrackRecommendation:
    track = result.track
    return TrackRecommendation(
        catalog_id=track.catalog_id,
        title=track.title,
        artist=track.artist,
        source_url=track.source_url,
        license=track.license,
        license_url=track.license_url,
        genres=list(track.genres),
        score=result.score,
        content_similarity=result.content_similarity,
        preference_match=result.preference_match,
        liked_genre_match=result.liked_genre_match,
        reasons=list(result.reasons),
    )


def create_app(
    database_path: str | Path,
    catalog_path: str | Path | None = None,
) -> FastAPI:
    """Create an app instance with explicit local database/catalog locations.

    On startup an empty database is seeded from the versioned catalog CSV so a
    fresh clone is usable without a manual import step.
    """
    db_path = Path(database_path)
    catalog_csv = Path(catalog_path) if catalog_path is not None else DEFAULT_CATALOG_PATH

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = connect(db_path)
        try:
            initialize_database(connection)
            seeded = seed_catalog_if_empty(connection, catalog_csv)
            if seeded:
                LOGGER.info("Seeded %s catalog tracks from %s", seeded, catalog_csv)
            yield
        finally:
            connection.close()

    app = FastAPI(title="VibeMatch API", version="0.2.0", lifespan=lifespan)
    app.state.database_path = db_path
    app.state.image_captioner = BlipLocalCaptioner()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    @contextmanager
    def database() -> Generator:
        # FastAPI can run sync dependencies and endpoints on different worker
        # threads, so this per-request connection must allow cross-thread use.
        connection = connect(db_path, check_same_thread=False)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get_database() -> Generator:
        with database() as connection:
            yield connection

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/api/v1/catalog/genres", response_model=list[str])
    def catalog_genres(connection=Depends(get_database)) -> list[str]:
        tracks = fetch_tracks(connection)
        return sorted({genre for track in tracks for genre in track.genres}, key=str.casefold)

    @app.get("/api/v1/preferences/{session_id}", response_model=PreferenceResponse)
    def preferences(session_id: str, connection=Depends(get_database)) -> PreferenceResponse:
        session_id = _validate_session_id(session_id)
        ensure_session(connection, session_id)
        return PreferenceResponse(
            session_id=session_id,
            preferred_genres=get_preferred_genres(connection, session_id),
        )

    @app.put("/api/v1/preferences/{session_id}", response_model=PreferenceResponse)
    def update_preferences(
        session_id: str,
        request: PreferenceRequest,
        connection=Depends(get_database),
    ) -> PreferenceResponse:
        session_id = _validate_session_id(session_id)
        tracks = fetch_tracks(connection)
        known_genres = {genre.casefold(): genre for track in tracks for genre in track.genres}
        unknown = [genre for genre in request.preferred_genres if genre.strip().casefold() not in known_genres]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown catalog genres: {', '.join(unknown)}")
        canonical = list(
            dict.fromkeys(known_genres[genre.strip().casefold()] for genre in request.preferred_genres)
        )
        save_preferred_genres(connection, session_id, canonical)
        return PreferenceResponse(session_id=session_id, preferred_genres=canonical)

    @app.post("/api/v1/playlists", response_model=PlaylistResponse)
    def create_playlist(request: PlaylistRequest, connection=Depends(get_database)) -> PlaylistResponse:
        session_id = _validate_session_id(request.session_id)
        prompt = request.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=422, detail="prompt must contain non-whitespace text")
        ensure_session(connection, session_id)
        tracks = fetch_tracks(connection)
        preferred_genres = get_preferred_genres(connection, session_id)
        disliked_track_ids = get_disliked_track_ids(connection, session_id)
        profile_weights = liked_genre_weights(tracks, get_liked_track_ids(connection, session_id))
        results = recommend(
            tracks,
            prompt,
            preferred_genres=preferred_genres,
            disliked_track_ids=disliked_track_ids,
            liked_genre_weights=profile_weights,
            limit=request.limit,
        )
        playlist_id = save_playlist(connection, session_id, prompt, results)
        return PlaylistResponse(
            playlist_id=playlist_id,
            prompt=prompt,
            recommendations=[_track_recommendation(result) for result in results],
        )

    @app.post("/api/v1/feedback", response_model=FeedbackResponse)
    def feedback(request: FeedbackRequest, connection=Depends(get_database)) -> FeedbackResponse:
        session_id = _validate_session_id(request.session_id)
        saved = save_feedback(
            connection,
            session_id,
            request.playlist_id,
            request.catalog_id,
            request.feedback_type,
        )
        if not saved:
            raise HTTPException(status_code=404, detail="Track was not part of this session's playlist")
        return FeedbackResponse(saved=True)

    @app.post("/api/v1/images/interpret", response_model=ImageInterpretationResponse)
    async def interpret_image(file: UploadFile = File(...)) -> ImageInterpretationResponse:
        max_bytes = 8 * 1024 * 1024
        if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            await file.close()
            raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image")
        try:
            contents = await file.read(max_bytes + 1)
        finally:
            await file.close()
        if len(contents) > max_bytes:
            raise HTTPException(status_code=413, detail="Image must be 8 MiB or smaller")
        try:
            with Image.open(BytesIO(contents)) as source_image:
                if source_image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(status_code=415, detail="Image contents must be JPEG, PNG, or WebP")
                width, height = source_image.size
                if width < 1 or height < 1 or width > 4096 or height > 4096 or width * height > 12_000_000:
                    raise HTTPException(status_code=413, detail="Image dimensions exceed the 4096px / 12 megapixel limit")
                source_image.load()
                image = ImageOps.exif_transpose(source_image).convert("RGB")
        except HTTPException:
            raise
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise HTTPException(status_code=422, detail="Could not decode a valid image") from error
        finally:
            contents = b""

        try:
            caption = await run_in_threadpool(app.state.image_captioner.caption, image)
        except ImageModelUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        finally:
            image.close()
        return ImageInterpretationResponse(caption=caption, model_id="Salesforce/blip-image-captioning-base")

    return app


app = create_app(PROJECT_ROOT / "data" / "vibematch.sqlite")
