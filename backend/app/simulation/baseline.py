"""
Baseline validation tests for external drift and horizon APIs.

Each scenario has a known expected outcome derived from extreme genome values.
Results expose whether the external model agrees with genesis's internal reference scorer.
All tests run before the main generation loop and are stored in the simulation result.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import numpy as np

from app.simulation.behavioral import generate_metrics, generate_raw_events
from app.simulation.drift import score_drift

# ---------------------------------------------------------------------------
# Drift baseline scenarios
# ---------------------------------------------------------------------------

DRIFT_SCENARIOS = [
    {
        "name": "cognitive_overload",
        "description": "High stress sensitivity, low adaptability in a high-pressure culture",
        "genome": np.array([0.5, 0.5, 0.95, 0.05, 0.3, 0.5], dtype=np.float32),
        "culture": {"ambient_stress": 0.9, "pace": 0.7, "tech_fluency": 0.5},
        "time_pressure": 0.85,
        "expected_type": "cognitive_overload",
    },
    {
        "name": "disengagement",
        "description": "Low attention span, low-pace culture — agent disengages quickly",
        "genome": np.array([0.2, 0.05, 0.2, 0.5, 0.7, 0.5], dtype=np.float32),
        "culture": {"ambient_stress": 0.15, "pace": 0.15, "tech_fluency": 0.6},
        "time_pressure": 0.0,
        "expected_type": "disengagement",
    },
    {
        "name": "unusual_urgency",
        "description": "High risk tolerance, high-pace culture — frenetic interaction pattern",
        "genome": np.array([0.95, 0.5, 0.1, 0.8, 0.3, 0.5], dtype=np.float32),
        "culture": {"ambient_stress": 0.2, "pace": 0.95, "tech_fluency": 0.85},
        "time_pressure": 0.0,
        "expected_type": "unusual_urgency",
    },
]

_NORMAL_GENOME  = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5], dtype=np.float32)
_NORMAL_CULTURE = {"ambient_stress": 0.3, "pace": 0.5, "tech_fluency": 0.6}
_N_WARMUP = 5   # must satisfy behavioral-drift's min_baseline_sessions

# ---------------------------------------------------------------------------
# Horizon baseline scenarios
# ---------------------------------------------------------------------------

HORIZON_SCENARIOS = [
    {"name": "early_stage",  "elapsed_fraction": 0.10, "expected_range": (0,  30)},
    {"name": "mid_stage",    "elapsed_fraction": 0.60, "expected_range": (20, 65)},
    {"name": "late_stage",   "elapsed_fraction": 0.85, "expected_range": (50, 100)},
]

_HORIZON_WINDOW_H = 48.0
_BASELINE_SIGNALS = [
    ("stress_index",     0.4),
    ("engagement_score", 0.6),
    ("error_rate",       0.1),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_drift_baselines(client, drift_url: str, drift_key: str, sim_id: str) -> list[dict] | None:
    if not (drift_url and drift_key):
        return None

    rng = np.random.default_rng(0)   # fixed seed for reproducibility
    headers = {"X-API-Key": drift_key, "Content-Type": "application/json"}
    results: list[dict] = []

    for scenario in DRIFT_SCENARIOS:
        user_id = f"bl-drift-{sim_id}-{scenario['name']}"

        # Warmup: establish behavioral baseline with N normal sessions
        warmup_metrics: list[np.ndarray] = []
        for _ in range(_N_WARMUP):
            m = generate_metrics(_NORMAL_GENOME, _NORMAL_CULTURE, rng)
            warmup_metrics.append(m)
            r = await client.post(
                f"{drift_url}/api/v1/sessions",
                json={"user_id": user_id, "context": "bl-warmup"},
                headers=headers,
            )
            if r.status_code not in (200, 201):
                break
            sid = r.json()["id"]
            await client.post(
                f"{drift_url}/api/v1/sessions/{sid}/events",
                json={"events": generate_raw_events(m, rng)},
                headers=headers,
            )
            await client.post(f"{drift_url}/api/v1/sessions/{sid}/end", headers=headers)

        if len(warmup_metrics) < _N_WARMUP:
            results.append({"scenario": scenario["name"], "error": "warmup_failed"})
            continue

        # Compute reference baseline from warmup sessions
        stack    = np.stack(warmup_metrics)
        ref_mean = stack.mean(axis=0).astype(np.float32)
        ref_std  = np.clip(stack.std(axis=0), 1e-4, None).astype(np.float32)

        # Deviant session
        test_m = generate_metrics(
            scenario["genome"], scenario["culture"], rng,
            time_pressure=scenario["time_pressure"],
        )
        internal = score_drift(test_m, ref_mean, ref_std)

        r = await client.post(
            f"{drift_url}/api/v1/sessions",
            json={"user_id": user_id, "context": "bl-test"},
            headers=headers,
        )
        if r.status_code not in (200, 201):
            results.append({"scenario": scenario["name"], "error": "test_session_failed"})
            continue

        sid = r.json()["id"]
        await client.post(
            f"{drift_url}/api/v1/sessions/{sid}/events",
            json={"events": generate_raw_events(test_m, rng)},
            headers=headers,
        )
        r2 = await client.post(f"{drift_url}/api/v1/sessions/{sid}/end", headers=headers)

        ext_body  = r2.json() if r2.status_code in (200, 201) else {}
        ext_drift = ext_body.get("drift")

        int_type = internal["type"]  if internal   else None
        ext_type = ext_drift["drift_type"] if ext_drift else None
        expected = scenario["expected_type"]

        results.append({
            "scenario":    scenario["name"],
            "description": scenario["description"],
            "expected":    expected,
            "internal": {
                "type":    int_type,
                "score":   round(internal["score"], 3) if internal else None,
                "correct": int_type == expected,
            },
            "external": {
                "type":    ext_type,
                "score":   round(float(ext_drift["score"]), 3) if ext_drift else None,
                "correct": ext_type == expected,
            },
            "agreement": int_type == ext_type,
        })

    return results


async def run_horizon_baselines(client, horiz_url: str, horiz_key: str, sim_id: str) -> list[dict] | None:
    if not (horiz_url and horiz_key):
        return None

    headers = {"X-API-Key": horiz_key, "Content-Type": "application/json"}
    results: list[dict] = []
    now = datetime.now(timezone.utc)

    for scenario in HORIZON_SCENARIOS:
        entity_id  = f"bl-horizon-{sim_id}-{scenario['name']}"
        elapsed_h  = _HORIZON_WINDOW_H * scenario["elapsed_fraction"]
        remaining_h = _HORIZON_WINDOW_H - elapsed_h
        deadline   = (now + timedelta(hours=remaining_h)).isoformat()

        await client.post(
            f"{horiz_url}/api/v1/entities",
            json={"external_id": entity_id, "entity_type": "baseline_test", "deadline_at": deadline},
            headers=headers,
        )

        for sig, val in _BASELINE_SIGNALS:
            await client.post(
                f"{horiz_url}/api/v1/entities/{entity_id}/observe",
                json={"signal": sig, "value": val},
                headers=headers,
            )

        r = await client.get(f"{horiz_url}/api/v1/entities/{entity_id}", headers=headers)
        if r.status_code != 200:
            results.append({"scenario": scenario["name"], "error": f"http {r.status_code}"})
            continue

        body    = r.json()
        urgency = float(body.get("urgency_score", 0))
        lo, hi  = scenario["expected_range"]

        results.append({
            "scenario":              scenario["name"],
            "elapsed_fraction":      scenario["elapsed_fraction"],
            "lead_time_h":           round(remaining_h, 1),
            "expected_urgency_range": list(scenario["expected_range"]),
            "actual_urgency":        round(urgency, 2),
            "in_expected_range":     lo <= urgency <= hi,
        })

    return results
