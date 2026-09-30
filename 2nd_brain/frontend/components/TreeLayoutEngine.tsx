/**
 * TreeLayoutEngine — Interactive Map (Tauri-compatible)
 * Zoom: scroll over component, +/- keys. Pan: drag.
 */

import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import type { BrainGraphNode } from '../../../Igris_Interface/web/backend';

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  node: BrainGraphNode;
  level: number;
  children: string[];
  allDesc: string[];
  isFather: boolean;
}

interface LayoutEdge { source: string; target: string }

interface TreeLayout {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  bounds: { w: number; h: number; minX: number; minY: number };
}

interface Props {
  width: number;
  height: number;
  nodes: BrainGraphNode[];
  links: [string, string][];
  nodeMap: Record<string, BrainGraphNode>;
  selectedFatherId?: string | null;
  onNodeSelect?: (nodeId: string) => void;
  onFatherSelect?: (fatherId: string | null) => void;
}

const HS = 160, VS = 120, P = 80;
const KC: Record<string, string> = {
  fact: '#10b981', session: '#2dd4bf', pattern: '#a78bfa', architecture: '#60a5fa',
  memory: '#f472b6', module: '#a78bfa', concept: '#60a5fa',
  person: '#fbbf24', place: '#34d399', tool: '#f87171', event: '#c084fc',
  idea: '#818cf8', project: '#fb923c', skill: '#22d3ee', goal: '#a3e635',
  note: '#94a3b8', task: '#f43f5e', unknown: '#6b7280',
};

function buildTree(nodes: BrainGraphNode[], links: [string, string][]) {
  const ch = new Map<string, string[]>();
  const hasP = new Set<string>();
  for (const [s, t] of links) { if (!ch.has(s)) ch.set(s, []); ch.get(s)!.push(t); hasP.add(t); }
  let root: string | null = null, mx = -1;
  for (const n of nodes) if (!hasP.has(n.id)) { const c = ch.get(n.id)?.length || 0; if (c > mx) { mx = c; root = n.id; } }
  if (!root && nodes.length) root = nodes[0].id;
  return { root, ch };
}

function doLayout(nodes: BrainGraphNode[], links: [string, string][], nm: Record<string, BrainGraphNode>): TreeLayout {
  const { root, ch } = buildTree(nodes, links);
  if (!root) return circ(nodes, nm);
  const ln: LayoutNode[] = [], le: LayoutEdge[] = [];
  const vis = new Set<string>(), sw = new Map<string, number>();

  function w(id: string): number {
    if (vis.has(id)) return HS;
    vis.add(id);
    const c = ch.get(id) || [];
    if (!c.length) { sw.set(id, HS); return HS; }
    let t = 0; for (const x of c) t += w(x);
    const r = Math.max(HS, t); sw.set(id, r); return r;
  }
  w(root); vis.clear();

  function desc(id: string): string[] {
    const c = ch.get(id) || []; let r = [...c]; for (const x of c) r = r.concat(desc(x)); return r;
  }

  function pos(id: string, cx: number, y: number, lv: number) {
    if (vis.has(id)) return; vis.add(id);
    const n = nm[id]; if (!n) return;
    const c = ch.get(id) || [], d = desc(id);
    ln.push({ id, x: cx, y, node: n, level: lv, children: c, allDesc: d, isFather: c.length > 0 });
    if (c.length) {
      const tw = c.reduce((s, x) => s + (sw.get(x) || HS), 0);
      let sx = cx - tw / 2;
      for (const x of c) { const cw = sw.get(x) || HS; pos(x, sx + cw / 2, y + VS, lv + 1); le.push({ source: id, target: x }); sx += cw; }
    }
  }
  pos(root, (sw.get(root) || HS) / 2, P, 0);

  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const n of ln) { x0 = Math.min(x0, n.x - 50); x1 = Math.max(x1, n.x + 50); y0 = Math.min(y0, n.y - 30); y1 = Math.max(y1, n.y + 30); }
  return { nodes: ln, edges: le, bounds: { w: x1 - x0 + P * 2, h: y1 - y0 + P * 2, minX: x0, minY: y0 } };
}

function circ(nodes: BrainGraphNode[], nm: Record<string, BrainGraphNode>): TreeLayout {
  const ln: LayoutNode[] = [];
  nodes.forEach((n, i) => { const a = 2 * Math.PI * i / nodes.length; ln.push({ id: n.id, x: 400 + 200 * Math.cos(a), y: 300 + 200 * Math.sin(a), node: n, level: 0, children: [], allDesc: [], isFather: false }); });
  return { nodes: ln, edges: [], bounds: { w: 800, h: 600, minX: 0, minY: 0 } };
}

export function TreeLayoutEngine({ width, height, nodes, links, nodeMap, onNodeSelect }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [px, setPx] = useState(0);
  const [py, setPy] = useState(0);
  const drag = useRef(false);
  const last = useRef({ x: 0, y: 0 });
  const zoomRef = useRef(1);
  const [sel, setSel] = useState<string | null>(null);
  const [hov, setHov] = useState<string | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; node: BrainGraphNode } | null>(null);

  const lay = useMemo(() => doLayout(nodes, links, nodeMap), [nodes, links, nodeMap]);

  const bs = useMemo(() => {
    if (!lay.bounds.w) return 1;
    return Math.min((width - P * 2) / lay.bounds.w, (height - P * 2) / lay.bounds.h, 1);
  }, [lay.bounds, width, height]);

  const sc = bs * zoom;
  const ox = (width - lay.bounds.w * sc) / 2 - lay.bounds.minX * sc + px;
  const oy = (height - lay.bounds.h * sc) / 2 - lay.bounds.minY * sc + py;

  // Wheel — ONLY when hovering over this component
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      // Only handle if mouse is over this component
      const rect = el.getBoundingClientRect();
      if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) return;
      e.preventDefault();
      e.stopPropagation();
      const f = e.deltaY > 0 ? 0.9 : 1.1;
      zoomRef.current = Math.max(0.15, Math.min(6, zoomRef.current * f));
      setZoom(zoomRef.current);
    };
    el.addEventListener('wheel', onWheel, { passive: false, capture: true });
    return () => el.removeEventListener('wheel', onWheel, true);
  }, []);

  // Keyboard — only when no input is focused
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === '+' || e.key === '=') { zoomRef.current = Math.min(6, zoomRef.current * 1.15); setZoom(zoomRef.current); }
      if (e.key === '-' || e.key === '_') { zoomRef.current = Math.max(0.15, zoomRef.current * 0.85); setZoom(zoomRef.current); }
      if (e.key === '0') { zoomRef.current = 1; setZoom(1); setPx(0); setPy(0); }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  // Drag
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!drag.current) return;
      setPx(p => p + (e.clientX - last.current.x));
      setPy(p => p + (e.clientY - last.current.y));
      last.current = { x: e.clientX, y: e.clientY };
    };
    const onUp = () => { drag.current = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  const onDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    drag.current = true;
    last.current = { x: e.clientX, y: e.clientY };
  }, []);

  const onClick = useCallback((id: string) => { setSel(id); onNodeSelect?.(id); }, [onNodeSelect]);

  const onEnter = useCallback((id: string, e: React.MouseEvent) => {
    setHov(id);
    const n = nodeMap[id]; if (n) { const r = (e.target as SVGElement).getBoundingClientRect(); setTip({ x: r.left + r.width / 2, y: r.top - 8, node: n }); }
  }, [nodeMap]);

  // Visible nodes
  const vis = useMemo(() => {
    const v = new Set<string>();
    for (const n of lay.nodes) { if (n.level === 0 || n.isFather) v.add(n.id); else if (zoom >= 0.5) v.add(n.id); }
    const f = sel || hov;
    if (f) { const fn = lay.nodes.find(n => n.id === f); if (fn) { v.add(fn.id); for (const c of fn.children) v.add(c); if (zoom >= 0.35) for (const d of fn.allDesc) v.add(d); } }
    return v;
  }, [lay.nodes, zoom, sel, hov]);

  const ve = useMemo(() => lay.edges.filter(e => vis.has(e.source) && vis.has(e.target)), [lay.edges, vis]);
  const zl = zoom >= 0.8 ? 'Close' : zoom >= 0.45 ? 'Medium' : 'Far';

  const zoomIn = () => { zoomRef.current = Math.min(6, zoomRef.current * 1.3); setZoom(zoomRef.current); };
  const zoomOut = () => { zoomRef.current = Math.max(0.15, zoomRef.current * 0.7); setZoom(zoomRef.current); };
  const zoomReset = () => { zoomRef.current = 1; setZoom(1); setPx(0); setPy(0); };

  return (
    <div ref={wrapRef} className="relative bg-zinc-950 overflow-hidden select-none" style={{ width, height }}>
      {/* Top bar */}
      <div className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-3 py-2 bg-zinc-950/90 border-b border-zinc-800/50">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-zinc-300">Interactive Map</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">{vis.size}/{lay.nodes.length}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-zinc-500">{zl}</span>
          <span className="text-[10px] font-mono text-zinc-400">{Math.round(zoom * 100)}%</span>
        </div>
      </div>

      {/* Zoom buttons */}
      <div className="absolute right-3 top-1/2 -translate-y-1/2 z-20 flex flex-col gap-1">
        <button onClick={zoomIn} className="w-8 h-8 rounded bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-700 active:bg-zinc-600">+</button>
        <button onClick={zoomReset} className="w-8 h-8 rounded bg-zinc-800 border border-zinc-700 text-zinc-400 text-[9px] font-mono hover:bg-zinc-700 active:bg-zinc-600">⟲</button>
        <button onClick={zoomOut} className="w-8 h-8 rounded bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm hover:bg-zinc-700 active:bg-zinc-600">−</button>
      </div>

      {/* Hint */}
      <div className="absolute bottom-3 right-3 z-20 text-[9px] font-mono text-zinc-600">
        scroll · zoom | +/− keys | drag · pan | click · select
      </div>

      {/* SVG */}
      <svg width={width} height={height} className="cursor-grab active:cursor-grabbing" onMouseDown={onDown} style={{ touchAction: 'none' }}>
        <g transform={`translate(${ox}, ${oy}) scale(${sc})`}>
          {ve.map(e => {
            const s = lay.nodes.find(n => n.id === e.source);
            const t = lay.nodes.find(n => n.id === e.target);
            if (!s || !t) return null;
            const hl = hov === e.source || hov === e.target || sel === e.source || sel === e.target;
            const my = (s.y + t.y) / 2;
            return <path key={`${e.source}-${e.target}`} d={`M ${s.x} ${s.y} C ${s.x} ${my}, ${t.x} ${my}, ${t.x} ${t.y}`} fill="none" stroke={hl ? '#e4e4e7' : '#374151'} strokeWidth={hl ? 2.5 : 1.2} opacity={hl ? 0.85 : 0.4} />;
          })}

          {lay.nodes.map(n => {
            if (!vis.has(n.id)) return null;
            const isS = sel === n.id, isH = hov === n.id, isF = isS || isH;
            const col = KC[n.kind] || KC.unknown;
            const r = n.isFather ? (isF ? 28 : 24) : (isF ? 20 : 16);
            return (
              <g key={n.id} transform={`translate(${n.x}, ${n.y})`} onClick={(e) => { e.stopPropagation(); onClick(n.id); }} onMouseEnter={(e) => onEnter(n.id, e)} onMouseLeave={() => { setHov(null); setTip(null); }} className="cursor-pointer">
                {(isF || (sel && (n.children.includes(sel) || n.allDesc.includes(sel)))) && <circle r={r + 10} fill={col} opacity={0.12} />}
                {n.isFather && <circle r={r + 4} fill="none" stroke={col} strokeWidth="1.5" opacity={0.5} strokeDasharray={isF ? 'none' : '4 2'} />}
                <circle r={r} fill={isS ? col : '#18181b'} stroke={isS ? '#f59e0b' : isF ? col : col} strokeWidth={isS ? 3 : isF ? 2 : 1.5} style={{ transition: 'r 0.15s' }} />
                {n.isFather && <circle r={r * 0.35} fill={col} opacity={0.7} />}
                {(zoom >= 0.5 || isF) && <text y={r + 14} textAnchor="middle" fontSize={isF ? 11 : 9} fill={isF ? '#e4e4e7' : '#9ca3af'} fontFamily="IBM Plex Sans, sans-serif" fontWeight={isF ? '600' : '400'}>{n.node.label.length > 16 ? n.node.label.slice(0, 14) + '…' : n.node.label}</text>}
                {n.isFather && (zoom >= 0.5 || isF) && <text y={4} textAnchor="middle" fontSize="9" fill={col} fontFamily="IBM Plex Mono, monospace" fontWeight="bold">{n.children.length}</text>}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Tooltip */}
      {tip && (
        <div className="fixed z-50 pointer-events-none px-2.5 py-1.5 rounded bg-zinc-900/95 border border-zinc-700 shadow-xl max-w-[240px]"
          style={{ left: tip.x, top: tip.y, transform: 'translate(-50%, -100%)' }}>
          <div className="text-[11px] font-medium text-zinc-200">{tip.node.label}</div>
          <div className="text-[9px] text-zinc-500">{tip.node.kind}</div>
          {tip.node.detail && <div className="text-[9px] text-zinc-400 mt-0.5 truncate">{tip.node.detail}</div>}
        </div>
      )}
    </div>
  );
}

export default TreeLayoutEngine;
