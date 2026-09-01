import React, { useMemo, useState } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { STAGES, SidebarChatItem } from '../../shared/constants';
import { WorkspaceToolbar } from './WorkspaceToolbar';
import { TreeNodeComponent } from './TreeNode';

/** Claude-style sidebar — Actions / Starred / Recents / Workspace / Agent. */
export function Sidebar() {
  const {
    sidebarMode,
    setSidebarMode,
    tree,
    recents,
    sidebarQuery,
    setSidebarQuery,
    selectChat,
    newChat,
    backendOnline,
    agentInfo,
    stage,
    setSettingsOpen,
  } = useAgentConsoleStore();

  const [activeAction, setActiveAction] = useState<string>('chats');

  const filteredRecents = useMemo(() => {
    const q = sidebarQuery.trim().toLowerCase();
    if (!q) return recents;
    return recents.filter((c) => c.title.toLowerCase().includes(q));
  }, [recents, sidebarQuery]);

  const starred = useMemo(() => recents.filter((c) => c.starred), [recents]);

  const actions = [
    { id: 'chats', label: 'Chats', icon: '💬' },
    { id: 'workspace', label: 'Workspace', icon: '📁' },
    { id: 'agent', label: 'Agent', icon: '🤖' },
  ];

  const selectMode = (mode: 'chats' | 'workspace' | 'agent') => {
    setActiveAction(mode);
    setSidebarMode(mode);
  };

  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-900 bg-opacity-40 shrink-0 z-10 flex flex-col">
      {/* Brand + status */}
      <div className="flex items-center gap-2 px-3 h-10 border-b border-zinc-800 shrink-0">
        <div className="w-6 h-6 rounded-md bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-[11px] font-bold text-zinc-950 shrink-0">
          I
        </div>
        <span className="text-sm font-semibold tracking-wide text-zinc-200 font-ui">IGRIS</span>
        <span className="ml-auto flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-teal-400' : 'bg-zinc-600'}`} />
          <span className={`text-[10px] font-mono ${backendOnline ? 'text-teal-400' : 'text-zinc-600'}`}>
            {backendOnline ? 'online' : 'offline'}
          </span>
        </span>
      </div>

      {/* Search */}
      <div className="px-2.5 pt-2 shrink-0">
        <div className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 rounded-md px-2.5 h-8 focus-within:border-amber-500/40 transition-colors">
          <span className="text-zinc-600 text-xs">🔍</span>
          <input
            value={sidebarQuery}
            onChange={(e) => setSidebarQuery(e.target.value)}
            placeholder="Search chats & notes..."
            className="bg-transparent outline-none text-xs text-zinc-200 font-ui flex-1 placeholder-zinc-600"
          />
        </div>
      </div>

      {/* New chat */}
      <div className="px-2.5 pt-2 shrink-0">
        <button
          onClick={newChat}
          className="w-full flex items-center gap-2 px-2.5 h-8 rounded-md text-xs font-ui text-zinc-300 bg-gradient-to-r from-amber-400/15 to-transparent border border-amber-500/30 hover:from-amber-400/25 hover:border-amber-500/50 transition-all"
        >
          <span className="text-amber-300 text-sm leading-none">✚</span>
          <span className="font-medium text-amber-200">New Chat</span>
        </button>
      </div>

      {/* Action nav */}
      <div className="flex items-center gap-0.5 px-2.5 pt-2 shrink-0">
        {actions.map((a) => (
          <button
            key={a.id}
            onClick={() => selectMode(a.id as 'chats' | 'workspace' | 'agent')}
            className={`flex-1 flex items-center justify-center gap-1.5 px-2 h-7 rounded text-[11px] font-ui transition-colors ${
              activeAction === a.id
                ? 'bg-zinc-800 text-amber-300'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60'
            }`}
          >
            <span className="text-xs">{a.icon}</span>
            {a.label}
          </button>
        ))}
      </div>

      {/* ---------- CHATS ---------- */}
      {sidebarMode === 'chats' && (
        <div className="flex-1 overflow-y-auto py-1.5 px-1.5 space-y-3">
          {starred.length > 0 && (
            <section>
              <div className="px-2 pb-1 text-[10px] font-ui font-medium tracking-widest text-zinc-600">
                STARRED
              </div>
              <div className="space-y-0.5">
                {starred.map((c) => (
                  <ChatRow key={c.id} item={c} onSelect={() => selectChat(c.id)} starred />
                ))}
              </div>
            </section>
          )}
          <section>
            <div className="px-2 pb-1 text-[10px] font-ui font-medium tracking-widest text-zinc-600">
              RECENTS
            </div>
            {filteredRecents.length === 0 ? (
              <div className="px-2 py-4 text-center text-[11px] font-ui text-zinc-600">
                {sidebarQuery ? 'No matching chats' : 'No chats yet — start one above.'}
              </div>
            ) : (
              <div className="space-y-0.5">
                {filteredRecents.map((c) => (
                  <ChatRow key={c.id} item={c} onSelect={() => selectChat(c.id)} />
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* ---------- WORKSPACE ---------- */}
      {sidebarMode === 'workspace' && (
        <div className="flex-1 overflow-y-auto py-1">
          <WorkspaceToolbar />
          <div className="pt-1">
            {tree.map((node) => (
              <TreeNodeComponent key={node.name} node={node} path={node.name} depth={0} />
            ))}
          </div>
        </div>
      )}

      {/* ---------- AGENT ---------- */}
      {sidebarMode === 'agent' && (
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          <div>
            <div className="text-xs font-ui text-zinc-500 mb-1">Model</div>
            <div className="text-sm font-mono text-zinc-200">
              {agentInfo?.model || (backendOnline ? '—' : 'offline')}
            </div>
            <div className="text-xs font-ui text-zinc-600">
              {agentInfo ? (agentInfo.llmAvailable ? 'via Ollama · local' : 'Ollama mavjud emas') : 'bridge ulanmagan'}
            </div>
          </div>
          <div>
            <div className="text-xs font-ui text-zinc-500 mb-1">Brain bridge</div>
            <div className="flex items-center gap-1.5 text-xs font-ui">
              <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-teal-400' : 'bg-zinc-600'}`} />
              <span className={backendOnline ? 'text-teal-400' : 'text-zinc-500'}>
                {backendOnline ? 'connected' : 'offline'}
              </span>
            </div>
          </div>
          <div>
            <div className="text-xs font-ui text-zinc-500 mb-1">RAG memory</div>
            <div className="flex items-center gap-1.5 text-xs font-ui">
              <span className={`w-1.5 h-1.5 rounded-full ${agentInfo?.memoryEnabled ? 'bg-amber-400' : 'bg-zinc-600'}`} />
              <span className={agentInfo?.memoryEnabled ? 'text-amber-300' : 'text-zinc-500'}>
                {agentInfo?.memoryEnabled ? 'on (Igris_Memory)' : 'off'}
              </span>
            </div>
          </div>
          <div>
            <div className="text-xs font-ui text-zinc-500 mb-1.5">Pipeline stage</div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {STAGES.map((s, i) => (
                <span
                  key={s}
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    i < stage
                      ? 'bg-zinc-800 text-amber-300'
                      : i === stage
                        ? 'bg-amber-400 text-zinc-950'
                        : 'text-zinc-600'
                  }`}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
          <button
            onClick={() => setSettingsOpen(true)}
            className="w-full text-xs font-ui text-zinc-400 hover:text-zinc-200 border border-zinc-800 rounded-md px-2 py-1.5 transition-colors"
          >
            ⚙️ Settings
          </button>
        </div>
      )}

      {/* Status footer — real agent holati */}
      <div className="border-t border-zinc-800 px-3 py-2 shrink-0 flex items-center gap-2">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-[11px] font-bold text-zinc-950 shrink-0">
          I
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-ui text-zinc-200 truncate">IGRIS · local agent</div>
          <div className="text-[10px] font-ui text-zinc-600 truncate">
            {agentInfo?.model || (backendOnline ? 'yuklanmoqda…' : 'bridge offline')}
          </div>
        </div>
        <button
          onClick={() => setSettingsOpen(true)}
          title="Settings"
          className="w-6 h-6 flex items-center justify-center rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
        >
          ⚙️
        </button>
      </div>
    </aside>
  );
}

function ChatRow({
  item,
  onSelect,
  starred,
}: {
  item: SidebarChatItem;
  onSelect: () => void;
  starred?: boolean;
}) {
  const starChat = useAgentConsoleStore((s) => s.starChat);
  const renameChat = useAgentConsoleStore((s) => s.renameChat);
  const deleteChat = useAgentConsoleStore((s) => s.deleteChat);
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(item.title);
  const kindIcon = item.kind === 'artifact' ? '🧩' : item.kind === 'project' ? '🗂' : '💬';

  const commitRename = () => {
    if (draft.trim()) renameChat(item.id, draft);
    setRenaming(false);
  };

  return (
    <div className="relative">
      <div
        onClick={onSelect}
        className="group w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left hover:bg-zinc-800/70 cursor-pointer transition-colors"
      >
        <span className="text-xs text-zinc-500 shrink-0">{starred || item.starred ? '⭐' : kindIcon}</span>
        <span className="flex-1 min-w-0">
          <span className="block text-xs font-ui text-zinc-300 truncate group-hover:text-zinc-100">
            {item.title}
          </span>
          <span className="block text-[10px] font-ui text-zinc-600">{item.time}</span>
        </span>
        {item.unread && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />}
        {/* Hover actions — star / rename / delete */}
        <span
          className="hidden group-hover:flex items-center gap-0.5 shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => starChat(item.id, !item.starred)}
            title={item.starred ? 'Unstar' : 'Star'}
            className="w-5 h-5 flex items-center justify-center rounded text-xs text-zinc-500 hover:text-amber-300 hover:bg-zinc-700/60 transition-colors"
          >
            {item.starred ? '★' : '☆'}
          </button>
          <button
            onClick={() => { setDraft(item.title); setRenaming(true); }}
            title="Rename"
            className="w-5 h-5 flex items-center justify-center rounded text-[10px] text-zinc-500 hover:text-zinc-200 hover:bg-zinc-700/60 transition-colors"
          >
            ✎
          </button>
          <button
            onClick={() => deleteChat(item.id)}
            title="Delete"
            className="w-5 h-5 flex items-center justify-center rounded text-[10px] text-zinc-500 hover:text-rose-400 hover:bg-zinc-700/60 transition-colors"
          >
            🗑
          </button>
        </span>
      </div>
      {renaming && (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitRename();
            if (e.key === 'Escape') setRenaming(false);
          }}
          onBlur={commitRename}
          className="absolute inset-x-1 top-1/2 -translate-y-1/2 bg-zinc-950 border border-amber-500/50 rounded px-2 py-1 text-xs font-ui text-zinc-200 outline-none shadow-lg"
        />
      )}
    </div>
  );
}
