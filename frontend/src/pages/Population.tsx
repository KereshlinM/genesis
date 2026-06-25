import { useState } from "react";
import type { SimResult } from "../api";
import ForceGraph from "../components/ForceGraph";
import GenomeHeatmap from "../components/GenomeHeatmap";
import { cultureColor, driftColor, fmt, pct } from "../hooks";
import { DRIFT_TYPES } from "../constants";

interface Props { sim: SimResult | null }

export default function Population({ sim }: Props) {
  const [colorBy, setColorBy] = useState<"culture" | "drift" | "fitness">("culture");

  if (!sim?.result) {
    return <div className="empty">Run a simulation to see population data</div>;
  }

  const { final_population: pop, edge_list, social_network } = sim.result;
  const cultures = sim.result.cultures ?? [];

  const driftCounts: Record<string, number> = {};
  for (const a of pop) {
    if (a.most_common_drift) driftCounts[a.most_common_drift] = (driftCounts[a.most_common_drift] ?? 0) + 1;
  }

  const meanFitness = pop.reduce((s, a) => s + a.fitness, 0) / pop.length;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Population</div>
          <div className="page-sub">
            {sim.name} — {pop.length} agents, {social_network.n_edges} social edges
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {(["culture", "drift", "fitness"] as const).map(m => (
            <button key={m} className={`btn btn-sm ${colorBy === m ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setColorBy(m)}>
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="stat-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Population</div>
          <div className="stat-value cyan">{pop.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Clustering Coeff.</div>
          <div className="stat-value violet">{fmt(social_network.clustering_coefficient, 3)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Mean Fitness</div>
          <div className="stat-value green">{fmt(meanFitness, 3)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Cultures</div>
          <div className="stat-value">{cultures.length}</div>
        </div>
      </div>

      <div className="two-col" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">Social Network</div>
          <ForceGraph agents={pop} edges={edge_list} colorBy={colorBy} width={480} height={380} />
        </div>
        <div className="card">
          <div className="card-title">Genome Heatmap (agents x traits)</div>
          <GenomeHeatmap agents={pop} />
          <div style={{ marginTop: 12, fontSize: 11, color: "var(--muted)" }}>
            Green = high value, Red = low. Rows = agents (up to 80), Columns = traits.
          </div>
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <div className="card-title">Culture Distribution</div>
          {cultures.map((c, i) => {
            const count = pop.filter(a => a.culture_id === c.id).length;
            const bar = count / pop.length;
            return (
              <div key={c.name} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: cultureColor(i) }}>{c.name}</span>
                  <span style={{ color: "var(--muted)" }}>{count} agents</span>
                </div>
                <div className="progress-bar">
                  <div style={{ height: "100%", width: `${bar * 100}%`, background: cultureColor(i), borderRadius: 3 }} />
                </div>
              </div>
            );
          })}
        </div>

        <div className="card">
          <div className="card-title">Drift Type Distribution</div>
          {DRIFT_TYPES.map(dt => {
            const count = driftCounts[dt] ?? 0;
            const bar = count / pop.length;
            return (
              <div key={dt} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: driftColor(dt) }}>{dt.replace(/_/g, " ")}</span>
                  <span style={{ color: "var(--muted)" }}>{count}</span>
                </div>
                <div className="progress-bar">
                  <div style={{ height: "100%", width: `${bar * 100}%`, background: driftColor(dt), borderRadius: 3 }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
