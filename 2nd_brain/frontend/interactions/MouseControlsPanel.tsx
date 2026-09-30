import React, { useState, useCallback } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';

/**
 * Interactive mouse controls panel for the graph.
 * Shows available mouse actions and current state.
 */

interface MouseControlsPanelProps {
  isShiftDown: boolean;
  isCtrlDown: boolean;
  isAltDown: boolean;
  onToggleShift: () => void;
  onToggleCtrl: () => void;
  onToggleAlt: () => void;
  onClearModifiers: () => void;
  expandedNodes: Set<string>;
  onToggleExpandAll: () => void;
  onCollapseAll: () => void;
}

export function MouseControlsPanel({
  isShiftDown,
  isCtrlDown,
  isAltDown,
  onToggleShift,
  onToggleCtrl,
  onToggleAlt,
  onClearModifiers,
  expandedNodes,
  onToggleExpandAll,
  onCollapseAll,
}: MouseControlsPanelProps) {
  const [showPanel, setShowPanel] = useState(false);

  return (
    <div className="absolute top-14 right-2 z-30">
      {/* Toggle button */}
      <button
        onClick={() => setShowPanel((v) => !v)}
        className={`px-2 py-1 rounded border text-[9px] font-mono transition-colors ${
          showPanel
            ? 'bg-zinc-800 border-zinc-600 text-zinc-300'
            : 'bg-zinc-950/80 border-zinc-700 text-zinc-500 hover:text-zinc-300'
        }`}
        title="Mouse controls"
      >
        🖱 controls
      </button>

      {/* Panel */}
      {showPanel && (
        <div className="mt-1 w-64 bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl backdrop-blur-sm overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-2.5 py-1.5 border-b border-zinc-800">
            <span className="text-[9px] font-ui font-medium text-zinc-400">MOUSE CONTROLS</span>
            <button
              onClick={() => setShowPanel(false)}
              className="text-[9px] font-mono text-zinc-600 hover:text-zinc-300"
            >
              ✕
            </button>
          </div>

          {/* Modifiers */}
          <div className="px-2.5 py-2 border-b border-zinc-800/50">
            <div className="text-[8px] font-mono text-zinc-600 mb-1.5">MODIFIERS</div>
            <div className="flex items-center gap-1">
              <button
                onClick={onToggleShift}
                className={`px-1.5 py-0.5 rounded text-[8px] font-mono border transition-colors ${
                  isShiftDown
                    ? 'bg-amber-900/50 border-amber-600/50 text-amber-300'
                    : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'
                }`}
              >
                Shift
              </button>
              <button
                onClick={onToggleCtrl}
                className={`px-1.5 py-0.5 rounded text-[8px] font-mono border transition-colors ${
                  isCtrlDown
                    ? 'bg-amber-900/50 border-amber-600/50 text-amber-300'
                    : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'
                }`}
              >
                Ctrl
              </button>
              <button
                onClick={onToggleAlt}
                className={`px-1.5 py-0.5 rounded text-[8px] font-mono border transition-colors ${
                  isAltDown
                    ? 'bg-amber-900/50 border-amber-600/50 text-amber-300'
                    : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'
                }`}
              >
                Alt
              </button>
              <button
                onClick={onClearModifiers}
                className="px-1.5 py-0.5 rounded text-[8px] font-mono border border-zinc-800 text-zinc-600 hover:text-zinc-300 transition-colors"
              >
                clear
              </button>
            </div>
          </div>

          {/* Actions */}
          <div className="px-2.5 py-2 space-y-1.5">
            <div className="text-[8px] font-mono text-zinc-600 mb-1">ACTIONS</div>

            {/* Left click */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-zinc-500">L-click</div>
              <div className="text-[8px] font-mono text-zinc-400">Select node</div>
            </div>

            {/* Double click */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-zinc-500">Dbl-click</div>
              <div className="text-[8px] font-mono text-zinc-400">Expand/collapse</div>
            </div>

            {/* Right click */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-zinc-500">R-click</div>
              <div className="text-[8px] font-mono text-zinc-400">Context menu</div>
            </div>

            {/* Middle click */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-zinc-500">M-click</div>
              <div className="text-[8px] font-mono text-zinc-400">Toggle expand</div>
            </div>

            {/* Shift+click */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-amber-400">⇧+click</div>
              <div className="text-[8px] font-mono text-zinc-400">Expand neighbors</div>
            </div>

            {/* Ctrl+click */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-amber-400">⌘+click</div>
              <div className="text-[8px] font-mono text-zinc-400">Multi-select</div>
            </div>

            {/* Scroll */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-zinc-500">Scroll</div>
              <div className="text-[8px] font-mono text-zinc-400">Zoom in/out</div>
            </div>

            {/* Drag */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-zinc-500">Drag</div>
              <div className="text-[8px] font-mono text-zinc-400">Pan canvas</div>
            </div>

            {/* Node drag */}
            <div className="flex items-center gap-2">
              <div className="w-16 text-[8px] font-mono text-zinc-500">Node drag</div>
              <div className="text-[8px] font-mono text-zinc-400">Move node</div>
            </div>
          </div>

          {/* Expand controls */}
          <div className="px-2.5 py-2 border-t border-zinc-800/50">
            <div className="text-[8px] font-mono text-zinc-600 mb-1.5">EXPAND</div>
            <div className="flex items-center gap-1">
              <button
                onClick={onToggleExpandAll}
                className="flex-1 px-1.5 py-0.5 rounded text-[8px] font-mono border border-zinc-800 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
              >
                expand all
              </button>
              <button
                onClick={onCollapseAll}
                className="flex-1 px-1.5 py-0.5 rounded text-[8px] font-mono border border-zinc-800 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
              >
                collapse all
              </button>
            </div>
            {expandedNodes.size > 0 && (
              <div className="text-[7px] font-mono text-zinc-600 mt-1">
                {expandedNodes.size} node(s) expanded
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
