/**
 * Radial Visualization — Binary tree with semantic father and radius layers
 * 
 * Features:
 *   - Binary tree structure
 *   - Semantic father as center
 *   - Concentric radius layers
 *   - Mouse interactions (click, drag, zoom, pan)
 *   - Node selection and expansion
 *   - Edge visualization for semantic relations
 *   - Smooth animations
 */

import React, { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { treeStore } from '../../db/tree-store';
import type { TreeNode, SemanticFather, SemanticRelation, SemanticProjection, RadiusLevel } from '../../db/tree-schema';
import { NODE_TYPE_CONFIG, RELATION_TYPE_CONFIG, RADIUS_CONFIG } from '../../db/tree-schema';

// ═══════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════

interface View {
  scale: number;
  tx: number;
  ty: number;
}

interface RadialNode {
  id: string;
  x: number;
  y: number;
  radius: number;
  label: string;
  type: string;
  domain: string;
}

interface RadialEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
}

interface Props {
  width?: number;
  height?: number;
  fatherId?: string;
  onNodeSelect?: (nodeId: string) => void;
  onNodeExpand?: (nodeId: string) => void;
}

// ═══════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════

export function RadialVisualization({
  width = 600,
  height = 400,
  fatherId,
  onNodeSelect,
  onNodeExpand,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<View>({ scale: 1, tx: 0, ty: 0 });
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  
  // Drag state
  const dragRef = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const nodeDragRef = useRef<{ id: string; sx: number; sy: number; ox: number; oy: number } | null>(null);
  const movedRef = useRef(false);

  // ─── DATA ────────────────────────────────

  const projection = useMemo(() => {
    if (!fatherId) return null;
    return treeStore.generateProjection(fatherId);
  }, [fatherId]);

  const father = useMemo(() => {
    if (!fatherId) return null;
    return treeStore.getFather(fatherId);
  }, [fatherId]);

  // ─── MOUSE HANDLERS ──────────────────────

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      dragRef.current = {
        x: e.clientX,
        y: e.clientY,
        tx: view.tx,
        ty: view.ty,
      };
      movedRef.current = false;
    }
  }, [view.tx, view.ty]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (dragRef.current) {
      const dx = e.clientX - dragRef.current.x;
      const dy = e.clientY - dragRef.current.y;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
        movedRef.current = true;
      }
      setView({
        scale: view.scale,
        tx: dragRef.current.tx + dx,
        ty: dragRef.current.ty + dy,
      });
    }
  }, [view.scale]);

  const handleMouseUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(0.3, Math.min(4, view.scale * delta));
    setView({
      scale: newScale,
      tx: view.tx,
      ty: view.ty,
    });
  }, [view.scale, view.tx, view.ty]);

  const handleNodeMouseDown = useCallback((e: React.MouseEvent, nodeId: string) => {
    e.stopPropagation();
    const node = projection?.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    nodeDragRef.current = {
      id: nodeId,
      sx: e.clientX,
      sy: e.clientY,
      ox: node.x,
      oy: node.y,
    };
    movedRef.current = false;
  }, [projection]);

  const handleNodeMouseUp = useCallback((nodeId: string) => {
    if (!movedRef.current) {
      setSelectedNode(nodeId);
      onNodeSelect?.(nodeId);
    }
    nodeDragRef.current = null;
  }, [onNodeSelect]);

  const handleNodeDoubleClick = useCallback((nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
    onNodeExpand?.(nodeId);
  }, [onNodeExpand]);

  // ─── RENDER ──────────────────────────────

  const cx = width / 2;
  const cy = height / 2;

  return (
    <div className="relative bg-zinc-900 rounded-lg overflow-hidden border border-zinc-800">
      {/* Header */}
      <div className="absolute top-2 left-2 z-10">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-300">
            {father?.label || 'Radial View'}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">
            {projection?.nodes.length || 0} nodes
          </span>
        </div>
      </div>

      {/* Legend */}
      <div className="absolute top-2 right-2 z-10 flex flex-col gap-1">
        {Object.entries(RADIUS_CONFIG).map(([key, config]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: config.color }}
            />
            <span className="text-[9px] text-zinc-500">{config.label}</span>
          </div>
        ))}
      </div>

      {/* SVG */}
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
      >
        {/* Transform group */}
        <g transform={`translate(${cx + view.tx}, ${cy + view.ty}) scale(${view.scale})`}>
          {/* Radius circles */}
          {projection && (
            <>
              {Object.entries(RADIUS_CONFIG).map(([key, config]) => (
                <circle
                  key={key}
                  cx={0}
                  cy={0}
                  r={config.radius}
                  fill="none"
                  stroke={config.color}
                  strokeWidth={0.5}
                  strokeDasharray="4 4"
                  opacity={0.3}
                />
              ))}
            </>
          )}

          {/* Edges */}
          {projection?.edges.map((edge, i) => {
            const source = projection.nodes.find(n => n.id === edge.source);
            const target = projection.nodes.find(n => n.id === edge.target);
            if (!source || !target) return null;
            
            const relConfig = RELATION_TYPE_CONFIG[edge.type as keyof typeof RELATION_TYPE_CONFIG];
            
            return (
              <line
                key={i}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke={relConfig?.color || '#6b7280'}
                strokeWidth={1 + edge.weight}
                opacity={0.5}
                strokeDasharray={edge.type === 'contradicts' ? '4 2' : undefined}
              />
            );
          })}

          {/* Nodes */}
          {projection?.nodes.map(node => {
            const nodeConfig = NODE_TYPE_CONFIG[node.type as keyof typeof NODE_TYPE_CONFIG];
            const isSelected = selectedNode === node.id;
            const isHovered = hoveredNode === node.id;
            const isFather = node.radius === 0;
            
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                onMouseUp={() => handleNodeMouseUp(node.id)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onDoubleClick={() => handleNodeDoubleClick(node.id)}
                className="cursor-pointer"
              >
                {/* Selection ring */}
                {isSelected && (
                  <circle
                    r={isFather ? 20 : 14}
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    opacity={0.8}
                  />
                )}

                {/* Hover ring */}
                {isHovered && !isSelected && (
                  <circle
                    r={isFather ? 18 : 12}
                    fill="none"
                    stroke="#60a5fa"
                    strokeWidth={1}
                    opacity={0.5}
                  />
                )}

                {/* Node circle */}
                <circle
                  r={isFather ? 16 : 10}
                  fill={nodeConfig?.color || '#6b7280'}
                  stroke={isSelected ? '#f59e0b' : isHovered ? '#60a5fa' : '#374151'}
                  strokeWidth={isSelected ? 2 : 1}
                />

                {/* Node icon */}
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={isFather ? 12 : 10}
                  className="pointer-events-none select-none"
                >
                  {nodeConfig?.icon || '❓'}
                </text>

                {/* Label */}
                <text
                  y={isFather ? 28 : 20}
                  textAnchor="middle"
                  fontSize={9}
                  fill="#d1d5db"
                  className="pointer-events-none select-none"
                >
                  {node.label.length > 12 ? node.label.slice(0, 12) + '...' : node.label}
                </text>

                {/* Domain badge */}
                {isFather && (
                  <text
                    y={40}
                    textAnchor="middle"
                    fontSize={7}
                    fill="#6b7280"
                    className="pointer-events-none select-none"
                  >
                    {node.domain}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Controls */}
      <div className="absolute bottom-2 left-2 z-10 flex gap-1">
        <button
          onClick={() => setView({ scale: 1, tx: 0, ty: 0 })}
          className="px-2 py-1 text-[10px] bg-zinc-800 rounded text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          Reset
        </button>
        <button
          onClick={() => setView({ scale: view.scale * 1.2, tx: view.tx, ty: view.ty })}
          className="px-2 py-1 text-[10px] bg-zinc-800 rounded text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          Zoom +
        </button>
        <button
          onClick={() => setView({ scale: view.scale * 0.8, tx: view.tx, ty: view.ty })}
          className="px-2 py-1 text-[10px] bg-zinc-800 rounded text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          Zoom -
        </button>
      </div>

      {/* Selected node info */}
      {selectedNode && (
        <div className="absolute bottom-2 right-2 z-10 bg-zinc-800 rounded p-2 max-w-[200px]">
          <div className="text-[10px] text-zinc-300 font-medium mb-1">
            {projection?.nodes.find(n => n.id === selectedNode)?.label}
          </div>
          <div className="text-[9px] text-zinc-500">
            Type: {projection?.nodes.find(n => n.id === selectedNode)?.type}
          </div>
          <div className="text-[9px] text-zinc-500">
            Domain: {projection?.nodes.find(n => n.id === selectedNode)?.domain}
          </div>
        </div>
      )}
    </div>
  );
}
