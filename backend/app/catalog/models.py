"""Typed records used by catalog ingestion and recommendation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Track:
    catalog_id: str
    title: str
    artist: str
    source_name: str
    source_track_id: str
    source_url: str
    license: str
    license_url: str
    genres: tuple[str, ...]
    instrumental: bool
    source_checked_on: str


class CatalogValidationError(ValueError):
    """Raised when catalog input is incomplete or fails eligibility checks."""
