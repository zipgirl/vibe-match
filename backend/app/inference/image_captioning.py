"""Lazy CPU-only BLIP image captioning with no image persistence."""

from __future__ import annotations

from threading import Lock
from typing import Protocol

from PIL import Image

MODEL_ID = "Salesforce/blip-image-captioning-base"
MODEL_REVISION = "cab088ce3bed7a6b7ead5bf9bcd1ce3d4c69ee78"


class Captioner(Protocol):
    def caption(self, image: Image.Image) -> str: ...


class ImageModelUnavailable(RuntimeError):
    """Raised when optional local model dependencies or weights are unavailable."""


class BlipLocalCaptioner:
    """Caption images with a locally executed BLIP base checkpoint on CPU."""

    def __init__(self, *, local_files_only: bool = False) -> None:
        self.local_files_only = local_files_only
        self._processor = None
        self._model = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    def _load_model(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoProcessor, BlipForConditionalGeneration
            except ImportError as error:
                raise ImageModelUnavailable(
                    "Local image captioning dependencies are missing. Install requirements-image.txt."
                ) from error
            try:
                self._processor = AutoProcessor.from_pretrained(
                    MODEL_ID,
                    revision=MODEL_REVISION,
                    local_files_only=self.local_files_only,
                )
                self._model = BlipForConditionalGeneration.from_pretrained(
                    MODEL_ID,
                    revision=MODEL_REVISION,
                    local_files_only=self.local_files_only,
                ).to("cpu")
                self._model.eval()
                self._torch = torch
            except Exception as error:
                raise ImageModelUnavailable(
                    "The local BLIP model is unavailable. Check model-cache access or install its weights first."
                ) from error

    def caption(self, image: Image.Image) -> str:
        self._load_model()
        with self._inference_lock, self._torch.inference_mode():
            inputs = self._processor(images=image, return_tensors="pt")
            output = self._model.generate(**inputs, max_new_tokens=36, num_beams=3)
            caption = self._processor.decode(output[0], skip_special_tokens=True).strip()
        if not caption:
            raise RuntimeError("Image captioning returned an empty description")
        return caption
