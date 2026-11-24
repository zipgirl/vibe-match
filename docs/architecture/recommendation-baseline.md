# Text-to-playlist recommendation baseline

## Scope and assumptions

The first recommender is a content-based lexical baseline. It does not claim to understand emotion, acoustic sound, or user taste beyond explicit genre preferences. Its catalog representation is limited to verified track titles and genre labels. There are no user interaction labels yet, so collaborative filtering and supervised ranking are not justified.

## Feature engineering

- Build a document for each track from its title and source-provided genres.
- Omit artist names from the matching document to avoid treating artist identity as relevance evidence.
- Keep the original source genre strings for display and explanations.
- Use scikit-learn `TfidfVectorizer` with unigrams and bigrams. IDF reduces the weight of terms shared by many catalog entries; TF-IDF weights terms within a track document.
- Transform the user's prompt in the same vocabulary and use cosine similarity between the prompt vector and track vectors.
- Normalize explicit preferred genres by case and whitespace. Preference match is the fraction of the user's selected genres present on a track.

## Scoring

For track `i` and prompt `q`:

`content_similarity(i, q) = cosine(tfidf(q), tfidf(title_i + genres_i))`

`preference_match(i, p) = matching_preferred_genres(i, p) / number_of_preferred_genres(p)`

`liked_genre_match(i, h) = sum(normalized_genre_weight(g) for g in track_i.genres)`

`score(i) = content_similarity(i, q) + 0.2 * preference_match(i, p) + 0.2 * liked_genre_match(i, h)`

The liked-genre weights come from the latest explicit feedback state: a liked track distributes one total unit evenly across its source genres; current dislikes are excluded; skips do not contribute. Tracks explicitly disliked by the user are removed before ranking. Ties are resolved by stable catalog ID. Both 0.2 coefficients are transparent baseline constants, not learned or empirically optimized values. Future changes require a documented comparison against this baseline.

## Explainability

Reasons are generated from actual fields: genre labels whose tokens overlap the prompt, title overlap, exact normalized user genre preferences, or genres from tracks the user liked. If a track has no matching terms and remains in the result list, the explanation explicitly says it is a fallback with no metadata match. Scores expose content similarity, explicit-preference match, and liked-profile match.

## Limitations

- A small catalog produces sparse vocabulary and many zero-similarity results.
- Lexical overlap is not semantic mood understanding; “peaceful” will not automatically match “ambient” without an explicit synonym feature or learned representation.
- Source genres are broad and may be incomplete or inconsistent.
- The 0.2 preference weight is a baseline choice, not a measured optimum.
- The liked-genre profile is a transparent content summary, not latent-factor collaborative filtering or a learned ranking model.

## Evaluation plan

Keep hand-authored fixtures for deterministic ordering, preference boosts, exclusions, and explanation content. Once legitimate relevance labels or consented feedback exist, evaluate top-K output with Precision@K, Recall@K, and NDCG@K, alongside catalog coverage and artist diversity. Use time-based splits for interaction data and document that unobserved tracks are not reliable negatives.
