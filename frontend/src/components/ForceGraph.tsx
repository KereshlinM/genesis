import { useEffect, useRef, useMemo } from "react";
import type { Agent } from "../api";
import { cultureColor, driftColor } from "../hooks";

interface Props {
  agents: Agent[];
  edges: [number, number][];
  width?: number;
  height?: number;
  colorBy?: "culture" | "drift" | "fitness";
}

interface Node {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  culture_id: number;
  most_common_drift: string | null;
  fitness: number;
}

export default function ForceGraph({ agents, edges, width = 520, height = 420, colorBy = "culture" }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const nodesRef = useRef<Node[]>([]);

  const edgeSet = useMemo(() => edges.slice(0, 500), [edges]);

  useEffect(() => {
    const cx = width / 2;
    const cy = height / 2;
    nodesRef.current = agents.map((a, i) => {
      const angle = (i / agents.length) * 2 * Math.PI;
      const r = Math.min(width, height) * 0.35;
      return {
        id: a.id,
        x: cx + r * Math.cos(angle),
        y: cy + r * Math.sin(angle),
        vx: 0,
        vy: 0,
        culture_id: a.culture_id,
        most_common_drift: a.most_common_drift,
        fitness: a.fitness,
      };
    });
  }, [agents, width, height]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;

    const adjByNode: Map<number, number[]> = new Map();
    for (const [src, dst] of edgeSet) {
      if (!adjByNode.has(src)) adjByNode.set(src, []);
      if (!adjByNode.has(dst)) adjByNode.set(dst, []);
      adjByNode.get(src)!.push(dst);
      adjByNode.get(dst)!.push(src);
    }

    const K_REPEL = 0.8;
    const K_ATTRACT = 0.04;
    const DAMPING = 0.85;
    const TARGET_LEN = 60;
    const cx = width / 2, cy = height / 2;

    function step() {
      const nodes = nodesRef.current;
      const n = nodes.length;

      // Repulsion
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const d2 = dx * dx + dy * dy + 1;
          const f = K_REPEL * 400 / d2;
          nodes[i].vx -= f * dx;
          nodes[i].vy -= f * dy;
          nodes[j].vx += f * dx;
          nodes[j].vy += f * dy;
        }
      }

      // Attraction along edges
      for (const [src, dst] of edgeSet) {
        if (src >= n || dst >= n) continue;
        const dx = nodes[dst].x - nodes[src].x;
        const dy = nodes[dst].y - nodes[src].y;
        const d = Math.sqrt(dx * dx + dy * dy) + 1e-6;
        const f = K_ATTRACT * (d - TARGET_LEN);
        nodes[src].vx += (f * dx) / d;
        nodes[src].vy += (f * dy) / d;
        nodes[dst].vx -= (f * dx) / d;
        nodes[dst].vy -= (f * dy) / d;
      }

      // Gravity toward centre
      for (const nd of nodes) {
        nd.vx += (cx - nd.x) * 0.002;
        nd.vy += (cy - nd.y) * 0.002;
        nd.vx *= DAMPING;
        nd.vy *= DAMPING;
        nd.x += nd.vx;
        nd.y += nd.vy;
        nd.x = Math.max(8, Math.min(width - 8, nd.x));
        nd.y = Math.max(8, Math.min(height - 8, nd.y));
      }
    }

    function draw() {
      ctx.clearRect(0, 0, width, height);
      const nodes = nodesRef.current;

      // Edges
      ctx.lineWidth = 0.5;
      ctx.strokeStyle = "rgba(31,31,53,0.9)";
      ctx.beginPath();
      for (const [src, dst] of edgeSet) {
        if (src >= nodes.length || dst >= nodes.length) continue;
        ctx.moveTo(nodes[src].x, nodes[src].y);
        ctx.lineTo(nodes[dst].x, nodes[dst].y);
      }
      ctx.stroke();

      // Nodes
      for (const nd of nodes) {
        let color: string;
        if (colorBy === "culture") color = cultureColor(nd.culture_id);
        else if (colorBy === "drift") color = driftColor(nd.most_common_drift);
        else {
          const t = Math.max(0, Math.min(1, nd.fitness));
          color = `hsl(${(t * 120).toFixed(0)}, 70%, 55%)`;
        }
        const r = 4 + nd.fitness * 3;
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = "rgba(8,8,16,0.6)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    let frame = 0;
    function loop() {
      step();
      if (frame % 2 === 0) draw();
      frame++;
      animRef.current = requestAnimationFrame(loop);
    }
    animRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animRef.current);
  }, [agents, edgeSet, colorBy, width, height]);

  return <canvas ref={canvasRef} width={width} height={height} style={{ borderRadius: 8 }} />;
}
