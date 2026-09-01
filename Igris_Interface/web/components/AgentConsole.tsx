import React, { useEffect, useRef } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { Sidebar } from './Sidebar';
import { PipelineStepper } from './PipelineStepper';
import { ChatMessage } from './ChatMessage';
import { PreviewView } from './PreviewView';
import { BrainView } from '../../../2nd_brain/frontend/BrainView';
import { RefactorView } from './RefactorView';
import { WebAIBridgeView } from './WebAIBridgeView';
import { CommandPalette } from './CommandPalette';
import { SettingsModal } from './SettingsModal';
import { PromptScroller } from './PromptScroller';

interface AgentConsoleProps {
  isDesktop?: boolean;
}

export function AgentConsole({ isDesktop = false }: AgentConsoleProps) {
  const {
    sidebarOpen,
    mainView,
    setMainView,
    paletteOpen,
    setPaletteOpen,
    settingsOpen,
    setSettingsOpen,
    setRootMenuOpen,
    messages,
    input,
    setInput,
    handleSend,
    runTask,
    answerHuman,
    pendingHuman,
    pendingClarification,
    answerClarification,
    stage,
    stageDetail,
    taskRunning,
    toast,
    setToast,
    loadWorkspace,
    loadChatHistory,
    loadAgentInfo,
    clearAllResults,
  } = useAgentConsoleStore();

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const { ping } = await import('../backend');
        const online = await ping();
        if (cancelled) return;
        setToast({ text: online ? 'Connected to Igris brain (FastAPI bridge)' : 'Brain offline — demo/mock mode' });
        if (online) {
          loadWorkspace();
          loadChatHistory();
          loadAgentInfo();
        }
      } catch {
        if (!cancelled) setToast({ text: 'Brain offline — demo/mock mode' });
      }
    }, 400);
    const t2 = setTimeout(() => setToast(null), 4200);
    return () => { cancelled = true; clearTimeout(t); clearTimeout(t2); };
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(true);
      }
      if (e.key === 'Escape') {
        setPaletteOpen(false);
        setSettingsOpen(false);
        setRootMenuOpen(false);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (mainView === 'chat' && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, mainView]);

  const views = [
    { id: 'chat', icon: '💬', label: 'Chat' },
    { id: 'preview', icon: '👁', label: 'Preview' },
    { id: 'brain', icon: '🧠', label: '2nd Brain' },
    { id: 'webai', icon: '🌐', label: 'Web AI' },
    { id: 'quality', icon: '📊', label: 'Quality' },
  ];

  return (
    <div className="flex-1 min-h-0 flex">
      {sidebarOpen && <Sidebar />}
      <div className="flex-1 min-w-0 flex flex-col z-10">
        <div className="flex items-center px-3 py-1.5 border-b border-zinc-800 shrink-0 z-20">
          <div className="inline-flex bg-zinc-900 border border-zinc-800 rounded-md p-0.5">
            {views.map(({ id, icon, label }) => (<button key={id} onClick={() => setMainView(id as any)} className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded font-ui ${mainView === id ? 'bg-zinc-800 text-amber-300' : 'text-zinc-500 hover:text-zinc-300'}`}><span>{icon}</span> {label}</button>))}
          </div>
          {mainView === 'chat' && (
            <button
              onClick={() => clearAllResults()}
              title="Oldingi natijalarni tozalash — chat tarixi, kesh va eski chizmalar o'chadi"
              className="ml-auto text-[11px] font-mono px-2 py-1 rounded border border-zinc-800 text-zinc-500 hover:text-rose-300 hover:border-rose-500/40 transition-colors"
            >
              🧹 tozalash
            </button>
          )}
        </div>
        {(mainView === 'chat' || mainView === 'preview') && (
          <PipelineStepper current={stage} detail={stageDetail} running={taskRunning} />
        )}
        {mainView === 'chat' && (<><div ref={scrollRef} data-chat-scroll className="flex-1 overflow-y-auto px-4 py-3">{messages.map((msg, i) => (<div key={i} data-chat-message={i}><ChatMessage msg={msg} /></div>))}</div><PromptScroller /><div className="border-t border-zinc-800 px-3 py-2.5 bg-zinc-900 bg-opacity-30 shrink-0">{(pendingClarification ? <div className="flex items-end gap-2 bg-teal-950/40 border border-teal-700/50 rounded-md px-3 py-2 focus-within:border-teal-500">            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); answerClarification(input); } }} placeholder={pendingClarification?.turn ? `Turn ${pendingClarification.turn}/${pendingClarification.maxTurns} — answer…` : 'Answer the clarification question…'} rows={1} className="flex-1 bg-transparent outline-none text-sm text-teal-100 font-ui placeholder-teal-700 resize-none" /><button onClick={() => answerClarification(input)} className="w-7 h-7 rounded-md bg-teal-400 hover:bg-teal-300 flex items-center justify-center shrink-0 transition-colors" title="Send clarification answer"><span className="text-zinc-950 text-sm">⏎</span></button></div> : pendingHuman ? <div className="flex items-end gap-2 bg-amber-950/40 border border-amber-700/50 rounded-md px-3 py-2 focus-within:border-amber-500">            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); answerHuman(input); } }} placeholder="Answer the agent's question…" rows={1} className="flex-1 bg-transparent outline-none text-sm text-amber-100 font-ui placeholder-amber-700 resize-none" /><button onClick={() => answerHuman(input)} className="w-7 h-7 rounded-md bg-amber-400 hover:bg-amber-300 flex items-center justify-center shrink-0 transition-colors" title="Send answer to agent"><span className="text-zinc-950 text-sm">⏎</span></button></div> : <div className="flex items-end gap-2 bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 focus-within:border-zinc-600">            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (input.trim().startsWith('⚡')) runTask(input.trim().slice(1).trim()); else handleSend(); } }} placeholder="Ask the agent, or ⚡ run a coding task..." rows={1} className="flex-1 bg-transparent outline-none text-sm text-zinc-200 font-ui placeholder-zinc-600 resize-none" /><button onClick={() => { if (input.trim().startsWith('⚡')) runTask(input.trim().slice(1).trim()); else handleSend(); }} className="w-7 h-7 rounded-md bg-amber-400 hover:bg-amber-300 flex items-center justify-center shrink-0 transition-colors"><span className="text-zinc-950 text-sm">⏎</span></button></div>)}      <div className="text-xs text-zinc-600 font-ui mt-1 px-0.5">{pendingClarification ? (pendingClarification.turn && pendingClarification.maxTurns ? `Clarification turn ${pendingClarification.turn}/${pendingClarification.maxTurns} — the agent needs more info` : 'Answer the clarification question — the agent needs more info') : pendingHuman ? 'Answer the agent — it is paused waiting for you' : 'Enter to send · Shift+Enter for newline · <span className="text-amber-500/80">⚡</span> = execute task (skills + MCP + human-in-the-loop)'}</div></div></>)}
        {mainView === 'preview' && <PreviewView />}
        {mainView === 'brain' && <BrainView />}
        {mainView === 'webai' && <WebAIBridgeView />}
        {mainView === 'quality' && <RefactorView />}
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      {toast && (<div className="fixed bottom-4 right-4 z-50 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 shadow-2xl flex items-center gap-2"><span className="text-teal-400">✓</span><span className="text-xs font-ui text-zinc-200">{toast.text}</span></div>)}
    </div>
  );
}
