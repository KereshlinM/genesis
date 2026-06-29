from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SimulationRun
from app.simulation.engine import run_simulation
from app.config import get_settings

router = APIRouter(prefix="/api/v1/simulations", tags=["simulations"])

SCALE_PRESETS = {
    "small":  {"population_size": 50,  "num_generations": 8,  "sessions_per_agent": 3, "num_cultures": 2},
    "medium": {"population_size": 200, "num_generations": 15, "sessions_per_agent": 4, "num_cultures": 3},
    "large":  {"population_size": 500, "num_generations": 25, "sessions_per_agent": 5, "num_cultures": 5},
}

# In-memory store of live progress (keyed by sim id)
_progress: dict[str, list] = {}


class SimulationCreate(BaseModel):
    name: str = Field(default="", max_length=120)
    scale: str = Field(default="small", pattern="^(small|medium|large|custom)$")
    population_size: int | None = Field(default=None, ge=10, le=2000)
    num_generations: int | None = Field(default=None, ge=2, le=100)
    num_cultures: int | None = Field(default=None, ge=1, le=5)
    sessions_per_agent: int | None = Field(default=None, ge=1, le=10)
    mutation_rate: float = Field(default=0.05, ge=0.0, le=0.5)
    drift_api_url: str = Field(default="")
    drift_api_key: str = Field(default="")
    horizon_api_url: str = Field(default="")
    horizon_api_key: str = Field(default="")
    test_mode: str = Field(default="full", pattern="^(full|drift_only|horizon_only|internal_only|comparison)$")
    seed: int | None = None


@router.post("", status_code=202)
async def create_simulation(
    body: SimulationCreate,
    bg: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    preset = SCALE_PRESETS.get(body.scale, SCALE_PRESETS["small"])
    sim_id = str(uuid.uuid4())[:8]

    config = {
        **preset,
        "mutation_rate": body.mutation_rate,
        "drift_api_url":  body.drift_api_url  or settings.drift_api_url,
        "drift_api_key":  body.drift_api_key  or settings.drift_api_key,
        "horizon_api_url": body.horizon_api_url or settings.horizon_api_url,
        "horizon_api_key": body.horizon_api_key or settings.horizon_api_key,
        "test_mode": body.test_mode,
        "sim_id": sim_id,
    }
    if body.population_size  is not None: config["population_size"]  = body.population_size
    if body.num_generations  is not None: config["num_generations"]  = body.num_generations
    if body.num_cultures     is not None: config["num_cultures"]     = body.num_cultures
    if body.sessions_per_agent is not None: config["sessions_per_agent"] = body.sessions_per_agent
    if body.seed is not None: config["seed"] = body.seed

    run = SimulationRun(
        id=sim_id,
        name=body.name or f"Run {sim_id}",
        config=config,
        status="pending",
        progress=0,
    )
    db.add(run)
    await db.commit()

    _progress[sim_id] = []
    bg.add_task(_run_background, sim_id, config)
    return {"id": sim_id, "status": "pending"}


@router.get("")
async def list_simulations(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(SimulationRun).order_by(SimulationRun.created_at.desc()).limit(50)
    )).scalars().all()
    return [_summary(r) for r in rows]


@router.get("/{sim_id}")
async def get_simulation(sim_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_or_404(sim_id, db)
    return _full(run)


@router.get("/{sim_id}/progress")
async def get_progress(sim_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_or_404(sim_id, db)
    generations = _progress.get(sim_id, [])
    if run.status == "completed" and run.result:
        generations = run.result.get("generations", generations)
    return {
        "id": sim_id,
        "status": run.status,
        "progress": run.progress,
        "total": run.config.get("num_generations", 0),
        "generations": generations,
    }


@router.delete("/{sim_id}", status_code=204)
async def delete_simulation(sim_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_or_404(sim_id, db)
    await db.delete(run)
    await db.commit()
    _progress.pop(sim_id, None)


# ---- helpers ----

async def _get_or_404(sim_id: str, db: AsyncSession) -> SimulationRun:
    run = await db.get(SimulationRun, sim_id)
    if not run:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return run


def _summary(run: SimulationRun) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "progress": run.progress,
        "total_generations": run.config.get("num_generations"),
        "population_size": run.config.get("population_size"),
        "final_drift_rate": run.final_drift_rate,
        "final_diversity": run.final_diversity,
        "total_drift_events": run.total_drift_events,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _full(run: SimulationRun) -> dict:
    return {**_summary(run), "config": run.config, "result": run.result}


async def _run_background(sim_id: str, config: dict):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        run = await db.get(SimulationRun, sim_id)
        run.status = "running"
        await db.commit()

        async def progress_cb(gen_done: int, total: int, gens: list):
            _progress[sim_id] = gens
            r = await db.get(SimulationRun, sim_id)
            r.progress = gen_done
            await db.commit()

        try:
            result = await run_simulation(config, progress_cb=progress_cb)
            run = await db.get(SimulationRun, sim_id)
            run.status = "completed"
            run.result = result
            gens = result.get("generations", [])
            if gens:
                run.final_drift_rate   = gens[-1]["stats"]["drift_rate"]
                run.final_diversity    = gens[-1]["stats"]["diversity_entropy"]
                run.total_drift_events = sum(
                    sum(g["stats"]["drift_by_type"].values()) for g in gens
                )
            _progress[sim_id] = gens
        except Exception as exc:
            run = await db.get(SimulationRun, sim_id)
            run.status = "failed"
            run.result = {"error": str(exc)}

        await db.commit()
