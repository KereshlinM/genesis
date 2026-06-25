import { useState, useCallback } from "react";
import { api, type SimResult } from "./api";
import { useAsync } from "./hooks";
import Simulator from "./pages/Simulator";
import Population from "./pages/Population";
import Generations from "./pages/Generations";
import Insights from "./pages/Insights";

type Page = "simulator" | "population" | "generations" | "insights";

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: "simulator",   label: "Simulator",   icon: "◈" },
  { id: "population",  label: "Population",  icon: "⬡" },
  { id: "generations", label: "Generations", icon: "⟳" },
  { id: "insights",    label: "Insights",    icon: "◎" },
];

export default function App() {
  const [page, setPage]         = useState<Page>("simulator");
  const [activeSim, setActiveSim] = useState<string | null>(null);

  const simFn = useCallback(
    () => (activeSim ? api.getSim(activeSim) : Promise.resolve(null as unknown as SimResult)),
    [activeSim]
  );
  const { data: sim } = useAsync(simFn, [activeSim]);

  return (
    <div id="root" style={{ display: "flex" }}>
      <aside className="app-sidebar">
        <div className="app-logo">
          gene<span>sis</span>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(({ id, label, icon }) => (
            <button
              key={id}
              className={`nav-item${page === id ? " active" : ""}`}
              onClick={() => setPage(id)}
            >
              <span>{icon}</span> {label}
            </button>
          ))}
        </nav>
        {activeSim && (
          <div style={{ padding: "16px 20px", borderTop: "1px solid var(--border)", fontSize: 11, color: "var(--muted)" }}>
            Active: <span style={{ color: "var(--cyan)", fontFamily: "monospace" }}>{activeSim}</span>
          </div>
        )}
      </aside>

      <main className="app-main">
        {page === "simulator" && (
          <Simulator activeSim={activeSim} onActiveSim={setActiveSim} />
        )}
        {page === "population"  && <Population  sim={sim} />}
        {page === "generations" && <Generations sim={sim} />}
        {page === "insights"    && <Insights    sim={sim} />}
      </main>
    </div>
  );
}
