from __future__ import annotations

import sys
from contextlib import contextmanager
from types import ModuleType

from PIL import Image

from backend.app.inference.image_captioning import BlipLocalCaptioner, MODEL_ID, MODEL_REVISION


def test_blip_captioner_loads_pinned_checkpoint_once_on_cpu(monkeypatch) -> None:
    processor_loads: list[dict[str, object]] = []
    model_loads: list[dict[str, object]] = []
    calls: list[str] = []

    class FakeProcessor:
        def __call__(self, **kwargs):
            assert kwargs["images"].mode == "RGB"
            return {"pixel_values": "fake"}

        def decode(self, tokens, skip_special_tokens: bool) -> str:
            assert tokens == "tokens"
            assert skip_special_tokens
            return "A calm lakeside scene"

    class FakeModel:
        def to(self, device: str):
            calls.append(f"device:{device}")
            return self

        def eval(self):
            calls.append("eval")
            return self

        def generate(self, **kwargs):
            assert kwargs == {"pixel_values": "fake", "max_new_tokens": 36, "num_beams": 3}
            calls.append("generate")
            return ["tokens"]

    class FakeProcessorFactory:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs):
            processor_loads.append({"model_id": model_id, **kwargs})
            return FakeProcessor()

    class FakeModelFactory:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs):
            model_loads.append({"model_id": model_id, **kwargs})
            return FakeModel()

    fake_torch = ModuleType("torch")

    @contextmanager
    def inference_mode():
        calls.append("inference")
        yield

    fake_torch.inference_mode = inference_mode
    fake_transformers = ModuleType("transformers")
    fake_transformers.AutoProcessor = FakeProcessorFactory
    fake_transformers.BlipForConditionalGeneration = FakeModelFactory
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    captioner = BlipLocalCaptioner(local_files_only=True)
    image = Image.new("RGB", (8, 8))
    assert captioner.caption(image) == "A calm lakeside scene"
    assert captioner.caption(image) == "A calm lakeside scene"
    assert len(processor_loads) == len(model_loads) == 1
    for load in processor_loads + model_loads:
        assert load["model_id"] == MODEL_ID
        assert load["revision"] == MODEL_REVISION
        assert load["local_files_only"] is True
    assert calls.count("device:cpu") == 1
    assert calls.count("generate") == 2
