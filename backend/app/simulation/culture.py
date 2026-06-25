"""Cultural parameter representation and generational evolution."""

from __future__ import annotations

import numpy as np

CULTURE_PALETTES = [
    ("Verdania",   0.25, 0.45, 0.80, 0.65),  # low stress, moderate pace, high tech, high collectivism
    ("Ignara",     0.70, 0.85, 0.55, 0.30),  # high stress, fast pace, moderate tech, low collectivism
    ("Solveth",    0.40, 0.60, 0.90, 0.50),  # moderate stress, moderate pace, high tech
    ("Kresh",      0.55, 0.70, 0.40, 0.80),  # moderate-high stress, fast, low tech, high collectivism
    ("Nulmara",    0.20, 0.30, 0.70, 0.90),  # very low stress, slow pace, moderate tech, very collective
]


def init_cultures(n: int, rng: np.random.Generator) -> list[dict]:
    cultures = []
    for i in range(n):
        if i < len(CULTURE_PALETTES):
            name, stress, pace, tech, coll = CULTURE_PALETTES[i]
        else:
            name = f"Culture-{i}"
            stress, pace, tech, coll = rng.beta(2, 2, size=4).tolist()
        cultures.append({
            "id": i,
            "name": name,
            "ambient_stress": float(stress),
            "pace": float(pace),
            "tech_fluency": float(tech),
            "collectivism": float(coll),
        })
    return cultures


def evolve_culture(culture: dict, drift_rate: float, rng: np.random.Generator) -> dict:
    """
    Cultures update each generation based on how much behavioural drift their
    population produced. High drift drives ambient stress up (feedback loop).
    Tech fluency slowly increases. Pace drifts stochastically.
    """
    # Ambient stress is partly driven by drift rate — a sign of cultural instability
    new_stress = culture["ambient_stress"] * 0.88 + drift_rate * 0.18
    new_stress = float(np.clip(new_stress + rng.normal(0, 0.015), 0, 1))

    # Pace undergoes slow random walk
    new_pace = float(np.clip(culture["pace"] + rng.normal(0, 0.02), 0, 1))

    # Tech fluency grows monotonically (civilisational learning)
    new_tech = float(min(1.0, culture["tech_fluency"] + 0.004))

    return {**culture, "ambient_stress": new_stress, "pace": new_pace, "tech_fluency": new_tech}
