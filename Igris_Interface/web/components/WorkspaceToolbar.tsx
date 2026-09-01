import React from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { ROOTS } from '../../shared/constants';

export function WorkspaceToolbar() {
  const { rootName, rootMenuOpen, setRootMenuOpen, setRootName, setTree, tree, loadWorkspace } =
    useAgentConsoleStore();

  return (
    <div className="border-b border-zinc-800 relative">
      <button
        onClick={() => setRootMenuOpen(!rootMenuOpen)}
        className="w-full flex items-center justify-between px-2.5 py-1.5 text-xs font-ui text-zinc-300 hover:bg-zinc-800"
      >
        <span className="truncate font-medium">{rootName}</span>
        <span className="text-zinc-600 shrink-0">▾</span>
      </button>
      <div className="flex items-center gap-0.5 px-2 pb-1.5">
        <button
          title="New File"
          className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
        >
          +
        </button>
        <button
          title="New Folder"
          className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
        >
          📁+
        </button>
        <button
          title="Refresh"
          onClick={() => loadWorkspace()}
          className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
        >
          ↻
        </button>
        <button
          title="Collapse All"
          className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
        >
          ⇑
        </button>
      </div>
      {rootMenuOpen && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setRootMenuOpen(false)} />
          <div className="absolute left-2 right-2 top-full mt-1 bg-zinc-900 border border-zinc-700 rounded-md shadow-xl z-30 py-1">
            {ROOTS.map((r) => (
              <button
                key={r}
                onClick={() => {
                  setRootName(r);
                  setRootMenuOpen(false);
                  loadWorkspace(r);
                }}
                className="w-full text-left px-2.5 py-1.5 text-xs font-ui text-zinc-300 hover:bg-zinc-800"
              >
                {r}
              </button>
            ))}
            <div className="border-t border-zinc-800 mt-1 pt-1">
              <button
                onClick={() => setRootMenuOpen(false)}
                className="w-full text-left px-2.5 py-1.5 text-xs font-ui text-zinc-500 hover:bg-zinc-800"
              >
                Open folder…
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
