import React, { useState, useCallback } from 'react';

type StreamGroup = 'understand' | 'investigate' | 'plan' | 'execute' | 'test' | 'verify' | 'recover';
type StreamStatus = 'pending' | 'running' | 'completed' | 'failed';
type DetailLevel = 'L0' | 'L1' | 'L2' | 'L3';

interface MicroAction {
  type: string;
  description: string;
  target: string;
  result: string;
  duration_ms: number;
}

interface StreamAction {
  action_id: string;
  group: StreamGroup;
  label: string;
  status: StreamStatus;
  summary: string;
  progress: string;
  duration: number;
  files_changed?: { path: string; type: 'M' | 'A' | 'D'; lines?: string }[];
  reason?: string;
  symbols?: string[];
  dependencies?: string[];
  micro_actions?: MicroAction[];
  raw_output?: string;
  commands?: { command: string; output: string; exit_code: number }[];
  evidence?: { type: string; passed: boolean; details: string }[];
}

interface ChatStreamViewProps {
  task: string;
  actions: StreamAction[];
  totalDuration: number;
  status: 'running' | 'completed' | 'failed';
  result?: string;
}

const GROUP_CONFIG: Record<StreamGroup, { icon: string; color: string }> = {
  understand: { icon: '🔍', color: 'text-blue-400' },
  investigate: { icon: '🔎', color: 'text-purple-400' },
  plan: { icon: '📋', color: 'text-amber-400' },
  execute: { icon: '✏️', color: 'text-cyan-400' },
  test: { icon: '🧪', color: 'text-green-400' },
  verify: { icon: '✓', color: 'text-teal-400' },
  recover: { icon: '🔄', color: 'text-orange-400' },
};

const STATUS_CONFIG: Record<StreamStatus, { icon: string; color: string }> = {
  pending: { icon: '○', color: 'text-zinc-600' },
  running: { icon: '◉', color: 'text-amber-400 animate-pulse' },
  completed: { icon: '✓', color: 'text-green-400' },
  failed: { icon: '✗', color: 'text-red-400' },
};

function ActionNode({ action, defaultExpanded = false }: { action: StreamAction; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('L1');

  const groupConfig = GROUP_CONFIG[action.group];
  const statusConfig = STATUS_CONFIG[action.status];
  const duration = action.duration > 0 ? ` · ${action.duration.toFixed(1)}s` : '';
  const progress = action.progress ? ` · ${action.progress}` : '';

  const cycleDetail = useCallback(() => {
    setDetailLevel(prev => {
      if (prev === 'L0') return 'L1';
      if (prev === 'L1') return 'L2';
      if (prev === 'L2') return 'L3';
      return 'L0';
    });
  }, []);

  return (
    <div className="group">
      <div
        className="flex items-center gap-2 px-3 py-1.5 hover:bg-zinc-900/50 rounded cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <span className={`${statusConfig.color} text-sm`}>{statusConfig.icon}</span>
        <span className={`text-sm ${groupConfig.color}`}>
          {action.label}{progress}{duration}
        </span>
        {action.status === 'running' && (
          <span className="text-[10px] text-zinc-500 ml-auto">
            {action.micro_actions?.length || 0} ops
          </span>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); cycleDetail(); }}
          className="opacity-0 group-hover:opacity-100 text-[10px] text-zinc-600 hover:text-zinc-400"
        >
          {detailLevel}
        </button>
      </div>

      {expanded && (
        <div className="ml-6 border-l border-zinc-800 pl-3 py-1 space-y-1">
          {detailLevel >= 'L1' && action.files_changed && action.files_changed.length > 0 && (
            <div className="space-y-0.5">
              {action.files_changed.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-xs font-mono">
                  <span className={`w-4 text-center ${
                    f.type === 'M' ? 'text-amber-400' : f.type === 'A' ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {f.type}
                  </span>
                  <span className="text-zinc-300">{f.path}</span>
                  {f.lines && <span className="text-zinc-600">{f.lines}</span>}
                </div>
              ))}
              {action.reason && (
                <div className="text-xs text-zinc-500 mt-1">Reason: {action.reason}</div>
              )}
            </div>
          )}

          {detailLevel >= 'L1' && action.symbols && action.symbols.length > 0 && (
            <div className="text-xs">
              <span className="text-zinc-500">Symbols: </span>
              <span className="text-zinc-400 font-mono">{action.symbols.join(', ')}</span>
            </div>
          )}

          {detailLevel >= 'L2' && action.micro_actions && action.micro_actions.length > 0 && (
            <div className="space-y-0.5 mt-2">
              <div className="text-[10px] text-zinc-600 uppercase tracking-wider">Trace</div>
              {action.micro_actions.map((m, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-zinc-500">
                  <span className="text-zinc-700 font-mono w-24 truncate">{m.type}</span>
                  <span className="text-zinc-400 truncate">{m.description}</span>
                  {m.duration_ms > 0 && (
                    <span className="text-zinc-600 ml-auto">{m.duration_ms.toFixed(0)}ms</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {detailLevel >= 'L3' && action.commands && action.commands.length > 0 && (
            <div className="mt-2 space-y-2">
              <div className="text-[10px] text-zinc-600 uppercase tracking-wider">Commands</div>
              {action.commands.map((cmd, i) => (
                <div key={i} className="bg-zinc-950 rounded p-2 text-xs font-mono">
                  <div className="text-zinc-400">$ {cmd.command}</div>
                  <div className="text-zinc-500 mt-1 whitespace-pre-wrap">{cmd.output}</div>
                  <div className={`mt-1 ${cmd.exit_code === 0 ? 'text-green-500' : 'text-red-500'}`}>
                    exit: {cmd.exit_code}
                  </div>
                </div>
              ))}
            </div>
          )}

          {detailLevel >= 'L3' && action.evidence && action.evidence.length > 0 && (
            <div className="mt-2 space-y-1">
              <div className="text-[10px] text-zinc-600 uppercase tracking-wider">Evidence</div>
              {action.evidence.map((e, i) => (
                <div key={i} className={`text-xs ${e.passed ? 'text-green-400' : 'text-red-400'}`}>
                  {e.passed ? '✓' : '✗'} {e.type}: {e.details}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ChatStreamView({ task, actions, totalDuration, status, result }: ChatStreamViewProps) {
  return (
    <div className="space-y-1">
      <div className="text-xs text-zinc-500 px-3 py-1">{task}</div>
      {actions.map(action => (
        <ActionNode
          key={action.action_id}
          action={action}
          defaultExpanded={action.status === 'failed' || action.status === 'running'}
        />
      ))}
      {status !== 'running' && (
        <div className={`flex items-center gap-2 px-3 py-2 text-sm ${
          status === 'completed' ? 'text-green-400' : 'text-red-400'
        }`}>
          <span>{status === 'completed' ? '✓' : '✗'}</span>
          <span>{status === 'completed' ? 'Completed' : 'Failed'}</span>
          <span className="text-zinc-500">· {totalDuration.toFixed(1)}s</span>
          {result && <span className="text-zinc-400 ml-2">— {result}</span>}
        </div>
      )}
    </div>
  );
}

export default ChatStreamView;
