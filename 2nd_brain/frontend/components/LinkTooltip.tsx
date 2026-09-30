import React from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';

interface LinkTooltipProps {
  source: BrainGraphNode;
  target: BrainGraphNode;
  position: { x: number; y: number };
  reasons: string[];
}

export function LinkTooltip({ source, target, position, reasons }: LinkTooltipProps) {
  return (
    <div
      className="fixed z-50 pointer-events-none"
      style={{
        left: position.x + 12,
        top: position.y - 8,
        maxWidth: 320,
      }}
    >
      <div className="bg-zinc-950/95 border border-amber-800/50 rounded-lg shadow-2xl px-3 py-2 backdrop-blur-sm">
        {/* Connection header */}
        <div className="flex items-center gap-1 text-[10px] font-ui text-zinc-300 mb-1">
          <span className="text-zinc-400">{source.label.slice(0, 20)}</span>
          <span className="text-amber-400">↔</span>
          <span className="text-zinc-400">{target.label.slice(0, 20)}</span>
        </div>

        {/* Connection types */}
        {reasons.length > 0 ? (
          <div className="text-[9px] font-mono text-zinc-500 border-t border-zinc-800 pt-1 mt-1">
            <span className="text-zinc-600">sabab:</span>{' '}
            {reasons.map((r, i) => (
              <span key={i}>
                <span className="text-amber-300/80">{r}</span>
                {i < reasons.length - 1 && <span className="text-zinc-700">, </span>}
              </span>
            ))}
          </div>
        ) : (
          <div className="text-[9px] font-mono text-zinc-600 border-t border-zinc-800 pt-1 mt-1">
            wikilink / umumiy so'zlar
          </div>
        )}
      </div>
    </div>
  );
}
