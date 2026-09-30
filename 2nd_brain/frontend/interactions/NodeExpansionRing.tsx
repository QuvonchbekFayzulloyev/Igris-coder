import React, { useState, useEffect, useMemo } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

/**
 * Animated expansion ring effect when a node is clicked/hovered.
 * Shows concentric rings that pulse outward, with neighbor nodes
 * appearing along the rings.
 */

interface ExpansionRingProps {
  sourceNode: BrainGraphNode | null;
  neighbors: BrainGraphNode[];
  nodeMap: Record<string, BrainGraphNode>;
  position: { x: number; y: number };
  isExpanding: boolean;
  onSelectNode: (node: BrainGraphNode) => void;
  maxRings?: number;
}

export function NodeExpansionRing({
  sourceNode,
  neighbors,
  nodeMap,
  position,
  isExpanding,
  onSelectNode,
  maxRings = 3,
}: ExpansionRingProps) {
  const [activeRings, setActiveRings] = useState(0);
  const [hoveredNeighbor, setHoveredNeighbor] = useState<string | null>(null);

  // Animate rings expanding
  useEffect(() => {
    if (!isExpanding || !sourceNode) {
      setActiveRings(0);
      return;
    }

    let current = 0;
    const interval = setInterval(() => {
      current++;
      setActiveRings(current);
      if (current >= maxRings) {
        clearInterval(interval);
      }
    }, 120);

    return () => clearInterval(interval);
  }, [isExpanding, sourceNode, maxRings]);

  // Group neighbors by distance (1-hop, 2-hop, etc.)
  const groupedNeighbors = useMemo(() => {
    const groups: BrainGraphNode[][] = [];
    // Currently we only show direct neighbors (1-hop)
    // Future: could compute multi-hop distances
    groups.push(neighbors);
    return groups;
  }, [neighbors]);

  if (!sourceNode || !isExpanding) return null;

  const sourceColor = KIND_COLOR_TAILWIND[sourceNode.kind as keyof typeof KIND_COLOR_TAILWIND];

  return (
    <g className="pointer-events-none">
      {/* Animated rings */}
      {[1, 2, 3].map((ring) => (
        <g key={ring} opacity={activeRings >= ring ? 1 : 0} className="transition-opacity duration-300">
          <circle
            cx={position.x}
            cy={position.y}
            r={ring * 40}
            fill="none"
            stroke={sourceColor?.fill || '#71717a'}
            strokeWidth={1}
            opacity={0.2 / ring}
            strokeDasharray="4 4"
          >
            <animate
              attributeName="r"
              from={ring * 35}
              to={ring * 45}
              dur={`${1.5 + ring * 0.3}s`}
              repeatCount="indefinite"
              values={`${ring * 35};${ring * 45};${ring * 35}`}
              keyTimes="0;0.5;1"
            />
          </circle>
        </g>
      ))}

      {/* Neighbor nodes on first ring */}
      {groupedNeighbors[0] && activeRings >= 1 && (
        <g>
          {groupedNeighbors[0].map((neighbor, i) => {
            const angle = (i / groupedNeighbors[0].length) * Math.PI * 2 - Math.PI / 2;
            const radius = 60;
            const nx = position.x + Math.cos(angle) * radius;
            const ny = position.y + Math.sin(angle) * radius;
            const neighborColor = KIND_COLOR_TAILWIND[neighbor.kind as keyof typeof KIND_COLOR_TAILWIND];
            const isHovered = hoveredNeighbor === neighbor.id;

            return (
              <g
                key={neighbor.id}
                className="pointer-events-auto cursor-pointer"
                onMouseEnter={() => setHoveredNeighbor(neighbor.id)}
                onMouseLeave={() => setHoveredNeighbor(null)}
                onClick={() => onSelectNode(neighbor)}
              >
                {/* Connection line */}
                <line
                  x1={position.x}
                  y1={position.y}
                  x2={nx}
                  y2={ny}
                  stroke={isHovered ? '#f59e0b' : '#3f3f46'}
                  strokeWidth={isHovered ? 2 : 1}
                  opacity={isHovered ? 0.8 : 0.3}
                />

                {/* Node circle */}
                <circle
                  cx={nx}
                  cy={ny}
                  r={isHovered ? 6 : 4}
                  fill={neighborColor?.fill || '#71717a'}
                  stroke={isHovered ? '#f59e0b' : '#09090b'}
                  strokeWidth={isHovered ? 2 : 1.5}
                  className="transition-all duration-150"
                />

                {/* Label */}
                <text
                  x={nx}
                  y={ny + 10}
                  textAnchor="middle"
                  fontSize="7"
                  fill={isHovered ? '#e4e4e7' : '#71717a'}
                  fontFamily="IBM Plex Sans"
                  className="pointer-events-none"
                >
                  {neighbor.label.length > 12 ? neighbor.label.slice(0, 10) + '…' : neighbor.label}
                </text>
              </g>
            );
          })}
        </g>
      )}

      {/* Center node pulse */}
      <circle
        cx={position.x}
        cy={position.y}
        r={8}
        fill={sourceColor?.fill || '#71717a'}
        opacity={0.4}
      >
        <animate
          attributeName="r"
          values="8;12;8"
          dur="1.5s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="opacity"
          values="0.4;0.1;0.4"
          dur="1.5s"
          repeatCount="indefinite"
        />
      </circle>
    </g>
  );
}
