import React, { useState, useEffect, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────

interface SmartBuildTask {
  id: string;
  task: string;
  status: 'pending' | 'analyzing' | 'context' | 'llm' | 'execute' | 'verify' | 'done' | 'failed';
  complexity: string;
  confidence: number;
  evidenceCount: number;
  evidencePassed: number;
  tokensUsed: number;
  tokenBudget: number;
  duration: number;
  error?: string;
  createdAt: number;
}

interface SmartBuildStats {
  totalTasks: number;
  successRate: number;
  avgDuration: number;
  tokensSaved: number;
}

interface SmartBuildPanelProps {
  onRun?: (task: string) => void;
  tasks?: SmartBuildTask[];
  stats?: SmartBuildStats;
  isRunning?: boolean;
}

// ── Status Badge ───────────────────────────────────────────────

function StatusBadge({ status }: { status: SmartBuildTask['status'] }) {
  const config = {
    pending: { color: 'bg-zinc-600', label: 'Pending' },
    analyzing: { color: 'bg-blue-500', label: 'Analyzing' },
    context: { color: 'bg-purple-500', label: 'Context' },
    llm: { color: 'bg-amber-500', label: 'LLM' },
    execute: { color: 'bg-cyan-500', label: 'Execute' },
    verify: { color: 'bg-teal-500', label: 'Verify' },
    done: { color: 'bg-green-500', label: 'Done' },
    failed: { color: 'bg-red-500', label: 'Failed' },
  };
  const { color, label } = config[status] || config.pending;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${color} text-white`}>
      <span className={`w-1.5 h-1.5 rounded-full ${status === 'done' || status === 'failed' ? '' : 'animate-pulse'} bg-white/80`} />
      {label}
    </span>
  );
}

// ── Complexity Badge ───────────────────────────────────────────

function ComplexityBadge({ complexity }: { complexity: string }) {
  const config: Record<string, { color: string; icon: string }> = {
    trivial: { color: 'text-zinc-500', icon: '⚡' },
    simple: { color: 'text-green-400', icon: '○' },
    medium: { color: 'text-amber-400', icon: '◎' },
    complex: { color: 'text-orange-400', icon: '◉' },
    ambiguous: { color: 'text-red-400', icon: '⊕' },
  };
  const { color, icon } = config[complexity] || config.medium;

  return (
    <span className={`text-xs font-mono ${color}`}>
      {icon} {complexity}
    </span>
  );
}

// ── Evidence Bar ───────────────────────────────────────────────

function EvidenceBar({ passed, total }: { passed: number; total: number }) {
  const pct = total > 0 ? (passed / total) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-zinc-500">
        {passed}/{total}
      </span>
    </div>
  );
}

// ── Task Card ──────────────────────────────────────────────────

function TaskCard({ task }: { task: SmartBuildTask }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-zinc-800 rounded-lg bg-zinc-900/50 hover:bg-zinc-900 transition-colors">
      <div
        className="flex items-center gap-3 px-3 py-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <StatusBadge status={task.status} />
        <span className="flex-1 text-sm text-zinc-200 truncate">{task.task}</span>
        <ComplexityBadge complexity={task.complexity} />
        <span className="text-[10px] font-mono text-zinc-600">
          {task.duration.toFixed(1)}s
        </span>
      </div>

      {expanded && (
        <div className="px-3 pb-3 border-t border-zinc-800">
          <div className="mt-2 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Confidence</span>
              <span className="text-zinc-300 font-mono">{(task.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Evidence</span>
              <EvidenceBar passed={task.evidencePassed} total={task.evidenceCount} />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-500">Tokens</span>
              <span className="text-zinc-300 font-mono">{task.tokensUsed}/{task.tokenBudget}</span>
            </div>
            {task.error && (
              <div className="mt-2 p-2 bg-red-950/30 border border-red-900/50 rounded text-xs text-red-300 font-mono">
                {task.error}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Stats Bar ──────────────────────────────────────────────────

function StatsBar({ stats }: { stats: SmartBuildStats }) {
  return (
    <div className="flex items-center gap-4 px-3 py-2 bg-zinc-900/50 border border-zinc-800 rounded-lg">
      <div className="text-center">
        <div className="text-lg font-bold text-zinc-200">{stats.totalTasks}</div>
        <div className="text-[10px] text-zinc-500">Tasks</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-bold text-green-400">{(stats.successRate * 100).toFixed(0)}%</div>
        <div className="text-[10px] text-zinc-500">Success</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-bold text-amber-400">{stats.avgDuration.toFixed(1)}s</div>
        <div className="text-[10px] text-zinc-500">Avg Time</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-bold text-cyan-400">{stats.tokensSaved}</div>
        <div className="text-[10px] text-zinc-500">Tokens Saved</div>
      </div>
    </div>
  );
}

// ── Main Panel ─────────────────────────────────────────────────

export function SmartBuildPanel({
  onRun,
  tasks = [],
  stats,
  isRunning = false,
}: SmartBuildPanelProps) {
  const [input, setInput] = useState('');
  const [filter, setFilter] = useState<string>('all');

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && onRun) {
      onRun(input.trim());
      setInput('');
    }
  }, [input, onRun]);

  const filteredTasks = filter === 'all'
    ? tasks
    : tasks.filter(t => t.status === filter);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-zinc-200">Smart Build</span>
          <span className="text-[10px] px-1.5 py-0.5 bg-zinc-800 rounded text-zinc-400">v2.0</span>
        </div>
        {stats && <StatsBar stats={stats} />}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2 px-4 py-3 border-b border-zinc-800">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Task (e.g., 'add authentication', 'fix bug in auth.py')"
          className="flex-1 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
          disabled={isRunning}
        />
        <button
          type="submit"
          disabled={isRunning || !input.trim()}
          className="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 disabled:bg-zinc-800 disabled:text-zinc-600 rounded text-sm text-zinc-200 transition-colors"
        >
          {isRunning ? 'Running...' : 'Run'}
        </button>
      </form>

      {/* Filter */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-zinc-800">
        {['all', 'pending', 'analyzing', 'execute', 'verify', 'done', 'failed'].map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
              filter === f
                ? 'bg-zinc-700 text-zinc-200'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Tasks */}
      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2">
        {filteredTasks.length === 0 ? (
          <div className="text-center text-zinc-600 text-sm py-8">
            No tasks yet. Enter a task above to start.
          </div>
        ) : (
          filteredTasks.map(task => (
            <TaskCard key={task.id} task={task} />
          ))
        )}
      </div>
    </div>
  );
}

// ── Vision Integration Panel ───────────────────────────────────

interface VisionCheck {
  type: string;
  status: 'success' | 'failed' | 'unknown';
  description: string;
  confidence: number;
  timestamp: number;
}

interface VisionPanelProps {
  checks?: VisionCheck[];
  onCheck?: (type: string, params: any) => void;
}

export function VisionBuildPanel({ checks = [], onCheck }: VisionPanelProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <span className="text-sm font-semibold text-zinc-200">Vision + Build</span>
        <div className="flex gap-1">
          <button
            onClick={() => onCheck?.('ui_element', { description: 'all' })}
            className="px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300"
          >
            Check UI
          </button>
          <button
            onClick={() => onCheck?.('error', {})}
            className="px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300"
          >
            Check Errors
          </button>
          <button
            onClick={() => onCheck?.('success', {})}
            className="px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300"
          >
            Check Success
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-2 space-y-1">
        {checks.length === 0 ? (
          <div className="text-center text-zinc-600 text-xs py-4">
            No vision checks yet.
          </div>
        ) : (
          checks.map((check, i) => (
            <div
              key={i}
              className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${
                check.status === 'success'
                  ? 'bg-green-950/30 text-green-300'
                  : check.status === 'failed'
                    ? 'bg-red-950/30 text-red-300'
                    : 'bg-zinc-900 text-zinc-400'
              }`}
            >
              <span className="font-mono">
                {check.status === 'success' ? '✓' : check.status === 'failed' ? '✗' : '?'}
              </span>
              <span className="flex-1 truncate">{check.description}</span>
              <span className="text-[10px] font-mono opacity-60">
                {(check.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default SmartBuildPanel;
