import React from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

interface NodeTooltipProps {
  node: BrainGraphNode;
  position: { x: number; y: number };
  linkReasons?: string[];
}

export function NodeTooltip({ node, position, linkReasons }: NodeTooltipProps) {
  const kindColor = KIND_COLOR_TAILWIND[node.kind as keyof typeof KIND_COLOR_TAILWIND];

  return (
    <div
      className="fixed z-50 pointer-events-none"
      style={{
        left: position.x + 12,
        top: position.y - 8,
        maxWidth: 300,
      }}
    >
      <div className="bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl px-3 py-2 backdrop-blur-sm">
        {/* Header */}
        <div className="flex items-center gap-1.5 mb-1">
          <span className={`w-2 h-2 rounded-full ${kindColor?.dot || 'bg-zinc-500'}`} />
          <span className={`text-[11px] font-ui font-medium ${kindColor?.text || 'text-zinc-400'}`}>
            {node.label}
          </span>
        </div>

        {/* Kind + time */}
        <div className="flex items-center gap-2 text-[9px] font-mono text-zinc-600 mb-1">
          <span>{node.kind}</span>
          {node.kind === 'session' && node.updated_at && (
            <span className="text-teal-500/70">· {relTime(node.updated_at)}</span>
          )}
        </div>

        {/* Detail preview */}
        {node.detail && (
          <div className="text-[10px] font-ui text-zinc-500 leading-snug line-clamp-3 mt-1 border-t border-zinc-800 pt-1">
            {node.detail}
          </div>
        )}

        {/* Link reasons */}
        {linkReasons && linkReasons.length > 0 && (
          <div className="text-[9px] font-mono text-amber-400/70 mt-1 border-t border-zinc-800 pt-1">
            🔗 {linkReasons.slice(0, 3).join(', ')}
            {linkReasons.length > 3 && ` +${linkReasons.length - 3}`}
          </div>
        )}
      </div>
    </div>
  );
}

function relTime(epochSec?: number): string {
  if (!epochSec || !(epochSec > 0)) return '';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - epochSec));
  if (s < 45) return 'hozir';
  if (s < 90) return '1 daq';
  if (s < 3600) return `${Math.floor(s / 60)} daq`;
  if (s < 86400) return `${Math.floor(s / 3600)} soat`;
  return `${Math.floor(s / 86400)} kun`;
}
