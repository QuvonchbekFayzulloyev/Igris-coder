import React, { useEffect, useState } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import type { AgentStateType } from '../../shared/constants';

const STATE_CONFIG: Record<AgentStateType, { icon: string; label: string; color: string; bgColor: string; pulse: boolean }> = {
  idle: { icon: '◇', label: 'Tayyor', color: 'text-zinc-400', bgColor: 'bg-zinc-800/50', pulse: false },
  thinking: { icon: '◈', label: 'Fikrlamoqda', color: 'text-amber-400', bgColor: 'bg-amber-900/20', pulse: true },
  planning: { icon: '◆', label: 'Rejalashtirmoqda', color: 'text-blue-400', bgColor: 'bg-blue-900/20', pulse: true },
  executing: { icon: '◉', label: 'Bajarilmoqda', color: 'text-teal-400', bgColor: 'bg-teal-900/20', pulse: true },
  verifying: { icon: '✓', label: 'Tekshirmoqda', color: 'text-green-400', bgColor: 'bg-green-900/20', pulse: false },
  error: { icon: '✗', label: 'Xato', color: 'text-red-400', bgColor: 'bg-red-900/20', pulse: false },
  paused: { icon: '⏸', label: 'To\'xtatilgan', color: 'text-orange-400', bgColor: 'bg-orange-900/20', pulse: false },
};

function formatUptime(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  const h = Math.floor(s / 3600);
  return `${h}h ${Math.floor((s % 3600) / 60)}m`;
}

export function AgentStatusPanel() {
  const {
    agentState,
    agentCapabilities,
    agentTaskQueue,
    agentCompletedToday,
    agentAutoMode,
    agentStartTime,
    toggleAutoMode,
    backendOnline,
    agentInfo,
    taskRunning,
    stageDetail,
  } = useAgentConsoleStore();

  const [now, setNow] = useState(Date.now());
  const cfg = STATE_CONFIG[agentState];

  // Uptime tick
  useEffect(() => {
    const iv = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(iv);
  }, []);

  const activeTasks = agentTaskQueue.filter((t) => t.status === 'running' || t.status === 'queued');
  const queueTasks = agentTaskQueue.filter((t) => t.status === 'queued');
  const pausedTasks = agentTaskQueue.filter((t) => t.status === 'paused');

  return (
    <div className="space-y-3 p-3 overflow-y-auto h-full">
      {/* ── Agent State ── */}
      <div className="flex items-center gap-2">
        <span className={`text-lg ${cfg.color} ${cfg.pulse ? 'animate-pulse' : ''}`}>{cfg.icon}</span>
        <span className={`text-sm font-medium ${cfg.color}`}>{cfg.label}</span>
        <span className="ml-auto text-[10px] text-zinc-500 font-mono">
          {backendOnline ? (agentInfo?.model || 'local') : 'offline'}
        </span>
      </div>

      {/* Current task */}
      {taskRunning && stageDetail && (
        <div className="text-xs text-zinc-400 truncate">
          <span className="text-amber-500">▸</span> {stageDetail}
        </div>
      )}

      {/* ── Auto Mode + Stats ── */}
      <div className="flex items-center justify-between">
        <button
          onClick={toggleAutoMode}
          className={`flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md transition-colors ${
            agentAutoMode ? 'bg-amber-500/20 text-amber-300' : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          Auto
        </button>
        <span className="text-[10px] text-zinc-600">
          ✓ {agentCompletedToday} · ◻ {activeTasks.length}
        </span>
      </div>

      {/* ── Capabilities (compact) ── */}
      <div className="space-y-0.5">
        {agentCapabilities.filter(c => c.enabled).map((cap) => (
          <div key={cap.name} className="flex items-center gap-1.5 text-[10px] text-zinc-400">
            <span>{cap.icon}</span>
            <span className="truncate">{cap.description}</span>
          </div>
        ))}
      </div>

      {/* ── Task Queue (compact) ── */}
      {agentTaskQueue.length > 0 && (
        <div className="space-y-0.5">
          {agentTaskQueue.slice(0, 3).map((task) => (
            <div key={task.id} className="flex items-center gap-1.5 text-[10px]">
              <span className={
                task.status === 'running' ? 'text-teal-400 animate-pulse' :
                task.status === 'completed' ? 'text-green-400' :
                task.status === 'failed' ? 'text-red-400' : 'text-zinc-500'
              }>
                {task.status === 'running' ? '◉' : task.status === 'completed' ? '✓' : task.status === 'failed' ? '✗' : '○'}
              </span>
              <span className="text-zinc-400 truncate">{task.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


