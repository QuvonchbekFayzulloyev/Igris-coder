import React from 'react';
import { KIND_COLOR_TAILWIND } from '../colors';

interface GraphToolbarProps {
  nodeCount: number;
  linkCount: number;
  stats: {
    vault_files?: number;
    chat_sessions?: number;
    persistent_entries?: number;
    runtime_entries?: number;
  } | null;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onReset: () => void;
  onRefresh: () => void;
  onToggleStats: () => void;
  onToggleHelp: () => void;
  live: boolean;
  stale: boolean;
  loading: boolean;
}

export function GraphToolbar({
  nodeCount,
  linkCount,
  stats,
  onZoomIn,
  onZoomOut,
  onFit,
  onReset,
  onRefresh,
  onToggleStats,
  onToggleHelp,
  live,
  stale,
  loading,
}: GraphToolbarProps) {
  return (
    <div className="absolute top-2 left-2 flex items-center gap-1 z-20">
      {/* Zoom controls */}
      <div className="flex items-center bg-zinc-950/80 border border-zinc-700 rounded-md backdrop-blur-sm overflow-hidden">
        <button
          onClick={onZoomOut}
          className="px-1.5 py-1 text-[11px] font-mono text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          title="Zoom out"
        >
          −
        </button>
        <button
          onClick={onZoomIn}
          className="px-1.5 py-1 text-[11px] font-mono text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors border-x border-zinc-700"
          title="Zoom in"
        >
          +
        </button>
        <button
          onClick={onFit}
          className="px-1.5 py-1 text-[10px] font-mono text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          title="Fit all (F)"
        >
          ⤢
        </button>
        <button
          onClick={onReset}
          className="px-1.5 py-1 text-[10px] font-mono text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          title="Reset view (R)"
        >
          ⟲
        </button>
      </div>

      {/* Status */}
      <div className="flex items-center gap-1 bg-zinc-950/80 border border-zinc-700 rounded-md px-2 py-1 backdrop-blur-sm">
        {loading ? (
          <span className="text-[10px] font-mono text-zinc-500">⏳</span>
        ) : stale ? (
          <span className="text-[10px] font-mono text-amber-500" title="Stale data">⚠</span>
        ) : live ? (
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" title="Live" />
        ) : (
          <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" title="Offline" />
        )}
        <span className="text-[9px] font-mono text-zinc-600">
          {nodeCount}n · {linkCount}l
        </span>
      </div>

      {/* Quick actions */}
      <div className="flex items-center bg-zinc-950/80 border border-zinc-700 rounded-md backdrop-blur-sm overflow-hidden">
        <button
          onClick={onRefresh}
          className="px-1.5 py-1 text-[10px] font-mono text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          title="Refresh graph"
        >
          ↻
        </button>
        <button
          onClick={onToggleStats}
          className="px-1.5 py-1 text-[10px] font-mono text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors border-l border-zinc-700"
          title="Statistics"
        >
          📊
        </button>
        <button
          onClick={onToggleHelp}
          className="px-1.5 py-1 text-[10px] font-mono text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors border-l border-zinc-700"
          title="Keyboard shortcuts (?)"
        >
          ?
        </button>
      </div>
    </div>
  );
}
