import random

from shiftloop.stats import drop_is_real, trend_eta


def test_noisy_samples_around_target_are_not_a_real_drop():
    rng = random.Random(1)
    samples = [60 + rng.gauss(0, 3) for _ in range(30)]
    real, info = drop_is_real(samples, target=60)
    assert not real
    assert "noise" in info["verdict"]


def test_sustained_slowdown_is_real():
    rng = random.Random(2)
    samples = [60 + rng.gauss(0, 2) for _ in range(20)] + [68 + rng.gauss(0, 2) for _ in range(12)]
    real, info = drop_is_real(samples, target=60)
    assert real
    assert info["slower_pct"] > 8


def test_too_few_samples_is_never_real():
    real, info = drop_is_real([90, 95, 99], target=60)
    assert not real
    assert "not enough" in info["verdict"]


def test_trend_eta_extrapolates_linear_rise():
    xs = list(range(10))
    ys = [1.0 + 0.5 * x for x in xs]  # reaches 10 at x = 18
    eta = trend_eta(xs, ys, threshold=10.0)
    assert abs(eta - 9.0) < 1e-6  # 18 - last x (9)


def test_trend_eta_is_none_when_flat_or_falling():
    assert trend_eta([0, 1, 2, 3], [5, 5, 5, 5], threshold=10) is None
    assert trend_eta([0, 1, 2, 3], [5, 4, 3, 2], threshold=10) is None
