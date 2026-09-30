import React, { useMemo } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

interface MiniMapProps {
  nodes: BrainGraphNode[];
  links: [string, string][];
  nodeMap: Record<string, BrainGraphNode>;
  view: { scale: number; tx: number; ty: number };
  svgWidth: number;
  svgHeight: number;
  onNavigate: (x: number, y: number) => void;
}

const MINI_W = 140;
const MINI_H = 90;
const PADDING = 5;

export function MiniMap({ nodes, links, nodeMap, view, svgWidth, svgHeight, onNavigate }: MiniMapProps) {
  // Node boundaries in world coordinates
  const bounds = useMemo(() => {
    if (nodes.length === 0) return { minX: 0, maxX: 100, minY: 0, maxY: 100 };
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.forEach((n) => {
      minX = Math.min(minX, n.x || 0);
      maxX = Math.max(maxX, n.x || 0);
      minY = Math.min(minY, n.y || 0);
      maxY = Math.max(maxY, n.y || 0);
    });
    return { minX: minX - 20, maxX: maxX + 20, minY: minY - 20, maxY: maxY + 20 };
  }, [nodes]);

  const worldW = bounds.maxX - bounds.minX || 1;
  const worldH = bounds.maxY - bounds.minY || 1;
  const scaleX = (MINI_W - PADDING * 2) / worldW;
  const scaleY = (MINI_H - PADDING * 2) / worldH;
  const scale = Math.min(scaleX, scaleY);

  const toMini = (wx: number, wy: number) => ({
    x: PADDING + (wx - bounds.minX) * scale,
    y: PADDING + (wy - bounds.minY) * scale,
  });

  // Current viewport rectangle in world coordinates
  const vp = useMemo(() => {
    const left = -view.tx / view.scale;
    const top = -view.ty / view.scale;
    const width = svgWidth / view.scale;
    const height = svgHeight / view.scale;
    return { left, top, width, height };
  }, [view, svgWidth, svgHeight]);

  const vpMini = useMemo(() => {
    const tl = toMini(vp.left, vp.top);
    const br = toMini(vp.left + vp.width, vp.top + vp.height);
    return { x: tl.x, y: tl.y, w: br.x - tl.x, h: br.y - tl.y };
  }, [vp, scale, bounds]);

  const handleClick = (e: React.MouseEvent) => {
    const rect = (e.target as SVGElement).getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    // Convert mini coords back to world coords, then center viewport
    const wx = (mx - PADDING) / scale + bounds.minX;
    const wy = (my - PADDING) / scale + bounds.minY;
    onNavigate(wx, wy);
  };

  return (
    <svg
      width={MINI_W}
      height={MINI_H}
      className="absolute top-2 right-2 bg-zinc-950/80 border border-zinc-700 rounded-md cursor-pointer backdrop-blur-sm"
      onClick={handleClick}
    >
      {/* Links */}
      {links.map(([a, b], i) => {
        const na = nodeMap[a], nb = nodeMap[b];
        if (!na || !nb) return null;
        const pa = toMini(na.x || 0, na.y || 0);
        const pb = toMini(nb.x || 0, nb.y || 0);
        return (
          <line
            key={i}
            x1={pa.x} y1={pa.y}
            x2={pb.x} y2={pb.y}
            stroke="#3f3f46"
            strokeWidth={0.5}
            opacity={0.4}
          />
        );
      })}

      {/* Nodes */}
      {nodes.map((n) => {
        const p = toMini(n.x || 0, n.y || 0);
        return (
          <circle
            key={n.id}
            cx={p.x}
            cy={p.y}
            r={1.5}
            fill={KIND_COLOR_TAILWIND[n.kind as keyof typeof KIND_COLOR_TAILWIND]?.fill || '#71717a'}
          />
        );
      })}

      {/* Viewport rectangle */}
      <rect
        x={vpMini.x}
        y={vpMini.y}
        width={vpMini.w}
        height={vpMini.h}
        fill="none"
        stroke="#f59e0b"
        strokeWidth={1}
        opacity={0.7}
        rx={1}
      />
    </svg>
  );
}
