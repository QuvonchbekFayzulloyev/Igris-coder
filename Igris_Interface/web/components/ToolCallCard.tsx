import React, { useState } from 'react';
import { ChatMessage } from '../../shared/constants';

/**
 * ToolCallCard — agent tool chaqiruvining ixcham kartasi.
 *
 * Claude uslubi: yorug' rejimda nozik kulrang qator, dark rejimda
 * zo'rga ko'rinadigan qator; running holatda spinner, done ✓, error ⚠.
 * Detali (preview/diff) bosilganda ochiladi.
 */
export function ToolCallCard(props: ChatMessage) {
  const [open, setOpen] = useState(props.status !== 'running');

  const statusIcon =
    props.status === 'running' ? (
      <span className="w-3.5 h-3.5 text-amber-500 animate-spin shrink-0">⟳</span>
    ) : props.status === 'done' ? (
      <span className="w-3.5 h-3.5 text-teal-500 shrink-0">✓</span>
    ) : (
      <span className="w-3.5 h-3.5 text-rose-500 shrink-0">⚠</span>
    );

  return (
    <div className="border border-zinc-200/80 dark:border-zinc-800 rounded-lg bg-zinc-50/80 dark:bg-zinc-900 overflow-hidden mb-2 max-w-2xl">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-left transition-colors"
      >
        {statusIcon}
        <span className="font-mono text-xs text-zinc-700 dark:text-zinc-200">{props.name}</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-500 truncate flex-1 font-ui">{props.detail}</span>
        {props.diff && (
          <span className="text-zinc-400 dark:text-zinc-600 shrink-0">{open ? '▾' : '▸'}</span>
        )}
      </button>
      {open && props.diff && (
        <div className="border-t border-zinc-200/80 dark:border-zinc-800 px-3 py-2 font-mono text-xs space-y-0.5 bg-white dark:bg-zinc-950">
          {props.diff.map((line, i) => (
            <div
              key={i}
              className={
                line[0] === '+'
                  ? 'bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300 px-1.5 rounded'
                  : line[0] === '-'
                    ? 'bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300 px-1.5 rounded'
                    : 'text-zinc-500 dark:text-zinc-500 px-1.5'
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
