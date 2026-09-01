import React from 'react';
import { ChatMessage as ChatMessageType } from '../../shared/constants';
import { ToolCallCard } from './ToolCallCard';
import { LiveBuildView } from './LiveBuildView';
import { useAgentConsoleStore } from '../../shared/store';

interface ChatMessageProps {
  msg: ChatMessageType;
}

export function ChatMessage({ msg }: ChatMessageProps) {
  const setSelectedFile = useAgentConsoleStore((s) => s.setSelectedFile);
  const setMainView = useAgentConsoleStore((s) => s.setMainView);
  const pushDrawing = useAgentConsoleStore((s) => s.pushDrawing);
  // Thinking bloki ochiq/yopiq holati — stream paytida ochiq boshlanadi, lekin
  // foydalanuvchi qo'lda yopsa hurmat qilinadi (har token'da qayta ochilmaydi).
  const [thinkingOpen, setThinkingOpen] = React.useState<boolean>(!!msg.streaming);

  if (msg.kind === 'toolcall') {
    return <ToolCallCard {...msg} />;
  }

  if (msg.kind === 'drawing') {
    if (!msg.path) {
      return (
        <div className="flex mb-3 justify-start">
          <div className="max-w-xl px-3 py-2 rounded-md text-sm font-ui bg-zinc-900 border border-zinc-800 text-zinc-500">
            🖼 drawing preview — {msg.caption || 'file not specified'}
          </div>
        </div>
      );
    }
    const path = msg.path;
    return (
      <div className="flex mb-3 justify-start">
        {/* Part M (A2): off-screen karta layout/paint o'tkazmaydi — 5-6 karta
            montajda qolsa ham ekran og'irlashmaydi/qoraymaydi. */}
        <div
          className="w-full max-w-xl overflow-hidden rounded-md border border-zinc-800 bg-zinc-950 shadow-lg shadow-black/30"
          style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 288px' }}
        >
          <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-zinc-800 bg-zinc-900/70">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-[10px] font-mono text-amber-300 tracking-widest">LIVE BUILD</span>
            <span className="ml-2 text-[10px] font-mono text-zinc-500 truncate">{msg.path}</span>
            <button
              onClick={() => { setSelectedFile(path); setMainView('preview'); }}
              title="Open in preview"
              className="ml-auto shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-400 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
            >
              ⌕ preview
            </button>
          </div>
          <div className="h-72 flex flex-col min-h-0">
            <LiveBuildView
              path={path}
              onEdited={(p) => pushDrawing(p, '✎ chat ichida tahrirlandi — yangi versiya')}
            />
          </div>
          {msg.caption && (
            <div className="px-3 py-1.5 text-[11px] font-ui text-zinc-500 border-t border-zinc-800 bg-zinc-900/40">
              {msg.caption}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (msg.kind === 'log') {
    // 2nd Brain yangilanish logi — badge'dan farqli doimiy chat qatori.
    // Sabab backend'dan kelgan haqiqiy izoh ("yangi xotira moduli: ...").
    // QATORNI BOSISH — 2nd Brain ko'rinishiga o'tadi (graf o'sha yerda).
    return (
      <div className="flex mb-3 justify-start">
        <button
          onClick={() => setMainView('brain')}
          title="2nd Brain ko'rinishiga o'tish"
          className="max-w-xl w-full flex items-start gap-1.5 px-2.5 py-1.5 rounded-md text-left text-[11px] font-mono leading-relaxed bg-sky-950/30 border border-sky-900/40 text-sky-300/80 cursor-pointer hover:bg-sky-900/50 hover:border-sky-700/60 hover:text-sky-200 transition-colors group"
        >
          <span className="shrink-0 text-sky-400">🧠</span>
          <span className="shrink-0 text-sky-500/80 tracking-widest text-[9px] pt-0.5">2ND BRAIN</span>
          <span className="shrink-0 text-sky-800">·</span>
          <span className="min-w-0 flex-1 break-words">{msg.text}</span>
          <span className="shrink-0 text-[9px] font-mono text-sky-600 group-hover:text-sky-300 mt-0.5">
            → 2nd Brain
          </span>
        </button>
      </div>
    );
  }

  if (msg.kind === 'human') {
    return (
      <div className="flex mb-3 justify-start">
        <div className="max-w-xl w-full px-3 py-2.5 rounded-md text-sm font-ui bg-amber-950/40 border border-amber-700/40 text-amber-200">
          <div className="flex items-center gap-1.5 mb-1 text-amber-300 text-xs font-medium">
            <span>👤</span> human-in-the-loop · agent asks
          </div>
          {msg.text}
        </div>
      </div>
    );
  }

  if (msg.kind === 'clarify') {
    return (
      <div className="flex mb-3 justify-start">
        <div className="max-w-xl w-full px-3 py-2.5 rounded-md text-sm font-ui bg-teal-950/40 border border-teal-700/40 text-teal-200">
          <div className="flex items-center gap-1.5 mb-1 text-teal-300 text-xs font-medium">
            <span>❓</span> clarification · agent needs more info
          </div>
          {msg.text}
        </div>
      </div>
    );
  }

  const isUser = msg.role === 'user';

  return (
    <div className={`flex mb-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-xl px-3 py-2 rounded-md text-sm font-ui leading-relaxed ${
          isUser
            ? 'bg-zinc-800 text-zinc-100'
            : 'bg-zinc-900 border border-zinc-800 text-zinc-300'
        }`}
      >
        {!isUser && (
          <div className="flex items-center gap-1.5 mb-1 text-amber-300 text-xs font-medium">
            <span>✦</span> agent
            {msg.streaming && (
              <span className="inline-flex items-center gap-1 text-[10px] font-mono text-amber-400 animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                {msg.thinking && !msg.text ? 'fikrlashmoqda' : 'yozilmoqda'}
              </span>
            )}
            {(msg.engine || msg.duration_ms) && (
              <span className="ml-auto text-[10px] text-zinc-500 font-mono normal-case pl-3">
                {msg.engine ?? ''}
                {msg.duration_ms != null ? ` · ${(msg.duration_ms / 1000).toFixed(1)}s` : ''}
              </span>
            )}
          </div>
        )}
        {!isUser && msg.thinking && (
          <details
            className="group mb-2"
            open={thinkingOpen}
            onToggle={(e) => setThinkingOpen((e.target as HTMLDetailsElement).open)}
          >
            <summary className="cursor-pointer select-none flex items-center gap-1.5 text-[10px] font-mono text-amber-400/70 hover:text-amber-300 transition-colors">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400/70 animate-pulse" />
              thinking
              <span className="text-zinc-600">· {msg.thinking.length} belgi</span>
              <span className="ml-auto text-zinc-600 group-open:hidden">▸ ochish</span>
              <span className="ml-auto text-zinc-600 hidden group-open:inline">▾ yopish</span>
            </summary>
            <div className="mt-1.5 max-h-60 overflow-y-auto rounded-md border border-amber-900/40 bg-amber-950/25 px-3 py-2 text-[12px] leading-relaxed text-amber-200/70 font-mono whitespace-pre-wrap">
              {msg.thinking}
            </div>
          </details>
        )}
        {!isUser && msg.warning && (
          <div className="mb-2 rounded-md border border-red-800/60 bg-red-950/30 px-3 py-2 text-[12px] leading-relaxed text-red-200/90">
            {msg.warning}
          </div>
        )}
        {!isUser && msg.completion && (
          <details
            className="group mb-2 rounded-md border border-emerald-900/40 bg-emerald-950/20 px-2.5 py-1.5"
            open={!msg.text}
          >
            <summary className="cursor-pointer select-none flex items-center gap-1.5 text-[10px] font-mono text-emerald-400/80 hover:text-emerald-300 transition-colors">
              <span>▣</span>
              agentic pipeline
              <span className="ml-1 text-emerald-300/90">· {msg.completion.label || msg.completion.pipeline || 'ish'}</span>
              {msg.completion.engine && (
                <span className="text-zinc-500">· {msg.completion.engine}</span>
              )}
              {msg.completion.status && msg.completion.status !== 'ok' && (
                <span className="text-amber-400">· {msg.completion.status}</span>
              )}
              <span className="ml-auto text-zinc-600 group-open:hidden">▸ ochish</span>
              <span className="ml-auto text-zinc-600 hidden group-open:inline">▾ yopish</span>
            </summary>
            <div className="mt-1.5 space-y-1">
              {(msg.completion.stages || []).length > 0 && (
                <div className="flex items-center gap-1 flex-wrap">
                  {(msg.completion.stages || []).map((s, i) => (
                    <span key={i} className="px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-900/40 text-[10px] font-mono text-emerald-300/80">
                      {s}
                    </span>
                  ))}
                </div>
              )}
              {msg.completion.subject && (
                <div className="text-[11px] text-emerald-200/60">
                  obyekt: <span className="text-emerald-300/90">{msg.completion.subject}</span>
                </div>
              )}
              {(msg.completion.framework || msg.completion.language || msg.completion.database) && (
                <div className="flex items-center gap-1 flex-wrap">
                  {msg.completion.framework && (
                    <span className="px-1.5 py-0.5 rounded bg-sky-950/60 border border-sky-900/40 text-[10px] font-mono text-sky-300/80">
                      {msg.completion.framework}
                    </span>
                  )}
                  {msg.completion.language && (
                    <span className="px-1.5 py-0.5 rounded bg-violet-950/60 border border-violet-900/40 text-[10px] font-mono text-violet-300/80">
                      {msg.completion.language}
                    </span>
                  )}
                  {msg.completion.database && (
                    <span className="px-1.5 py-0.5 rounded bg-teal-950/60 border border-teal-900/40 text-[10px] font-mono text-teal-300/80">
                      🗄 {msg.completion.database}
                    </span>
                  )}
                </div>
              )}
              {(msg.completion.tools || []).length > 0 && (
                <div className="text-[11px] text-emerald-200/60">
                  bajarildi: {msg.completion.tools!.join(', ')}
                </div>
              )}
              {(msg.completion.planned_tools || []).length > 0 && (
                <div className="text-[11px] text-emerald-200/50">
                  reja: {msg.completion.planned_tools!.join(', ')}
                </div>
              )}
              {msg.completion.image && (
                <div className="text-[11px] text-emerald-200/60">
                  🖼 {msg.completion.image}
                </div>
              )}
              {(msg.completion.sub_pipelines || []).length > 0 && (
                <div className="text-[11px] text-emerald-200/50">
                  qo'shimcha: {msg.completion.sub_pipelines!.join(', ')}
                </div>
              )}
            </div>
          </details>
        )}
        {msg.text}
        {msg.streaming && (
          <span className="inline-block w-[2px] h-[1.05em] ml-0.5 align-middle bg-amber-400/90 animate-pulse" />
        )}
      </div>
    </div>
  );
}
