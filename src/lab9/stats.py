"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    # M2
    out = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        h_fail = h == POS
        j_fail = j == POS
        if h_fail and j_fail: out["tp"] += 1
        elif h_fail and not j_fail: out["fn"] += 1
        elif not h_fail and j_fail: out["fp"] += 1
        elif not h_fail and not j_fail: out["tn"] += 1
    return out


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    # M2: precision = tp/(tp+fp), recall = tp/(tp+fn); return 0.0 when the denominator is 0
    c = confusion(human, judge)
    tp, fp, fn = (c[k] for k in ("tp", "fp", "fn"))
    precision = tp / (tp + fp) if tp + fp != 0 else 0.0
    recall = tp / (tp + fn) if tp + fn != 0 else 0.0

    return (precision, recall)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    # M2
    c = confusion(human, judge)
    tp, fp, fn, tn = (c[k] for k in ("tp", "fp", "fn", "tn"))
    n = tp + fp + fn + tn
    if n == 0:
        raise ValueError("kappa undefined: total = 0")
    p_o = (tp + tn) / n
    human_fail = (tp + fn) / n
    judge_fail = (tp + fp) / n
    p_e = human_fail * judge_fail + (1 - human_fail) * (1 - judge_fail)
    if p_e == 1:
        raise ValueError("kappa undefined: constant labels (p_e = 1)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    # M2: (p_obs + spec - 1) / (sens + spec - 1)
    if sensitivity + specificity - 1 <= 0:
        raise ValueError("rogan_gladen undefined: judge no better than chance (sens + spec <= 1)")
    true_rate = (observed_rate + specificity - 1) / (sensitivity + specificity - 1)
    return min(1.0, max(0.0, true_rate))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    # TODO M4
    raise NotImplementedError


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    # TODO M6
    raise NotImplementedError


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    # TODO M6
    raise NotImplementedError
