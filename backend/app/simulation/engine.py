"""
Main simulation engine.

Each generation:
  1. Each agent runs `sessions_per_agent` behavioural sessions
  2. Raw events are sent to behavioral-drift API (or scored internally as fallback)
  3. Drift scores update agent fitness and baseline
  4. Agents with active lifecycle events push signal observations to causal-horizon
  5. Urgency scores are recorded
  6. Population reproduces (tournament selection + BLX crossover + mutation)
  7. Cultures evolve based on aggregate drift rate
  8. Social influence updates genomes of high-conformity agents
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np

from app.simulation.behavioral import (
    METRIC_NAMES, N_METRICS,
    generate_metrics, generate_raw_events, metrics_to_dict,
)
from app.simulation.culture import evolve_culture, init_cultures
from app.simulation.drift import DRIFT_TYPES, score_drift
from app.simulation.genome import (
    N_TRAITS, TRAITS,
    crossover, genome_to_dict, mutate, random_genomes, shannon_diversity,
)
from app.simulation.insights import compute_insights
from app.simulation.network import (
    apply_social_influence, build_small_world, clustering_coefficient, edge_list,
)

HORIZON_FRACTION = 0.3   # fraction of agents that face lifecycle events each generation
HORIZON_WINDOW_H = 48.0  # causal window in hours for lifecycle events


async def run_simulation(config: dict, progress_cb=None) -> dict:
    """
    Execute a full simulation and return the result dict.
    `progress_cb(gen_index, total_gens, partial_result)` is called after each generation.
    """
    rng = np.random.default_rng(config.get("seed", int(time.time())))
    n_pop      = int(config["population_size"])
    n_gen      = int(config["num_generations"])
    n_cultures = min(int(config.get("num_cultures", 3)), 5)
    mut_rate   = float(config.get("mutation_rate", 0.05))
    sessions   = int(config.get("sessions_per_agent", 4))

    drift_url = config.get("drift_api_url", "")
    drift_key = config.get("drift_api_key", "")
    horiz_url = config.get("horizon_api_url", "")
    horiz_key = config.get("horizon_api_key", "")

    # ---- Initialise ----
    cultures     = init_cultures(n_cultures, rng)
    genomes      = random_genomes(n_pop, rng)
    culture_ids  = np.array([i % n_cultures for i in range(n_pop)], dtype=int)
    adj          = build_small_world(n_pop, k=6, p=0.12, rng=rng)

    # Rolling baselines per agent
    baselines     = np.full((n_pop, N_METRICS), -1.0, dtype=np.float32)
    baseline_stds = np.full((n_pop, N_METRICS),  0.1, dtype=np.float32)
    baseline_counts = np.zeros(n_pop, dtype=int)

    # Lifetime drift counters
    drift_counts       = np.zeros(n_pop, dtype=int)
    drift_type_counts  = np.zeros((n_pop, len(DRIFT_TYPES)), dtype=int)
    fitness            = np.ones(n_pop, dtype=np.float32)

    # Causal-horizon tracking
    urgency_scores = np.zeros(n_pop, dtype=np.float32)
    urgency_at_alert = np.full(n_pop, -1.0, dtype=np.float32)  # lead_time_h when alert fired

    generations: list[dict] = []

    async with httpx.AsyncClient(timeout=8.0) as client:
        for gen_idx in range(n_gen):
            gen_drift_events: list[dict | None] = []
            gen_api_calls = {"drift_sessions": 0, "horizon_observes": 0, "failures": 0}
            time_pressure = gen_idx / max(1, n_gen - 1)  # ramps 0→1 over generations

            # Decide which agents face lifecycle events this generation
            horizon_mask = rng.random(n_pop) < HORIZON_FRACTION

            # ---- Per-agent sessions ----
            sem = asyncio.Semaphore(20)
            tasks = [
                _agent_generation(
                    agent_idx=i,
                    genome=genomes[i],
                    culture=cultures[int(culture_ids[i])],
                    baseline=baselines[i] if baseline_counts[i] >= 2 else None,
                    baseline_std=baseline_stds[i] if baseline_counts[i] >= 2 else None,
                    sessions=sessions,
                    time_pressure=time_pressure,
                    rng=rng,
                    client=client,
                    drift_url=drift_url,
                    drift_key=drift_key,
                    horiz_url=horiz_url,
                    horiz_key=horiz_key,
                    sim_id=config.get("sim_id", "sim"),
                    gen_idx=gen_idx,
                    has_horizon_event=bool(horizon_mask[i]),
                    window_hours=HORIZON_WINDOW_H,
                    sem=sem,
                )
                for i in range(n_pop)
            ]
            results = await asyncio.gather(*tasks)

            # ---- Aggregate results ----
            for i, res in enumerate(results):
                metrics   = res["metrics"]
                drift_evt = res.get("drift")
                urgency   = res.get("urgency_score", 0.0)

                # Update rolling baseline (exponential moving average)
                if baseline_counts[i] == 0:
                    baselines[i] = metrics
                    baseline_stds[i] = np.full(N_METRICS, 0.1, dtype=np.float32)
                else:
                    alpha = 0.2
                    diff = metrics - baselines[i]
                    baselines[i]     = baselines[i] + alpha * diff
                    baseline_stds[i] = np.sqrt((1 - alpha) * baseline_stds[i]**2 + alpha * diff**2)
                baseline_counts[i] += 1

                if drift_evt:
                    drift_counts[i] += 1
                    dt_idx = DRIFT_TYPES.index(drift_evt["type"])
                    drift_type_counts[i, dt_idx] += 1
                    # Fitness penalty scales with drift score
                    fitness[i] *= max(0.05, 1.0 - drift_evt["score"] * 0.18)

                urgency_scores[i] = urgency
                if urgency >= 70 and urgency_at_alert[i] < 0:
                    urgency_at_alert[i] = float(res.get("lead_time_h") or 0)

                gen_drift_events.append(drift_evt)
                gen_api_calls["drift_sessions"]  += res.get("api_drift", 0)
                gen_api_calls["horizon_observes"] += res.get("api_horizon", 0)
                gen_api_calls["failures"]         += res.get("api_failures", 0)

            # ---- Generation stats ----
            drift_this_gen = sum(1 for d in gen_drift_events if d)
            drift_rate     = drift_this_gen / n_pop
            diversity      = shannon_diversity(genomes)

            per_culture_stats = []
            for c in cultures:
                mask = culture_ids == c["id"]
                c_drift = sum(1 for i, d in enumerate(gen_drift_events) if mask[i] and d)
                per_culture_stats.append({
                    **{k: round(v, 4) if isinstance(v, float) else v for k, v in c.items()},
                    "drift_rate": round(c_drift / max(1, mask.sum()), 4),
                    "size": int(mask.sum()),
                })

            drift_by_type = {dt: int(sum(1 for d in gen_drift_events if d and d["type"] == dt))
                             for dt in DRIFT_TYPES}

            gen_result = {
                "index": gen_idx,
                "stats": {
                    "drift_rate":    round(float(drift_rate), 4),
                    "mean_fitness":  round(float(fitness.mean()), 4),
                    "diversity_entropy": round(diversity, 4),
                    "drift_by_type": drift_by_type,
                    "mean_genome":   {t: round(float(genomes[:, j].mean()), 4) for j, t in enumerate(TRAITS)},
                    "std_genome":    {t: round(float(genomes[:, j].std()), 4)  for j, t in enumerate(TRAITS)},
                    "mean_urgency":  round(float(urgency_scores.mean()), 2),
                },
                "cultures": per_culture_stats,
                "api_calls": gen_api_calls,
            }
            generations.append(gen_result)

            if progress_cb:
                await progress_cb(gen_idx + 1, n_gen, generations)

            # ---- Evolution ----
            genomes, culture_ids = _reproduce(genomes, culture_ids, fitness, mut_rate, n_cultures, rng)
            genomes = apply_social_influence(genomes, adj, rng)
            for c in cultures:
                mask = culture_ids == c["id"]
                dr = float(np.mean([1 if gen_drift_events[i] else 0 for i in range(n_pop) if mask[i]] or [0]))
                cultures[c["id"]] = evolve_culture(c, dr, rng)

    # ---- Final population snapshot ----
    cc = clustering_coefficient(adj)
    n_edges = int(adj.sum() / 2)
    edges = edge_list(adj)

    most_common_drift = []
    for i in range(n_pop):
        if drift_type_counts[i].sum() == 0:
            most_common_drift.append(None)
        else:
            most_common_drift.append(DRIFT_TYPES[int(drift_type_counts[i].argmax())])

    final_population = [
        {
            "id": i,
            "culture": cultures[int(culture_ids[i])]["name"],
            "culture_id": int(culture_ids[i]),
            "genome": genome_to_dict(genomes[i]),
            "drift_count": int(drift_counts[i]),
            "most_common_drift": most_common_drift[i],
            "fitness": round(float(fitness[i]), 4),
            "urgency_score": round(float(urgency_scores[i]), 2),
            "urgency_at_alert": round(float(urgency_at_alert[i]), 2) if urgency_at_alert[i] >= 0 else None,
            "connections": [c for c in np.where(adj[i] > 0)[0].tolist()],
        }
        for i in range(n_pop)
    ]

    insights = compute_insights(generations, final_population)

    return {
        "generations": generations,
        "final_population": final_population,
        "edge_list": edges,
        "social_network": {
            "n_nodes": n_pop,
            "n_edges": n_edges,
            "clustering_coefficient": round(cc, 4),
        },
        "cultures": cultures,
        "insights": insights,
    }


async def _agent_generation(
    agent_idx, genome, culture, baseline, baseline_std,
    sessions, time_pressure, rng,
    client, drift_url, drift_key, horiz_url, horiz_key,
    sim_id, gen_idx, has_horizon_event, window_hours, sem
) -> dict:
    async with sem:
        all_metrics = np.zeros(N_METRICS, dtype=np.float32)
        drift_result = None
        api_drift = api_horizon = api_failures = 0
        lead_time_h = None
        urgency_score = 0.0

        for s_idx in range(sessions):
            tp = time_pressure if s_idx == sessions - 1 else 0.0
            metrics = generate_metrics(genome, culture, rng, time_pressure=tp)
            all_metrics += metrics / sessions

            # Drift scoring
            if drift_url and drift_key and s_idx == sessions - 1:
                dr = await _call_drift_api(client, drift_url, drift_key,
                                           agent_idx, sim_id, gen_idx, metrics, rng)
                if dr is not None:
                    drift_result = dr
                    api_drift = 1
                else:
                    api_failures += 1

        # Internal fallback drift scoring
        if drift_result is None and baseline is not None:
            drift_result = score_drift(all_metrics, baseline, baseline_std)

        # Causal horizon
        if has_horizon_event and horiz_url and horiz_key:
            urg, lt, ok = await _call_horizon_api(
                client, horiz_url, horiz_key,
                agent_idx, sim_id, gen_idx, all_metrics, genome, culture, window_hours
            )
            if ok:
                urgency_score = urg
                lead_time_h = lt
                api_horizon = 1
            else:
                api_failures += 1

        if urgency_score == 0.0:
            # Internal urgency approximation based on time_pressure
            urgency_score = float(time_pressure * 60 + (drift_result["score"] * 5 if drift_result else 0))
            urgency_score = min(100.0, urgency_score)

        return {
            "metrics": all_metrics,
            "drift": drift_result,
            "urgency_score": urgency_score,
            "lead_time_h": lead_time_h,
            "api_drift": api_drift,
            "api_horizon": api_horizon,
            "api_failures": api_failures,
        }


async def _call_drift_api(client, base_url, api_key, agent_idx, sim_id, gen_idx, metrics, rng):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    user_id = f"genesis-{sim_id}-a{agent_idx}"
    try:
        r = await client.post(f"{base_url}/api/v1/sessions/start",
                              json={"external_id": user_id, "context": f"gen-{gen_idx}"},
                              headers=headers)
        if r.status_code not in (200, 201):
            return None
        session_id = r.json()["id"]

        events = generate_raw_events(metrics, rng)
        await client.post(f"{base_url}/api/v1/sessions/{session_id}/events",
                          json={"events": events}, headers=headers)

        r2 = await client.post(f"{base_url}/api/v1/sessions/{session_id}/end", headers=headers)
        if r2.status_code not in (200, 201):
            return None
        body = r2.json()
        if body.get("drift"):
            d = body["drift"]
            return {
                "type": d.get("drift_type", "unknown"),
                "score": float(d.get("score", 0)),
                "severity": d.get("severity", "low"),
                "all_scores": {},
                "source": "api",
            }
        return None
    except Exception:
        return None


async def _call_horizon_api(client, base_url, api_key, agent_idx, sim_id, gen_idx,
                             metrics, genome, culture, window_hours):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    entity_id = f"genesis-{sim_id}-a{agent_idx}"
    from datetime import timedelta
    deadline = (datetime.now(timezone.utc) + timedelta(hours=window_hours * (1 - gen_idx * 0.02))).isoformat()
    try:
        await client.post(f"{base_url}/api/v1/entities",
                          json={"external_id": entity_id, "entity_type": "genesis_agent",
                                "deadline_at": deadline, "window_hours": window_hours},
                          headers=headers)
        # Push 3 signals derived from behavioral metrics
        stress_idx  = float(metrics[4]) + float(metrics[5])  # backspace + hesitation
        engagement  = float(metrics[10]) / 480.0              # normalised session duration
        error_rate  = float(metrics[4])

        for sig, val in [("stress_index", stress_idx), ("engagement_score", engagement),
                          ("error_rate", error_rate)]:
            await client.post(f"{base_url}/api/v1/entities/{entity_id}/observe",
                              json={"signal": sig, "value": val}, headers=headers)

        r = await client.get(f"{base_url}/api/v1/entities/{entity_id}", headers=headers)
        if r.status_code == 200:
            body = r.json()
            urg = float(body.get("urgency_score", 0))
            ud = body.get("urgency_detail") or {}
            lt = ud.get("lead_time_h")
            return urg, lt, True
        return 0.0, None, False
    except Exception:
        return 0.0, None, False


def _reproduce(genomes, culture_ids, fitness, mut_rate, n_cultures, rng):
    n = len(genomes)
    new_genomes     = np.zeros_like(genomes)
    new_culture_ids = np.zeros_like(culture_ids)
    safe_fitness = fitness - fitness.min() + 1e-6
    probs = safe_fitness / safe_fitness.sum()

    for i in range(n):
        # Tournament selection (size 4)
        c1 = int(rng.choice(n, p=probs))
        c2 = int(rng.choice(n, p=probs))
        child = crossover(genomes[c1], genomes[c2], rng)
        child = mutate(child, mut_rate, rng)
        new_genomes[i] = child
        # Culture inherited from fitter parent; 5% random culture switch
        if rng.random() < 0.05:
            new_culture_ids[i] = rng.integers(0, n_cultures)
        else:
            new_culture_ids[i] = culture_ids[c1] if fitness[c1] >= fitness[c2] else culture_ids[c2]

    return new_genomes.astype(np.float32), new_culture_ids
