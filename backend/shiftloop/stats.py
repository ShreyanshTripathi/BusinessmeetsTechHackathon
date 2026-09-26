"""Small statistics helpers: separating real drops from noise and extrapolating trends."""
from __future__ import annotations

from math import sqrt
from statistics import mean, pstdev


def drop_is_real(samples: list[float], target: float, min_samples: int = 10, rel: float = 0.08,
                 z_crit: float = 3.0) -> tuple[bool, dict]:
    """Is the recent cycle time really slower than target, or just normal variation?

    Compares the mean of the last `min_samples` against the target, scaled by the variation seen earlier.
    """
    if len(samples) < min_samples:
        return False, {"verdict": "not enough data yet", "samples": len(samples)}
    recent = samples[-min_samples:]
    baseline = samples[:-min_samples] if len(samples) >= 2 * min_samples else samples
    spread = max(pstdev(baseline) if len(baseline) >= 3 else pstdev(recent), 0.5)
    recent_mean = mean(recent)
    slower_pct = (recent_mean - target) / target * 100
    z = (recent_mean - target) / (spread / sqrt(min_samples))
    real = slower_pct > rel * 100 and z > z_crit
    verdict = "real drop" if real else "noise (within normal variation)"
    return real, {"verdict": verdict, "slower_pct": round(slower_pct, 1), "z": round(z, 1),
                  "recent_mean": round(recent_mean, 1), "target": target}


def trend_eta(xs: list[float], ys: list[float], threshold: float) -> float | None:
    """Least-squares line through (xs, ys); how far past the last x until y reaches `threshold`."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    if slope <= 1e-9:
        return None
    intercept = my - slope * mx
    return max(0.0, (threshold - intercept) / slope - xs[-1])
