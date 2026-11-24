# Catalog source decision

**Status:** Initial implementation policy  
**Scope:** Milestone 1 application catalog; research datasets are out of scope for the playable catalog.

## Decision

Use a small, explicitly reviewed catalog of tracks for which the project can retain a source page, artist/title attribution, and track-level license or permission. The first source to investigate is Free Music Archive (FMA). Include a track only when its individual license permits the exact intended use. Prefer CC0 or CC BY tracks for the initial catalog; do not infer permission from a dataset-level label.

The MVP stores metadata and an outbound link to the source/platform. It does not redistribute or stream audio. It does not download or retain audio for model training or feature extraction in this milestone. If a source or track's permitted use is unclear, exclude it pending review.

This is a project data-handling policy, not a legal opinion. Track eligibility must be checked against the applicable source terms and rights information at the time of import.

## Source notes

- FMA's license guide describes multiple track-level licenses and their restrictions. FMA does not own all underlying copyrights; attribution and the selected license conditions apply. Some tracks are download-only and are not suitable as recommendation catalog entries absent additional permission. See [FMA License Guide](https://freemusicarchive.org/License_Guide).
- The Library of Congress describes FMA metadata files as CC BY 4.0 and the code as MIT, while warning that the audio may have separate rights and that users are responsible for obtaining required permissions. See [Library of Congress FMA record](https://www.loc.gov/item/2018655052/).
- The Million Song Dataset (MSD) contains metadata and derived audio features, not audio. Its Echo Nest data terms are distinct from its software license; its records are research material only for this project unless the applicable terms are confirmed for a specific use. It will not be imported into the app catalog. See [MSD overview](https://millionsongdataset.com/) and [MSD data license](https://github.com/tbertinmahieux/MSongsDB/blob/master/LICENSE).

## Eligibility requirements

An application-catalog record must have:

1. A stable source identifier and source page URL.
2. Track title and artist attribution as presented by the source.
3. The exact track-level license or permission and its URL/text reference.
4. A source/platform URL for the user to follow.
5. Import date and the name/version of the source manifest or source export.
6. A documented eligibility decision for metadata display and outbound linking.

Records missing any required rights or provenance information are rejected from the application catalog. Research data, including MSD, remains in a separate research-only area and must not flow into application-catalog imports by default.

## Reproducibility and change control

- Preserve source-provided values alongside normalized values.
- Keep a manifest with source, retrieval date, attribution, license reference, and checksums where files are available.
- Do not commit audio, image uploads, or large source datasets to Git.
- Recheck current source terms before publishing or materially changing how catalog records are used.
- Record changes to this policy in version control and review affected records when a license or source changes.

## Open checks before importing records

- For the initial four-record hand-curated sample, individual FMA pages expose the selected CC0 1.0 statements and metadata in their official indexed content; the application catalog stores metadata and outbound links only.
- Confirm the four source links in a normal browser before a public demo. Direct fetches from the research browser returned HTTP 403, so current direct accessibility was not independently confirmed there.
- Bulk FMA dataset import remains unapproved by this policy. It would need a separate review of the dataset files, current source access, record-level license fields, and intended processing before acquisition.
- If those checks fail or cannot be automated/reliably recorded, use individually permissioned artist sources for the sample instead of silently treating FMA records as cleared.
