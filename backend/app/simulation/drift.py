"""
Internal drift scorer — mirrors behavioral-drift's logic exactly.
Used as fallback when the live API is unreachable.
"""

from __future__ import annotations

import numpy as np
from app.simulation.behavioral import N_METRICS

DRIFT_TYPES = [
    "cognitive_overload",
    "disengagement",
    "unusual_urgency",
    "context_switch_fatigue",
    "confusion",
]

# Metric indices (matching METRIC_NAMES in behavioral.py)
APM    = 0  # actions_per_minute
CLK    = 1  # click_rate
CIM    = 2  # mean_click_interval_ms
TYP    = 3  # typing_speed
BSP    = 4  # backspace_rate
HES    = 5  # hesitation_rate
SCR    = 6  # scroll_velocity
NAV    = 7  # nav_back_rate
IDL    = 8  # idle_ratio
RPT    = 9  # repeated_click_ratio
DUR    = 10 # session_duration_s

Z_THRESHOLD   = 1.8
SCORE_MINIMUM = 0.5


def score_drift(
    metrics: np.ndarray,
    baseline_mean: np.ndarray,
    baseline_std: np.ndarray,
) -> dict | None:
    safe_std = np.where(baseline_std < 1e-6, 1e-6, baseline_std)
    z = (metrics - baseline_mean) / safe_std
    th = Z_THRESHOLD

    def sig(idx: int, direction: int = 0) -> float:
        v = float(z[idx])
        if direction > 0  and v >  th: return v
        if direction < 0  and v < -th: return abs(v)
        if direction == 0 and abs(v) > th: return abs(v)
        return 0.0

    scores = {
        "cognitive_overload":       (sig(DUR,1)*1.2 + sig(BSP,1)*1.0 + sig(HES,1)*1.5
                                     + sig(CIM,1)*0.8 + sig(TYP,-1)*0.8) / 5.3,
        "disengagement":            (sig(DUR,-1)*1.0 + sig(IDL,1)*1.5 + sig(APM,-1)*1.0
                                     + sig(HES,1)*0.8) / 4.3,
        "unusual_urgency":          (sig(APM,1)*1.5 + sig(CLK,1)*1.2 + sig(HES,-1)*1.0
                                     + sig(DUR,-1)*0.8) / 4.5,
        "context_switch_fatigue":   (sig(NAV,1)*1.5 + sig(RPT,1)*1.0 + sig(HES,1)*0.8) / 3.3,
        "confusion":                (sig(RPT,1)*1.5 + sig(NAV,1)*1.2 + sig(TYP,-1)*0.8
                                     + sig(BSP,1)*0.8) / 4.3,
    }

    best = max(scores, key=scores.__getitem__)
    best_score = scores[best]

    if best_score < SCORE_MINIMUM:
        return None

    severity = "low" if best_score < 1.5 else "medium" if best_score < 3.0 else "high"
    return {
        "type": best,
        "score": round(best_score, 3),
        "severity": severity,
        "all_scores": {k: round(v, 3) for k, v in scores.items()},
        "source": "internal",
    }
