# Image-assisted text matching

## Model choice

The optional local captioner uses `Salesforce/blip-image-captioning-base`, pinned to model revision `cab088ce3bed7a6b7ead5bf9bcd1ce3d4c69ee78`. The model card identifies a BSD-3-Clause license and documents CPU inference; the official Transformers BLIP documentation shows direct processor/model use. Review the [model card](https://huggingface.co/Salesforce/blip-image-captioning-base) and [BLIP documentation](https://huggingface.co/docs/transformers/main/model_doc/blip) when changing the model or revision.

The checkpoint is optional and is not downloaded during text-only startup. On the first image request, the local model files are fetched from Hugging Face and cached unless the model cache is already populated. Inference then runs in the backend process on CPU. The backend serializes caption calls to limit simultaneous CPU/memory load. A missing checkpoint or dependency produces HTTP 503; text playlist generation remains available.

Install the CPU PyTorch wheel and optional Transformers package in the active virtual environment:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-image.txt
```

Transformers v5 documents Python 3.11 or newer; the core text app can run on Python 3.10 or newer. See [Transformers installation guidance](https://huggingface.co/docs/transformers/main/installation).

## Request flow and privacy

`POST /api/v1/images/interpret` accepts JPEG, PNG, and WebP uploads up to 8 MiB, 4096 pixels per dimension, and 12 megapixels. The server checks the decoded image format and dimensions, applies EXIF orientation, converts to RGB, and sends it to BLIP. The upload stream is closed and the decoded image is closed after inference; no image is written to the catalog or database. The browser clears its selected file after a successful response.

The endpoint returns a caption and requires review. The frontend inserts it into the editable prompt. Playlist generation remains a separate user action, so the user can edit or replace the caption first. The caption is matched with the existing text/metadata recommender; no direct image/audio embedding alignment is claimed.

## Limitations

- A caption describes visible content, not a validated emotional state or musical property.
- The base checkpoint can be slow on a CPU and consumes substantially more memory than the text-only app; model weights are not vendored in the repository.
- Captions can be incomplete or wrong, so user review is required.
- This is a caption-to-text bridge, not trained image-to-music retrieval. It does not infer identity or private traits.
