import { useEffect, useRef, useState, type FormEvent } from "react";

type Preferences = { session_id: string; preferred_genres: string[] };
type TrackRecommendation = {
  catalog_id: string;
  title: string;
  artist: string;
  source_url: string;
  license: string;
  license_url: string;
  genres: string[];
  score: number;
  content_similarity: number;
  preference_match: number;
  liked_genre_match: number;
  reasons: string[];
};
type Playlist = { playlist_id: string; prompt: string; recommendations: TrackRecommendation[] };
type Feedback = "like" | "dislike" | "skip";
type ImageInterpretation = { caption: string; review_required: true; image_retained: false; model_id: string };

function getSessionId(): string {
  const stored = window.localStorage.getItem("vibematch.session_id");
  if (stored) return stored;
  const created = window.crypto.randomUUID();
  window.localStorage.setItem("vibematch.session_id", created);
  return created;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(problem?.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export default function App() {
  const [sessionId] = useState(getSessionId);
  const [genres, setGenres] = useState<string[]>([]);
  const [preferredGenres, setPreferredGenres] = useState<string[]>([]);
  const [prompt, setPrompt] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const [imageCaption, setImageCaption] = useState("");
  const [imageLoading, setImageLoading] = useState(false);
  const [playlist, setPlaylist] = useState<Playlist | null>(null);
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      requestJson<string[]>("/api/v1/catalog/genres"),
      requestJson<Preferences>(`/api/v1/preferences/${sessionId}`),
    ])
      .then(([availableGenres, savedPreferences]) => {
        if (!active) return;
        setGenres(availableGenres);
        setPreferredGenres(savedPreferences.preferred_genres);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Could not load VibeMatch.");
      });
    return () => {
      active = false;
    };
  }, [sessionId]);

  function toggleGenre(genre: string) {
    setPreferredGenres((current) =>
      current.includes(genre) ? current.filter((item) => item !== genre) : [...current, genre],
    );
  }

  async function describeImage() {
    if (!imageFile) return;
    setImageLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", imageFile);
      const result = await requestJson<ImageInterpretation>("/api/v1/images/interpret", {
        method: "POST",
        body: form,
      });
      setImageCaption(result.caption);
      setPrompt(result.caption);
      setImageFile(null);
      if (imageInputRef.current) imageInputRef.current.value = "";
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not interpret this image.");
    } finally {
      setImageLoading(false);
    }
  }

  async function generatePlaylist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await requestJson<Preferences>(`/api/v1/preferences/${sessionId}`, {
        method: "PUT",
        body: JSON.stringify({ preferred_genres: preferredGenres }),
      });
      const nextPlaylist = await requestJson<Playlist>("/api/v1/playlists", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, prompt, limit: 10 }),
      });
      setPlaylist(nextPlaylist);
      setFeedback({});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not generate a playlist.");
    } finally {
      setLoading(false);
    }
  }

  async function sendFeedback(track: TrackRecommendation, action: Feedback) {
    if (!playlist) return;
    setError("");
    try {
      await requestJson<{ saved: boolean }>("/api/v1/feedback", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          playlist_id: playlist.playlist_id,
          catalog_id: track.catalog_id,
          feedback_type: action,
        }),
      });
      setFeedback((current) => ({ ...current, [track.catalog_id]: action }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save feedback.");
    }
  }

  return (
    <main className="page-shell">
      <header className="masthead">
        <a className="wordmark" href="#top" aria-label="VibeMatch home">
          <span className="wordmark-mark" aria-hidden="true">v.</span> vibematch
        </a>
        <span className="local-note"><span aria-hidden="true">●</span> anonymous session · no account</span>
      </header>

      <section className="intro" id="top" aria-labelledby="page-title">
        <p className="eyebrow">A soundtrack for right now</p>
        <h1 id="page-title">What does this moment <em>sound like?</em></h1>
        <p className="intro-copy">Describe the feeling, the scene, or the kind of sound you want around you.</p>
      </section>

      <section className="image-panel" aria-labelledby="image-title">
        <div className="image-copy">
          <p className="eyebrow">Optional starting point</p>
          <h2 id="image-title">Bring a picture into the moment</h2>
          <p>We’ll suggest a description on this machine. You decide what to keep before making a playlist.</p>
        </div>
        <div className="image-controls">
          <label className="file-picker" htmlFor="mood-image">
            <span>{imageFile ? imageFile.name : "Choose an image"}</span>
            <input
              id="mood-image"
              ref={imageInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => {
                setImageFile(event.target.files?.[0] ?? null);
                setImageCaption("");
              }}
            />
          </label>
          <button className="describe-button" type="button" onClick={() => void describeImage()} disabled={!imageFile || imageLoading}>
            {imageLoading ? "Describing…" : "Suggest a description"}
          </button>
        </div>
        <p className="image-privacy">JPEG, PNG, or WebP · up to 8 MiB · the uploaded file is deleted after processing</p>
        {imageCaption && <p className="caption-confirmation" role="status">Suggested caption added below. Review and edit it before generating.</p>}
      </section>

      <form className="prompt-panel" onSubmit={generatePlaylist}>
        <label className="field-label" htmlFor="mood-prompt">Describe your vibe</label>
        <textarea
          id="mood-prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="A slow Sunday morning, sunlight through the window, nowhere to be…"
          maxLength={500}
          required
          rows={4}
        />
        <div className="prompt-meta"><span>Be as specific or as open as you like</span><span>{prompt.length}/500</span></div>

        <fieldset className="genre-fieldset">
          <legend>Anything you want more of? <span>Optional</span></legend>
          {genres.length ? (
            <div className="genre-list">
              {genres.map((genre) => (
                <label className={`genre-chip${preferredGenres.includes(genre) ? " selected" : ""}`} key={genre}>
                  <input
                    type="checkbox"
                    checked={preferredGenres.includes(genre)}
                    onChange={() => toggleGenre(genre)}
                  />
                  {genre}
                </label>
              ))}
            </div>
          ) : <p className="muted small">Loading catalog genres…</p>}
        </fieldset>

        <button className="generate-button" type="submit" disabled={loading || !prompt.trim()}>
          {loading ? "Finding your sound…" : "Make me a playlist"}
          <span aria-hidden="true">↗</span>
        </button>
      </form>

      {error && <p className="error-message" role="alert">{error}</p>}

      {playlist && (
        <section className="results" aria-labelledby="results-title" aria-live="polite">
          <div className="results-heading">
            <div>
              <p className="eyebrow">Made from your description</p>
              <h2 id="results-title">A little something for the moment</h2>
            </div>
            <span className="track-count">{playlist.recommendations.length} tracks</span>
          </div>
          {playlist.recommendations.length === 0 ? (
            <p className="empty-state">No eligible tracks matched this request yet. Try another description or clear a disliked track later.</p>
          ) : (
            <ol className="track-list">
              {playlist.recommendations.map((track, index) => (
                <li className="track-card" key={track.catalog_id}>
                  <span className="track-number">{String(index + 1).padStart(2, "0")}</span>
                  <div className="track-main">
                    <h3>{track.title}</h3>
                    <p className="track-artist">{track.artist}</p>
                    <div className="track-genres">{track.genres.slice(0, 4).map((genre) => <span key={genre}>{genre}</span>)}</div>
                    <ul className="reasons">{track.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                    <p className="license-note">{track.license} · <a href={track.license_url} target="_blank" rel="noreferrer">license details</a></p>
                  </div>
                  <div className="track-actions">
                    <a className="source-link" href={track.source_url} target="_blank" rel="noreferrer">Listen ↗</a>
                    <div className="feedback-actions" aria-label={`Feedback for ${track.title}`}>
                      {(["like", "dislike", "skip"] as const).map((action) => (
                        <button
                          className={feedback[track.catalog_id] === action ? "active" : ""}
                          key={action}
                          type="button"
                          aria-pressed={feedback[track.catalog_id] === action}
                          onClick={() => void sendFeedback(track, action)}
                        >
                          {action === "like" ? "Like" : action === "dislike" ? "Not for me" : "Skip"}
                        </button>
                      ))}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
          <p className="baseline-note">This early version matches words to catalog genres and track titles. It learns from your dislikes; it does not yet understand mood semantically.</p>
        </section>
      )}

      <footer className="footer-note">A small catalog, thoughtfully matched. Music opens at its source.</footer>
    </main>
  );
}
