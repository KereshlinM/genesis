import { useState } from "react";
import type { SimResult, GenerationStats } from "../api";
import { cultureColor, fmt, pct } from "../hooks";
import { TRAITS, DRIFT_TYPES } from "../constants";

interface Props { sim: SimResult | null }

const W = 460, H = 160;

function LineChart({ series, colors, labels }: {
  series: number[][];
  colors: string[];
  labels?: string[];
}) {
  if (!series.length || !series[0].length) return null;
  const n = series[0].length;
  if (n < 2) return null;

  const allVals = series.flat();
  const min = Math.min(...allVals), max = Math.max(...allVals) + 1e-9;

  const toSvg = (vals: number[]) =>
    vals.map((v, i) =>
      `${(i / (n - 1)) * W},${H - ((v - min) / (max - min)) * H}`
    ).join(" ");

  return (
    <svg width={W} height={H} className="mini-chart" style={{ marginTop: 8 }}>
      {series.map((vals, si) => (
        <polyline key={si} points={toSvg(vals)} stroke={colors[si]} opacity={0.85} />
      ))}
      {labels && (
        <g>
          {labels.map((l, i) => (
            <text key={l} x={W - 4} y={12 + i * 14} textAnchor="end" fontSize={9} fill={colors[i]}>{l}</text>
          ))}
        </g>
      )}
    </svg>
  );
}

export default function Generations({ sim }: Props) {
  const [scrubIdx, setScrubIdx] = useState(0);

  if (!sim?.result) return <div className="empty">Run a simulation to see generation data</div>;

  const gens: GenerationStats[] = sim.result.generations;
  if (!gens.length) return <div className="empty">No generation data yet</div>;

  const gen = gens[Math.min(scrubIdx, gens.length - 1)];

  const cultureNames = [...new Set(gens.flatMap(g => g.cultures.map(c => c.name)))];

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Generations</div>
          <div className="page-sub">{sim.name} — {gens.length} generations</div>
        </div>
      </div>

      <div className="scrubber">
        <span className="scrubber-label">Generation 0</span>
        <input type="range" min={0} max={gens.length - 1} value={scrubIdx}
          onChange={e => setScrubIdx(Number(e.target.value))} />
        <span className="scrubber-label">Gen {scrubIdx} / {gens.length - 1}</span>
      </div>

      <div className="stat-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Drift Rate</div>
          <div className="stat-value red">{pct(gen.stats.drift_rate)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Mean Fitness</div>
          <div className="stat-value green">{fmt(gen.stats.mean_fitness, 3)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Diversity</div>
          <div className="stat-value violet">{fmt(gen.stats.diversity_entropy, 2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Mean Urgency</div>
          <div className="stat-value cyan">{fmt(gen.stats.mean_urgency, 1)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">API Drift Calls</div>
          <div className="stat-value">{gen.api_calls.drift_sessions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">API Horizon Calls</div>
          <div className="stat-value">{gen.api_calls.horizon_observes}</div>
        </div>
      </div>

      <div className="two-col" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">Drift Rate over Time</div>
          <LineChart
            series={[gens.map(g => g.stats.drift_rate)]}
            colors={["var(--red)"]}
          />
          <LineChart
            series={[gens.map(g => g.stats.mean_fitness)]}
            colors={["var(--green)"]}
            labels={["fitness"]}
          />
        </div>

        <div className="card">
          <div className="card-title">Drift by Type</div>
          <LineChart
            series={DRIFT_TYPES.map(dt => gens.map(g => g.stats.drift_by_type[dt] ?? 0))}
            colors={["var(--red)", "var(--yellow)", "var(--cyan)", "var(--violet)", "var(--pink)"]}
            labels={DRIFT_TYPES.map(d => d.split("_")[0])}
          />
        </div>
      </div>

      <div className="two-col" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">Genome Trait Means</div>
          <LineChart
            series={TRAITS.map(t => gens.map(g => g.stats.mean_genome[t] ?? 0.5))}
            colors={["#22d3ee","#a78bfa","#f472b6","#fb923c","#34d399","#facc15"]}
            labels={TRAITS.map(t => t.split("_")[0])}
          />
        </div>

        <div className="card">
          <div className="card-title">Culture Drift Rates (Gen {scrubIdx})</div>
          {gen.cultures.map((c, i) => (
            <div key={c.name} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                <span style={{ color: cultureColor(i) }}>{c.name}</span>
                <span style={{ color: "var(--muted)" }}>
                  drift {pct(c.drift_rate)} / stress {fmt(c.ambient_stress, 2)}
                </span>
              </div>
              <div className="progress-bar">
                <div style={{ height: "100%", width: `${c.drift_rate * 100}%`, background: cultureColor(i), borderRadius: 3 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
