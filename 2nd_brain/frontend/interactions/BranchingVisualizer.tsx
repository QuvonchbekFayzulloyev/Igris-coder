import React, { useMemo, useState, useCallback, useEffect } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

/**
 * Branching Visualizer — tree/hierarchy view from any root node.
 *
 * Shows:
 * - Root node at center
 * - Direct neighbors as first ring
 * - Expanded neighbors show their neighbors (recursive)
 * - Animated expansion/collapse
 * - Connection lines with directional arrows
 * - Branch count badges
 */

interface BranchNode {
  id: string;
  node: BrainGraphNode;
  depth: number;
  angle: number;
  radius: number;
  children: string[];
  isExpanded: boolean;
}

interface BranchingVisualizerProps {
  nodes: BrainGraphNode[];
  links: [string, string][];
  nodeMap: Record<string, BrainGraphNode>;
  rootId: string | null;
  expandedNodes: Set<string>;
  onToggleExpand: (nodeId: string) => void;
  onSelectNode: (node: BrainGraphNode) => void;
  onFocusNode: (node: BrainGraphNode) => void;
  onClose: () => void;
  position: { x: number; y: number };
}

const RING_RADIUS = 80;
const NODE_RADIUS = 6;
const ANIM_DURATION = 300;

export function BranchingVisualizer({
  nodes,
  links,
  nodeMap,
  rootId,
  expandedNodes,
  onToggleExpand,
  onSelectNode,
  onFocusNode,
  onClose,
  position,
}: BranchingVisualizerProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [animating, setAnimating] = useState<boolean>(false);

  // Build tree structure from root
  const tree = useMemo((): BranchNode[] => {
    if (!rootId || !nodeMap[rootId]) return [];

    const root = nodeMap[rootId];
    const result: BranchNode[] = [];
    const visited = new Set<string>();

    // Add root
    result.push({
      id: rootId,
      node: root,
      depth: 0,
      angle: 0,
      radius: 0,
      children: [],
      isExpanded: expandedNodes.has(rootId),
    });
    visited.add(rootId);

    // BFS to build tree
    const queue = [{ id: rootId, depth: 0 }];

    while (queue.length > 0) {
      const { id, depth } = queue.shift()!;
      const branchNode = result.find((n) => n.id === id);

      if (!expandedNodes.has(id)) continue;

      // Get neighbors
      const neighbors: string[] = [];
      links.forEach(([a, b]) => {
        if (a === id && !visited.has(b)) neighbors.push(b);
        if (b === id && !visited.has(a)) neighbors.push(a);
      });

      if (branchNode) {
        branchNode.children = neighbors;
      }

      // Position neighbors in a ring
      const parentAngle = branchNode?.angle ?? 0;
      const ringRadius = RING_RADIUS * (depth + 1);
      const angleStep = neighbors.length > 0 ? (Math.PI * 2) / neighbors.length : 0;
      const startAngle = parentAngle - (Math.PI * 2) / 2;

      neighbors.forEach((neighborId, i) => {
        if (visited.has(neighborId)) return;
        visited.add(neighborId);

        const neighbor = nodeMap[neighborId];
        if (!neighbor) return;

        const angle = startAngle + angleStep * i;
        const x = Math.cos(angle) * ringRadius;
        const y = Math.sin(angle) * ringRadius;

        result.push({
          id: neighborId,
          node: neighbor,
          depth: depth + 1,
          angle,
          radius: ringRadius,
          children: [],
          isExpanded: expandedNodes.has(neighborId),
        });

        queue.push({ id: neighborId, depth: depth + 1 });
      });
    }

    return result;
  }, [rootId, nodeMap, links, expandedNodes]);

  // Count total branches
  const branchCount = useMemo(() => {
    return tree.reduce((sum, n) => sum + n.children.length, 0);
  }, [tree]);

  // Handle expand/collapse with animation
  const handleToggle = useCallback((nodeId: string) => {
    setAnimating(true);
    onToggleExpand(nodeId);
    setTimeout(() => setAnimating(false), ANIM_DURATION);
  }, [onToggleExpand]);

  if (!rootId || tree.length === 0) return null;

  const root = tree[0];

  return (
    <div
      className="absolute z-30 pointer-events-auto"
      style={{
        left: position.x,
        top: position.y,
        transform: 'translate(-50%, -50%)',
      }}
    >
      {/* Branch View Panel */}
      <div className="bg-zinc-950/95 border border-zinc-700 rounded-xl shadow-2xl backdrop-blur-sm overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-ui font-medium text-zinc-200">🌳 Branch View</span>
            <span className="text-[9px] font-mono text-zinc-600">
              {tree.length} nodes · {branchCount} branches
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onFocusNode(root.node)}
              className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
              title="Focus root node"
            >
              ⛶ focus
            </button>
            <button
              onClick={onClose}
              className="text-[10px] font-mono text-zinc-600 hover:text-zinc-300 transition-colors"
            >
              ✕
            </button>
          </div>
        </div>

        {/* SVG Canvas */}
        <svg width={Math.min(500, 200 + root.depth * RING_RADIUS * 2)} height={Math.min(400, 150 + root.depth * RING_RADIUS * 2)} className="bg-zinc-900/30">
          {/* Connection lines */}
          {tree.map((branchNode) =>
            branchNode.children.map((childId) => {
              const child = tree.find((n) => n.id === childId);
              if (!child) return null;

              const parentX = 250 + (branchNode.depth === 0 ? 0 : Math.cos(branchNode.angle) * branchNode.radius);
              const parentY = 200 + (branchNode.depth === 0 ? 0 : Math.sin(branchNode.angle) * branchNode.radius);
              const childX = 250 + Math.cos(child.angle) * child.radius;
              const childY = 200 + Math.sin(child.angle) * child.radius;

              const isHighlighted = hoveredNode === branchNode.id || hoveredNode === childId;

              return (
                <g key={`${branchNode.id}-${childId}`}>
                  <line
                    x1={parentX}
                    y1={parentY}
                    x2={childX}
                    y2={childY}
                    stroke={isHighlighted ? '#f59e0b' : '#3f3f46'}
                    strokeWidth={isHighlighted ? 2 : 1}
                    opacity={isHighlighted ? 0.8 : 0.4}
                    className="transition-all duration-200"
                  />
                  {/* Arrow at midpoint */}
                  <circle
                    cx={(parentX + childX) / 2}
                    cy={(parentY + childY) / 2}
                    r={2}
                    fill={isHighlighted ? '#f59e0b' : '#52525b'}
                    opacity={0.6}
                  />
                </g>
              );
            })
          )}

          {/* Nodes */}
          {tree.map((branchNode) => {
            const x = 250 + (branchNode.depth === 0 ? 0 : Math.cos(branchNode.angle) * branchNode.radius);
            const y = 200 + (branchNode.depth === 0 ? 0 : Math.sin(branchNode.angle) * branchNode.radius);
            const color = KIND_COLOR_TAILWIND[branchNode.node.kind as keyof typeof KIND_COLOR_TAILWIND];
            const isRoot = branchNode.depth === 0;
            const isHovered = hoveredNode === branchNode.id;
            const isSelected = branchNode.node.id === rootId;
            const r = isRoot ? 10 : isHovered ? 7 : 5;

            return (
              <g
                key={branchNode.id}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredNode(branchNode.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => onSelectNode(branchNode.node)}
                onDoubleClick={() => handleToggle(branchNode.id)}
              >
                {/* Glow for root */}
                {isRoot && (
                  <circle cx={x} cy={y} r={r + 4} fill={color?.fill || '#71717a'} opacity={0.2} />
                )}

                {/* Main circle */}
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={color?.fill || '#71717a'}
                  stroke={isSelected ? '#f59e0b' : isHovered ? '#e4e4e7' : '#09090b'}
                  strokeWidth={isSelected ? 2.5 : 2}
                  className="transition-all duration-200"
                />

                {/* Expand indicator */}
                {branchNode.children.length > 0 && !branchNode.isExpanded && (
                  <circle
                    cx={x + r + 3}
                    cy={y - r - 3}
                    r={4}
                    fill="#18181b"
                    stroke="#52525b"
                    strokeWidth={1}
                  />
                )}
                {branchNode.children.length > 0 && !branchNode.isExpanded && (
                  <text
                    x={x + r + 3}
                    y={y - r - 1}
                    textAnchor="middle"
                    fontSize="6"
                    fill="#a1a1aa"
                    fontFamily="IBM Plex Mono"
                  >
                    {branchNode.children.length}
                  </text>
                )}

                {/* Label */}
                <text
                  x={x}
                  y={y + r + 12}
                  textAnchor="middle"
                  fontSize="8"
                  fill={isHovered || isSelected ? '#e4e4e7' : '#a1a1aa'}
                  fontFamily="IBM Plex Sans"
                  className="pointer-events-none"
                >
                  {branchNode.node.label.length > 15
                    ? branchNode.node.label.slice(0, 13) + '…'
                    : branchNode.node.label}
                </text>

                {/* Depth badge */}
                {branchNode.depth > 0 && (
                  <text
                    x={x}
                    y={y - r - 6}
                    textAnchor="middle"
                    fontSize="6"
                    fill="#52525b"
                    fontFamily="IBM Plex Mono"
                    className="pointer-events-none"
                  >
                    d{branchNode.depth}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Legend */}
        <div className="flex items-center gap-3 px-3 py-1.5 border-t border-zinc-800 text-[8px] font-mono text-zinc-600">
          <span>click → select</span>
          <span>double-click → expand</span>
          <span>shift+click → toggle</span>
          <span className="ml-auto">{tree.length} visible</span>
        </div>
      </div>
    </div>
  );
}
