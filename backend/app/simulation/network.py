"""
Small-world social network (Watts-Strogatz model).

Agents in the same cultural group have denser local connections.
Cross-culture edges transmit cultural influence and drive conformity drift.
"""

from __future__ import annotations

import numpy as np


def build_small_world(n: int, k: int = 6, p: float = 0.12,
                      rng: np.random.Generator | None = None) -> np.ndarray:
    """
    Returns adjacency matrix (n×n, float32).
    k: each node connects to k nearest neighbours in ring lattice.
    p: rewiring probability (creates long-range shortcuts).
    """
    if rng is None:
        rng = np.random.default_rng()

    adj = np.zeros((n, n), dtype=np.float32)
    half_k = k // 2

    # Ring lattice
    for i in range(n):
        for j in range(1, half_k + 1):
            nb = (i + j) % n
            adj[i, nb] = 1.0
            adj[nb, i] = 1.0

    # Rewire
    for i in range(n):
        for j in range(1, half_k + 1):
            if rng.random() < p:
                old_nb = (i + j) % n
                adj[i, old_nb] = 0.0
                adj[old_nb, i] = 0.0
                # Pick new target (no self-loops, no duplicate edges)
                candidates = np.where((adj[i] == 0) & (np.arange(n) != i))[0]
                if len(candidates):
                    new_nb = rng.choice(candidates)
                    adj[i, new_nb] = 1.0
                    adj[new_nb, i] = 1.0

    return adj


def apply_social_influence(
    genomes: np.ndarray,
    adj: np.ndarray,
    rng: np.random.Generator,
    influence_scale: float = 0.04,
) -> np.ndarray:
    """
    Agents with high social_conformity (trait index 5) shift their genome
    slightly toward the mean of their immediate neighbours.
    This models cultural transmission and peer pressure.
    """
    new_genomes = genomes.copy()
    n = len(genomes)
    conformity_col = 5

    for i in range(n):
        conformity = float(genomes[i, conformity_col])
        if conformity < 0.2:
            continue
        neighbours = np.where(adj[i] > 0)[0]
        if not len(neighbours):
            continue
        mean_nb = genomes[neighbours].mean(axis=0)
        weight = conformity * influence_scale
        new_genomes[i] = np.clip((1 - weight) * genomes[i] + weight * mean_nb, 0, 1)

    return new_genomes.astype(np.float32)


def clustering_coefficient(adj: np.ndarray) -> float:
    """Mean local clustering coefficient across all nodes."""
    n = len(adj)
    coeffs = []
    for i in range(n):
        neighbours = np.where(adj[i] > 0)[0]
        k = len(neighbours)
        if k < 2:
            coeffs.append(0.0)
            continue
        sub = adj[np.ix_(neighbours, neighbours)]
        actual_edges = sub.sum() / 2
        possible = k * (k - 1) / 2
        coeffs.append(float(actual_edges / possible))
    return float(np.mean(coeffs))


def edge_list(adj: np.ndarray, limit: int = 600) -> list[list[int]]:
    """Return upper-triangle edges as [[src, dst], ...] capped at limit."""
    rows, cols = np.where(np.triu(adj, 1) > 0)
    edges = list(zip(rows.tolist(), cols.tolist()))
    if len(edges) > limit:
        idx = np.random.choice(len(edges), limit, replace=False)
        edges = [edges[i] for i in idx]
    return [[int(r), int(c)] for r, c in edges]
