import type { Agent } from "../api";
import { TRAITS } from "../constants";

interface Props {
  agents: Agent[];
  maxAgents?: number;
}

function traitColor(v: number) {
  const h = (v * 120).toFixed(0);
  return `hsl(${h}, 65%, 45%)`;
}

export default function GenomeHeatmap({ agents, maxAgents = 80 }: Props) {
  const sample = agents.slice(0, maxAgents);
  if (!sample.length) return <div className="empty">No population data</div>;

  const cellW = Math.min(16, Math.floor(520 / TRAITS.length));
  const cellH = Math.max(3, Math.min(8, Math.floor(280 / sample.length)));
  const width  = TRAITS.length * cellW;
  const height = sample.length * cellH + 20;

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {/* Trait labels */}
      {TRAITS.map((t, j) => (
        <text
          key={t}
          x={j * cellW + cellW / 2}
          y={height - 4}
          textAnchor="middle"
          fontSize={9}
          fill="var(--muted)"
          transform={`rotate(-45, ${j * cellW + cellW / 2}, ${height - 4})`}
        >
          {t.split("_")[0]}
        </text>
      ))}
      {/* Cells */}
      {sample.map((agent, i) =>
        TRAITS.map((t, j) => (
          <rect
            key={`${i}-${j}`}
            x={j * cellW}
            y={i * cellH}
            width={cellW - 1}
            height={cellH - 1}
            fill={traitColor(agent.genome[t] ?? 0.5)}
            opacity={0.92}
          />
        ))
      )}
    </svg>
  );
}
