import React, { useState, useEffect, useCallback } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { AgentStatusPanel } from './AgentStatusPanel';

/* ------------------------------------------------------------------ */
/*  Right Sidebar — Agent Status / Inspector                          */
/* ------------------------------------------------------------------ */

type Tab = 'agent' | 'inspector';

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: 'agent', icon: '🤖', label: 'Agent' },
  { id: 'inspector', icon: '🔍', label: 'Inspector' },
];

export function RightSidebar() {
  const {
    rightSidebarTab,
    setRightSidebarTab,
    setRightSidebarOpen,
    messages,
    stage,
    stageDetail,
    taskRunning,
    agentInfo,
    backendOnline,
    selectedFile,
    setMainView,
  } = useAgentConsoleStore();

  return (
    <aside className="w-80 border-l border-zinc-800 bg-zinc-900 bg-opacity-40 shrink-0 z-10 flex flex-col">
      {/* Tab bar */}
      <div className="flex items-center border-b border-zinc-800 shrink-0">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setRightSidebarTab(t.id)}
            className={`flex-1 flex items-center justify-center gap-1 px-1 py-2 text-[11px] font-ui transition-colors ${
              rightSidebarTab === t.id
                ? 'text-amber-300 border-b-2 border-amber-400 bg-zinc-800/50'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30'
            }`}
          >
            <span className="text-xs">{t.icon}</span>
            <span className="hidden lg:inline">{t.label}</span>
          </button>
        ))}
        <button
          onClick={() => setRightSidebarOpen(false)}
          className="w-7 h-7 flex items-center justify-center text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors shrink-0"
          title="Close right sidebar"
        >
          ✕
        </button>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {rightSidebarTab === 'agent' && (
          <AgentStatusPanel />
        )}
        {rightSidebarTab === 'inspector' && (
          <InspectorPanel />
        )}
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  Panel 1: Agent Activity — tool calls tarixi, progress, agent holati */
/* ------------------------------------------------------------------ */

function ActivityPanel() {
  const { messages, stage, stageDetail, taskRunning, agentInfo, backendOnline } =
    useAgentConsoleStore();

  // Collect all tool calls from messages
  const toolCalls = messages
    .filter((m) => m.kind === 'toolcall')
    .slice(-20)
    .reverse();

  return (
    <div className="p-3 space-y-4">
      {/* Agent status */}
      <Section title="Agent Status">
        <div className="space-y-2">
          <StatusRow
            label="Backend"
            value={backendOnline ? 'Connected' : 'Offline'}
            color={backendOnline ? 'teal' : 'zinc'}
          />
          <StatusRow
            label="Model"
            value={agentInfo?.model || '—'}
            color={agentInfo?.llmAvailable ? 'amber' : 'zinc'}
          />
          <StatusRow
            label="LLM"
            value={
              agentInfo?.llmDegraded
                ? `Degraded (${agentInfo.llmFailureCount}×)`
                : agentInfo?.llmAvailable
                  ? 'Available'
                  : 'Offline'
            }
            color={
              agentInfo?.llmDegraded
                ? 'rose'
                : agentInfo?.llmAvailable
                  ? 'teal'
                  : 'zinc'
            }
          />
          <StatusRow
            label="Memory"
            value={agentInfo?.memoryEnabled ? 'RAG on' : 'RAG off'}
            color={agentInfo?.memoryEnabled ? 'amber' : 'zinc'}
          />
          <StatusRow
            label="Intelligence"
            value={agentInfo?.intelligenceEnabled ? '12 modules' : 'Off'}
            color={agentInfo?.intelligenceEnabled ? 'teal' : 'zinc'}
          />
        </div>
      </Section>

      {/* Pipeline progress */}
      <Section title="Pipeline">
        <div className="space-y-1.5">
          {['Plan', 'Read', 'Edit', 'Test', 'Review'].map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  i < stage
                    ? 'bg-teal-400'
                    : i === stage && taskRunning
                      ? 'bg-amber-400 animate-pulse'
                      : 'bg-zinc-700'
                }`}
              />
              <span
                className={`text-[11px] font-ui ${
                  i === stage && taskRunning
                    ? 'text-amber-300 font-medium'
                    : i < stage
                      ? 'text-zinc-400'
                      : 'text-zinc-600'
                }`}
              >
                {i < stage ? '✓ ' : ''}
                {s}
              </span>
            </div>
          ))}
        </div>
        {stageDetail && (
          <div className="mt-2 text-[10px] font-mono text-zinc-500 truncate">
            {stageDetail}
          </div>
        )}
      </Section>

      {/* Recent tool calls */}
      <Section title={`Tool Calls (${toolCalls.length})`}>
        {toolCalls.length === 0 ? (
          <div className="text-[11px] font-ui text-zinc-600 text-center py-4">
            No tool calls yet
          </div>
        ) : (
          <div className="space-y-1.5 max-h-80 overflow-y-auto">
            {toolCalls.map((tc, i) => (
              <div
                key={i}
                className="border border-zinc-800 rounded-md px-2.5 py-1.5 bg-zinc-950"
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      tc.status === 'running'
                        ? 'bg-amber-400 animate-pulse'
                        : tc.status === 'error'
                          ? 'bg-rose-400'
                          : 'bg-teal-400'
                    }`}
                  />
                  <span className="text-[11px] font-mono text-zinc-200 truncate">
                    {tc.name || 'tool'}
                  </span>
                </div>
                {tc.detail && (
                  <div className="text-[10px] font-ui text-zinc-500 truncate mt-0.5">
                    {tc.detail}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Panel 2: File Inspector — tanlangan fayl tafsilotlari              */
/* ------------------------------------------------------------------ */

function InspectorPanel() {
  const { selectedFile, tree } = useAgentConsoleStore();
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const loadFile = useCallback(async () => {
    if (!selectedFile) return;
    setLoading(true);
    try {
      const { getBackendUrl } = await import('../backend');
      const base = await getBackendUrl();
      const res = await fetch(`${base}/api/workspace/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: selectedFile }),
      });
      if (res.ok) {
        const data = await res.json();
        setFileContent(data.content || '');
      } else {
        setFileContent(`// Error reading file: ${res.status}`);
      }
    } catch {
      setFileContent('// Could not load file — backend offline');
    } finally {
      setLoading(false);
    }
  }, [selectedFile]);

  useEffect(() => {
    loadFile();
  }, [loadFile]);

  // Find file info from tree
  const fileInfo = findNode(tree, selectedFile);

  return (
    <div className="p-3 space-y-4">
      <Section title="Selected File">
        {selectedFile ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs">📄</span>
              <span className="text-xs font-mono text-zinc-200 truncate">
                {selectedFile}
              </span>
            </div>
            {fileInfo && (
              <div className="flex gap-2 flex-wrap">
                <Tag label={fileInfo.type === 'folder' ? 'Folder' : 'File'} color="zinc" />
                {fileInfo.status && (
                  <Tag
                    label={fileInfo.status}
                    color={fileInfo.status === 'new' ? 'teal' : 'amber'}
                  />
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="text-[11px] font-ui text-zinc-600 text-center py-4">
            Select a file from the workspace to inspect it
          </div>
        )}
      </Section>

      {selectedFile && (
        <Section title="Preview">
          {loading ? (
            <div className="text-[11px] font-ui text-zinc-500 text-center py-4">
              Loading...
            </div>
          ) : (
            <div className="bg-zinc-950 border border-zinc-800 rounded-md overflow-hidden">
              <div className="flex items-center gap-2 px-2.5 py-1.5 border-b border-zinc-800">
                <span className="text-[10px] font-mono text-zinc-500">
                  {selectedFile.split('.').pop()?.toUpperCase() || 'TXT'}
                </span>
                <span className="text-[10px] font-ui text-zinc-600 ml-auto">
                  {fileContent.split('\n').length} lines
                </span>
              </div>
              <pre className="p-2.5 text-[11px] font-mono text-zinc-300 overflow-x-auto max-h-96 overflow-y-auto leading-relaxed">
                {fileContent || '// Empty file'}
              </pre>
            </div>
          )}
        </Section>
      )}

      {/* Quick actions */}
      {selectedFile && (
        <Section title="Quick Actions">
          <div className="space-y-1.5">
            <ActionButton
              icon="✏️"
              label="Edit in Chat"
              onClick={() => {
                const store = useAgentConsoleStore.getState();
                store.setInput(`Edit file: ${selectedFile}`);
                store.setMainView('chat');
              }}
            />
            <ActionButton
              icon="👁"
              label="Preview"
              onClick={() => {
                const store = useAgentConsoleStore.getState();
                store.setMainView('preview');
              }}
            />
            <ActionButton
              icon="📋"
              label="Copy path"
              onClick={() => navigator.clipboard?.writeText(selectedFile)}
            />
          </div>
        </Section>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Panel 3: Memory — RAG memory holati va stats                       */
/* ------------------------------------------------------------------ */

function MemoryPanel() {
  const { agentInfo, backendOnline } = useAgentConsoleStore();
  const [memStatus, setMemStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!backendOnline) return;
    setLoading(true);
    const { getBackendUrl } = require('../backend');
    getBackendUrl()
      .then((base: string) =>
        fetch(`${base}/api/memory/status`)
          .then((r) => r.json())
          .then(setMemStatus)
          .catch(() => {})
          .finally(() => setLoading(false))
      )
      .catch(() => setLoading(false));
  }, [backendOnline]);

  return (
    <div className="p-3 space-y-4">
      <Section title="RAG Memory">
        <div className="space-y-2">
          <StatusRow
            label="Status"
            value={
              agentInfo?.memoryEnabled
                ? 'Enabled'
                : 'Disabled'
            }
            color={agentInfo?.memoryEnabled ? 'teal' : 'zinc'}
          />
          {memStatus && (
            <>
              <StatusRow
                label="Corpus"
                value={memStatus.corpus_loaded ? 'Loaded' : 'Loading...'}
                color={memStatus.corpus_loaded ? 'teal' : 'amber'}
              />
              <StatusRow
                label="Entries"
                value={String(memStatus.total_entries || 0)}
                color="zinc"
              />
              <StatusRow
                label="Sessions"
                value={String(memStatus.sessions || 0)}
                color="zinc"
              />
            </>
          )}
          {loading && (
            <div className="text-[11px] font-ui text-zinc-500 text-center py-2">
              Loading memory status...
            </div>
          )}
        </div>
      </Section>

      <Section title="Memory Layers">
        <div className="space-y-1.5">
          {[
            { name: 'L1 — Short-turn', desc: 'Active context, recent messages' },
            { name: 'L2 — Persistent', desc: 'Knowledge, solutions, experience' },
            { name: 'RAG — Recall', desc: 'Semantic search over all memory' },
            { name: 'CAG — Cache', desc: 'Cached responses for fast queries' },
            { name: 'MAG — Session', desc: 'Memory-augmented generation' },
          ].map((layer) => (
            <div key={layer.name} className="border border-zinc-800 rounded-md px-2.5 py-2 bg-zinc-950">
              <div className="text-[11px] font-ui text-zinc-200">{layer.name}</div>
              <div className="text-[10px] font-ui text-zinc-500">{layer.desc}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Intelligence">
        <div className="space-y-1.5">
          <StatusRow
            label="12 Modules"
            value={agentInfo?.intelligenceEnabled ? 'Active' : 'Off'}
            color={agentInfo?.intelligenceEnabled ? 'amber' : 'zinc'}
          />
          {agentInfo?.intelligenceEnabled && (
            <div className="flex flex-wrap gap-1">
              {[
                'harm-filter', 'user-model', 'tone', 'language',
                'logic', 'spatial', 'creative', 'self-eval',
                'naturalist', 'music', 'reasoning', 'calibration',
              ].map((m) => (
                <span
                  key={m}
                  className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400"
                >
                  {m}
                </span>
              ))}
            </div>
          )}
        </div>
      </Section>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Panel 4: Task — joriy vazifa tafsilotlari                           */
/* ------------------------------------------------------------------ */

function TaskPanel() {
  const { messages, taskRunning, stage, stageDetail } =
    useAgentConsoleStore();

  // Find the last user message
  const lastUser = [...messages].reverse().find((m) => m.role === 'user');
  // Find completion records
  const completions = messages
    .filter((m) => m.completion)
    .slice(-5)
    .reverse();

  return (
    <div className="p-3 space-y-4">
      <Section title="Current Task">
        {taskRunning ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-[11px] font-ui text-amber-300">
                Running...
              </span>
            </div>
            <div className="text-[11px] font-ui text-zinc-300">
              {lastUser?.text || '—'}
            </div>
            <div className="text-[10px] font-mono text-zinc-500">
              Stage: {['Plan', 'Read', 'Edit', 'Test', 'Review'][stage]} — {stageDetail}
            </div>
          </div>
        ) : lastUser ? (
          <div className="space-y-2">
            <div className="text-[11px] font-ui text-zinc-400">Last request:</div>
            <div className="text-[11px] font-ui text-zinc-200 leading-relaxed">
              {lastUser.text}
            </div>
          </div>
        ) : (
          <div className="text-[11px] font-ui text-zinc-600 text-center py-4">
            No active task
          </div>
        )}
      </Section>

      {/* Completion history */}
      <Section title={`Completions (${completions.length})`}>
        {completions.length === 0 ? (
          <div className="text-[11px] font-ui text-zinc-600 text-center py-4">
            No completions yet
          </div>
        ) : (
          <div className="space-y-2">
            {completions.map((msg, i) => {
              const c = msg.completion!;
              return (
                <div
                  key={i}
                  className="border border-zinc-800 rounded-md px-2.5 py-2 bg-zinc-950"
                >
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {c.pipeline && (
                      <Tag label={c.pipeline} color="amber" />
                    )}
                    {c.engine && (
                      <Tag label={c.engine} color="teal" />
                    )}
                    {c.status && (
                      <Tag
                        label={c.status}
                        color={c.status === 'ok' ? 'teal' : 'rose'}
                      />
                    )}
                  </div>
                  {c.tools && c.tools.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {c.tools.map((t) => (
                        <span
                          key={t}
                          className="text-[9px] font-mono px-1 py-0.5 rounded bg-zinc-800 text-zinc-400"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  {c.subject && (
                    <div className="text-[10px] font-ui text-zinc-500 mt-1">
                      Subject: {c.subject}
                    </div>
                  )}
                  {c.duration_ms && (
                    <div className="text-[10px] font-mono text-zinc-600 mt-1">
                      {Math.round(c.duration_ms)}ms
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Section>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Shared small components                                            */
/* ------------------------------------------------------------------ */

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] font-ui font-medium tracking-widest text-zinc-500 mb-2 uppercase">
        {title}
      </div>
      {children}
    </div>
  );
}

function StatusRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    teal: 'text-teal-400',
    amber: 'text-amber-300',
    rose: 'text-rose-400',
    zinc: 'text-zinc-500',
  };
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] font-ui text-zinc-500">{label}</span>
      <span className={`text-[11px] font-mono ${colorMap[color] || 'text-zinc-400'}`}>
        {value}
      </span>
    </div>
  );
}

function Tag({ label, color }: { label: string; color: string }) {
  const colorMap: Record<string, string> = {
    teal: 'bg-teal-950 text-teal-300 border-teal-800',
    amber: 'bg-amber-950 text-amber-300 border-amber-800',
    rose: 'bg-rose-950 text-rose-300 border-rose-800',
    zinc: 'bg-zinc-800 text-zinc-400 border-zinc-700',
  };
  return (
    <span
      className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
        colorMap[color] || colorMap.zinc
      }`}
    >
      {label}
    </span>
  );
}

function ActionButton({
  icon,
  label,
  onClick,
}: {
  icon: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[11px] font-ui text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/70 transition-colors text-left"
    >
      <span className="text-xs">{icon}</span>
      {label}
    </button>
  );
}

/** Find a node in the tree by path */
function findNode(
  tree: any[],
  path: string
): { type: string; status?: string } | null {
  for (const node of tree) {
    if (node.name === path) return node;
    if (node.children) {
      const found = findNode(
        node.children,
        path.replace(node.name + '/', '')
      );
      if (found) return found;
    }
  }
  return null;
}

/* ------------------------------------------------------------------ */
/*  Panel 5: Systems — Knowledge, Tasks, Artifacts, Evidence           */
/* ------------------------------------------------------------------ */

function SystemsPanel() {
  return (
    <div className="h-full">
      <SystemIntegrationPanel />
    </div>
  );
}
