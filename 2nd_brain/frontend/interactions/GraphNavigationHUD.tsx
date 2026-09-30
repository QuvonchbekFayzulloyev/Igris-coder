import React, { useState, useEffect } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';

/**
 * Heads-up display for graph navigation state.
 * Shows zoom level, selected node info, expanded count, and quick actions.
 */

interface NavigationHUDProps {
  zoom: number;
  selectedNode: BrainGraphNode | null;
  expandedCount: number;
  multiSelectCount: number;
  totalNodes: number;
  totalLinks: number;
  onFitView: () => void;
  onResetView: () => void;
  onToggleHelp: () => void;
}

export function GraphNavigationHUD({
  zoom,
  selectedNode,
  expandedCount,
  multiSelectCount,
  totalNodes,
  totalLinks,
  onFitView,
  onResetView,
  onToggleHelp,
}: NavigationHUDProps) {
  const [isMinimized, setIsMinimized] = useState(false);

  // Keyboard shortcut: H to toggle HUD
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'h' || e.key === 'H') {
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;
        setIsMinimized((v) => !v);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  if (isMinimized) {
    return (
      <button
        onClick={() => setIsMinimized(false)}
        className="absolute bottom-4 left-4 z-30 px-2 py-1 rounded bg-zinc-900/80 border border-zinc-700 text-[9px] font-mono text-zinc-500 hover:text-zinc-300 transition-colors"
        title="Show HUD (H)"
      >
        HUD ▸
      </button>
    );
  }

  return (
    <div className="absolute bottom-4 left-4 z-30 w-56 bg-zinc-950/90 border border-zinc-700 rounded-lg shadow-2xl backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-2.5 py-1.5 border-b border-zinc-800">
        <span className="text-[9px] font-ui font-medium text-zinc-400">NAV HUD</span>
        <div className="flex items-center gap-1">
          <button
            onClick={onToggleHelp}
            className="text-[9px] font-mono text-zinc-600 hover:text-zinc-300 transition-colors"
            title="Keyboard shortcuts (?)"
          >
            ?
          </button>
          <button
            onClick={() => setIsMinimized(true)}
            className="text-[9px] font-mono text-zinc-600 hover:text-zinc-300 transition-colors"
            title="Minimize HUD (H)"
          >
            ▾
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="px-2.5 py-2 space-y-2">
        {/* Zoom */}
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-mono text-zinc-500">Zoom</span>
          <span className="text-[10px] font-mono text-zinc-300">{(zoom * 100).toFixed(0)}%</span>
        </div>

        {/* Selected node */}
        {selectedNode && (
          <div className="pt-1 border-t border-zinc-800/50">
            <div className="text-[9px] font-mono text-zinc-500 mb-0.5">Selected</div>
            <div className="text-[10px] font-ui text-zinc-200 truncate">{selectedNode.label}</div>
            <div className="text-[8px] font-mono text-zinc-600">{selectedNode.kind} · {selectedNode.id.slice(0, 8)}…</div>
          </div>
        )}

        {/* Stats */}
        <div className="pt-1 border-t border-zinc-800/50 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-mono text-zinc-500">Nodes</span>
            <span className="text-[9px] font-mono text-zinc-400">{totalNodes}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[9px] font-mono text-zinc-500">Links</span>
            <span className="text-[9px] font-mono text-zinc-400">{totalLinks}</span>
          </div>
          {expandedCount > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-zinc-500">Expanded</span>
              <span className="text-[9px] font-mono text-amber-400">{expandedCount}</span>
            </div>
          )}
          {multiSelectCount > 1 && (
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-mono text-zinc-500">Selected</span>
              <span className="text-[9px] font-mono text-sky-400">{multiSelectCount}</span>
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="pt-1 border-t border-zinc-800/50 flex items-center gap-1">
          <button
            onClick={onFitView}
            className="flex-1 text-[8px] font-mono px-1.5 py-1 rounded border border-zinc-800 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
            title="Fit view (F)"
          >
            ⛶ fit
          </button>
          <button
            onClick={onResetView}
            className="flex-1 text-[8px] font-mono px-1.5 py-1 rounded border border-zinc-800 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
            title="Reset view (R)"
          >
            ↺ reset
          </button>
        </div>
      </div>
    </div>
  );
}
