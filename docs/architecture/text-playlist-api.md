# Text playlist API and anonymous feedback

## Request flow

The React client creates a random session identifier in local storage. It sends that identifier with playlist generation and feedback requests. There are no accounts or cross-device synchronization. The API validates the identifier format but treats it as an anonymous local session key, not a strong authentication credential.

The API loads the eligible catalog from SQLite, retrieves saved genre preferences and the latest feedback state for the session, calls the independent content-based recommender, persists the playlist and score breakdown, and returns tracks with source links, license information, and explanations.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/v1/health` | Basic process health. |
| `GET /api/v1/catalog/genres` | Return genres available in the imported catalog. |
| `GET /api/v1/preferences/{session_id}` | Return the session's saved genre preferences. |
| `PUT /api/v1/preferences/{session_id}` | Replace preferences; unknown catalog genres are rejected. |
| `POST /api/v1/playlists` | Generate and persist an ordered playlist from text. |
| `POST /api/v1/feedback` | Record like, dislike, or skip for a track shown in that session's playlist. |
| `POST /api/v1/images/interpret` | Optionally caption an in-memory image with the local CPU model; the user must review the returned text. |

Feedback submissions are append-only events. The latest event for a session and track determines whether the track is excluded or added to the liked-genre profile: the latest `dislike` excludes it; the latest `like` contributes its genres to the profile; a later `skip` clears both effects. These signals are explicit, lightweight features, not a trained model.

## SQLite additions

The API adds `anonymous_sessions`, `preferences`, `playlists`, `playlist_items`, and `feedback_events`. Playlist items retain the score components and explanation returned by the recommender. Feedback references a playlist item and session, preventing submissions for tracks that were not shown to that session.

## Scope and privacy

The application stores a random session ID in the browser and keeps preferences, prompts, playlists, and feedback in the configured SQLite database. Uploaded images are processed in memory and are not persisted. There is no authentication. This is intended for local portfolio use; a public deployment would need an explicit privacy/retention policy, abuse controls, and stronger session protection before collecting real user activity.
