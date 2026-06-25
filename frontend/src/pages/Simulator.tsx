import { useState, useCallback } from "react";
import { api, type SimConfig, type SimSummary, type ProgressData } from "../api";
import { useAsync, useAsyncFn, usePoll, fmt, pct } from "../hooks";

function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}

interface Props {
  activeSim: string | null;
  onActiveSim: (id: string) => void;
}

export default function Simulator({ activeSim, onActiveSim }: Props) {
  const [form, setForm] = useState<SimConfig>({
    scale: "small",
    mutation_rate: 0.05,
    drift_api_url: "",
    drift_api_key: "",
    horizon_api_url: "",
    horizon_api_key: "",
  });
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { data: sims, loading, error } = useAsync(() => api.listSims(), [activeSim]);
  const { run: createSim, loading: creating } = useAsyncFn(
    useCallback((cfg: SimConfig) => api.createSim(cfg), [])
  );

  const pollFn = useCallback(
    () => (activeSim ? api.getProgress(activeSim) : Promise.resolve(null as unknown as ProgressData)),
    [activeSim]
  );
  const progress = usePoll(pollFn, 2000, !!activeSim);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const res = await createSim(form);
    if (res) onActiveSim(res.id);
  }

  const running = progress && (progress.status === "running" || progress.status === "pending");
  const pct_done = progress ? (progress.progress / Math.max(1, progress.total)) : 0;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Simulator</div>
          <div className="page-sub">Configure and launch population simulations</div>
        </div>
      </div>

      <div className="two-col" style={{ gap: 24, marginBottom: 28 }}>
        <div className="card">
          <div className="card-title">New Simulation</div>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Name</label>
              <input className="form-input" value={form.name ?? ""} placeholder="Run name (optional)"
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Scale</label>
              <select className="form-select" value={form.scale}
                onChange={e => setForm(f => ({ ...f, scale: e.target.value as SimConfig["scale"] }))}>
                <option value="small">Small (50 agents, 8 generations)</option>
                <option value="medium">Medium (200 agents, 15 generations)</option>
                <option value="large">Large (500 agents, 25 generations)</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Mutation Rate</label>
              <input className="form-input" type="number" min={0} max={0.5} step={0.01}
                value={form.mutation_rate}
                onChange={e => setForm(f => ({ ...f, mutation_rate: parseFloat(e.target.value) }))} />
            </div>

            <button type="button" className="btn btn-ghost btn-sm" style={{ marginBottom: 12 }}
              onClick={() => setShowAdvanced(v => !v)}>
              {showAdvanced ? "Hide" : "Show"} API config
            </button>

            {showAdvanced && (
              <div style={{ marginBottom: 12 }}>
                <div className="form-group">
                  <label className="form-label">Behavioral-Drift URL</label>
                  <input className="form-input" placeholder="http://localhost:8000" value={form.drift_api_url}
                    onChange={e => setForm(f => ({ ...f, drift_api_url: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Behavioral-Drift API Key</label>
                  <input className="form-input" type="password" value={form.drift_api_key}
                    onChange={e => setForm(f => ({ ...f, drift_api_key: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Causal-Horizon URL</label>
                  <input className="form-input" placeholder="http://localhost:8002" value={form.horizon_api_url}
                    onChange={e => setForm(f => ({ ...f, horizon_api_url: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Causal-Horizon API Key</label>
                  <input className="form-input" type="password" value={form.horizon_api_key}
                    onChange={e => setForm(f => ({ ...f, horizon_api_key: e.target.value }))} />
                </div>
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={creating}>
              {creating ? "Launching..." : "Run Simulation"}
            </button>
          </form>
        </div>

        {progress && (
          <div className="card">
            <div className="card-title">Active Run — {progress.id}</div>
            <div style={{ marginBottom: 8 }}>
              <StatusBadge status={progress.status} />
              <span style={{ marginLeft: 10, color: "var(--muted)", fontSize: 12 }}>
                Generation {progress.progress} / {progress.total}
              </span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${pct_done * 100}%` }} />
            </div>

            {progress.generations.length > 0 && (() => {
              const last = progress.generations[progress.generations.length - 1].stats;
              return (
                <div className="stat-grid" style={{ marginTop: 16 }}>
                  <div className="stat-card">
                    <div className="stat-label">Drift Rate</div>
                    <div className="stat-value red">{pct(last.drift_rate)}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Diversity</div>
                    <div className="stat-value violet">{fmt(last.diversity_entropy, 2)}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Mean Fitness</div>
                    <div className="stat-value green">{fmt(last.mean_fitness, 3)}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Avg Urgency</div>
                    <div className="stat-value cyan">{fmt(last.mean_urgency, 1)}</div>
                  </div>
                </div>
              );
            })()}

            {running && (
              <MiniLineChart
                values={progress.generations.map(g => g.stats.drift_rate)}
                color="var(--red)"
                label="drift rate"
              />
            )}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Simulation History</div>
        {loading ? <div className="empty">Loading...</div> : error ? <div className="empty">{error}</div> : (
          <table className="sim-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Scale</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Drift Rate</th>
                <th>Diversity</th>
                <th>Total Drift Events</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {(sims ?? []).map(s => (
                <tr key={s.id} onClick={() => onActiveSim(s.id)}>
                  <td>{s.name}</td>
                  <td style={{ color: "var(--muted)" }}>{s.population_size}×{s.total_generations}</td>
                  <td><StatusBadge status={s.status} /></td>
                  <td>{s.progress} / {s.total_generations}</td>
                  <td>{s.final_drift_rate != null ? pct(s.final_drift_rate) : "--"}</td>
                  <td>{fmt(s.final_diversity, 2)}</td>
                  <td>{s.total_drift_events ?? "--"}</td>
                  <td style={{ color: "var(--muted)" }}>
                    {s.created_at ? new Date(s.created_at).toLocaleString() : "--"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function MiniLineChart({ values, color, label }: { values: number[]; color: string; label: string }) {
  if (values.length < 2) return null;
  const W = 300, H = 60;
  const min = Math.min(...values), max = Math.max(...values) + 1e-9;
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * W},${H - ((v - min) / (max - min)) * H}`)
    .join(" ");
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>{label}</div>
      <svg width={W} height={H} className="mini-chart">
        <polyline points={pts} stroke={color} />
      </svg>
    </div>
  );
}
