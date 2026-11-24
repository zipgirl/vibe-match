# Initial application catalog sample

This is a small, manually reviewed metadata sample for the application catalog. It contains no audio files. The `source_url` is the outbound track page; the external source remains responsible for playback availability.

## Source and selection

The sample uses four individual Free Music Archive track pages by HoliznaCC0. Each selected page states that the track is licensed under CC0 1.0 Universal and provides track metadata including genres and instrumental status. The FMA page is used as the evidence for the per-track license; the license URL points to the CC0 deed. The FMA terms explain that users should check the license shown on each song page, because licenses vary by track.

Tracks were checked on 2026-11-21. This date records the review performed for this repository; it does not guarantee that a source page or license statement will never change. The source pages' official indexed content was available for review, but direct page fetching in the research browser returned HTTP 403. Confirm the links in a normal browser before a public demo. Recheck before materially changing use or publishing a derived catalog.

## Field conventions

- `catalog_id` is a project-local identifier derived from the source page path; it is not asserted to be FMA's numeric track ID.
- `source_track_id` stores the source page path as an opaque identifier because no numeric FMA ID was verified for this hand-selected sample.
- `genres` preserves the genre labels shown on the track page, separated by `|`.
- `instrumental` records the explicit instrumental indicator shown on the track page.
- No mood labels, popularity features, or audio features have been inferred or added.
- These records are application-catalog candidates for metadata display and outbound linking. No audio is bundled, cached, or used for training.

## Source references

- [FMA track: Static](https://freemusicarchive.org/music/holiznacc0/lo-fi-and-chill/static-1/)
- [FMA track: Breath](https://freemusicarchive.org/music/holiznacc0/bassic/breath-1/)
- [FMA track: Sky Fish](https://freemusicarchive.org/music/holiznacc0/stranger-than-fiction-halloween-sci-fi/sky-fish/)
- [FMA track: An Ocean in Outer Space](https://freemusicarchive.org/music/holiznacc0/stranger-than-fiction-halloween-sci-fi/an-ocean-in-outer-space/)
- [FMA license guide](https://freemusicarchive.org/License_Guide)

This sample is not the FMA research dataset. Do not merge it with research-only records without an explicit review of source, license, and intended use.
