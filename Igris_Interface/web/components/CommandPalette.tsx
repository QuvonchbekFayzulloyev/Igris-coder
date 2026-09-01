import React, { useState, useEffect, useRef } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { COMMANDS } from '../../shared/constants';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const newChat = useAgentConsoleStore((s) => s.newChat);
  const setMainView = useAgentConsoleStore((s) => s.setMainView);
  const setSettingsOpen = useAgentConsoleStore((s) => s.setSettingsOpen);

  useEffect(() => {
    if (open) {
      setQuery('');
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  if (!open) return null;

  const run = (action?: string) => {
    switch (action) {
      case 'newChat': newChat(); break;
      case 'openBrain': setMainView('brain'); break;
      case 'openWebAI': setMainView('webai'); break;
      case 'openSettings': setSettingsOpen(true); break;
      default: break;
    }
    onClose();
  };

  const filtered = COMMANDS.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center pt-28" onClick={onClose}>
      <div className="absolute inset-0 bg-black bg-opacity-60" />
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-lg mx-4 bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl overflow-hidden"
      >
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-zinc-800">
          <span className="text-zinc-500">🔍</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command..."
            className="bg-transparent outline-none text-sm text-zinc-100 font-ui flex-1 placeholder-zinc-600"
          />
          <kbd className="text-xs text-zinc-600 border border-zinc-700 rounded px-1.5 py-0.5 font-mono">Esc</kbd>
        </div>
        <div className="max-h-72 overflow-y-auto py-1">
          {filtered.length === 0 && (
            <div className="px-3 py-4 text-xs text-zinc-600 font-ui">No matching commands.</div>
          )}
          {filtered.map((c) => (
            <button
              key={c.label}
              onClick={() => run(c.action)}
              className="w-full flex items-center justify-between px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 text-left font-ui transition-colors"
            >
              <span>{c.label}</span>
              {c.hint && <span className="text-xs text-zinc-600 font-mono">{c.hint}</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
