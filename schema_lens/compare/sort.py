"""Sort stability helpers."""

from __future__ import annotations


def sort_instability_ratio(base_ids: list[str], shadow_ids: list[str]) -> float:
    rank_b = {doc_id: idx for idx, doc_id in enumerate(base_ids)}
    rank_s = {doc_id: idx for idx, doc_id in enumerate(shadow_ids)}
    common = [doc_id for doc_id in base_ids if doc_id in rank_s]
    if not common:
        return 0.0
    changed = sum(1 for doc_id in common if rank_b[doc_id] != rank_s[doc_id])
    return changed / len(common)

