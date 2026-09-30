import React, { useState, useRef, useEffect, useMemo } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

interface SearchPanelProps {
  nodes: BrainGraphNode[];
  nodeMap: Record<string, BrainGraphNode>;
  onSelect: (node: BrainGraphNode) => void;
  onFocus: (node: BrainGraphNode) => void;
}

export function SearchPanel({ nodes, nodeMap, onSelect, onFocus }: SearchPanelProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return nodes
      .filter((n) => {
        return (
          n.label.toLowerCase().includes(q) ||
          n.kind.toLowerCase().includes(q) ||
          (n.detail && n.detail.toLowerCase().includes(q))
        );
      })
      .sort((a, b) => {
        // Exact match first
        const aExact = a.label.toLowerCase() === q ? 0 : 1;
        const bExact = b.label.toLowerCase() === q ? 0 : 1;
        if (aExact !== bExact) return aExact - bExact;
        // Then by starts-with
        const aStarts = a.label.toLowerCase().startsWith(q) ? 0 : 1;
        const bStarts = b.label.toLowerCase().startsWith(q) ? 0 : 1;
        if (aStarts !== bStarts) return aStarts - bStarts;
        return a.label.localeCompare(b.label);
      })
      .slice(0, 12);
  }, [query, nodes]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (selectedIndex >= 0 && listRef.current) {
      const item = listRef.current.children[selectedIndex] as HTMLElement;
      if (item) item.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      e.preventDefault();
      onSelect(results[selectedIndex]);
      onFocus(results[selectedIndex]);
      setIsOpen(false);
      setQuery('');
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setQuery('');
      inputRef.current?.blur();
    }
  };

  // Global keyboard shortcut: Ctrl+K or /
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement))) {
        e.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="relative">
      <div className="flex items-center gap-1.5">
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setIsOpen(true); }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder="Search nodes... (Ctrl+K)"
            className="w-44 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-[11px] font-mono text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); inputRef.current?.focus(); }}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 text-[10px]"
            >
              ✕
            </button>
          )}
        </div>
        {results.length > 0 && (
          <span className="text-[9px] font-mono text-zinc-600">
            {results.length}
          </span>
        )}
      </div>

      {/* Dropdown results */}
      {isOpen && query && results.length > 0 && (
        <div
          ref={listRef}
          className="absolute top-full left-0 mt-1 w-72 max-h-64 overflow-y-auto bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl z-40 backdrop-blur-sm"
        >
          {results.map((node, idx) => (
            <button
              key={node.id}
              onClick={() => {
                onSelect(node);
                onFocus(node);
                setIsOpen(false);
                setQuery('');
              }}
              className={`w-full text-left px-3 py-1.5 flex items-center gap-2 text-[11px] font-ui transition-colors ${
                idx === selectedIndex
                  ? 'bg-zinc-800 text-zinc-200'
                  : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-300'
              }`}
            >
              <span className={`w-2 h-2 rounded-full shrink-0 ${KIND_COLOR_TAILWIND[node.kind as keyof typeof KIND_COLOR_TAILWIND]?.dot || 'bg-zinc-500'}`} />
              <span className="truncate">{node.label}</span>
              <span className="ml-auto text-[9px] font-mono text-zinc-600 shrink-0">{node.kind}</span>
            </button>
          ))}
        </div>
      )}

      {/* No results */}
      {isOpen && query && results.length === 0 && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl z-40 p-3 backdrop-blur-sm">
          <div className="text-[11px] font-ui text-zinc-600 text-center">No matches found</div>
        </div>
      )}
    </div>
  );
}
