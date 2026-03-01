from schema_lens.compare.metrics import jaccard_at_k, kendall_tau_at_k, overlap_at_k


def test_overlap_and_jaccard():
    b = ["a", "b", "c"]
    s = ["b", "c", "d"]
    assert overlap_at_k(b, s) == 2
    assert jaccard_at_k(b, s) == 0.5


def test_kendall_tau_perfect():
    b = ["a", "b", "c"]
    s = ["a", "b", "c"]
    assert kendall_tau_at_k(b, s) == 1.0


def test_kendall_tau_inverse():
    b = ["a", "b", "c"]
    s = ["c", "b", "a"]
    assert kendall_tau_at_k(b, s) == -1.0


def test_kendall_tau_insufficient_common_docs():
    assert kendall_tau_at_k(["a"], ["a"]) is None
