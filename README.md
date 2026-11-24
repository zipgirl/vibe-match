# VibeMatch

Anonymous multimodal playlist matching. The current MVP includes a small provenance-aware music catalog, a text-based recommendation baseline, optional local image captioning, explicit-feedback personalization, a FastAPI backend, and a React interface. It links to external listening pages; it does not host audio.

## Local setup

Python 3.10 or newer is recommended. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Install frontend dependencies from the frontend directory with `npm ci`.

Image captioning is optional. To enable it, install a CPU-only PyTorch build and the optional Transformers dependency:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-image.txt
```

The BLIP weights download and cache on the first image request. The text flow works without this optional model. See [image-assisted matching](docs/architecture/multimodal-image-flow.md).

## Import the application catalog

```powershell
python -m backend.app.catalog --csv data/catalog/tracks.csv --db data/vibematch.sqlite
```

The import validates required provenance fields and the current MVP license allowlist before writing records. Re-running it updates matching catalog IDs. SQLite database files are local runtime artifacts and are ignored by Git.

## Generate a text playlist

```powershell
python -m backend.app.recommendations --db data/vibematch.sqlite --prompt "ambient, electronic, and calm" --preferred-genre Ambient --limit 5
```

The output includes ranking score components, metadata-based reasons, and source links. With the tiny initial catalog, a prompt may yield zero lexical similarity; such fallback items are labeled as such. This baseline matches terms and is not semantic mood understanding.

## Run the API and web app

Import the catalog once, then start the API in one terminal:

```powershell
python -m uvicorn backend.app.api.app:app --reload --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local Vite URL printed in the terminal. The browser stores only a random anonymous session identifier in local storage. Preferences and feedback are stored in the local SQLite database. Disliked tracks are excluded from later playlists; liked tracks contribute their genres to the session profile; a later like or skip clears a prior dislike. Image captions must be reviewed and edited before playlist generation.

## Validate

```powershell
python -m pytest -q
```

From `frontend/`, run `npm test` and `npm run build` for UI tests and a production build.

To calculate offline metrics after sessions have feedback across multiple chronological playlists, run:

```powershell
python -m backend.app.evaluation --db data/vibematch.sqlite --train-fraction 0.7 --k 5
```

The replay reports no metric (rather than a fabricated zero) when there are not enough explicit labels. It evaluates only explicitly liked/disliked items from held-out playlist slates; skips and unjudged tracks are not treated as negatives.

See [catalog provenance and selection](data/catalog/README.md), [source policy](docs/data-governance/catalog-source-decision.md), [recommendation baseline](docs/architecture/recommendation-baseline.md), [text playlist API](docs/architecture/text-playlist-api.md), [image flow](docs/architecture/multimodal-image-flow.md), and [feedback replay](docs/architecture/feedback-replay.md).
