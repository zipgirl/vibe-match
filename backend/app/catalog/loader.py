"""Load and validate the versioned CSV application catalog."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .models import CatalogValidationError, Track

REQUIRED_COLUMNS = {
    "catalog_id",
    "title",
    "artist",
    "source_name",
    "source_track_id",
    "source_url",
    "license",
    "license_url",
    "genres",
    "instrumental",
    "source_checked_on",
}
ALLOWED_MVP_LICENSES = {"CC0 1.0 Universal"}


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _parse_bool(value: str, field: str) -> bool:
    normalized = value.strip().casefold()
    if normalized not in {"true", "false"}:
        raise CatalogValidationError(f"{field} must be 'true' or 'false', got {value!r}")
    return normalized == "true"


def load_tracks_csv(path: str | Path) -> list[Track]:
    """Read CSV rows, normalize whitespace, and reject ineligible records."""
    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        raise CatalogValidationError(f"Missing required columns: {', '.join(sorted(missing_columns))}")

    records: list[Track] = []
    seen_ids: set[str] = set()
    problems: list[str] = []
    for row_number, row in enumerate(frame.to_dict(orient="records"), start=2):
        values = {key: str(row[key]).strip() for key in REQUIRED_COLUMNS}
        blank = [key for key, value in values.items() if not value]
        if blank:
            problems.append(f"row {row_number}: empty fields {', '.join(sorted(blank))}")
            continue
        if values["catalog_id"] in seen_ids:
            problems.append(f"row {row_number}: duplicate catalog_id {values['catalog_id']!r}")
            continue
        seen_ids.add(values["catalog_id"])
        if values["license"] not in ALLOWED_MVP_LICENSES:
            problems.append(f"row {row_number}: license is not approved by the MVP catalog policy")
            continue
        if not _valid_http_url(values["source_url"]) or not _valid_http_url(values["license_url"]):
            problems.append(f"row {row_number}: source_url and license_url must be HTTP(S) URLs")
            continue
        try:
            checked_date = date.fromisoformat(values["source_checked_on"])
            instrumental = _parse_bool(values["instrumental"], "instrumental")
        except (ValueError, CatalogValidationError) as error:
            problems.append(f"row {row_number}: {error}")
            continue

        genres = tuple(dict.fromkeys(part.strip() for part in values["genres"].split("|") if part.strip()))
        if not genres:
            problems.append(f"row {row_number}: at least one genre is required")
            continue
        records.append(
            Track(
                catalog_id=values["catalog_id"],
                title=values["title"],
                artist=values["artist"],
                source_name=values["source_name"],
                source_track_id=values["source_track_id"].strip("/"),
                source_url=values["source_url"],
                license=values["license"],
                license_url=values["license_url"],
                genres=genres,
                instrumental=instrumental,
                source_checked_on=checked_date.isoformat(),
            )
        )

    if problems:
        raise CatalogValidationError("Catalog validation failed:\n" + "\n".join(problems))
    if not records:
        raise CatalogValidationError("Catalog contains no track records")
    return records
