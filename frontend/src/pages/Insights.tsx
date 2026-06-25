import type { SimResult, PCAPoint, InsightCard } from "../api";
import { cultureColor, driftColor, fmt, severityColor } from "../hooks";
import { TRAITS, DRIFT_TYPES } from "../constants";

interface Props { sim: SimResult | null }

const PCA_W = 400, PCA_H = 320;

function PCAScatter({ points, varExp }: { points: PCAPoint[]; varExp: number[] }) {
  if (!points.length) return null;
  const pc1s = points.map(p => p.pc1);
  const pc2s = points.map(p => p.pc2);
  const minX = Math.min(...pc1s), maxX = Math.max(...pc1s) + 1e-9;
  const minY = Math.min(...pc2s), maxY = Math.max(...pc2s) + 1e-9;

  const toX = (v: number) => ((v - minX) / (maxX - minX)) * (PCA_W - 32) + 16;
  const toY = (v: number) => PCA_H - 16 - ((v - minY) / (maxY - minY)) * (PCA_H - 32);

  return (
    <svg width={PCA_W} height={PCA_H} style={{ display: "block" }}>
      {points.map(p => (
        <circle
          key={p.id}
          cx={toX(p.pc1)}
          cy={toY(p.pc2)}
          r={3 + (p.fitness ?? 0.5) * 3}
          fill={p.drift_type ? driftColor(p.drift_type) : cultureColor(
            // infer culture index from culture name hash
            p.culture.charCodeAt(0) % 5
          )}
          opacity={0.75}
        />
      ))}
      <text x={PCA_W / 2} y={PCA_H - 2} textAnchor="middle" fontSize={10} fill="var(--muted)">
        PC1 ({(varExp[0] * 100).toFixed(1)}%)
      </text>
      <text x={10} y={PCA_H / 2} textAnchor="middle" fontSize={10} fill="var(--muted)"
        transform={`rotate(-90, 10, ${PCA_H / 2})`}>
        PC2 ({(varExp[1] * 100).toFixed(1)}%)
      </text>
    </svg>
  );
}

function TraitDriftHeatmap({ correlations }: {
  correlations: Record<string, Record<string, { r: number; p: number }>>;
}) {
  const cellW = 72, cellH = 28;
  const W = DRIFT_TYPES.length * cellW + 110;
  const H = TRAITS.length * cellH + 28;

  const rToColor = (r: number) => {
    const abs = Math.min(1, Math.abs(r));
    if (r > 0) return `rgba(34,211,238,${abs * 0.8})`;
    return `rgba(248,113,113,${abs * 0.8})`;
  };

  return (
    <svg width={W} height={H} style={{ display: "block" }}>
      {DRIFT_TYPES.map((dt, j) => (
        <text key={dt} x={110 + j * cellW + cellW / 2} y={14} textAnchor="middle"
          fontSize={8} fill="var(--muted)">
          {dt.split("_")[0]}
        </text>
      ))}
      {TRAITS.map((t, i) => (
        <g key={t}>
          <text x={104} y={28 + i * cellH + cellH / 2} textAnchor="end"
            fontSize={9} fill="var(--muted)" dominantBaseline="middle">
            {t.replace(/_/g, " ")}
          </text>
          {DRIFT_TYPES.map((dt, j) => {
            const stat = correlations[t]?.[dt] ?? { r: 0, p: 1 };
            return (
              <g key={dt}>
                <rect x={110 + j * cellW} y={20 + i * cellH} width={cellW - 2} height={cellH - 2}
                  fill={rToColor(stat.r)} rx={3} />
                <text x={110 + j * cellW + cellW / 2} y={20 + i * cellH + cellH / 2}
                  textAnchor="middle" dominantBaseline="middle" fontSize={9} fill="var(--text)">
                  {stat.r > 0 ? "+" : ""}{stat.r.toFixed(2)}
                </text>
              </g>
            );
          })}
        </g>
      ))}
    </svg>
  );
}

export default function Insights({ sim }: Props) {
  if (!sim?.result?.insights) return <div className="empty">Run a simulation to see insights</div>;

  const ins = sim.result.insights;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Insights</div>
          <div className="page-sub">{sim.name} — statistical analysis</div>
        </div>
      </div>

      {ins.insight_cards?.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14, marginBottom: 24 }}>
          {ins.insight_cards.map((card, i) => (
            <InsightCardEl key={i} card={card} />
          ))}
        </div>
      )}

      <div className="two-col" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">PCA — Genome Space</div>
          <PCAScatter points={ins.pca?.points ?? []} varExp={ins.pca?.variance_explained ?? [0, 0]} />
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
            Color = drift type. Size = fitness. Each dot = one agent.
          </div>
        </div>

        <div className="card">
          <div className="card-title">ANOVA — Culture vs Drift</div>
          <div style={{ marginBottom: 12 }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>
              {ins.anova.significant ? "Significant" : "Not significant"}
            </span>
            <span style={{ color: "var(--muted)", fontSize: 12, marginLeft: 8 }}>
              F={fmt(ins.anova.f_statistic, 2)}, p={fmt(ins.anova.p_value, 4)}
            </span>
          </div>
          {Object.entries(ins.anova.culture_mean_drift ?? {}).map(([c, v], i) => (
            <div key={c} style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                <span style={{ color: cultureColor(i) }}>{c}</span>
                <span style={{ color: "var(--muted)" }}>mean drift {fmt(v as number, 3)}</span>
              </div>
              <div className="progress-bar">
                <div style={{ height: "100%", width: `${Math.min(100, (v as number) * 300)}%`, background: cultureColor(i), borderRadius: 3 }} />
              </div>
            </div>
          ))}

          {ins.anova.significant && (
            <div style={{ marginTop: 16 }}>
              <div className="card-title" style={{ marginBottom: 8 }}>KL Divergence (genome shift)</div>
              {Object.entries(ins.kl_divergence ?? {}).sort((a,b) => (b[1] as number) - (a[1] as number)).map(([t, kl]) => (
                <div key={t} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                  <span>{t.replace(/_/g, " ")}</span>
                  <span style={{ fontFamily: "monospace", color: "var(--cyan)" }}>{fmt(kl as number, 4)} nats</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title">Trait x Drift Correlation Matrix</div>
        <div style={{ overflowX: "auto" }}>
          <TraitDriftHeatmap correlations={ins.trait_drift_correlations ?? {}} />
        </div>
        <div style={{ marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
          Cyan = positive correlation. Red = negative. Pearson r.
        </div>
      </div>

      {ins.horizon_survival && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-title">Kaplan-Meier — Urgency Alert Survival</div>
          <KMCurve data={ins.horizon_survival} />
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
            Fraction of agents that had not yet crossed urgency=70 by lead time (hours before deadline).
          </div>
        </div>
      )}

      {ins.signal_effectiveness?.length > 0 && (
        <div className="card">
          <div className="card-title">Trait vs Urgency Correlation</div>
          {ins.signal_effectiveness.map(s => (
            <div key={s.trait} style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 13 }}>
              <span>{s.trait.replace(/_/g, " ")}</span>
              <span style={{ fontFamily: "monospace", color: s.r_urgency > 0 ? "var(--cyan)" : "var(--red)" }}>
                r={s.r_urgency > 0 ? "+" : ""}{s.r_urgency.toFixed(3)} (p={s.p_urgency.toFixed(3)})
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InsightCardEl({ card }: { card: InsightCard }) {
  return (
    <div className={`insight-card insight-${card.significance}`}>
      <div className="insight-card-title" style={{ color: severityColor(card.significance) }}>
        {card.title}
      </div>
      <div className="insight-card-body">{card.body}</div>
      <span className="insight-card-stat" style={{
        background: `${severityColor(card.significance)}22`,
        color: severityColor(card.significance),
      }}>
        {card.stat}
      </span>
    </div>
  );
}

function KMCurve({ data }: { data: { times: number[]; survival: number[] } }) {
  const { times, survival } = data;
  if (!times.length) return null;
  const W = 460, H = 160;
  const maxT = Math.max(...times);
  const toX = (t: number) => (t / maxT) * (W - 32) + 16;
  const toY = (s: number) => H - 16 - s * (H - 32);

  const pts = times.map((t, i) => `${toX(t)},${toY(survival[i])}`).join(" ");

  return (
    <svg width={W} height={H} className="mini-chart">
      <polyline points={pts} stroke="var(--cyan)" strokeWidth={2} fill="none" />
      <line x1={16} y1={H - 16} x2={W - 16} y2={H - 16} stroke="var(--border)" strokeWidth={1} />
      <line x1={16} y1={16} x2={16} y2={H - 16} stroke="var(--border)" strokeWidth={1} />
      <text x={W / 2} y={H - 2} textAnchor="middle" fontSize={9} fill="var(--muted)">Lead time (h)</text>
    </svg>
  );
}
