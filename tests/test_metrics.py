from __future__ import annotations

import pytest

from backend.app.evaluation.metrics import ndcg_at_k, precision_at_k, recall_at_k


def test_top_k_metrics_for_known_relevance() -> None:
    ranked = ["a", "b", "c", "d"]
    relevant = {"a", "c"}
    assert precision_at_k(ranked, relevant, 3) == pytest.approx(2 / 3)
    assert recall_at_k(ranked, relevant, 3) == pytest.approx(1.0)
    assert ndcg_at_k(ranked, relevant, 3) == pytest.approx((1 + 1 / 2) / (1 + 1 / 1.584962500721156))


def test_precision_uses_available_judged_items_when_slate_is_smaller_than_k() -> None:
    assert precision_at_k(["a", "b"], {"a"}, 5) == pytest.approx(0.5)
    assert precision_at_k([], {"a"}, 5) == 0.0


def test_metrics_reject_undefined_inputs() -> None:
    with pytest.raises(ValueError, match="k"):
        precision_at_k(["a"], {"a"}, 0)
    with pytest.raises(ValueError, match="relevant_ids"):
        recall_at_k(["a"], set(), 1)
    with pytest.raises(ValueError, match="relevant_ids"):
        ndcg_at_k(["a"], set(), 1)
