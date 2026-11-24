# Temporal feedback replay

## Personalization feature

For each session, find the latest feedback event for every track. A current `like` adds that track's source genres to a normalized profile; each liked track contributes one unit total, divided across its genres. This avoids giving tracks with many tags more total influence simply because they have more tags. The baseline adds `0.2 × liked_genre_match` to its TF-IDF and explicit-preference components. A current `dislike` remains a hard exclusion; a later like or skip changes the latest state. Skips do not create positive or negative genre weights.

The feature is a transparent content profile, not collaborative filtering, matrix factorization, or a trained ranking model. Cold-start sessions receive no profile contribution.

## Offline temporal replay

`python -m backend.app.evaluation` reads saved playlist slates and their latest feedback state. It splits each session independently by playlist insertion order. Earlier playlists form the profile history; later playlists are held out. The evaluator re-ranks eligible tracks for each held-out prompt using only that training history, then evaluates the relative order of held-out slate items with explicit `like` or `dislike` judgments.

It reports macro-averaged Precision@K, Recall@K, and NDCG@K, plus counts of sessions, playlists, explicit judgments, and positive judgments. With insufficient feedback it reports metric values as `null`, rather than claiming a score.

## Evaluation limits

- A recommendation must have been exposed before a person can judge it, so the logs have exposure and position bias.
- Only explicit likes and dislikes are used as judged items. Skips and unjudged items are omitted, not treated as negatives.
- Precision@K divides by the number of explicitly judged items available in the top K, not by K itself, so an unjudged slot is not counted as a miss.
- The candidate slate is the set originally shown to the user; this does not measure catalog-wide retrieval coverage.
- This is an offline replay diagnostic, not a randomized experiment or causal estimate of personalization benefit.
- Small samples, repeated listening, and changes in catalog/model behavior can make the result unstable. Report counts with the metrics and do not interpret tiny samples as general performance.
- Current user-selected genre preferences are excluded from the replay feature profile to avoid using present-day preferences as if they had been available historically.
