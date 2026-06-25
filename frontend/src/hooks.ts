import { useState, useEffect, useCallback, useRef } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fn()
      .then((d) => { if (!cancelled) { setData(d); setError(null); } })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, reload: () => setLoading(true) };
}

export function useAsyncFn<T, A extends unknown[]>(fn: (...args: A) => Promise<T>) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const run = useCallback(async (...args: A): Promise<T | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await fn(...args);
      if (mounted.current) setLoading(false);
      return result;
    } catch (e) {
      if (mounted.current) { setError(String(e)); setLoading(false); }
      return null;
    }
  }, [fn]);

  return { run, loading, error };
}

export function usePoll<T>(fn: () => Promise<T>, intervalMs: number, active: boolean) {
  const [data, setData] = useState<T | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const tick = useCallback(async () => {
    try {
      const d = await fn();
      setData(d);
    } catch (_) {}
    if (active) timerRef.current = setTimeout(tick, intervalMs);
  }, [fn, intervalMs, active]);

  useEffect(() => {
    if (!active) return;
    tick();
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [active, tick]);

  return data;
}

export function fmt(n: number | null | undefined, dec = 3) {
  if (n == null) return "--";
  return n.toFixed(dec);
}

export function pct(n: number | null | undefined, dec = 1) {
  if (n == null) return "--";
  return (n * 100).toFixed(dec) + "%";
}

const SEVERITY_COLORS: Record<string, string> = {
  high: "#22d3ee",
  moderate: "#a78bfa",
  low: "#6b7280",
};
export function severityColor(s: string) {
  return SEVERITY_COLORS[s] ?? "#6b7280";
}

const CULTURE_PALETTE = ["#22d3ee", "#a78bfa", "#f472b6", "#fb923c", "#34d399"];
export function cultureColor(id: number) {
  return CULTURE_PALETTE[id % CULTURE_PALETTE.length];
}

const DRIFT_PALETTE: Record<string, string> = {
  cognitive_overload:     "#f87171",
  disengagement:          "#fb923c",
  unusual_urgency:        "#facc15",
  context_switch_fatigue: "#a78bfa",
  confusion:              "#38bdf8",
};
export function driftColor(type: string | null) {
  return type ? (DRIFT_PALETTE[type] ?? "#6b7280") : "#374151";
}
