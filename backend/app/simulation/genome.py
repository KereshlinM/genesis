"""Agent genome encoding and genetic operators."""

from __future__ import annotations

import numpy as np

TRAITS = [
    "risk_tolerance",       # [0,1] — affects pace, click rate, urgency
    "attention_span",       # [0,1] — affects session duration, idle ratio
    "stress_sensitivity",   # [0,1] — affects backspace, hesitation under pressure
    "adaptability",         # [0,1] — how fast baseline updates; dampens drift
    "novelty_seeking",      # [0,1] — nav_back_rate, exploration behaviour
    "social_conformity",    # [0,1] — weight of peer influence on behaviour
]
N_TRAITS = len(TRAITS)


def random_genomes(n: int, rng: np.random.Generator) -> np.ndarray:
    """Beta(2,2) initialisation gives realistic bell-shaped trait distributions."""
    return rng.beta(2, 2, size=(n, N_TRAITS)).astype(np.float32)


def crossover(parent1: np.ndarray, parent2: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """BLX-α blend crossover: child trait = lerp(p1, p2, α) with α ~ U(0,1)."""
    alpha = rng.random(N_TRAITS, dtype=np.float32)
    return alpha * parent1 + (1 - alpha) * parent2


def mutate(genome: np.ndarray, rate: float, rng: np.random.Generator) -> np.ndarray:
    """Gaussian perturbation at each locus independently."""
    mask = rng.random(N_TRAITS) < rate
    noise = rng.normal(0, 0.08, N_TRAITS).astype(np.float32)
    return np.clip(genome + mask * noise, 0, 1)


def genome_to_dict(g: np.ndarray) -> dict[str, float]:
    return {t: round(float(g[i]), 4) for i, t in enumerate(TRAITS)}


def shannon_diversity(genomes: np.ndarray, n_bins: int = 10) -> float:
    """Mean per-trait Shannon entropy across discretised allele bins."""
    entropies = []
    for col in range(N_TRAITS):
        counts, _ = np.histogram(genomes[:, col], bins=n_bins, range=(0, 1))
        counts = counts[counts > 0].astype(float)
        p = counts / counts.sum()
        entropies.append(-float(np.sum(p * np.log(p + 1e-12))))
    return float(np.mean(entropies))
