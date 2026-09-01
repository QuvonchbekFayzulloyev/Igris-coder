import React, { useState } from 'react';
import { useAgentConsoleStore } from '../../shared/store';

export function StatusBar() {
  const backendOnline = useAgentConsoleStore((s) => s.backendOnline);
  const backendUrl = useAgentConsoleStore((s) => s.backendUrl);
  const memoryEnabled = useAgentConsoleStore((s) => s.agentInfo?.memoryEnabled ?? false);
  const intelligenceEnabled = useAgentConsoleStore((s) => s.agentInfo?.intelligenceEnabled ?? false);
  const model = useAgentConsoleStore((s) => s.agentInfo?.model || '');
  const llmDegraded = useAgentConsoleStore((s) => s.agentInfo?.llmDegraded ?? false);
  const llmFailureCount = useAgentConsoleStore((s) => s.agentInfo?.llmFailureCount ?? 0);
  const circuitState = useAgentConsoleStore((s) => s.agentInfo?.circuit?.state);
  const retryLLM = useAgentConsoleStore((s) => s.retryLLM);
  const [retrying, setRetrying] = useState(false);

  const isDegraded = llmDegraded || circuitState === 'open';

  return (
    <div className="shrink-0 z-20">
      {/* Degradation banner — LLM xatolari tufayli cheklangan holat */}
      {isDegraded && backendOnline && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-amber-950/60 border-t border-amber-800/50">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-[11px] font-ui text-amber-200">
              {circuitState === 'open' ? (
                <>⚡ Agent qayta tiklanmoqda — LLM xatolari ({llmFailureCount}×) tufayli to'xtatilgan</>
              ) : circuitState === 'half_open' ? (
                <>🔄 Agent qayta tekshirilmoqda — birinchi muvaffaqiyat kutilmoqda</>
              ) : (
                <>⚠️ LLM degraded — bricks + RAG ishlayapti (xato: {llmFailureCount}×)</>
              )}
            </span>
          </div>
          <button
            onClick={async () => {
              setRetrying(true);
              await retryLLM();
              setRetrying(false);
            }}
            disabled={retrying}
            className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-900/50 text-amber-200 hover:bg-amber-800/50 hover:text-amber-100 disabled:opacity-50 transition-colors"
          >
            {retrying ? 'sinamoqda...' : '↻ retry LLM'}
          </button>
        </div>
      )}
      {/* Asosiy status bar */}
      <div className="h-6 flex items-center justify-between px-3 border-t border-zinc-800 bg-zinc-900 text-xs font-ui text-zinc-500">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-teal-400' : 'bg-zinc-600'}`} />
            {backendOnline ? 'Igris brain · connected' : 'Igris brain · offline'}
          </span>
          <span className="font-mono text-zinc-400">{backendUrl}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            {memoryEnabled ? '🧠 RAG memory on' : '🧠 RAG memory off'}
          </span>
          <span
            className="flex items-center gap-1"
            title="12 intellekt arxitekturasi: harm-filter, user-model, tone, language, logic, spatial, creative, self-eval, naturalist, music"
          >
            {intelligenceEnabled ? '✨ 12 intellekt on' : '✨ intellekt off'}
          </span>
          {model && <span className="font-mono text-zinc-400 truncate max-w-40">{model}</span>}
        </div>
      </div>
    </div>
  );
}
