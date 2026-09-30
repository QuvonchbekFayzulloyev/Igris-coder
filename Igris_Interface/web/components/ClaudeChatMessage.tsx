import React from 'react';
import { ChatMessage as ChatMessageType } from '../../shared/constants';
import { ToolCallCard } from './ToolCallCard';
import { LiveBuildView } from './LiveBuildView';
import { useAgentConsoleStore } from '../../shared/store';

/**
 * ClaudeChatMessage — Claude-uslubidagi chat xabari.
 *
 * Claude dizayn tamoyillari (eski bubble dizayndan farqlari):
 *   - Xabarlar FULL-WIDTH — chat-bubble o'rniga hujjat uslubidagi oqim
 *   - User xabari: oq fonli yumshoq kartada, chap tomonda "You" yorlig'i
 *   - Agent xabari: fonsiz matn, Igris "sun" logotipi chap tomonda
 *   - Thinking: "Thinking" gipertext yorlig'i, bosilganda ochiladi
 *   - Metama'lumot (engine/davomiylik) xabar ostida nozik ko'rsatiladi
 */

/** Ko'p qatorli matnni paragraflar + inline bold/code bilan chizish. */
function RichText({ text }: { text: string }) {
  const blocks = String(text || '').split(/\n{2,}/);
  return (
    <div className="claude-prose">
      {blocks.map((block, bi) => {
        // ro'yxat bloki (—, -, *, 1. bilan boshlanadigan qatorlar)
        const lines = block.split('\n');
        const isList = lines.length > 1
          && lines.every((l) => /^\s*([\-—*•]|\d+[.)])\s+/.test(l));
        if (isList) {
          const ordered = /^\s*\d+[.)]/.test(lines[0]);
          const items = lines.map((l, i) => (
            <li key={i}>{inline(String(l).replace(/^\s*([\-—*•]|\d+[.)])\s+/, ''))}</li>
          ));
          return ordered ? <ol key={bi}>{items}</ol> : <ul key={bi}>{items}</ul>;
        }
        // sarlavha (### / ##)
        const h = /^(#{1,4})\s+(.*)$/.exec(block);
        if (h && lines.length === 1) {
          const lvl = h[1].length;
          if (lvl <= 2) return <h3 key={bi}>{inline(h[2])}</h3>;
          return <h4 key={bi}>{inline(h[2])}</h4>;
        }
        // kod bloki ```
        if (block.trimStart().startsWith('```')) {
          const code = block.replace(/^\s*```[a-z]*\n?/i, '').replace(/```\s*$/, '');
          return (
            <pre key={bi} className="claude-codeblock"><code>{code}</code></pre>
          );
        }
        return <p key={bi}>{inline(block)}</p>;
      })}
    </div>
  );
}

/** Inline formatlash: **bold**, *italic*, `code`. */
function inline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Ketma-ket tokenlash: `code` | **bold** | *italic*
  const re = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('`')) {
      parts.push(<code key={k++} className="claude-inline-code">{tok.slice(1, -1)}</code>);
    } else if (tok.startsWith('**')) {
      parts.push(<strong key={k++}>{tok.slice(2, -2)}</strong>);
    } else {
      parts.push(<em key={k++}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

/** Igris "sun" avatar belgisi (agent xabarlari chap tomonida). */
export function IgrisSun({ size = 22 }: { size?: number }) {
  return (
    <div
      className="shrink-0 rounded-md bg-gradient-to-br from-amber-300 to-orange-500 flex items-center justify-center text-zinc-950 font-bold select-none"
      style={{ width: size, height: size, fontSize: size * 0.55 }}
      aria-hidden
    >
      ✦
    </div>
  );
}

interface ChatMessageProps {
  msg: ChatMessageType;
}

export function ClaudeChatMessage({ msg }: ChatMessageProps) {
  const setSelectedFile = useAgentConsoleStore((s) => s.setSelectedFile);
  const setMainView = useAgentConsoleStore((s) => s.setMainView);
  const pushDrawing = useAgentConsoleStore((s) => s.pushDrawing);
  const [thinkingOpen, setThinkingOpen] = React.useState<boolean>(false);

  // Tool-call kartasi — expandable with result
  if (msg.kind === 'toolcall') {
    return (
      <div className="px-4 py-1.5 claude-row">
        <div className="flex items-start gap-3">
          <div className="w-[22px] shrink-0" />
          <div className="flex-1 min-w-0">
            <ToolCallCard {...msg} />
          </div>
        </div>
      </div>
    );
  }

  // Agent state indicator (thinking/planning/executing)
  if (msg.kind === 'agent_state') {
    const stateConfig: Record<string, { icon: string; label: string; color: string }> = {
      thinking: { icon: '◈', label: 'Fikrlamoqda', color: 'text-amber-400' },
      planning: { icon: '◆', label: 'Rejalashtirmoqda', color: 'text-blue-400' },
      executing: { icon: '◉', label: 'Bajarilmoqda', color: 'text-teal-400' },
      verifying: { icon: '✓', label: 'Tekshirmoqda', color: 'text-green-400' },
      error: { icon: '✗', label: 'Xato', color: 'text-red-400' },
    };
    const cfg = stateConfig[msg.text || 'thinking'] || stateConfig.thinking;
    return (
      <div className="px-4 py-1 claude-row">
        <div className="flex items-center gap-2 text-xs">
          <span className={`${cfg.color} animate-pulse`}>{cfg.icon}</span>
          <span className={cfg.color}>{cfg.label}</span>
          {msg.detail && <span className="text-zinc-500 truncate">· {msg.detail}</span>}
        </div>
      </div>
    );
  }

  // Task result — expandable card in chat
  if (msg.kind === 'task_result') {
    return (
      <div className="px-4 py-2 claude-row">
        <div className="flex items-start gap-3">
          <div className="w-[22px] shrink-0" />
          <TaskResultCard msg={msg} />
        </div>
      </div>
    );
  }

  // Chizma kartasi (live build) — Claude "Artifacts" uslubida
  if (msg.kind === 'drawing' && msg.path) {
    const path = msg.path;
    return (
      <div className="px-4 py-1.5 claude-row">
        <div className="flex items-start gap-3">
          <div className="w-[22px] shrink-0" />
          <div
            className="flex-1 max-w-2xl overflow-hidden rounded-xl border border-zinc-200/80 dark:border-zinc-700 bg-white shadow-sm"
            style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 288px' }}
          >
            <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-zinc-200/80 bg-zinc-50">
              <span className="text-[10px] font-mono text-amber-600 tracking-widest uppercase">Artifact</span>
              <span className="ml-2 text-[10px] font-mono text-zinc-400 truncate">{msg.path}</span>
              <button
                onClick={() => { setSelectedFile(path); setMainView('preview'); }}
                title="Open in preview"
                className="ml-auto shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-300 text-zinc-500 hover:text-amber-600 hover:border-amber-500/60 transition-colors"
              >
                preview
              </button>
            </div>
            <div className="h-72 flex flex-col min-h-0">
              <LiveBuildView
                path={path}
                onEdited={(p) => pushDrawing(p, '✎ chat ichida tahrirlandi — yangi versiya')}
              />
            </div>
            {msg.caption && (
              <div className="px-3 py-1.5 text-[11px] font-ui text-zinc-500 border-t border-zinc-200/80 bg-zinc-50/60">
                {msg.caption}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
  // Chizma (path yo'q) — ixcham placeholder
  if (msg.kind === 'drawing') {
    return (
      <div className="px-4 py-1.5 claude-row">
        <div className="flex items-start gap-3">
          <div className="w-[22px] shrink-0" />
          <div className="text-sm text-zinc-500 font-ui">🖼 {msg.caption || 'chizma'}</div>
        </div>
      </div>
    );
  }

  if (msg.kind === 'log') {
    return (
      <div className="px-4 py-1 claude-row">
        <div className="flex items-start gap-3">
          <div className="w-[22px] shrink-0" />
          <button
            onClick={() => setMainView('brain')}
            title="2nd Brain ko'rinishiga o'tish"
            className="max-w-2xl w-full flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg text-left text-[11px] font-mono leading-relaxed text-zinc-500 hover:text-zinc-300 hover:bg-zinc-100/60 dark:bg-transparent dark:hover:bg-zinc-800/40 transition-colors group"
          >
            <span className="shrink-0">🧠</span>
            <span className="min-w-0 flex-1 break-words">{msg.text}</span>
            <span className="shrink-0 text-[9px] font-mono text-zinc-400 group-hover:text-amber-600 mt-0.5">
              2nd Brain →
            </span>
          </button>
        </div>
      </div>
    );
  }

  if (msg.kind === 'human' || msg.kind === 'clarify') {
    const isHuman = msg.kind === 'human';
    return (
      <div className="px-4 py-1.5 claude-row">
        <div className="flex items-start gap-3">
          <div className="w-[22px] shrink-0" />
          <div className={`max-w-2xl w-full px-3.5 py-2.5 rounded-xl text-sm font-ui ${
            isHuman
              ? 'bg-amber-50 border border-amber-200 text-amber-900'
              : 'bg-teal-50 border border-teal-200 text-teal-900'
          }`}>
            <div className={`flex items-center gap-1.5 mb-1 text-xs font-medium ${isHuman ? 'text-amber-600' : 'text-teal-600'}`}>
              <span>{isHuman ? '👤' : '❓'}</span>
              {isHuman ? 'Igris sizdan so‘radi' : 'aniqlashtirish kerak'}
            </div>
            {msg.text}
          </div>
        </div>
      </div>
    );
  }

  const isUser = msg.role === 'user';

  // ---------------------------------------------------------------
  // USER xabari — Claude'dagi oq yumshoq kartalar (chap tekis, full-width)
  // ---------------------------------------------------------------
  if (isUser) {
    return (
      <div className="px-4 py-2 claude-row group">
        <div className="flex items-start gap-3">
          <div className="w-[22px] h-[22px] shrink-0 rounded-md bg-zinc-800 flex items-center justify-center text-[11px] text-zinc-300 select-none">S</div>
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100 mb-0.5 select-none">You</div>
            <div className="text-[15px] leading-relaxed font-ui text-zinc-800 dark:text-zinc-200 whitespace-pre-wrap break-words">
              {msg.text}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------
  // AGENT xabari — fonsiz hujjat uslubi, sun avatar chap tomonda
  // ---------------------------------------------------------------
  return (
    <div className="px-4 py-2 claude-row">
      <div className="flex items-start gap-3">
        <IgrisSun />
        <div className="min-w-0 flex-1 max-w-3xl">
          {/* THINKING — Claude'dagi gipertext "Thinking" yorlig'i */}
          {msg.thinking && (
            <div className="mb-1.5">
              <button
                onClick={() => setThinkingOpen((o) => !o)}
                className={`inline-flex items-center gap-1 text-[13px] font-ui transition-colors ${
                  thinkingOpen
                    ? 'text-zinc-500'
                    : 'text-zinc-400 hover:text-amber-600 underline decoration-zinc-300 underline-offset-4 hover:decoration-amber-400'
                }`}
              >
                {msg.streaming && !msg.text ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                    Thinking…
                  </span>
                ) : (
                  <>
                    {thinkingOpen ? 'Thinking’ni yashirish' : 'Thinking'}
                    <span className="text-[11px] text-zinc-400">{thinkingOpen ? '▾' : '▸'}</span>
                  </>
                )}
              </button>
              {thinkingOpen && (
                <div className="mt-1.5 max-h-64 overflow-y-auto rounded-lg border border-zinc-200/70 bg-zinc-50 px-3.5 py-2.5 text-[13px] leading-relaxed text-zinc-500 font-ui whitespace-pre-wrap dark:border-zinc-700/60 dark:bg-zinc-800/40 dark:text-zinc-400">
                  {msg.thinking}
                </div>
              )}
            </div>
          )}

          {msg.warning && (
            <div className="mb-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-[13px] leading-relaxed text-red-700">
              {msg.warning}
            </div>
          )}

          {/* ASOSIY MATN */}
          {msg.text ? (
            <RichText text={msg.text} />
          ) : (
            msg.streaming && !msg.thinking && (
              <div className="text-[15px] text-zinc-400 font-ui animate-pulse">yozilmoqda…</div>
            )
          )}

          {/* Pipeline umumiy xulosasi — nozik qator (ochiladigan emas, ixcham) */}
          {msg.completion && (msg.completion.tools?.length || msg.completion.image) ? (
            <div className="mt-2 flex items-center gap-2 flex-wrap text-[11px] font-mono text-zinc-400">
              {msg.completion.stages?.length ? (
                <span className="flex items-center gap-1">
                  {(msg.completion.stages).map((s, i) => (
                    <span key={i} className="px-1.5 py-0.5 rounded bg-zinc-100 border border-zinc-200 text-zinc-500 dark:bg-zinc-800/60 dark:border-zinc-700 dark:text-zinc-400">
                      {s}
                    </span>
                  ))}
                </span>
              ) : null}
              {msg.completion.image && (
                <span className="text-amber-600">🖼 {msg.completion.image}</span>
              )}
              {msg.completion.tools?.length ? (
                <span>{msg.completion.tools.join(', ')}</span>
              ) : null}
            </div>
          ) : null}

          {/* STREAMING kursori */}
          {msg.streaming && (
            <span className="inline-block w-[2px] h-[1.05em] ml-0.5 align-middle bg-amber-500 animate-pulse" />
          )}

          {/* METAMA'LUMOT — xabar ostida nozik (Claude'dagi model yorlig'i uslubida) */}
          {(msg.engine || msg.duration_ms != null) && !msg.streaming && (
            <div className="mt-1.5 flex items-center gap-2 text-[10px] font-mono text-zinc-400/70 select-none">
              {msg.model && <span>{msg.model}</span>}
              {msg.engine && <span>{msg.model ? '·' : ''} {msg.engine}</span>}
              {msg.duration_ms != null && (
                <span>{msg.duration_ms >= 1000 ? `${(msg.duration_ms / 1000).toFixed(1)}s` : `${Math.round(msg.duration_ms)}ms`}</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Task Result Card — expandable result in chat ──
function TaskResultCard({ msg }: { msg: ChatMessageType }) {
  const [expanded, setExpanded] = React.useState(false);
  const setSelectedFile = useAgentConsoleStore((s) => s.setSelectedFile);

  const status = msg.status || 'done';
  const statusConfig: Record<string, { icon: string; color: string; bg: string; border: string }> = {
    done: { icon: '✓', color: 'text-green-400', bg: 'bg-green-900/10', border: 'border-green-800/20' },
    error: { icon: '✗', color: 'text-red-400', bg: 'bg-red-900/10', border: 'border-red-800/20' },
    running: { icon: '◉', color: 'text-amber-400', bg: 'bg-amber-900/10', border: 'border-amber-800/20' },
  };
  const cfg = statusConfig[status] || statusConfig.done;

  return (
    <div className={`max-w-2xl w-full rounded-xl border ${cfg.border} ${cfg.bg} overflow-hidden`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 dark:hover:bg-zinc-800/30 transition-colors"
      >
        <span className={`${cfg.color} text-sm`}>{cfg.icon}</span>
        <span className="text-sm text-zinc-200 flex-1 truncate">{msg.text || 'Task natijasi'}</span>
        <span className="text-[10px] text-zinc-500">{expanded ? '▾' : '▸'}</span>
      </button>

      {expanded && (
        <div className="border-t border-zinc-800/30 p-3 space-y-2">
          {msg.name && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-zinc-500">Tool:</span>
              <span className="font-mono text-zinc-300">{msg.name}</span>
            </div>
          )}
          {msg.duration_ms && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-zinc-500">Davomiylik:</span>
              <span className="font-mono text-zinc-300">
                {msg.duration_ms >= 1000 ? `${(msg.duration_ms / 1000).toFixed(1)}s` : `${msg.duration_ms}ms`}
              </span>
            </div>
          )}
          {msg.completion && msg.completion.tools && msg.completion.tools.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {msg.completion.tools.map((t, i) => (
                <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">{t}</span>
              ))}
            </div>
          )}
          {msg.diff && msg.diff.length > 0 && (
            <div className="bg-zinc-950 rounded-lg p-2 text-[10px] font-mono text-zinc-400 max-h-32 overflow-y-auto">
              {msg.diff.map((line, i) => (
                <div key={i} className={line.startsWith('+') ? 'text-green-400' : line.startsWith('-') ? 'text-red-400' : ''}>
                  {line}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
