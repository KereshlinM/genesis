"""
Generate synthetic behavioural sessions and raw events from agent genome + culture.

The output is dual-purpose:
  1. Raw events  → sent to the behavioral-drift API exactly as the browser SDK would
  2. Pre-computed metrics → used for internal fallback drift scoring
"""

from __future__ import annotations

import time
import numpy as np

from app.simulation.genome import TRAITS

# Session metric order must match behavioral-drift's metrics.py
METRIC_NAMES = [
    "actions_per_minute",
    "click_rate",
    "mean_click_interval_ms",
    "typing_speed",
    "backspace_rate",
    "hesitation_rate",
    "scroll_velocity",
    "nav_back_rate",
    "idle_ratio",
    "repeated_click_ratio",
    "session_duration_s",
]
N_METRICS = len(METRIC_NAMES)


def generate_metrics(genome: np.ndarray, culture: dict, rng: np.random.Generator,
                     time_pressure: float = 0.0) -> np.ndarray:
    """
    Produce one session's worth of behavioural metrics.

    time_pressure [0,1]: external deadline urgency — raises pace, stress, errors.

    Returns: float32 array of shape (N_METRICS,), index matches METRIC_NAMES.
    """
    risk, attention, stress_sens, adaptability, novelty, conformity = genome

    ambient = culture["ambient_stress"]
    pace    = culture["pace"]
    tech    = culture["tech_fluency"]

    # Compound stress = personal sensitivity × ambient culture × deadline pressure
    eff_stress = float(np.clip(stress_sens * ambient * (1 + time_pressure * 0.6), 0, 1))
    eff_pace   = float(np.clip(pace * (0.6 + risk * 0.8) * (1 + time_pressure * 0.3), 0, 2))

    base = np.array([
        28 * eff_pace + 8,                                        # actions_per_minute
        0.25 + 0.3 * eff_pace,                                    # click_rate
        max(80, 900 / (eff_pace + 0.1) - 150),                   # mean_click_interval_ms
        max(5, 55 * tech * (1 - 0.35 * eff_stress)),             # typing_speed
        0.025 + 0.14 * eff_stress,                                # backspace_rate
        0.07 + 0.28 * eff_stress * (1 - adaptability * 0.5),    # hesitation_rate
        max(0, 400 * eff_pace + 50),                              # scroll_velocity
        0.025 + 0.09 * novelty + 0.06 * eff_stress,             # nav_back_rate
        max(0, 0.25 * (1 - eff_pace) * (1 + eff_stress * 0.2)), # idle_ratio
        0.02 + 0.09 * eff_stress + 0.04 * (1 - adaptability),  # repeated_click_ratio
        max(30, 160 + 280 * attention * (1 - 0.25 * eff_stress)), # session_duration_s
    ], dtype=np.float32)

    noise_sd = np.array([5, 0.05, 60, 7, 0.01, 0.02, 40, 0.01, 0.02, 0.01, 25], dtype=np.float32)
    metrics = base + rng.normal(0, noise_sd).astype(np.float32)

    # Hard clip bounds
    metrics = np.clip(metrics, 0, None)
    metrics[1]  = np.clip(metrics[1], 0, 1)   # click_rate
    metrics[5]  = np.clip(metrics[5], 0, 1)   # hesitation_rate
    metrics[7]  = np.clip(metrics[7], 0, 1)   # nav_back_rate
    metrics[8]  = np.clip(metrics[8], 0, 1)   # idle_ratio
    metrics[9]  = np.clip(metrics[9], 0, 1)   # repeated_click_ratio

    return metrics


def generate_raw_events(metrics: np.ndarray, rng: np.random.Generator) -> list[dict]:
    """
    Convert session metrics back into a plausible sequence of raw events.
    Sent to behavioral-drift's /sessions/{id}/events endpoint.
    """
    duration_ms = float(metrics[10]) * 1000
    apm         = float(metrics[0])
    click_rate  = float(metrics[1])
    typing_speed = float(metrics[3])
    idle_ratio  = float(metrics[8])
    nav_back    = float(metrics[7])
    scroll_vel  = float(metrics[6])

    total_actions = max(1, int(apm * float(metrics[10]) / 60))
    n_clicks    = int(total_actions * click_rate)
    n_keys      = int(typing_speed * float(metrics[10]) / 60)
    n_scrolls   = max(1, total_actions - n_clicks - n_keys)
    n_idles     = max(0, int(total_actions * idle_ratio))

    events: list[dict] = []
    base_ts = int(time.time() * 1000) - int(duration_ms)

    def rand_ts() -> int:
        return base_ts + int(rng.uniform(0, duration_ms))

    # Clicks
    for _ in range(n_clicks):
        events.append({
            "event_type": "click",
            "ts": rand_ts(),
            "data": {
                "x": int(rng.uniform(0, 1920)),
                "y": int(rng.uniform(0, 1080)),
                "element_type": rng.choice(["button", "link", "div", "input"]),
            },
        })

    # Keypresses
    backspace_n = int(n_keys * float(metrics[4]))
    for _ in range(n_keys):
        events.append({
            "event_type": "keypress",
            "ts": rand_ts(),
            "data": {"key_type": "char"},
        })
    for _ in range(backspace_n):
        events.append({
            "event_type": "keypress",
            "ts": rand_ts(),
            "data": {"key_type": "backspace"},
        })

    # Scrolls
    for _ in range(n_scrolls):
        events.append({
            "event_type": "scroll",
            "ts": rand_ts(),
            "data": {"delta": float(rng.normal(scroll_vel / max(1, n_scrolls), 20))},
        })

    # Nav-back events
    nav_n = int(n_clicks * nav_back)
    for _ in range(nav_n):
        events.append({
            "event_type": "keypress",
            "ts": rand_ts(),
            "data": {"key_type": "nav_back"},
        })

    # Idle events
    for _ in range(n_idles):
        events.append({
            "event_type": "idle",
            "ts": rand_ts(),
            "data": {"duration_ms": int(rng.exponential(3000))},
        })

    # Sort by timestamp
    events.sort(key=lambda e: e["ts"])
    return events


def metrics_to_dict(m: np.ndarray) -> dict[str, float]:
    return {name: round(float(m[i]), 4) for i, name in enumerate(METRIC_NAMES)}
