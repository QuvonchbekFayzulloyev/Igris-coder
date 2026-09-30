import React, { useState, useCallback } from 'react';
import { useAgentConsoleStore } from '../../shared/store';

type Priority = 'low' | 'normal' | 'high';

interface QuickTask {
  label: string;
  icon: string;
  description: string;
  priority: Priority;
  task: string;
}

const QUICK_TASKS: QuickTask[] = [
  {
    label: 'Kod tekshirish',
    icon: '🔍',
    description: 'Loyihadagi xatoliklarni topish va tuzatish',
    priority: 'normal',
    task: 'Loyihadagi barcha fayllarni tekshirib, xatoliklarni top va tuzat',
  },
  {
    label: 'Test yozish',
    icon: '🧪',
    description: 'Avtomatik test yozish',
    priority: 'normal',
    task: 'Loyiha uchun avtomatik testlar yoz',
  },
  {
    label: 'Dokumentatsiya',
    icon: '📝',
    description: 'README va kod komentariyalari',
    priority: 'low',
    task: 'Loyiha uchun README va kod komentariyalarini yoz',
  },
  {
    label: 'Refactor',
    icon: '♻️',
    description: 'Kod sifatini yaxshilash',
    priority: 'normal',
    task: 'Kodni refactor qil, takrorlanishlarni kamaytir',
  },
  {
    label: 'Xavfsizlik',
    icon: '🔒',
    description: 'Xavfsizlik tekshiruvi',
    priority: 'high',
    task: 'Loyihadagi xavfsizlik zaifliklarini tekshir va tuzat',
  },
  {
    label: 'Optimallashtirish',
    icon: '⚡',
    description: 'Tezlik va samaradorlik',
    priority: 'normal',
    task: 'Kod tezligini va samaradorligini oshir',
  },
];

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' });
}

function TaskCard({ task, onRemove, onPause, onResume }: {
  task: any;
  onRemove: () => void;
  onPause: () => void;
  onResume: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const statusColor = {
    queued: 'text-zinc-500',
    running: 'text-teal-400',
    completed: 'text-green-400',
    failed: 'text-red-400',
    paused: 'text-orange-400',
  }[task.status];

  const statusIcon = {
    queued: '○',
    running: '◉',
    completed: '✓',
    failed: '✗',
    paused: '⏸',
  }[task.status];

  const priorityLabel = {
    high: '🔴 Yuqori',
    normal: '🟡 O\'rta',
    low: '🔵 Past',
  }[task.priority];

  return (
    <div className="bg-zinc-900/50 rounded-xl border border-zinc-800/30 overflow-hidden">
      <div
        className="p-3 cursor-pointer hover:bg-zinc-800/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className={`${statusColor} text-sm ${task.status === 'running' ? 'animate-pulse' : ''}`}>
            {statusIcon}
          </span>
          <span className="text-sm text-zinc-200 flex-1">{task.title}</span>
          <span className="text-[10px] text-zinc-500">{priorityLabel}</span>
        </div>

        {/* Progress bar */}
        {task.steps.length > 0 && (
          <div className="mt-2 flex gap-0.5">
            {task.steps.map((step: any, i: number) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full transition-all ${
                  step.status === 'completed' ? 'bg-teal-500' :
                  step.status === 'running' ? 'bg-amber-500 animate-pulse' :
                  step.status === 'failed' ? 'bg-red-500' :
                  'bg-zinc-700'
                }`}
              />
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-zinc-500">
          <span>{formatTime(task.created_at)}</span>
          {task.duration_ms && <span>· {(task.duration_ms / 1000).toFixed(1)}s</span>}
          {task.tools_used.length > 0 && <span>· {task.tools_used.length} tools</span>}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-zinc-800/30 p-3 space-y-2">
          <p className="text-xs text-zinc-400">{task.description}</p>

          {/* Steps */}
          {task.steps.length > 0 && (
            <div className="space-y-1">
              {task.steps.map((step: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={
                    step.status === 'completed' ? 'text-green-400' :
                    step.status === 'running' ? 'text-amber-400' :
                    step.status === 'failed' ? 'text-red-400' :
                    'text-zinc-600'
                  }>
                    {step.status === 'completed' ? '✓' :
                     step.status === 'running' ? '◉' :
                     step.status === 'failed' ? '✗' : '○'}
                  </span>
                  <span className="text-zinc-400">{step.title}</span>
                  {step.tool && <span className="text-zinc-600 font-mono text-[10px]">{step.tool}</span>}
                </div>
              ))}
            </div>
          )}

          {/* Result */}
          {task.result && (
            <div className="bg-zinc-950 rounded-lg p-2 text-xs text-zinc-300 font-mono max-h-32 overflow-y-auto">
              {task.result}
            </div>
          )}

          {task.error && (
            <div className="bg-red-950/30 rounded-lg p-2 text-xs text-red-400 font-mono">
              {task.error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            {task.status === 'running' && (
              <button onClick={onPause} className="text-[10px] px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-orange-400">
                ⏸ To'xtatish
              </button>
            )}
            {task.status === 'paused' && (
              <button onClick={onResume} className="text-[10px] px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-teal-400">
                ▶ Davom ettirish
              </button>
            )}
            <button onClick={onRemove} className="text-[10px] px-2 py-1 rounded bg-zinc-800 text-zinc-400 hover:text-red-400">
              🗑 O'chirish
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function TaskManager() {
  const {
    agentTaskQueue,
    agentAutoMode,
    addTaskToQueue,
    removeTaskFromQueue,
    pauseTask,
    resumeTask,
    setAgentState,
    backendOnline,
  } = useAgentConsoleStore();

  const [customTask, setCustomTask] = useState('');
  const [customPriority, setCustomPriority] = useState<Priority>('normal');

  const handleQuickTask = useCallback((qt: QuickTask) => {
    addTaskToQueue({
      title: qt.label,
      description: qt.description,
      status: 'queued',
      priority: qt.priority,
      tools_used: [],
    });
  }, [addTaskToQueue]);

  const handleCustomTask = useCallback(() => {
    if (!customTask.trim()) return;
    addTaskToQueue({
      title: customTask.trim().slice(0, 60),
      description: customTask.trim(),
      status: 'queued',
      priority: customPriority,
      tools_used: [],
    });
    setCustomTask('');
  }, [customTask, customPriority, addTaskToQueue]);

  const activeCount = agentTaskQueue.filter((t) => t.status === 'running').length;
  const queuedCount = agentTaskQueue.filter((t) => t.status === 'queued').length;

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="max-w-2xl mx-auto p-4 space-y-6">
        {/* ── Header ── */}
        <div className="flex items-center gap-3">
          <div className="text-2xl">🤖</div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Agent boshqaruv paneli</h2>
            <p className="text-xs text-zinc-500">
              {activeCount > 0 ? `${activeCount} faol` : 'Tayyor'}
              {queuedCount > 0 ? ` · ${queuedCount} navbatda` : ''}
            </p>
          </div>
          <div className="ml-auto">
            <div className={`text-[10px] px-2 py-1 rounded-full ${
              backendOnline ? 'bg-teal-900/30 text-teal-400' : 'bg-red-900/30 text-red-400'
            }`}>
              {backendOnline ? '● Online' : '● Offline'}
            </div>
          </div>
        </div>

        {/* ── Quick Tasks ── */}
        <div>
          <h3 className="text-[11px] uppercase tracking-wider text-zinc-500 mb-3 px-1">Tezkor topshiriqlar</h3>
          <div className="grid grid-cols-2 gap-2">
            {QUICK_TASKS.map((qt) => (
              <button
                key={qt.label}
                onClick={() => handleQuickTask(qt)}
                disabled={!backendOnline}
                className="bg-zinc-900/50 hover:bg-zinc-800/50 border border-zinc-800/30 rounded-xl p-3 text-left transition-colors disabled:opacity-40"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{qt.icon}</span>
                  <span className="text-sm text-zinc-200">{qt.label}</span>
                </div>
                <p className="text-[11px] text-zinc-500 line-clamp-2">{qt.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* ── Custom Task ── */}
        <div className="bg-zinc-900/50 rounded-xl border border-zinc-800/30 p-4">
          <h3 className="text-[11px] uppercase tracking-wider text-zinc-500 mb-3">Maxsus topshiriq</h3>
          <textarea
            value={customTask}
            onChange={(e) => setCustomTask(e.target.value)}
            placeholder="Nima qilish kerakligini yozing..."
            rows={3}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-sm text-zinc-200 placeholder:text-zinc-600 resize-none focus:outline-none focus:border-zinc-600"
          />
          <div className="flex items-center gap-2 mt-2">
            <select
              value={customPriority}
              onChange={(e) => setCustomPriority(e.target.value as Priority)}
              className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1 text-xs text-zinc-400 focus:outline-none"
            >
              <option value="low">🔵 Past</option>
              <option value="normal">🟡 O'rta</option>
              <option value="high">🔴 Yuqori</option>
            </select>
            <button
              onClick={handleCustomTask}
              disabled={!customTask.trim() || !backendOnline}
              className="ml-auto px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500 text-zinc-950 hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              + Qo'shish
            </button>
          </div>
        </div>

        {/* ── Task Queue ── */}
        {agentTaskQueue.length > 0 && (
          <div>
            <h3 className="text-[11px] uppercase tracking-wider text-zinc-500 mb-3 px-1">
              Navbat ({agentTaskQueue.length})
            </h3>
            <div className="space-y-2">
              {agentTaskQueue.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onRemove={() => removeTaskFromQueue(task.id)}
                  onPause={() => pauseTask(task.id)}
                  onResume={() => resumeTask(task.id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Empty State ── */}
        {agentTaskQueue.length === 0 && (
          <div className="text-center py-12">
            <div className="text-4xl mb-3">🎯</div>
            <p className="text-sm text-zinc-400">Navbat bo'sh</p>
            <p className="text-xs text-zinc-600 mt-1">Tezkor topshiriq yoki maxsus vazifa qo'shing</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default TaskManager;
