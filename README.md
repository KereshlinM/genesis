# genesis

Population genetics simulator that validates [behavioral-drift](https://github.com/KereshlinM/behavioral-drift) and [causal-horizon](https://github.com/KereshlinM/causal-horizon) through synthetic agent evolution.

## What it does

Genesis simulates populations of agents across generations, each with a six-trait genome (risk tolerance, attention span, stress sensitivity, adaptability, novelty seeking, social conformity) embedded in a Watts-Strogatz small-world social network.

Each generation, agents run behavioral sessions. Their raw events are sent to the behavioral-drift API for real-time drift scoring, and agents approaching lifecycle deadlines push signal observations to causal-horizon for urgency tracking. When the live APIs are unreachable, genesis falls back to internal implementations of both scoring engines.

After the final generation, the simulator runs statistical analysis:

- **Pearson r** — 30 trait x drift-type correlation pairs
- **One-way ANOVA** — drift rates across cultures (F-statistic + p-value)
- **PCA** — eigendecomposition of the genome covariance matrix, 2-component scatter
- **KL divergence** — genome distribution shift from generation 0 to final per trait
- **Kaplan-Meier survival** — urgency alert lead-time curves from causal-horizon data
- **Shannon entropy** — allele diversity measurement per generation

## Architecture

```
backend/
  app/
    simulation/
      genome.py       # Beta(2,2) init, BLX-alpha crossover, Gaussian mutation
      culture.py      # 5 named cultures, ambient_stress feedback loop
      behavioral.py   # metric generation from genome+culture, raw event synthesis
      drift.py        # internal fallback drift scorer (mirrors behavioral-drift)
      network.py      # Watts-Strogatz small-world graph, social influence
      insights.py     # all statistical methods
      engine.py       # main orchestrator, async generation loop, live API calls
    routers/
      simulations.py  # REST API with BackgroundTasks for async execution
    main.py           # FastAPI app

frontend/
  src/
    pages/
      Simulator.tsx   # config form, progress bar, history table
      Population.tsx  # force graph + genome heatmap
      Generations.tsx # scrubber + line charts
      Insights.tsx    # PCA scatter, correlation heatmap, insight cards
    components/
      ForceGraph.tsx  # canvas Verlet physics force-directed graph
      GenomeHeatmap.tsx # SVG agents x traits grid
```

## Quickstart

```bash
# Backend (requires Python 3.12+)
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev
```

Or with Docker:

```bash
docker compose up
```

Open `http://localhost:5173`.

## Configuration

Set `DRIFT_API_URL` + `DRIFT_API_KEY` and `HORIZON_API_URL` + `HORIZON_API_KEY` in `.env` (or the frontend form) to enable live API validation. Without them, genesis uses internal fallback scorers.

Scale presets:

| Preset | Agents | Generations | Sessions/agent |
|--------|--------|-------------|----------------|
| small  | 50     | 8           | 3              |
| medium | 200    | 15          | 4              |
| large  | 500    | 25          | 5              |

## Simulation mechanics

**Genome:** Six traits, each in [0,1], initialized from Beta(2,2) (concentrates near 0.5). BLX-alpha blend crossover + Gaussian mutation (default rate 0.05).

**Culture:** Five named palettes (Verdania, Ignara, Solveth, Kresh, Nulmara) with distinct ambient stress, pace, tech fluency, and collectivism. Ambient stress feeds back from the population's drift rate each generation, creating emergent instability in high-drift cultures.

**Social network:** Watts-Strogatz ring lattice (k=6, p=0.12 rewiring). Agents with high social conformity blend their genome toward the mean of their immediate neighbours each generation.

**Selection:** Fitness-proportional selection. Drift events penalize fitness (scaled by drift score). Culture is inherited from the fitter parent with a 5% random culture switch rate.
