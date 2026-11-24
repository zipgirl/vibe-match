"""Small, dependency-light ranking metrics for offline recommendation checks."""

from __future__ import annotations

import math
from collections.abc import Iterable


def _validate_k(k: int) -> None:
    if k < 1:
        raise ValueError("k must be at least 1")


def precision_at_k(ranked_ids: Iterable[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of the first k recommendation slots that are relevant."""
    _validate_k(k)
    ranked = list(ranked_ids)[:k]
    return sum(item in relevant_ids for item in ranked) / k


def recall_at_k(ranked_ids: Iterable[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of known relevant items retrieved in the first k."""
    _validate_k(k)
    if not relevant_ids:
        raise ValueError("recall is undefined when relevant_ids is empty")
    ranked = list(ranked_ids)[:k]
    return sum(item in relevant_ids for item in ranked) / len(relevant_ids)


def ndcg_at_k(ranked_ids: Iterable[str], relevant_ids: set[str], k: int) -> float:
    """Binary-relevance NDCG@k with logarithmic rank discount."""
    _validate_k(k)
    if not relevant_ids:
        raise ValueError("NDCG is undefined when relevant_ids is empty")
    ranked = list(ranked_ids)[:k]
    dcg = sum(1.0 / math.log2(rank + 1) for rank, item in enumerate(ranked, start=1) if item in relevant_ids)
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg
