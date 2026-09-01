import React, { useState } from 'react';
import { ChatMessage } from '../../shared/constants';

export function ToolCallCard(props: ChatMessage) {
  const [open, setOpen] = useState(props.status !== 'running');

  const statusIcon =
    props.status === 'running' ? (
      <span className="w-3.5 h-3.5 text-amber-400 animate-spin shrink-0">⟳</span>
    ) : props.status === 'done' ? (
      <span className="w-3.5 h-3.5 text-teal-400 shrink-0">✓</span>
    ) : (
      <span className="w-3.5 h-3.5 text-rose-400 shrink-0">⚠</span>
    );

  return (
    <div className="border border-zinc-800 rounded-md bg-zinc-900 overflow-hidden mb-2 max-w-xl">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-zinc-800 text-left transition-colors"
      >
        {statusIcon}
        <span className="font-mono text-xs text-zinc-200">{props.name}</span>
        <span className="text-xs text-zinc-500 truncate flex-1 font-ui">{props.detail}</span>
        {props.diff && (
          <span className="text-zinc-600 shrink-0">{open ? '▾' : '▸'}</span>
        )}
      </button>
      {open && props.diff && (
        <div className="border-t border-zinc-800 px-3 py-2 font-mono text-xs space-y-0.5 bg-zinc-950">
          {props.diff.map((line, i) => (
            <div
              key={i}
              className={
                line[0] === '+'
                  ? 'bg-teal-950 text-teal-300 px-1.5 rounded'
                  : line[0] === '-'
                    ? 'bg-rose-950 text-rose-300 px-1.5 rounded'
                    : 'text-zinc-500 px-1.5'
              }
            >
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
