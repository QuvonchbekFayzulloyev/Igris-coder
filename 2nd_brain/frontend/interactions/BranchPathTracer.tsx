import React, { useState, useEffect, useMemo } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

/**
 * Animated path tracing between nodes.
 * Shows a glowing dot that follows the path from source to target.
 */

interface PathTracerProps {
  nodes: BrainGraphNode[];
  links: [string, string][];
  nodeMap: Record<string, BrainGraphNode>;
  posOf: (n: BrainGraphNode) => { x: number; y: number };
  sourceId: string | null;
  targetId: string | null;
  isActive: boolean;
  onComplete: () => void;
}

interface PathPoint {
  x: number;
  y: number;
}

export function BranchPathTracer({
  nodes,
  links,
  nodeMap,
  posOf,
  sourceId,
  targetId,
  isActive,
  onComplete,
}: PathTracerProps) {
  const [progress, setProgress] = useState(0);

  // Find shortest path using BFS
  const path = useMemo((): string[] => {
    if (!sourceId || !targetId || sourceId === targetId) return [];

    const adj = new Map<string, string[]>();
    links.forEach(([a, b]) => {
      if (!adj.has(a)) adj.set(a, []);
      if (!adj.has(b)) adj.set(b, []);
      adj.get(a)!.push(b);
      adj.get(b)!.push(a);
    });

    // BFS
    const prev = new Map<string, string>();
    const visited = new Set<string>();
    visited.add(sourceId);
    const queue = [sourceId];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (current === targetId) {
        // Reconstruct path
        const result: string[] = [];
        let node: string | undefined = targetId;
        while (node) {
          result.unshift(node);
          node = prev.get(node);
        }
        return result;
      }
      for (const neighbor of (adj.get(current) || [])) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          prev.set(neighbor, current);
          queue.push(neighbor);
        }
      }
    }

    return []; // No path found
  }, [sourceId, targetId, links]);

  // Convert path to points
  const pathPoints = useMemo((): PathPoint[] => {
    return path
      .map((id) => nodeMap[id])
      .filter(Boolean)
      .map((n) => posOf(n));
  }, [path, nodeMap, posOf]);

  // Animate progress
  useEffect(() => {
    if (!isActive || pathPoints.length < 2) {
      setProgress(0);
      return;
    }

    let frame: number;
    let start: number | null = null;
    const duration = 1500; // 1.5 seconds

    const animate = (timestamp: number) => {
      if (!start) start = timestamp;
      const elapsed = timestamp - start;
      const t = Math.min(elapsed / duration, 1);

      // Ease out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setProgress(eased);

      if (t < 1) {
        frame = requestAnimationFrame(animate);
      } else {
        onComplete();
      }
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [isActive, pathPoints.length, onComplete]);

  if (!isActive || pathPoints.length < 2 || progress === 0) return null;

  // Interpolate position along path
  const totalSegments = pathPoints.length - 1;
  const segmentProgress = progress * totalSegments;
  const currentSegment = Math.min(Math.floor(segmentProgress), totalSegments - 1);
  const segmentT = segmentProgress - currentSegment;

  const p1 = pathPoints[currentSegment];
  const p2 = pathPoints[currentSegment + 1];

  if (!p1 || !p2) return null;

  const tracerX = p1.x + (p2.x - p1.x) * segmentT;
  const tracerY = p1.y + (p2.y - p1.y) * segmentT;

  // Color of the current segment's target node
  const currentTargetNode = nodeMap[path[currentSegment + 1]];
  const tracerColor = currentTargetNode
    ? KIND_COLOR_TAILWIND[currentTargetNode.kind as keyof typeof KIND_COLOR_TAILWIND]?.fill || '#f59e0b'
    : '#f59e0b';

  return (
    <g className="pointer-events-none">
      {/* Path line (faded) */}
      <polyline
        points={pathPoints.map((p) => `${p.x},${p.y}`).join(' ')}
        fill="none"
        stroke="#f59e0b"
        strokeWidth={2}
        opacity={0.2}
        strokeDasharray="6 3"
      />

      {/* Tracer dot */}
      <circle
        cx={tracerX}
        cy={tracerY}
        r={5}
        fill={tracerColor}
        opacity={0.9}
      />
      <circle
        cx={tracerX}
        cy={tracerY}
        r={8}
        fill={tracerColor}
        opacity={0.3}
      >
        <animate
          attributeName="r"
          values="5;10;5"
          dur="0.8s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="opacity"
          values="0.3;0.1;0.3"
          dur="0.8s"
          repeatCount="indefinite"
        />
      </circle>

      {/* Trail glow */}
      <circle
        cx={tracerX}
        cy={tracerY}
        r={12}
        fill={tracerColor}
        opacity={0.15}
      />

      {/* Path nodes (highlighted) */}
      {pathPoints.map((p, i) => {
        const node = nodeMap[path[i]];
        if (!node) return null;
        const color = KIND_COLOR_TAILWIND[node.kind as keyof typeof KIND_COLOR_TAILWIND];
        const isVisited = i <= currentSegment;
        const isCurrent = i === currentSegment + 1;

        return (
          <g key={i}>
            <circle
              cx={p.x}
              cy={p.y}
              r={isCurrent ? 7 : isVisited ? 5 : 3}
              fill={color?.fill || '#71717a'}
              stroke={isCurrent ? '#f59e0b' : isVisited ? '#fbbf24' : 'none'}
              strokeWidth={isCurrent ? 2 : 1}
              opacity={isVisited ? 1 : 0.4}
              className="transition-all duration-200"
            />
          </g>
        );
      })}

      {/* Progress indicator */}
      <text
        x={tracerX + 10}
        y={tracerY - 10}
        fontSize="8"
        fill="#f59e0b"
        fontFamily="IBM Plex Mono"
        opacity={0.7}
      >
        {Math.round(progress * 100)}%
      </text>
    </g>
  );
}
