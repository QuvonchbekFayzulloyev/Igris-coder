import React, { useEffect } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { Sidebar } from './Sidebar';
import { PipelineStepper } from './PipelineStepper';
import { ClaudeChat } from './ClaudeChat';
import { PreviewView } from './PreviewView';
import { BrainView } from '../../../2nd_brain/frontend/BrainView';
import { RefactorView } from './RefactorView';
import { WebAIBridgeView } from './WebAIBridgeView';
import { CommandPalette } from './CommandPalette';
import { SettingsModal } from './SettingsModal';
import { RightSidebar } from './RightSidebar';
import { SmartBuildPanel, VisionBuildPanel } from './SmartBuildPanel';
import { AgentStatusPanel } from './AgentStatusPanel';

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
    rightSidebarOpen,
    toggleRightSidebar,
    stage,
    stageDetail,
    taskRunning,
    toast,
    setToast,
    loadWorkspace,
    loadChatHistory,
    loadAgentInfo,
    loadAgentState,
  } = useAgentConsoleStore();

  // ── Agent state polling — backend'dan real-time holat olish ──
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        await loadAgentState();
      } catch { /* offline */ }
    };
    // Birinchi yuklash
    poll();
    // Har 8 soniyada yangilash
    const iv = setInterval(poll, 8000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  // ── Auto-mode: navbatdagi tasklarni avtomatik bajarish ──
  useEffect(() => {
    let cancelled = false;
    let iv: ReturnType<typeof setInterval> | null = null;

    const processQueue = async () => {
      if (cancelled) return;
      const { agentAutoMode, agentTaskQueue, taskRunning, setAgentState, addTaskToQueue } = useAgentConsoleStore.getState();
      if (!agentAutoMode || taskRunning) return;

      const nextTask = agentTaskQueue.find((t) => t.status === 'queued');
      if (!nextTask) return;

      // Taskni 'running' ga o'zgartirish
      useAgentConsoleStore.setState((s) => ({
        agentTaskQueue: s.agentTaskQueue.map((t) =>
          t.id === nextTask.id ? { ...t, status: 'running' as const, started_at: Date.now() } : t
        ),
      }));

      setAgentState('planning');

      // Backend'ga yuborish
      try {
        const { agentTask, agentRunStatus } = await import('../backend');
        const started = await agentTask(nextTask.description);

        let terminal: Awaited<ReturnType<typeof agentRunStatus>> | null = null;
        for (let poll = 0; poll < 75; poll += 1) {
          await new Promise((resolve) => setTimeout(resolve, 4000));
          terminal = await agentRunStatus(started.run_id);
          if (terminal.status !== 'running' && terminal.status !== 'awaiting_human') break;
        }
        const resultStatus = terminal?.result?.status;
        if (terminal?.status !== 'done'
            || !terminal.result
            || !['ok', 'verified', 'completed'].includes(resultStatus || '')) {
          throw new Error(
            terminal?.error || `Task did not verify successfully (${resultStatus || terminal?.status || 'timeout'})`,
          );
        }

        // Taskni completed deb belgilash
        useAgentConsoleStore.setState((s) => ({
          agentTaskQueue: s.agentTaskQueue.map((t) =>
            t.id === nextTask.id ? { ...t, status: 'completed' as const, completed_at: Date.now(), duration_ms: Date.now() - (t.started_at || t.created_at) } : t
          ),
          agentCompletedToday: s.agentCompletedToday + 1,
        }));

        setAgentState('idle');
      } catch (err) {
        // Task xato bilan tugadi
        useAgentConsoleStore.setState((s) => ({
          agentTaskQueue: s.agentTaskQueue.map((t) =>
            t.id === nextTask.id ? { ...t, status: 'failed' as const, error: err instanceof Error ? err.message : 'Task failed' } : t
          ),
        }));
        setAgentState('error');
      }
    };

    const { agentAutoMode } = useAgentConsoleStore.getState();
    if (agentAutoMode) {
      iv = setInterval(processQueue, 5000);
    }

    // Auto-mode o'zgarganda qayta ishga tushirish
    const unsub = useAgentConsoleStore.subscribe((s, prev) => {
      if (s.agentAutoMode !== prev.agentAutoMode) {
        if (iv) clearInterval(iv);
        if (s.agentAutoMode) {
          iv = setInterval(processQueue, 5000);
        }
      }
    });

    return () => { cancelled = true; if (iv) clearInterval(iv); unsub(); };
  }, []);

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
          loadAgentState();
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

  const views = [
    { id: 'chat', icon: '💬', label: 'Chat' },
    { id: 'preview', icon: '👁', label: 'Preview' },
    { id: 'brain', icon: '🧠', label: 'Brain' },
  ];

  return (
    <div className="flex-1 min-h-0 flex">
      {sidebarOpen && <Sidebar />}
      <div className="flex-1 min-w-0 flex flex-col z-10">
        <div className="flex items-center px-3 py-1.5 border-b border-zinc-800 shrink-0 z-20">
          <div className="inline-flex bg-zinc-900 border border-zinc-800 rounded-md p-0.5">
            {views.map(({ id, icon, label }) => (<button key={id} onClick={() => setMainView(id as any)} className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded font-ui ${mainView === id ? 'bg-zinc-800 text-amber-300' : 'text-zinc-500 hover:text-zinc-300'}`}><span>{icon}</span> {label}</button>))}
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <button
              onClick={() => toggleRightSidebar()}
              title={rightSidebarOpen ? 'Close right sidebar' : 'Open right sidebar — activity / inspector / memory / task'}
              className={`w-7 h-7 flex items-center justify-center rounded text-sm transition-colors ${
                rightSidebarOpen
                  ? 'bg-amber-400/20 text-amber-300 border border-amber-500/40'
                  : 'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800'
              }`}
            >
              📊
            </button>
          </div>
        </div>
        {(mainView === 'chat' || mainView === 'preview' || mainView === 'agent') && (
          <PipelineStepper current={stage} detail={stageDetail} running={taskRunning} />
        )}
        {mainView === 'chat' && (
          /* Claude-uslubidagi chat: empty state + full-width oqim + katta composer.
             PipelineStepper pastda nozik qator sifatida qoladi (task holati). */
          <ClaudeChat />
        )}
        {mainView === 'preview' && <PreviewView />}
        {mainView === 'smartbuild' && <SmartBuildPanel />}
        {mainView === 'chatstream' && <ChatStreamView task="" actions={[]} totalDuration={0} status="idle" result="" />}
        {mainView === 'brain' && <BrainView />}
        {mainView === 'webai' && <WebAIBridgeView />}

      </div>
      {rightSidebarOpen && <RightSidebar />}
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      {toast && (<div className="fixed bottom-4 right-4 z-50 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 shadow-2xl flex items-center gap-2"><span className="text-teal-400">✓</span><span className="text-xs font-ui text-zinc-200">{toast.text}</span></div>)}
    </div>
  );
}
