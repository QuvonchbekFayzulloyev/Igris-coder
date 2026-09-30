import React, { useEffect, useRef, useState } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { ClaudeChatMessage } from './ClaudeChatMessage';
import { PromptScroller } from './PromptScroller';

/**
 * ClaudeChat — Claude-uslubidagi asosiy chat view.
 *
 * Claude dizayn tamoyillari:
 *   1. EMPTY STATE — markazda salom xato + katta input o'rtada
 *   2. SUHBAT BOSHLANGACH — xabarlar full-width hujjat oqimi,
 *      composer PASTKA o'tadi (ixcham, lekin xuddi shu uslubda)
 *   3. COMPOSER — katta yumshoq burchakli maydon, pastda nozik
 *      hint qatori (Enter to send · Shift+Enter newline)
 *   4. Yangi suhbat tugmasi (✎ New chat) o'ng yuqorida
 */

const GREETING = "Salom! Men Igris — lokal agentic coding assistant. Nima qilamiz?";
const SUGGESTIONS = [
  { icon: '🎨', label: 'Chizma', text: 'tuya rasmini chiz' },
  { icon: '💻', label: 'Kod', text: 'Python bilan fayl nomlarini sanovchi skript yoz' },
  { icon: '🌐', label: 'Web', text: 'https://example.com sahifasini o‘qib xulosa ber' },
  { icon: '🔨', label: 'UI', text: 'todo ilovasi uchun interaktiv UI qur' },
  { icon: '🤖', label: 'Agent', text: '⚡ Loyihadagi xatoliklarni top va tuzat' },
  { icon: '📊', label: 'Tahlil', text: '⚡ Loyiha arxitekturasini tahlil qil va hisobot ber' },
];

export function ClaudeChat() {
  const {
    messages,
    input,
    setInput,
    handleSend,
    runTask,
    answerHuman,
    pendingHuman,
    pendingClarification,
    answerClarification,
    taskRunning,
    newChat,
    clearAllResults,
    stopStream,
    agentInfo,
    backendOnline,
    agentState,
    agentAutoMode,
    toggleAutoMode,
    agentCompletedToday,
    agentTaskQueue,
  } = useAgentConsoleStore();

  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  // Composer rejimi: suhbat boshlanmaganda markazda, boshlangach pastda
  const empty = messages.length === 0;
  const [autoFocused, setAutoFocused] = useState(false);

  // Auto-scroll — yangi xabar/token kelganda pastga
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Auto-resize textarea (max ~8 qator)
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const max = empty ? 160 : 200;
    ta.style.height = `${Math.min(ta.scrollHeight, max)}px`;
  }, [input, empty]);

  // Sahifa yukilganda bir marta focus
  useEffect(() => {
    if (!autoFocused) {
      taRef.current?.focus();
      setAutoFocused(true);
    }
  }, [autoFocused, empty]);

  const submit = () => {
    const text = input.trim();
    if (!text || taskRunning) return;
    if (text.startsWith('⚡')) runTask(text.slice(1).trim());
    else if (pendingClarification) answerClarification(input);
    else if (pendingHuman) answerHuman(input);
    else handleSend();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const composerPlaceholder = pendingClarification
    ? (pendingClarification.turn
        ? `Turn ${pendingClarification.turn}/${pendingClarification.maxTurns} — javob bering…`
        : 'Aniqlashtiruv savoliga javob bering…')
    : pendingHuman
      ? 'Agentning savoliga javob bering…'
      : 'Igris’dan so‘rang — kod, rasm, web, fayl…  (⚡ task rejimi)';

  const composerDisabledHint = pendingClarification
    ? 'Aniqlashtiruv — agent ko‘proq ma’lumot so‘radi'
    : pendingHuman
      ? 'Agent sizning javobingizni kutmoqda'
      : 'Enter — yuborish · Shift+Enter — yangi qator · ⚡ = task (skills + MCP + HITL)';

  // ---------------- COMPOSER (markazda yoki pastda, bir xil uslub) -------------
  const composer = (big: boolean) => (
    <div className={`w-full ${big ? 'max-w-2xl mx-auto' : 'max-w-3xl mx-auto'}`}>
      <div className="claude-composer">
        <textarea
          ref={taRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={composerPlaceholder}
          rows={1}
          className="claude-composer-input"
        />
        <div className="flex items-center gap-2 px-3 pb-2.5">
          <span className="text-[11px] font-ui text-zinc-400 dark:text-zinc-500 truncate">
            {composerDisabledHint}
          </span>
          {taskRunning ? (
            /* STOP — agent ishlayotganda stream'ni to'xtatish (Claude'dagi kabi).
               Qisman javob chatda qoladi — foydalanuvchi nazoratda. */
            <button
              onClick={stopStream}
              title="To'xtatish — agent javobini uzish"
              className="ml-auto w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-rose-600 text-white hover:bg-rose-500 transition-all"
            >
              <span className="text-[10px] leading-none">■</span>
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!input.trim()}
              title="Yuborish"
              className={`ml-auto w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all ${
                input.trim()
                  ? 'bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-amber-500 dark:hover:bg-amber-400 dark:text-zinc-950'
                  : 'bg-zinc-200 text-zinc-400 cursor-not-allowed dark:bg-zinc-800 dark:text-zinc-600'
              }`}
            >
              <span className="text-sm">↑</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex-1 min-h-0 flex flex-col bg-white dark:bg-zinc-900">
      {/* ---------- Yuqori qator: agent status + yangi suhbat ---------- */}
      <div className="flex items-center px-4 py-2 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-zinc-400 dark:text-zinc-500 select-none">
            igris · local agent
          </span>
          {/* Agent state indicator */}
          <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
            agentState === 'idle' ? 'bg-zinc-800 text-zinc-500' :
            agentState === 'thinking' ? 'bg-amber-900/30 text-amber-400 animate-pulse' :
            agentState === 'executing' ? 'bg-teal-900/30 text-teal-400 animate-pulse' :
            agentState === 'planning' ? 'bg-blue-900/30 text-blue-400 animate-pulse' :
            agentState === 'verifying' ? 'bg-green-900/30 text-green-400' :
            agentState === 'error' ? 'bg-red-900/30 text-red-400' :
            'bg-orange-900/30 text-orange-400'
          }`}>
            <span className="w-1 h-1 rounded-full bg-current" />
            {agentState === 'idle' ? 'tayyor' :
             agentState === 'thinking' ? 'fikrlamoqda' :
             agentState === 'planning' ? 'rejalashtirmoqda' :
             agentState === 'executing' ? 'bajarilmoqda' :
             agentState === 'verifying' ? 'tekshirmoqda' :
             agentState === 'error' ? 'xato' : 'to\'xtatilgan'}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {/* REAL agent status — backend/model jonli holati (soxta emas) */}
          <span
            className="inline-flex items-center gap-1.5 text-[11px] font-mono select-none"
            title={
              backendOnline
                ? `Backend online · model: ${agentInfo?.model || '?'}${agentInfo?.llmAvailable ? '' : ' · LLM mavjud emas'}${agentInfo?.circuit && agentInfo.circuit.state !== 'closed' ? ` · circuit: ${agentInfo.circuit.state}` : ''}`
                : 'Backend offline — javob olinmaydi'
            }
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                backendOnline
                  ? agentInfo?.llmAvailable === false
                    ? 'bg-amber-500'
                    : 'bg-teal-500'
                  : 'bg-rose-500'
              }`}
            />
            <span className="text-zinc-400 dark:text-zinc-500">
              {backendOnline ? agentInfo?.model || 'local' : 'offline'}
            </span>
          </span>
          <button
            onClick={clearAllResults}
            title="Natijalarni tozalash — chat tarixi, kesh va eski chizmalar o‘chadi"
            className="text-[11px] font-ui px-2 py-1 rounded-md text-zinc-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
          >
            Tozalash
          </button>
          <button
            onClick={newChat}
            title="Yangi suhbat boshlash"
            className="text-[11px] font-ui px-2.5 py-1 rounded-md border border-zinc-200 text-zinc-600 hover:border-zinc-400 hover:text-zinc-900 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-500 dark:hover:text-white transition-colors"
          >
            ✎ Yangi suhbat
          </button>
        </div>
      </div>

      {empty ? (
        /* ================= EMPTY STATE (Claude welcome) ================= */
        <div className="flex-1 min-h-0 flex flex-col items-center justify-center px-4 pb-10">
          <div className="w-full max-w-2xl mx-auto flex flex-col items-center">
            <div className="mb-6 flex items-center gap-3 select-none">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-300 to-orange-500 flex items-center justify-center text-zinc-950 text-xl font-bold shadow-sm">
                ✦
              </div>
              <h1 className="text-[26px] font-ui font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">
                {GREETING.split('!')[0]}!
              </h1>
            </div>
            <p className="mb-6 text-[15px] font-ui text-zinc-500 dark:text-zinc-400 text-center max-w-lg">
              {GREETING.split('!').slice(1).join('!').trim()}
            </p>
            {composer(true)}
            {/* Taklif chiplari */}
            <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => { setInput(s.text); setTimeout(submit, 50); }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-zinc-200 text-[12px] font-ui text-zinc-600 hover:border-amber-400 hover:text-amber-700 hover:bg-amber-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-amber-500/60 dark:hover:text-amber-300 dark:hover:bg-amber-950/30 transition-colors"
                >
                  <span>{s.icon}</span> {s.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* ================= SUHBAT OQIMI (full-width hujjat) ================= */
        <>
          <div ref={scrollRef} data-chat-scroll className="flex-1 min-h-0 overflow-y-auto py-4">
            <div className="max-w-3xl mx-auto">
              {messages.map((msg, i) => (
                <div key={i} data-chat-message={i}>
                  <ClaudeChatMessage msg={msg} />
                </div>
              ))}
              <div className="h-2" />
            </div>
          </div>
          <PromptScroller />
          {/* Composer pastda */}
          <div className="shrink-0 px-4 pb-3 pt-1">
            {composer(false)}
          </div>
        </>
      )}
    </div>
  );
}
