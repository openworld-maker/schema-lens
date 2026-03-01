"""Metric functions for ranking comparison."""

from __future__ import annotations


def overlap_at_k(baseline_ids: list[str], shadow_ids: list[str]) -> int:
    return len(set(baseline_ids) & set(shadow_ids))


def jaccard_at_k(baseline_ids: list[str], shadow_ids: list[str]) -> float:
    b = set(baseline_ids)
    s = set(shadow_ids)
    union = b | s
    if not union:
        return 1.0
    return len(b & s) / len(union)


def kendall_tau_at_k(baseline_ids: list[str], shadow_ids: list[str]) -> float | None:
    shadow_set = set(shadow_ids)
    common = [doc_id for doc_id in baseline_ids if doc_id in shadow_set]
    if len(common) < 2:
        return None

    rank_b = {doc_id: i for i, doc_id in enumerate(baseline_ids)}
    rank_s = {doc_id: i for i, doc_id in enumerate(shadow_ids)}

    concordant = 0
    discordant = 0
    n = len(common)

    for i in range(n):
        for j in range(i + 1, n):
            a = common[i]
            b = common[j]
            diff_b = rank_b[a] - rank_b[b]
            diff_s = rank_s[a] - rank_s[b]
            prod = diff_b * diff_s
            if prod > 0:
                concordant += 1
            elif prod < 0:
                discordant += 1

    denom = concordant + discordant
    if denom == 0:
        return 0.0
    return (concordant - discordant) / denom
