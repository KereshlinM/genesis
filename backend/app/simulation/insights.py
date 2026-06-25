"""
Statistical insights extracted from a completed simulation.

Methods used:
  - Pearson correlation (trait × drift affinity)
  - One-way ANOVA (drift rates across cultures)
  - Shannon entropy (allele diversity)
  - PCA via eigendecomposition of covariance matrix
  - KL divergence (genome distribution shift across generations)
  - Survival analysis approximation (causal horizon lead-time curves)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

from app.simulation.genome import TRAITS, N_TRAITS
from app.simulation.drift import DRIFT_TYPES


def compute_insights(
    generations: list[dict],
    final_population: list[dict],
) -> dict[str, Any]:

    if not final_population:
        return {}

    genomes = np.array([[a["genome"][t] for t in TRAITS] for a in final_population], dtype=float)
    n = len(final_population)

    # ---- 1. Trait × Drift correlations (Pearson r) ----
    trait_drift_corr: dict[str, dict] = {}
    for trait in TRAITS:
        trait_vals = np.array([a["genome"][trait] for a in final_population])
        trait_drift_corr[trait] = {}
        for dt in DRIFT_TYPES:
            drift_indicator = np.array([1.0 if a.get("most_common_drift") == dt else 0.0
                                        for a in final_population])
            if drift_indicator.sum() < 3:
                trait_drift_corr[trait][dt] = {"r": 0.0, "p": 1.0}
                continue
            r, p = stats.pearsonr(trait_vals, drift_indicator)
            trait_drift_corr[trait][dt] = {"r": round(float(r), 3), "p": round(float(p), 4)}

    # ---- 2. One-way ANOVA across cultures ----
    culture_names = list({a["culture"] for a in final_population})
    culture_groups = {
        c: [a["drift_count"] for a in final_population if a["culture"] == c]
        for c in culture_names
    }
    if len(culture_groups) > 1:
        f_stat, anova_p = stats.f_oneway(*culture_groups.values())
    else:
        f_stat, anova_p = 0.0, 1.0

    # ---- 3. PCA (eigendecomposition of scaled covariance) ----
    g_c = genomes - genomes.mean(axis=0)
    g_s = genomes.std(axis=0)
    g_scaled = g_c / np.where(g_s < 1e-9, 1, g_s)
    cov = np.cov(g_scaled.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    pcs = g_scaled @ eigenvectors[:, :2]
    var_exp = eigenvalues[:2] / (eigenvalues.sum() + 1e-9)

    pca_points = [
        {
            "id": a["id"],
            "pc1": round(float(pcs[i, 0]), 4),
            "pc2": round(float(pcs[i, 1]), 4),
            "culture": a["culture"],
            "drift_type": a.get("most_common_drift"),
            "fitness": round(a.get("fitness", 0.5), 4),
            "urgency_score": a.get("urgency_score"),
        }
        for i, a in enumerate(final_population)
    ]

    pca_loadings = [
        {"trait": TRAITS[j], "pc1": round(float(eigenvectors[j, 0]), 4), "pc2": round(float(eigenvectors[j, 1]), 4)}
        for j in range(N_TRAITS)
    ]

    # ---- 4. KL divergence between generation 0 and final (genome drift) ----
    kl_per_trait = {}
    if len(generations) >= 2:
        g0 = generations[0]["stats"]
        gf = generations[-1]["stats"]
        for trait in TRAITS:
            mu0 = g0["mean_genome"].get(trait, 0.5)
            sd0 = max(1e-4, g0["std_genome"].get(trait, 0.15))
            muf = gf["mean_genome"].get(trait, 0.5)
            sdf = max(1e-4, gf["std_genome"].get(trait, 0.15))
            # KL(N0 || Nf)
            kl = math.log(sdf / sd0) + (sd0**2 + (mu0 - muf)**2) / (2 * sdf**2) - 0.5
            kl_per_trait[trait] = round(kl, 4)

    # ---- 5. Survival curves for causal-horizon (lead-time at which urgency crossed 70) ----
    horizon_agents = [a for a in final_population if a.get("urgency_at_alert") is not None]
    horizon_survival = None
    if horizon_agents:
        lead_times = sorted([a["urgency_at_alert"] for a in horizon_agents if a.get("urgency_at_alert")])
        n_h = len(lead_times)
        km_t, km_s = [], []
        for i, t in enumerate(lead_times):
            km_t.append(round(t, 1))
            km_s.append(round(1 - (i + 1) / n_h, 4))
        horizon_survival = {"times": km_t, "survival": km_s}

    # ---- 6. Human-readable insight cards ----
    insight_cards = _generate_cards(trait_drift_corr, generations, culture_groups, kl_per_trait, anova_p)

    # ---- 7. Signal effectiveness (which behavioral signals correlate with urgency) ----
    urgency_vals = np.array([a.get("urgency_score") or 0 for a in final_population])
    signal_effectiveness = []
    for trait in TRAITS:
        trait_vals = np.array([a["genome"][trait] for a in final_population])
        if urgency_vals.std() < 1e-6:
            continue
        r, p = stats.pearsonr(trait_vals, urgency_vals)
        signal_effectiveness.append({
            "trait": trait,
            "r_urgency": round(float(r), 3),
            "p_urgency": round(float(p), 4),
        })
    signal_effectiveness.sort(key=lambda x: abs(x["r_urgency"]), reverse=True)

    return {
        "trait_drift_correlations": trait_drift_corr,
        "anova": {
            "f_statistic": round(float(f_stat), 3),
            "p_value": round(float(anova_p), 4),
            "significant": bool(anova_p < 0.05),
            "culture_mean_drift": {c: round(float(np.mean(v)), 3) for c, v in culture_groups.items()},
        },
        "pca": {
            "points": pca_points,
            "variance_explained": [round(float(v), 4) for v in var_exp],
            "loadings": pca_loadings,
        },
        "kl_divergence": kl_per_trait,
        "horizon_survival": horizon_survival,
        "signal_effectiveness": signal_effectiveness,
        "insight_cards": insight_cards,
    }


def _generate_cards(trait_drift_corr, generations, culture_groups, kl_per_trait, anova_p) -> list[dict]:
    cards = []

    # Strongest trait-drift correlations
    corrs = []
    for trait, drift_dict in trait_drift_corr.items():
        for dt, stat in drift_dict.items():
            r, p = stat["r"], stat["p"]
            if abs(r) > 0.12 and p < 0.15:
                corrs.append((trait, dt, r, p))
    corrs.sort(key=lambda x: abs(x[2]), reverse=True)

    for trait, dt, r, p in corrs[:4]:
        direction = "increases" if r > 0 else "reduces"
        sig = "high" if p < 0.05 else "moderate"
        trait_label = trait.replace("_", " ")
        dt_label = dt.replace("_", " ")
        cards.append({
            "type": "correlation",
            "title": f"{trait_label.title()} {direction} {dt_label}",
            "body": (f"Agents with elevated {trait_label} show {'more' if r > 0 else 'less'} "
                     f"{dt_label} drift across generations (r={r:+.2f}, p={p:.3f}). "
                     f"{'Consider weighting this trait in the drift model.' if sig == 'high' else 'Marginal effect — monitor across more generations.'}"),
            "stat": f"r = {r:+.2f}",
            "significance": sig,
            "drift_type": dt,
        })

    # Cultural ANOVA finding
    if anova_p < 0.05 and culture_groups:
        worst = max(culture_groups, key=lambda c: float(np.mean(culture_groups[c])))
        best  = min(culture_groups, key=lambda c: float(np.mean(culture_groups[c])))
        cards.append({
            "type": "anova",
            "title": "Culture significantly drives drift rate",
            "body": (f"One-way ANOVA confirms drift rates differ significantly across cultures "
                     f"(p={anova_p:.4f}). {worst} shows the highest drift; {best} the lowest. "
                     f"Cultural ambient_stress is the primary driver — consider it as a model covariate."),
            "stat": f"p = {anova_p:.4f}",
            "significance": "high",
        })

    # Genome evolution finding
    if kl_per_trait:
        most_shifted = max(kl_per_trait, key=kl_per_trait.get)
        kl_val = kl_per_trait[most_shifted]
        if kl_val > 0.01:
            cards.append({
                "type": "evolution",
                "title": f"{most_shifted.replace('_', ' ').title()} under selection",
                "body": (f"KL divergence of {kl_val:.3f} nats between generation 0 and final for "
                         f"{most_shifted.replace('_', ' ')} — the largest genome shift. "
                         f"Selection pressure is reshaping this trait, suggesting it strongly predicts fitness."),
                "stat": f"KL = {kl_val:.3f} nats",
                "significance": "high" if kl_val > 0.05 else "moderate",
            })

    # Generational drift trend
    if len(generations) >= 4:
        early_drift = float(np.mean([g["stats"]["drift_rate"] for g in generations[:len(generations)//3]]))
        late_drift  = float(np.mean([g["stats"]["drift_rate"] for g in generations[-len(generations)//3:]]))
        delta = late_drift - early_drift
        if abs(delta) > 0.02:
            direction = "decreases" if delta < 0 else "increases"
            cards.append({
                "type": "trend",
                "title": f"Population drift rate {direction} over generations",
                "body": (f"Mean drift rate moved from {early_drift:.1%} (early) to {late_drift:.1%} (late). "
                         f"{'Selection is successfully pruning high-drift genomes.' if delta < 0 else 'Ambient stress is rising faster than adaptation — cultural feedback loop detected.'} "
                         f"The behavioral-drift baseline window may need tuning."),
                "stat": f"Δ = {delta:+.1%}",
                "significance": "high" if abs(delta) > 0.05 else "moderate",
            })

    return cards
