const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

export interface SimConfig {
  name?: string;
  scale: "small" | "medium" | "large" | "custom";
  population_size?: number;
  num_generations?: number;
  num_cultures?: number;
  sessions_per_agent?: number;
  mutation_rate?: number;
  drift_api_url?: string;
  drift_api_key?: string;
  horizon_api_url?: string;
  horizon_api_key?: string;
  seed?: number;
}

export interface SimSummary {
  id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  total_generations: number;
  population_size: number;
  final_drift_rate: number | null;
  final_diversity: number | null;
  total_drift_events: number | null;
  created_at: string | null;
}

export interface GenerationStats {
  index: number;
  stats: {
    drift_rate: number;
    mean_fitness: number;
    diversity_entropy: number;
    drift_by_type: Record<string, number>;
    mean_genome: Record<string, number>;
    std_genome: Record<string, number>;
    mean_urgency: number;
  };
  cultures: Array<{
    name: string;
    drift_rate: number;
    size: number;
    ambient_stress: number;
    tech_fluency: number;
  }>;
  api_calls: { drift_sessions: number; horizon_observes: number; failures: number };
}

export interface Agent {
  id: number;
  culture: string;
  culture_id: number;
  genome: Record<string, number>;
  drift_count: number;
  most_common_drift: string | null;
  fitness: number;
  urgency_score: number;
  urgency_at_alert: number | null;
  connections: number[];
}

export interface PCAPoint {
  id: number;
  pc1: number;
  pc2: number;
  culture: string;
  drift_type: string | null;
  fitness: number;
  urgency_score: number | null;
}

export interface InsightCard {
  type: string;
  title: string;
  body: string;
  stat: string;
  significance: "high" | "moderate" | "low";
  drift_type?: string;
}

export interface SimResult {
  id: string;
  name: string;
  status: string;
  config: SimConfig;
  result: {
    generations: GenerationStats[];
    final_population: Agent[];
    edge_list: [number, number][];
    social_network: { n_nodes: number; n_edges: number; clustering_coefficient: number };
    cultures: Array<{ id: number; name: string; ambient_stress: number; tech_fluency: number; pace: number }>;
    insights: {
      pca: { points: PCAPoint[]; variance_explained: number[]; loadings: Array<{ trait: string; pc1: number; pc2: number }> };
      insight_cards: InsightCard[];
      anova: { f_statistic: number; p_value: number; significant: boolean; culture_mean_drift: Record<string, number> };
      kl_divergence: Record<string, number>;
      horizon_survival: { times: number[]; survival: number[] } | null;
      signal_effectiveness: Array<{ trait: string; r_urgency: number; p_urgency: number }>;
      trait_drift_correlations: Record<string, Record<string, { r: number; p: number }>>;
    };
  } | null;
}

export interface ProgressData {
  id: string;
  status: string;
  progress: number;
  total: number;
  generations: GenerationStats[];
}

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  createSim: (body: SimConfig) =>
    req<{ id: string; status: string }>("/api/v1/simulations", { method: "POST", body: JSON.stringify(body) }),

  listSims: () => req<SimSummary[]>("/api/v1/simulations"),

  getSim: (id: string) => req<SimResult>(`/api/v1/simulations/${id}`),

  getProgress: (id: string) => req<ProgressData>(`/api/v1/simulations/${id}/progress`),

  deleteSim: (id: string) =>
    fetch(`${BASE}/api/v1/simulations/${id}`, { method: "DELETE" }),
};
