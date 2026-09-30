import React, { useState, useEffect, useMemo } from 'react';
import { useAgentConsoleStore } from '../../shared/store';

interface ThinkingStep {
  id: string;
  type: 'analyze' | 'plan' | 'execute' | 'verify' | 'synthesize';
  title: string;
  detail?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  duration_ms?: number;
  tool?: string;
  result?: string;
}

interface ThinkingTrace {
  steps: ThinkingStep[];
  total_duration_ms: number;
  quality_score: number;
  optimization_level: 'none' | 'basic' | 'advanced';
}

const STEP_CONFIG = {
  analyze: { icon: '🔍', label: 'Tahlil', color: 'text-blue-400', bgColor: 'bg-blue-900/20' },
  plan: { icon: '📋', label: 'Reja', color: 'text-amber-400', bgColor: 'bg-amber-900/20' },
  execute: { icon: '⚡', label: 'Bajarish', color: 'text-teal-400', bgColor: 'bg-teal-900/20' },
  verify: { icon: '✓', label: 'Tekshirish', color: 'text-green-400', bgColor: 'bg-green-900/20' },
  synthesize: { icon: '🎯', label: 'Yakunlash', color: 'text-purple-400', bgColor: 'bg-purple-900/20' },
};

const STATUS_CONFIG = {
  pending: { icon: '○', color: 'text-zinc-600' },
  running: { icon: '◉', color: 'text-amber-400 animate-pulse' },
  completed: { icon: '✓', color: 'text-green-400' },
  failed: { icon: '✗', color: 'text-red-400' },
  skipped: { icon: '⊘', color: 'text-zinc-500' },
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function QualityMeter({ score }: { score: number }) {
  const getColor = (s: number) => {
    if (s >= 80) return 'text-green-400';
    if (s >= 60) return 'text-amber-400';
    return 'text-red-400';
  };

  const getLabel = (s: number) => {
    if (s >= 80) return 'Yuqori sifat';
    if (s >= 60) return "O'rta sifat";
    return 'Past sifat';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            score >= 80 ? 'bg-green-500' :
            score >= 60 ? 'bg-amber-500' : 'bg-red-500'
          }`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`text-[10px] font-mono ${getColor(score)}`}>
        {score}%
      </span>
      <span className="text-[9px] text-zinc-500">
        {getLabel(score)}
      </span>
    </div>
  );
}

export function ThinkingPanel() {
  const {
    messages,
    agentState,
    taskRunning,
    stageDetail,
  } = useAgentConsoleStore();

  // Extract thinking trace from messages
  const thinkingTrace = useMemo(() => {
    const steps: ThinkingStep[] = [];
    let totalDuration = 0;

    // Parse messages for thinking steps
    messages.forEach((msg, i) => {
      if (msg.kind === 'toolcall') {
        const step: ThinkingStep = {
          id: `step-${i}`,
          type: msg.name?.includes('read') || msg.name?.includes('list') ? 'analyze' :
                msg.name?.includes('write') || msg.name?.includes('create') ? 'execute' :
                msg.name?.includes('test') || msg.name?.includes('verify') ? 'verify' : 'execute',
          title: msg.name || 'Tool call',
          detail: msg.detail,
          status: msg.status || 'pending',
          tool: msg.name,
          duration_ms: msg.duration_ms,
        };
        steps.push(step);
        if (msg.duration_ms) totalDuration += msg.duration_ms;
      }
    });

    // Add context steps based on agent state
    if (agentState === 'thinking' || agentState === 'planning') {
      steps.unshift({
        id: 'analyze-1',
        type: 'analyze',
        title: 'So\'rov tahlil qilinmoqda',
        detail: stageDetail || 'Foydalanuvchi so\'rovini tahlil qilish',
        status: 'running',
      });
    }

    // Calculate quality score based on various factors
    const qualityScore = Math.min(100, Math.max(0,
      50 + // base score
      (steps.filter(s => s.status === 'completed').length * 5) + // completion bonus
      (steps.filter(s => s.type === 'verify').length * 10) + // verification bonus
      (steps.length > 0 ? 15 : 0) // has steps bonus
    ));

    return {
      steps,
      total_duration_ms: totalDuration,
      quality_score: qualityScore,
      optimization_level: steps.length > 5 ? 'advanced' : steps.length > 2 ? 'basic' : 'none',
    };
  }, [messages, agentState, stageDetail]);

  if (thinkingTrace.steps.length === 0 && !taskRunning) {
    return (
      <div className="p-4 text-center">
        <div className="text-2xl mb-2">🧠</div>
        <p className="text-sm text-zinc-400">Fikrlash izi yo'q</p>
        <p className="text-[11px] text-zinc-600 mt-1">
          Agent ishlayotganda fikrlash jarayoni ko'rinadi
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 overflow-y-auto h-full">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Fikrlash izi</h3>
        <div className="flex items-center gap-2">
          {thinkingTrace.optimization_level !== 'none' && (
            <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
              thinkingTrace.optimization_level === 'advanced'
                ? 'bg-teal-900/30 text-teal-400'
                : 'bg-amber-900/30 text-amber-400'
            }`}>
              {thinkingTrace.optimization_level === 'advanced' ? '⚡ Tezlashtirilgan' : '🔄 Optomal'}
            </span>
          )}
          {thinkingTrace.total_duration_ms > 0 && (
            <span className="text-[10px] text-zinc-500 font-mono">
              {formatDuration(thinkingTrace.total_duration_ms)}
            </span>
          )}
        </div>
      </div>

      {/* ── Quality Score ── */}
      <div className="bg-zinc-900/50 rounded-lg p-3 border border-zinc-800/30">
        <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Sifat bahosi</div>
        <QualityMeter score={thinkingTrace.quality_score} />
      </div>

      {/* ── Thinking Steps ── */}
      <div className="space-y-1">
        {thinkingTrace.steps.map((step) => {
          const stepCfg = STEP_CONFIG[step.type];
          const statusCfg = STATUS_CONFIG[step.status];

          return (
            <div
              key={step.id}
              className={`${stepCfg.bgColor} rounded-lg p-2.5 border border-zinc-800/30`}
            >
              <div className="flex items-center gap-2">
                <span className={`${statusCfg.color} text-sm`}>{statusCfg.icon}</span>
                <span className="text-sm">{stepCfg.icon}</span>
                <span className={`text-xs font-medium ${stepCfg.color}`}>{step.title}</span>
                {step.tool && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                    {step.tool}
                  </span>
                )}
                {step.duration_ms && (
                  <span className="text-[10px] text-zinc-500 font-mono ml-auto">
                    {formatDuration(step.duration_ms)}
                  </span>
                )}
              </div>
              {step.detail && (
                <div className="text-[10px] text-zinc-400 mt-1 ml-6 truncate">
                  {step.detail}
                </div>
              )}
              {step.result && (
                <div className="text-[10px] text-zinc-300 mt-1 ml-6 font-mono bg-zinc-950 rounded p-1.5 max-h-16 overflow-y-auto">
                  {step.result}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Live Agent State ── */}
      {taskRunning && (
        <div className="bg-amber-900/10 rounded-lg p-3 border border-amber-800/20">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-xs text-amber-300 font-medium">Jonli fikrlash</span>
          </div>
          {stageDetail && (
            <div className="text-[10px] text-amber-200/70 ml-4">
              {stageDetail}
            </div>
          )}
          {/* Thinking animation */}
          <div className="flex items-center gap-1 ml-4 mt-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-amber-500"
                style={{
                  animation: `pulse 1.5s ease-in-out ${i * 0.3}s infinite`,
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Statistics ── */}
      {thinkingTrace.steps.length > 0 && (
        <div className="bg-zinc-900/50 rounded-lg p-3 border border-zinc-800/30">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Statistika</div>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="flex justify-between">
              <span className="text-zinc-400">Qadamlar:</span>
              <span className="text-zinc-300 font-mono">{thinkingTrace.steps.length}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Tool'lar:</span>
              <span className="text-zinc-300 font-mono">
                {new Set(thinkingTrace.steps.map(s => s.tool).filter(Boolean)).size}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Muvaffaqiyat:</span>
              <span className="text-green-400 font-mono">
                {thinkingTrace.steps.filter(s => s.status === 'completed').length}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Xatolar:</span>
              <span className={`font-mono ${thinkingTrace.steps.filter(s => s.status === 'failed').length > 0 ? 'text-red-400' : 'text-zinc-300'}`}>
                {thinkingTrace.steps.filter(s => s.status === 'failed').length}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ThinkingPanel;
