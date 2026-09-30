import { create } from 'zustand';
import {
  TreeNode,
  ChatMessage,
  MainView,
  SidebarMode,
  SidebarChatItem,
  AgentState,
  AgentTask,
  AgentTaskStep,
  AgentCapability,
  AgentStateType,
} from './constants';
import { relativeTime, newChatId, activeStreamCtrl, setActiveStreamCtrl } from './time-helpers';
import { loadBrainLogs, appendBrainLog, removeBrainLogs } from './brain-logs';
import { DRAWING_EXT, drawingPathsFromRun, drawingMessages } from './drawing-helpers';
import { buildTree } from './tree-helpers';

// Tauri API detection
let tauriInvoke: ((cmd: string, args?: any) => Promise<any>) | null = null;
if (typeof window !== 'undefined' && (window as any).__TAURI__) {
  tauriInvoke = (window as any).__TAURI__.core.invoke;
}

import { chat as bridgeChat, getBackendUrl, StreamError } from '../web/backend';
import type { AgentRunResult } from '../web/backend';

// ── Default agent capabilities ─────────────────────────────────────
const DEFAULT_CAPABILITIES: AgentCapability[] = [
  { name: 'code_write', icon: '💻', description: 'Kod yozish va tahrirlash', enabled: true, tools: ['write_file', 'edit_file', 'create_file'] },
  { name: 'code_read', icon: '📖', description: "Fayllarni o'qish va tahlil qilish", enabled: true, tools: ['read_file', 'list_files', 'search_code'] },
  { name: 'file_management', icon: '📁', description: 'Fayl tizimini boshqarish', enabled: true, tools: ['read_file', 'write_file', 'list_files', 'run_command'] },
  { name: 'web_research', icon: '🌐', description: 'Webdan malumot olish', enabled: true, tools: ['web_search', 'web_browse', 'fetch_url'] },
  { name: 'draw', icon: '🎨', description: 'SVG rasm chizish', enabled: true, tools: ['use_skill'] },
  { name: 'shell', icon: '⚡', description: 'Buyruq satri amallari', enabled: true, tools: ['run_command'] },
  { name: 'data_analysis', icon: '📊', description: "Ma'lumotlarni tahlil qilish", enabled: true, tools: ['run_command'] },
  { name: 'skill_use', icon: '🧩', description: "Maxsus ko'nikmalardan foydalanish", enabled: true, tools: ['use_skill'] },
];

interface AgentConsoleState {
  sidebarOpen: boolean;
  sidebarMode: SidebarMode;
  sidebarQuery: string;
  recents: SidebarChatItem[];
  chatSessionId: string;
  /** Real backend status (model, LLM, RAG memory, 12 intellekt) — /api/status'dan. */
  agentInfo: { model: string; llmAvailable: boolean; memoryEnabled: boolean; intelligenceEnabled: boolean; circuit?: { state: string; failure_count: number; last_failure: number; last_success: number; open_since: number | null }; llmDegraded?: boolean; llmFailureCount?: number; omniroute?: { connected: boolean; url: string; default_model: string; models_count: number; providers: string[] }; lsp?: { servers: Record<string, { running: boolean; initialized: boolean }>; languages: string[] } } | null;
  terminalOpen: boolean;
  mainView: MainView;
  paletteOpen: boolean;
  settingsOpen: boolean;
  toast: { text: string } | null;
  expanded: Set<string>;
  tree: TreeNode[];
  rootName: string;
  rootMenuOpen: boolean;
  selectedFile: string;
  previewMode: 'code' | 'diff';
  stage: number;
  /** REAL pipeline progress — agent ishlayotganda backend'ning jonli bosqichi. */
  stageDetail: string;
  /** Task run hozir fon'da ishlayaptimi (poll davom etmoqdami). */
  taskRunning: boolean;
  /** Nega LLM/Ollama ishlamayapti (agentStatus llm.error'dan). */
  llmError: string | null;
  /** Universal tez rejim (TURBO) — barcha modellarga birdek, Settings'dan. */
  turbo: boolean;
  /** TURBO rejimdagi avtomatik tez model (pick_fast_model). */
  fastModel: string | null;
  messages: ChatMessage[];
  input: string;
  backendOnline: boolean;
  backendUrl: string;
  pendingHuman: { runId: string; question: string } | null;
  /** Layered agent clarification — userdan qo'shimcha ma'lumot so'ralmoqda. */
  pendingClarification: { sessionId: string; question: string; turn?: number; maxTurns?: number } | null;
  /** Right sidebar tab — qaysi panel ochiq. */
  rightSidebarTab: 'agent' | 'activity' | 'inspector' | 'memory' | 'task' | 'systems';
  setRightSidebarTab: (tab: 'agent' | 'activity' | 'inspector' | 'memory' | 'task' | 'systems') => void;
  rightSidebarOpen: boolean;
  setRightSidebarOpen: (open: boolean) => void;
  toggleRightSidebar: () => void;
  // ── Agent state ─────────────────────────────────────────────────
  agentState: AgentStateType;
  agentCapabilities: AgentCapability[];
  agentTaskQueue: AgentTask[];
  agentCompletedToday: number;
  agentAutoMode: boolean;
  agentStartTime: number;
  setAgentState: (state: AgentStateType) => void;
  toggleAutoMode: () => void;
  addTaskToQueue: (task: Omit<AgentTask, 'id' | 'created_at' | 'steps' | 'tools_used'>) => string;
  removeTaskFromQueue: (id: string) => void;
  pauseTask: (id: string) => void;
  resumeTask: (id: string) => void;
  updateTaskStep: (taskId: string, stepId: number, update: Partial<AgentTaskStep>) => void;
  loadAgentState: () => Promise<void>;
  setBackendOnline: (online: boolean) => void;
  setBackendUrl: (url: string) => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setSidebarMode: (mode: SidebarMode) => void;
  setSidebarQuery: (q: string) => void;
  setRecents: (items: SidebarChatItem[]) => void;
  selectChat: (id: string) => Promise<void>;
  newChat: () => void;
  clearAllResults: () => Promise<void>;
  loadChatHistory: () => Promise<void>;
  loadAgentInfo: () => Promise<void>;
  loadSpeedSettings: () => Promise<void>;
  setSpeed: (turbo: boolean) => Promise<void>;
  switchModel: (model: string) => Promise<void>;
  /** Chat history actions — star / rename / delete + backend restart from UI. */
  starChat: (id: string, starred: boolean) => Promise<void>;
  renameChat: (id: string, title: string) => Promise<void>;
  deleteChat: (id: string) => Promise<void>;
  restartBackend: () => Promise<boolean>;
  startOllama: () => Promise<{ ok: boolean; running?: boolean; error?: string }>;
  restartOllama: () => Promise<{ ok: boolean; running?: boolean; error?: string }>;
  /** Circuit breaker: agent'ni majburiy qayta yaratish yoki reset. */
  rebuildAgent: () => Promise<{ ok: boolean; error?: string }>;
  resetCircuit: () => Promise<{ ok: boolean }>;
  /** LLM qayta sinab ko'rish — circuit reset + avtomatik tekshirish. */
  retryLLM: () => Promise<{ ok: boolean; available?: boolean; error?: string }>;
  setTerminalOpen: (open: boolean) => void;
  toggleTerminal: () => void;
  setMainView: (view: MainView) => void;
  setPaletteOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setToast: (toast: { text: string } | null) => void;
  toggleExpanded: (path: string) => void;
  setExpanded: (expanded: Set<string>) => void;
  setTree: (tree: TreeNode[]) => void;
  setRootName: (name: string) => void;
  setRootMenuOpen: (open: boolean) => void;
  setSelectedFile: (file: string) => void;
  setPreviewMode: (mode: 'code' | 'diff') => void;
  setStage: (stage: number) => void;
  setStageDetail: (detail: string) => void;
  setTaskRunning: (running: boolean) => void;
  /** Jonli agent stream'ni to'xtatish (Claude'dagi Stop tugmasi) —
   * abort qilinadi, qisman javob chatda qoladi. */
  stopStream: () => void;
  setMessages: (messages: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
  setInput: (input: string) => void;
  handleSend: () => void;
  runAgent: (task: string) => Promise<void>;
  runTask: (task: string) => Promise<void>;
  answerHuman: (answer: string) => Promise<void>;
  answerClarification: (answer: string) => Promise<void>;
  loadWorkspace: (root?: string) => Promise<void>;
  pushDrawing: (path: string, caption?: string) => void;
  /** 2nd Brain yangilanish sababini chatga LOG qatori sifatida qo'shadi
   *  (badge vaqtinchalik — chat logi doimiy yozuv bo'lib qoladi). */
  pushBrainLog: (reason: string) => void;
  pushAgentState: (state: string, detail?: string) => void;
  pushTaskResult: (text: string, opts?: { name?: string; status?: string; duration_ms?: number; engine?: string; diff?: string[]; completion?: any }) => void;
}

/** Backend stage nomi -> STAGES indeksi (REAL pipeline progress). */
const STAGE_INDEX: Record<string, number> = {
  plan: 0,
  read: 1,
  edit: 2,
  test: 3,
  review: 4,
};

// ------------------------------------------------------------------ //
// Asosiy store — AgentConsole holati va amallari.
// ------------------------------------------------------------------ //
export const useAgentConsoleStore = create<AgentConsoleState>((set, get) => ({
  sidebarOpen: true,
  sidebarMode: 'chats',
  sidebarQuery: '',
  recents: [],
  chatSessionId: newChatId(),
  agentInfo: null,
  terminalOpen: false,
  mainView: 'chat',
  paletteOpen: false,
  settingsOpen: false,
  toast: null,
  expanded: new Set<string>(),
  tree: [],
  rootName: 'agent_workspace',
  rootMenuOpen: false,
  selectedFile: '',
  previewMode: 'code',
  stage: 0,
  stageDetail: '',
  taskRunning: false,
  llmError: null,
  turbo: false,
  fastModel: null,
  messages: [],
  input: '',
  backendOnline: false,
  backendUrl: getBackendUrl(),
  pendingHuman: null,
  pendingClarification: null,
  rightSidebarTab: 'agent',
  rightSidebarOpen: false,
  setRightSidebarTab: (tab) => set({ rightSidebarTab: tab, rightSidebarOpen: true }),
  setRightSidebarOpen: (open) => set({ rightSidebarOpen: open }),
  toggleRightSidebar: () => set((state) => ({ rightSidebarOpen: !state.rightSidebarOpen })),
  // Agent state
  agentState: 'idle' as AgentStateType,
  agentCapabilities: DEFAULT_CAPABILITIES,
  agentTaskQueue: [],
  agentCompletedToday: 0,
  agentAutoMode: false,
  agentStartTime: Date.now(),
  setAgentState: (agentState) => set({ agentState }),
  loadAgentState: async () => {
    try {
      const { agentState: fetchAgentState } = await import('../web/backend');
      const st = await fetchAgentState();
      set({
        agentState: st.state as AgentStateType,
        agentCapabilities: st.capabilities,
        agentCompletedToday: st.completed_today,
      });
    } catch {
      // offline — keep current state
    }
  },
  toggleAutoMode: () => set((s) => ({ agentAutoMode: !s.agentAutoMode })),
  addTaskToQueue: (task) => {
    const id = `task-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const newTask: AgentTask = {
      ...task,
      id,
      created_at: Date.now(),
      steps: [],
      tools_used: [],
    };
    set((s) => ({ agentTaskQueue: [...s.agentTaskQueue, newTask] }));
    return id;
  },
  removeTaskFromQueue: (id) => set((s) => ({
    agentTaskQueue: s.agentTaskQueue.filter((t) => t.id !== id),
  })),
  pauseTask: (id) => set((s) => ({
    agentTaskQueue: s.agentTaskQueue.map((t) =>
      t.id === id ? { ...t, status: 'paused' as const } : t
    ),
  })),
  resumeTask: (id) => set((s) => ({
    agentTaskQueue: s.agentTaskQueue.map((t) =>
      t.id === id ? { ...t, status: 'queued' as const } : t
    ),
  })),
  updateTaskStep: (taskId, stepId, update) => set((s) => ({
    agentTaskQueue: s.agentTaskQueue.map((t) =>
      t.id === taskId
        ? { ...t, steps: t.steps.map((st) => st.id === stepId ? { ...st, ...update } : st) }
        : t
    ),
  })),
  setBackendOnline: (online) => set({ backendOnline: online }),
  setBackendUrl: (url) => {
    set({ backendUrl: url });
    import('../web/backend').then((m) => m.setBackendUrl(url));
  },
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarMode: (mode) => set({ sidebarMode: mode }),
  setSidebarQuery: (q) => set({ sidebarQuery: q }),
  setRecents: (items) => set({ recents: items }),
  selectChat: async (id) => {
    // chat tanlanganda — unread belgini o'chiramiz, chat bo'limiga o'tamiz,
    // so'ng suhbatni backend'dan to'liq yuklaymiz (haqiqiy xabarlar).
    set((state) => ({
      recents: state.recents.map((c) => (c.id === id ? { ...c, unread: false } : c)),
      sidebarMode: 'chats',
    }));
    try {
      const { chatConversation } = await import('../web/backend');
      const res = await chatConversation(id);
      if (res.ok && res.conversation) {
        const msgs: ChatMessage[] = res.conversation.messages.map((m) => ({
          role: m.role === 'user' ? 'user' : 'agent',
          text: m.text || '',
          // structure_check fail — transcript'da alohida saqlangan ogohlantirish
          // (matnning o'zida EMAS, shuning uchun LLM konteksti toza qoladi).
          warning: m.warning || undefined,
          // AGENTIK completion — suhbatda qaysi pipeline ishlaganini ko'rsatadi
          // (tarix yuklanganda ham saqlanadi).
          completion: (m as any).completion || undefined,
        }));
        // 2nd Brain loglari localStorage'dan TIKLANADI — suhbatga qaytilganda
        // doimiy yozuvlar chatda ko'rinadi (backend history'ga aralashmaydi).
        const logs: ChatMessage[] = loadBrainLogs(id).map((l) => ({
          kind: 'log' as const,
          text: l.text,
        }));
        set({ messages: [...msgs, ...logs], chatSessionId: id, mainView: 'chat' });
      }
    } catch {
      // backend offline — faqat unread tozalandi, xabarlar o'zgarmaydi
    }
  },
  starChat: async (id, starred) => {
    try {
      const { chatStar } = await import('../web/backend');
      await chatStar(id, starred);
    } catch {
      // offline — lokal holat o'zgaradi, keyingi yuklashda haqiqiy holat keladi
    }
    set((state) => ({
      recents: state.recents.map((c) => (c.id === id ? { ...c, starred } : c)),
    }));
  },
  renameChat: async (id, title) => {
    const t = title.trim();
    if (!t) return;
    try {
      const { chatRename } = await import('../web/backend');
      await chatRename(id, t);
    } catch {
      // offline
    }
    set((state) => ({
      recents: state.recents.map((c) => (c.id === id ? { ...c, title: t } : c)),
    }));
  },
  deleteChat: async (id) => {
    try {
      const { chatDelete } = await import('../web/backend');
      await chatDelete(id);
    } catch {
      // offline — lokal holatda olib tashlaymiz; qayta yuklashda backend sinxronlanadi
    }
    const { chatSessionId } = get();
    set((state) => ({
      recents: state.recents.filter((c) => c.id !== id),
      // ochiq bo'lgan suhbat o'chirilsa — yangi sessiyaga o'tamiz
      ...(chatSessionId === id ? { chatSessionId: newChatId(), messages: [] } : {}),
    }));
    // O'chirilgan suhbatning 2nd Brain loglari ham localStorage'dan o'chiriladi
    // (toza holat — qayta ochilganda eski loglar qaytmaydi).
    removeBrainLogs(id);
    // O'chirish backend'da PERSIST qilinganini ta'minlash — recents backend'dan
    // qayta yuklanadi, shunda o'chirilgan suhbat qayta ochilganda ham ko'rinmaydi.
    await get().loadChatHistory();
  },
  restartBackend: async () => {
    try {
      const { systemRestart, ping } = await import('../web/backend');
      await systemRestart();
      set({ backendOnline: false });
      // Backend qayta ochilishini kuting (max ~60s — backend marker handshake'i ham
      // 60s kutadi, mos keladi), so'ng ma'lumotlarni yangilang
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          if (await ping()) {
            await get().loadAgentInfo();
            await get().loadChatHistory();
            await get().loadWorkspace();
            set({ backendOnline: true });
            return true;
          }
        } catch {
          // hali tayyor emas
        }
      }
      return false;
    } catch {
      return false;
    }
  },
  startOllama: async () => {
    try {
      const { ollamaStart } = await import('../web/backend');
      const r = await ollamaStart();
      await get().loadAgentInfo();
      return { ok: Boolean(r.ok), running: r.running, error: r.error };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : 'ollama start failed' };
    }
  },
  restartOllama: async () => {
    try {
      const { ollamaRestart } = await import('../web/backend');
      const r = await ollamaRestart();
      await get().loadAgentInfo();
      return { ok: Boolean(r.ok), running: r.running, error: r.error };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : 'ollama restart failed' };
    }
  },
  rebuildAgent: async () => {
    try {
      const res = await fetch(`${get().backendUrl}/api/agent/rebuild`, {
        method: 'POST',
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json();
      await get().loadAgentInfo();
      return { ok: Boolean(data.ok), error: data.error };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : 'rebuild failed' };
    }
  },
  resetCircuit: async () => {
    try {
      const res = await fetch(`${get().backendUrl}/api/circuit/reset`, {
        method: 'POST',
        signal: AbortSignal.timeout(5000),
      });
      const data = await res.json();
      await get().loadAgentInfo();
      return { ok: Boolean(data.ok) };
    } catch {
      return { ok: false };
    }
  },
  retryLLM: async () => {
    try {
      const { retryLLM: retryLLMFn } = await import('../web/backend');
      const r = await retryLLMFn();
      // Kichik kutish - LLM tekshiruvi uchun vaqt
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await get().loadAgentInfo();
      return { ok: Boolean(r.ok), available: r.available, error: r.error };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : 'retry failed' };
    }
  },
  newChat: () => {
    set((state) => ({
      input: '',
      mainView: 'chat',
      messages: [],
      sidebarMode: 'chats',
      chatSessionId: newChatId(),
      stage: 0,
      stageDetail: '',
    }));
  },
  clearAllResults: async () => {
    // "Oldingi natijalarni tozala": backend chat tarixi + CAG kesh + workspace
    // chizma fayllari tozalanadi; frontend chat va workspace daraxti yangilanadi.
    try {
      const { chatClear } = await import('../web/backend');
      await chatClear();
    } catch {
      /* offline — baribir lokal tozalaymiz */
    }
    get().newChat();
    await get().loadChatHistory();
    await get().loadWorkspace();
  },
  loadChatHistory: async () => {
    try {
      const { chatHistory } = await import('../web/backend');
      const res = await chatHistory(30);
      if (!res.ok) return;
      const items: SidebarChatItem[] = res.conversations.map((c) => ({
        id: c.id,
        title: c.title || c.preview || 'Yangi chat',
        time: relativeTime(c.time),
        starred: c.starred,
        unread: c.unread,
        kind: 'chat',
      }));
      set({ recents: items });
    } catch {
      // offline — bo'sh qoladi
    }
  },
  loadAgentInfo: async () => {
    try {
      const { agentStatus } = await import('../web/backend');
      const st = await agentStatus();
      set({
        backendOnline: true,
        agentInfo: {
          model: st.llm?.model || '',
          llmAvailable: Boolean(st.llm?.available),
          memoryEnabled: Boolean(st.memory?.enabled),
          // 12 intellekt arxitekturasi yoqilganmi — StatusBar'da ko'rsatiladi.
          intelligenceEnabled: Boolean(st.intelligence?.enabled),
          // Circuit breaker holati — Settings'da ko'rsatiladi.
          circuit: st.circuit || undefined,
          llmDegraded: Boolean(st.llm?.degraded),
          llmFailureCount: st.llm?.failure_count || 0,
          // OmniRoute gateway status
          omniroute: st.omniroute || undefined,
          // LSP server status
          lsp: st.lsp || undefined,
        },
        llmError: st.llm?.error || null,
        // TURBO holati /api/status'da ham keladi — real vaqtda sinxronlash.
        ...(st.llm?.turbo !== undefined ? { turbo: st.llm.turbo } : {}),
        ...(st.llm?.fast_model !== undefined ? { fastModel: st.llm.fast_model } : {}),
      });
      // TURBO sozlamasini ham yuklaymiz — UI backend holatini DARHOL aks ettiradi
      // (Settings ochilishini kutmaydi; restart'dan keyin ham to'g'ri ko'rinadi).
      get().loadSpeedSettings();
    } catch {
      // offline — agentInfo null qoladi
    }
  },
  loadSpeedSettings: async () => {
    try {
      const { speedSettings } = await import('../web/backend');
      const st = await speedSettings();
      set({ turbo: Boolean(st.turbo), fastModel: st.fast_model || null });
    } catch {
      // offline — lokal holat o'zgarishsiz
    }
  },
  setSpeed: async (turbo: boolean) => {
    try {
      const { setSpeed } = await import('../web/backend');
      const st = await setSpeed(turbo);
      set({ turbo: Boolean(st.turbo), fastModel: st.fast_model || null });
      get().setToast({ text: st.turbo ? '⚡ TURBO rejim yoqildi — barcha modellar tezlashdi' : 'TURBO rejim o\'chirildi' });
    } catch {
      get().setToast({ text: 'Backend offline — tez rejim saqlanmadi' });
    }
  },
  switchModel: async (model: string) => {
    try {
      const { setModel } = await import('../web/backend');
      await setModel(model);
      await get().loadAgentInfo();
    } catch {
      // backend javob bermadi — keyingi yuklashda haqiqiy holat ko'rinadi
    }
  },
  setTerminalOpen: (open) => set({ terminalOpen: open }),
  toggleTerminal: () => set((state) => ({ terminalOpen: !state.terminalOpen })),
  setMainView: (view) => set({ mainView: view }),
  setPaletteOpen: (open) => set({ paletteOpen: open }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setToast: (toast) => set({ toast }),
  toggleExpanded: (path) => set((state) => {
    const next = new Set(state.expanded);
    next.has(path) ? next.delete(path) : next.add(path);
    return { expanded: next };
  }),
  setExpanded: (expanded) => set({ expanded }),
  setTree: (tree) => set({ tree }),
  setRootName: (name) => set({ rootName: name }),
  setRootMenuOpen: (open) => set({ rootMenuOpen: open }),
  setSelectedFile: (file) => set({ selectedFile: file }),
  setPreviewMode: (mode) => set({ previewMode: mode }),
  setStage: (stage) => set({ stage }),
  setStageDetail: (detail) => set({ stageDetail: detail }),
  setTaskRunning: (running) => set({ taskRunning: running }),
  // JONLI stream'ni foydalanuvchi to'xtatadi — abort signal stream reader'ini
  // buzadi, handleSend catch yo'li kursor to'xtatadi, qisman javob chatda qoladi.
  stopStream: () => {
    if (activeStreamCtrl) {
      activeStreamCtrl.abort();
      setActiveStreamCtrl(null);
    }
  },
  setMessages: (messages) => set((state) => ({
    messages: typeof messages === 'function' ? messages(state.messages) : messages,
  })),
  setInput: (input) => set({ input }),
  runTask: async (task: string) => {
    const text = task.trim();
    if (!text) return;
    set((state) => ({
      input: '',
      mainView: 'chat',
      messages: [...state.messages, { role: 'user', text: `⚡ ${text}` }],
    }));
    // REAL pipeline: ish boshlandi — backend jonli bosqich yuboradi
    set({ stage: 0, stageDetail: 'task tahlil qilinmoqda…', taskRunning: true });
    let runId: string;
    try {
      const { agentTask } = await import('../web/backend');
      const started = await agentTask(text, get().chatSessionId);
      runId = started.run_id;
      set({ backendOnline: true });
    } catch {
      set({ backendOnline: false, taskRunning: false, stageDetail: '' });
      set((state) => ({
        messages: [...state.messages, { role: 'agent', text: 'Brain offline — agent execution unavailable (start `python server.py`).' }],
      }));
      return;
    }

    // poll until done / awaiting human
    const { agentRunStatus, agentRespond } = await import('../web/backend');
    // Backend uzok vaqt offline bo'lsa ham cheksiz poll qilinmaydi (task "osilib
    // qolgan" ko'rinmasin): ~5 daqiqadan so'ng aniq xato ko'rsatiladi.
    const POLL_CAP = 75;
    let polls = 0;
    // Poll orqali jonli ko'rsatilgan tool chaqiruvlar soni — dublikat kartochkalarni oldini oladi.
    let shownToolCalls = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      await new Promise((r) => setTimeout(r, 4000));
      let state;
      try {
        state = await agentRunStatus(runId);
      } catch {
        polls += 1;
        if (polls >= POLL_CAP) {
          set((s) => ({
            taskRunning: false,
            stageDetail: '',
            pendingHuman: null,
            messages: [...s.messages, { role: 'agent', text: '✗ Task tugallanmadi — backend uzok vaqt javob bermadi (offline). Taskni qayta yuboring.' }],
          }));
          return;
        }
        continue;
      }
      // Run yo'qolgan — backend restart qilingan yoki run xotiradan o'chgan.
      // Cheksiz poll o'rniga aniq xato ko'rsatamiz ("task chala qoldi" holati).
      if (state.status === 'not_found') {
        set((s) => ({
          taskRunning: false,
          stageDetail: '',
          pendingHuman: null,
          messages: [
            ...s.messages,
            { role: 'agent', text: '✗ Task yo\'qoldi — backend restart qilingan (run server xotirasida saqlanmagan). Taskni qayta yuboring.' },
          ],
        }));
        return;
      }
      // REAL stage — backend'ning jonli pipeline bosqichini ko'rsatamiz
      if (state.stage) {
        const idx = STAGE_INDEX[state.stage];
        if (typeof idx === 'number') {
          set({ stage: idx, stageDetail: state.stage_detail || '' });
        }
      }
      // RUN DAVOMIDA jonli kuzatish: agent chizma/tool fayl yaratsa — karta
      // darhol qo'shiladi va qurilish jarayoni ko'rsatiladi (run tugashini kutmaymiz).
      if (Array.isArray(state.tool_calls) && state.tool_calls.length) {
        drawingPathsFromRun({ tool_calls: state.tool_calls }).forEach((p) =>
          get().pushDrawing(p, 'agent hozir chizmoqda — ▶ jarayonni jonli kuzatish'),
        );
        // JONLI tool kartochkalari — yangi bajarilgan tool'lar darhol ko'rinadi
        const freshTools = state.tool_calls.slice(shownToolCalls);
        if (freshTools.length) {
          shownToolCalls = state.tool_calls.length;
          set((s) => ({
            messages: [
              ...s.messages,
              ...freshTools.map((tc) => ({
                kind: 'toolcall' as const,
                name: tc.tool,
                status: (tc.result && tc.result.ok ? 'done' : 'error') as 'done' | 'error',
                detail: typeof tc.args === 'object' && tc.args ? JSON.stringify(tc.args).slice(0, 90) : '',
                diff: tc.result && tc.result.ok && tc.output_preview
                  ? tc.output_preview.split('\n').slice(0, 12).map((l) => `  ${l}`)
                  : undefined,
              })),
            ],
          }));
        }
      }
      if (state.status === 'awaiting_human' && state.question) {
        const question = state.question || '';
        set((s) => ({
          pendingHuman: { runId, question },
          messages: [...s.messages, { kind: 'human' as const, text: question, runId }],
        }));
        break;
      }
      if (state.status === 'done' || state.status === 'error') {
        const r = state.result;
        const drawings = state.status === 'done' ? drawingMessages(r) : [];
        // Jonli poll'da allaqachon ko'rsatilgan tool'lar QAYTA qo'shilmasin
        const toolMsgs: ChatMessage[] = (r?.tool_calls || []).slice(shownToolCalls).map((tc) => ({
          kind: 'toolcall',
          name: tc.tool,
          status: tc.result && tc.result.ok ? 'done' : 'error',
          detail: typeof tc.args === 'object' && tc.args ? JSON.stringify(tc.args).slice(0, 90) : '',
          diff: tc.result && tc.result.ok && tc.output_preview
            ? tc.output_preview.split('\n').slice(0, 12).map((l) => `  ${l}`)
            : undefined,
        }));
        const stats = r?.stats;
        const summary = state.status === 'error'
          ? `✗ ERROR — ${state.error || 'agent failed'}`
          : `✓ ${(r?.status || 'OK').toUpperCase()} — ${r?.engine || ''} · ${(stats?.tool_calls ?? 0)} tool calls · ${stats ? (stats.duration_ms / 1000).toFixed(1) : '?'}s`;
        set((s) => {
          // Jonli push'da karta allaqachon qo'shilgan bo'lishi mumkin — dublikat qo'shmaymiz.
          const existing = new Set(
            s.messages.filter((m) => m.kind === 'drawing' && m.path).map((m) => m.path as string),
          );
          const fresh = drawings.filter((d) => d.path && !existing.has(d.path));
          return {
            pendingHuman: null,
            taskRunning: false,
            stageDetail: '',
            messages: [
              ...s.messages,
              ...toolMsgs,
              ...fresh,
              { role: 'agent', text: r?.final || summary, engine: r?.engine },
            ],
          };
        });
        get().loadWorkspace();
        get().loadChatHistory();
        return;
      }
    }
  },
  answerHuman: async (answer: string) => {
    const { pendingHuman } = get();
    if (!pendingHuman) return;
    const { runId } = pendingHuman;
    const text = answer.trim();
    if (!text) return;
    set((state) => ({
      pendingHuman: null,
      messages: [...state.messages, { role: 'user', text: `↳ ${text}` }],
    }));
    try {
      const { agentRespond } = await import('../web/backend');
      await agentRespond(runId, text);
    } catch {
      set((state) => ({
        messages: [...state.messages, { role: 'agent', text: 'Failed to deliver your answer — the run may have timed out.' }],
      }));
      return;
    }
    // resume polling from current runId
    const { agentRunStatus } = await import('../web/backend');
    // Backend uzok vaqt offline bo'lsa ham cheksiz poll qilinmaydi.
    const POLL_CAP = 75;
    let polls = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      await new Promise((r) => setTimeout(r, 4000));
      let st;
      try {
        st = await agentRunStatus(runId);
      } catch {
        polls += 1;
        if (polls >= POLL_CAP) {
          set((s) => ({
            taskRunning: false,
            stageDetail: '',
            pendingHuman: null,
            messages: [...s.messages, { role: 'agent', text: '✗ Task tugallanmadi — backend uzok vaqt javob bermadi (offline). Taskni qayta yuboring.' }],
          }));
          return;
        }
        continue;
      }
      // Run yo'qolgan — backend restart qilingan; cheksiz poll o'rniga xato ko'rsatamiz.
      if (st.status === 'not_found') {
        set((s) => ({
          taskRunning: false,
          stageDetail: '',
          pendingHuman: null,
          messages: [
            ...s.messages,
            { role: 'agent', text: '✗ Task yo\'qoldi — backend restart qilingan (run server xotirasida saqlanmagan). Taskni qayta yuboring.' },
          ],
        }));
        return;
      }
      // REAL stage — backend'ning jonli pipeline bosqichini ko'rsatamiz
      if (st.stage) {
        const idx = STAGE_INDEX[st.stage];
        if (typeof idx === 'number') {
          set({ stage: idx, stageDetail: st.stage_detail || '' });
        }
      }
      // RUN DAVOMIDA jonli kuzatish (answerHuman polling'ida ham)
      if (Array.isArray(st.tool_calls) && st.tool_calls.length) {
        drawingPathsFromRun({ tool_calls: st.tool_calls }).forEach((p) =>
          get().pushDrawing(p, 'agent hozir chizmoqda — ▶ jarayonni jonli kuzatish'),
        );
      }
      if (st.status === 'awaiting_human' && st.question) {
        const question = st.question || '';
        set((s) => ({
          pendingHuman: { runId, question },
          messages: [...s.messages, { kind: 'human' as const, text: question, runId }],
        }));
        return;
      }
      if (st.status === 'done' || st.status === 'error') {
        const r = st.result;
        const drawings = st.status === 'done' ? drawingMessages(r) : [];
        const toolMsgs: ChatMessage[] = (r?.tool_calls || []).map((tc) => ({
          kind: 'toolcall',
          name: tc.tool,
          status: tc.result && tc.result.ok ? 'done' : 'error',
          detail: typeof tc.args === 'object' && tc.args ? JSON.stringify(tc.args).slice(0, 90) : '',
          diff: tc.result && tc.result.ok && tc.output_preview
            ? tc.output_preview.split('\n').slice(0, 12).map((l) => `  ${l}`)
            : undefined,
        }));
        const stats = r?.stats;
        const summary = st.status === 'error'
          ? `✗ ERROR — ${st.error || 'agent failed'}`
          : `✓ ${(r?.status || 'OK').toUpperCase()} — ${r?.engine || ''} · ${(stats?.tool_calls ?? 0)} tool calls · ${stats ? (stats.duration_ms / 1000).toFixed(1) : '?'}s`;
        set((s) => {
          // Jonli push'da karta allaqachon qo'shilgan bo'lishi mumkin — dublikat qo'shmaymiz.
          const existing = new Set(
            s.messages.filter((m) => m.kind === 'drawing' && m.path).map((m) => m.path as string),
          );
          const fresh = drawings.filter((d) => d.path && !existing.has(d.path));
          return {
            taskRunning: false,
            stageDetail: '',
            messages: [
              ...s.messages,
              ...toolMsgs,
              ...fresh,
              { role: 'agent', text: r?.final || summary, engine: r?.engine },
            ],
          };
        });
        get().loadChatHistory();
        return;
      }
    }
  },
  answerClarification: async (answer: string) => {
    const { pendingClarification } = get();
    if (!pendingClarification) return;
    const { sessionId } = pendingClarification;
    const text = answer.trim();
    if (!text) return;
    set((state) => ({
      pendingClarification: null,
      messages: [...state.messages, { role: 'user', text: `↳ ${text}` }],
    }));
    try {
      const { clarifyChat } = await import('../web/backend');
      await clarifyChat(sessionId, text);
    } catch {
      set((state) => ({
        messages: [...state.messages, { role: 'agent', text: 'Failed to deliver your clarification — the session may have timed out.' }],
      }));
      return;
    }
    // Clarification yuborildi — agent davom etadi (stream'da keyingi eventlarni kutamiz)
  },
  runAgent: async (task: string) => {
    const { messages } = get();
    const text = task.trim();
    if (!text) return;

    set({
      input: '',
      mainView: 'chat',
      messages: [...messages, { role: 'user', text: `⚡ ${text}` }],
    });

    const { agentRun } = await import('../web/backend');
    let result: AgentRunResult;
    try {
      result = await agentRun(text);
      set({ backendOnline: true });
    } catch {
      set({ backendOnline: false });
      set((state) => ({
        messages: [...state.messages, { role: 'agent', text: 'Brain offline — agent execution unavailable (start `python server.py`).' }],
      }));
      return;
    }

    const toolMsgs: ChatMessage[] = (result.tool_calls || []).map((tc) => ({
      kind: 'toolcall',
      name: tc.tool,
      status: tc.result && tc.result.ok ? 'done' : 'error',
      detail: typeof tc.args === 'object' && tc.args ? JSON.stringify(tc.args).slice(0, 90) : '',
      diff: tc.result && tc.result.ok && tc.output_preview
        ? tc.output_preview.split('\n').slice(0, 12).map((l) => `  ${l}`)
        : undefined,
    }));

    const summary = `✓ ${result.status.toUpperCase()} — ${result.steps.length} steps, ${result.stats.tool_calls} tool calls, ${(result.stats.duration_ms / 1000).toFixed(1)}s${result.stats.corrections ? `, ${result.stats.corrections} auto-fixes` : ''}`;

    set((state) => ({
      stage: 0,
      stageDetail: '',
      taskRunning: false,
      messages: [
        ...state.messages,
        ...toolMsgs,
        ...drawingMessages(result),
        { role: 'agent', text: summary },
      ],
    }));
  },
  pushDrawing: (path, caption) => {
    if (!path) return;
    const { mainView, selectedFile } = get();
    // Preview oynasida bo'lsak — yangi chizma avtomatik ochiladi va qurilish
    // jarayoni o'sha yerda jonli ko'rinadi (real vaqtda kuzatish).
    if (mainView === 'preview' && selectedFile !== path) {
      set({ selectedFile: path });
    }
    set((state) => {
      // Faqat eng oxirgi xabar xuddi shu chizma kartasi bo'lsa — takror kiritmaymiz.
      // (Preview'da ikki marta ketma-ket tahrirlashda dublikat oldini oladi, lekin
      // oraga chat xabari tushsa yangi karta ochiladi.)
      const last = state.messages[state.messages.length - 1];
      if (last?.kind === 'drawing' && last.path === path) return {};
      return {
        messages: [
          ...state.messages,
          { kind: 'drawing' as const, path, caption: caption || 'chizma yangilandi — ▶ tomosha qilish' },
        ],
      };
    });
  },
  pushAgentState: (state, detail) => {
    set((s) => ({
      messages: [
        ...s.messages,
        { kind: 'agent_state' as const, text: state, detail } as ChatMessage,
      ],
    }));
  },
  pushTaskResult: (text, opts) => {
    set((s) => ({
      messages: [
        ...s.messages,
        {
          kind: 'task_result' as const,
          text,
          name: opts?.name,
          status: opts?.status,
          duration_ms: opts?.duration_ms,
          engine: opts?.engine,
          diff: opts?.diff,
          completion: opts?.completion,
        } as ChatMessage,
      ],
    }));
  },
  pushBrainLog: (reason) => {
    const text = reason.trim();
    if (!text) return;
    // localStorage'ga ham yoziladi (sessiya id kalitida) — sahifa qayta
    // yuklanganda yoki suhbatga qaytilganda log doimiy saqlanadi.
    appendBrainLog(get().chatSessionId, text);
    set((state) => {
      // Xuddi shu sabab eng oxirgi log bo'lsa — takror kiritmaymiz (cooldown
      // tufayli qayta-qayta bir xil sabab chatga to'planib qolmaydi).
      const last = state.messages[state.messages.length - 1];
      if (last?.kind === 'log' && last.text === text) return {};
      return {
        messages: [...state.messages, { kind: 'log' as const, text }],
      };
    });
  },
  loadWorkspace: async (root?: string) => {
    try {
      const { agentWorkspace } = await import('../web/backend');
      const listing = await agentWorkspace(root);
      if (!listing.ok) return;
      const tree = buildTree(listing.entries);
      const rootName = listing.root.split(/[\\/]/).pop() || 'agent_workspace';
      set((state) => ({
        tree,
        rootName,
        expanded: new Set([...state.expanded, ...tree.map((t) => t.name)]),
        backendOnline: true,
      }));
    } catch {
      // offline — keep the mock tree
    }
  },
  handleSend: async () => {
    const { input, messages } = get();
    const text = input.trim();
    if (!text) return;

    // Oldingi stream'ni to'xtatamiz — yangi xabar yuborilganda eski SSE oqimi
    // yakunlangan xabarga yozmasligi uchun (abort -> reader.read() xato beradi,
    // catch fallback yo'liga tushadi, lekin taskRunning holati tozalanadi).
    activeStreamCtrl?.abort();
    setActiveStreamCtrl(null);

    set({
      input: '',
      mainView: 'chat',
      messages: [...messages, { role: 'user', text }, { kind: 'agent_state' as const, text: 'thinking', detail: 'So\'rov tahlil qilinmoqda...' } as ChatMessage],
      stage: 0,
      stageDetail: 'tahlil qilinmoqda…',
      taskRunning: true,
    });

    // Chat run davomida jonli pipeline poll (har ~1.2s) — PipelineStepper real
    // bosqichni ko'rsatadi: plan -> read/edit/test -> review, tool detallari bilan.
    // TOKEN STREAM'da stage voqealari ham shu buferga yoziladi — poll ikki yo'lga
    // ham ishlaydi (stream'da tokenlar asosiy manba, poll stepper uchun).
    let stopProgress: (() => void) | null = null;
    try {
      const { chatProgress } = await import('../web/backend');
      // So'rov boshlangandagi session id — chat davomida yangi suhbat ochilsa
      // ham poll shu suhbatning progressini kuzatadi.
      const pollSid = get().chatSessionId;
      const iv = setInterval(() => {
        (async () => {
          try {
            const p = await chatProgress(pollSid);
            if (p && p.active && p.stage) {
              const idx = STAGE_INDEX[p.stage];
              if (typeof idx === 'number') {
                set({ stage: idx, stageDetail: p.stage_detail || '' });
              }
            }
          } catch {
            // backend vaqtincha javob bermadi — keyingi tikka davom etadi
          }
        })();
      }, 1200);
      stopProgress = () => clearInterval(iv);

      // Real backend bridge (Igris_brain FastAPI server)
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'agent')
        .map((m) => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text || '' }));

      // TOKEN STREAM yo'li: /api/chat/stream — javob token-ketma-token keladi.
      // Agent javobi yozilayotganda foydalanuvchi darhol ko'radi (kutish yo'q).
      // Stream tugagach `done` voqeasi to'liq natijani beradi (tool'lar, rasm...).
      const streamed = await (async () => {
        // Abort signali — yangi xabar yuborilsa eski oqim to'xtatiladi
        const ctrl = new AbortController();
        setActiveStreamCtrl(ctrl);
        // To'plangan javob/fikrlash matni — catch'da ham (stream uzilganda
        // qisman javobni saqlash uchun) ko'rinishi kerak, shuning uchun try
        // TASHQARISIDA e'lon qilinadi.
        let finalContent = '';
        let finalThinking = '';
        // Ushbu oqimga tegishli streaming xabar indeksi — atayin to'xtatilganda
        // (yangi xabar yuborildi) faqat shu xabarning kursorini to'xtatamiz,
        // yangi oqimning xabariga tegmaymiz.
        let streamingIdx = -1;
        try {
          const { chatStream } = await import('../web/backend');
          let streamedOk = false;
          // Bo'sh agent xabari — tokenlar shu xabarga oqib boradi (jonli kursor).
          // Indeks saqlanadi — stream atayin to'xtatilsa aynan shu xabarning
          // kursorini to'xtatish uchun (boshqa oqimlarning xabariga tegmaymiz).
          set((state) => {
            streamingIdx = state.messages.length;
            return {
              messages: [...state.messages, { role: 'agent', text: '', streaming: true } as ChatMessage],
            };
          });
          const appendToken = (delta: string) => {
            set((state) => {
              const msgs = [...state.messages];
              const last = msgs[msgs.length - 1];
              if (last?.role === 'agent' && last.streaming) {
                msgs[msgs.length - 1] = { ...last, text: (last.text || '') + delta };
              }
              return { messages: msgs };
            });
          };
          // JONLI TOOL KARTOCHKALARI — stream davomida agent nima qilayotganini
          // real vaqtda ko'rsatadi (tool/mcp/skill start/done, layer eventlari).
          // Kartochna streaming agent xabarining OLDIGA qo'yiladi — tokenlar
          // oxirgi (streaming) xabarga to'g'ri oqib borishida davom etadi.
          const insertLiveTool = (msg: ChatMessage) => {
            set((state) => {
              const msgs = [...state.messages];
              let at = msgs.length;
              for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].role === 'agent' && msgs[i].streaming) { at = i; break; }
              }
              msgs.splice(at, 0, msg);
              return { messages: msgs };
            });
          };
          const finishLiveTool = (name: string, status: 'done' | 'error', detail?: string) => {
            set((state) => {
              const msgs = [...state.messages];
              for (let i = msgs.length - 1; i >= 0; i--) {
                const m = msgs[i];
                if (m.kind === 'toolcall' && m.status === 'running' && m.name === name) {
                  msgs[i] = { ...m, status, detail: detail || m.detail } as ChatMessage;
                  break;
                }
              }
              return { messages: msgs };
            });
          };
          await chatStream(text, history, get().chatSessionId, (ev) => {
            if (ctrl.signal.aborted) return; // eski stream — voqealarni o'tkazib yuboramiz
            if (ev.type === 'stage') {
              const idx = STAGE_INDEX[ev.stage || ''];
              if (typeof idx === 'number') {
                set({ stage: idx, stageDetail: ev.detail || ev.stage_detail || '' });
              }
            } else if (ev.type === 'thinking' && ev.content) {
              // qwen3 reasoning tokenlari — thinking blokiga token-ketma-token oqadi
              finalThinking += ev.content;
              set((state) => {
                const msgs = [...state.messages];
                const last = msgs[msgs.length - 1];
                if (last?.role === 'agent' && last.streaming) {
                  msgs[msgs.length - 1] = { ...last, thinking: (last.thinking || '') + ev.content };
                }
                return { messages: msgs };
              });
            } else if (ev.type === 'token' && ev.content) {
              finalContent += ev.content;
              appendToken(ev.content);
            } else if (ev.type === 'meta' && ev.session_id) {
              set({ chatSessionId: ev.session_id });
            } else if (ev.type === 'tool_start' && ev.tool) {
              // JONLI tool chaqiruvi — agent ishlayotgan paytda ko'rinadi
              // (LayeredAgent: {tool, layer, description})
              insertLiveTool({ kind: 'toolcall', name: ev.tool, status: 'running', detail: ev.description || '' } as ChatMessage);
            } else if (ev.type === 'tool_done' && ev.tool) {
              finishLiveTool(ev.tool, ev.status === 'error' ? 'error' : 'done', ev.result || ev.detail);
            } else if (ev.type === 'mcp_start' && ev.mcp) {
              insertLiveTool({ kind: 'toolcall', name: `mcp:${ev.mcp}`, status: 'running', detail: ev.description || '' } as ChatMessage);
            } else if (ev.type === 'mcp_done' && ev.mcp) {
              finishLiveTool(`mcp:${ev.mcp}`, ev.status === 'error' ? 'error' : 'done', ev.result || ev.detail);
            } else if (ev.type === 'skill_start' && ev.skill) {
              insertLiveTool({ kind: 'toolcall', name: `skill:${ev.skill}`, status: 'running', detail: ev.description || '' } as ChatMessage);
            } else if (ev.type === 'skill_done' && ev.skill) {
              finishLiveTool(`skill:${ev.skill}`, ev.status === 'error' ? 'error' : 'done', ev.result || ev.detail);
            } else if (ev.type === 'layer_start' && ev.layer) {
              // Qatlam boshlandi — stepper ham yangilanadi (pipeline stage bo'lsa)
              const lIdx = STAGE_INDEX[ev.layer];
              if (typeof lIdx === 'number') set({ stage: lIdx, stageDetail: ev.detail || ev.layer });
            } else if (ev.type === 'layer_done' && ev.layer) {
              const lIdx = STAGE_INDEX[ev.layer];
              if (typeof lIdx === 'number') set({ stage: lIdx + 1, stageDetail: ev.detail || `${ev.layer} tugadi` });
            } else if (ev.type === 'clarify' && ev.question) {
              // Layered agent clarification — userdan qo'shimcha ma'lumot so'ralmoqda
              // Multi-turn: turn/max_turns maydonlari orqali qaysi tur ekanligini ko'rsatadi
              const sessionId = ev.session_id || get().chatSessionId;
              const turnInfo = ev.turn && ev.max_turns
                ? ` [Turn ${ev.turn}/${ev.max_turns}]`
                : '';
              set((state) => ({
                pendingClarification: {
                  sessionId,
                  question: ev.question!,
                  turn: ev.turn,
                  maxTurns: ev.max_turns,
                },
                messages: [
                  ...state.messages,
                  { kind: 'clarify' as const, text: `${ev.question!}${turnInfo}`, sessionId } as ChatMessage,
                ],
              }));
            } else if (ev.type === 'done') {
              streamedOk = true;
              // Yakuniy natija — streaming xabarni to'liq holatga yakunlaymiz
              set((state) => {
                const msgs = [...state.messages];
                const last = msgs[msgs.length - 1];
                const toolMsgs: ChatMessage[] = (ev.tool_calls || []).map((tc) => ({
                  kind: 'toolcall',
                  name: tc.tool,
                  status: tc.result && tc.result.ok ? 'done' : 'error',
                  detail: typeof tc.args === 'object' && tc.args ? JSON.stringify(tc.args).slice(0, 90) : '',
                  diff: tc.result && tc.result.ok && tc.output_preview
                    ? tc.output_preview.split('\n').slice(0, 12).map((l) => `  ${l}`)
                    : undefined,
                }));
                const drawMsgs: ChatMessage[] = ev.image
                  ? [{ kind: 'drawing', path: ev.image, caption: 'agent bu chizmani chatda yaratdi — ▶ qurilishni tomosha qilish' }]
                  : [];
                const finalText = ev.content && ev.content.trim() ? ev.content : finalContent || 'I could not generate a response.';
                if (last?.role === 'agent' && last.streaming) {
                  msgs[msgs.length - 1] = {
                    role: 'agent',
                    text: finalText,
                    engine: ev.engine,
                    model: ev.model,
                    duration_ms: ev.duration_ms,
                    // structure_check fail — backend `done` voqeasida ogohlantirish
                    // yuboradi (transcript'ga yozilgan bilan BIR XIL matn).
                    warning: ev.warning || undefined,
                    // AGENTIK completion — ish yakuni konversatsiyaga to'ldiriladi
                    // (qaysi pipeline qurildi, qaysi bosqichlar/tool'lar ishladi).
                    completion: ev.completion || undefined,
                    // Backend done voqeasi TO'LIQ fikrlash matnini yuboradi —
                    // stream paytida biror chunk tushib qolsa ham ishonchli
                    // manba (lokal yig'ilgan finalThinking zaxira).
                    thinking: ev.thinking || finalThinking || last.thinking,
                  } as ChatMessage;
                }
                return {
                  backendOnline: true,
                  messages: [...msgs, ...toolMsgs, ...drawMsgs],
                };
              });
              if (ev.session_id) set({ chatSessionId: ev.session_id });
              // Task result — chat'ga natija qo'shish
              if (ev.tool_calls && ev.tool_calls.length > 0) {
                get().pushTaskResult(
                  `Bajarildi — ${ev.tool_calls.length} tool call`,
                  {
                    name: ev.tool_calls[0]?.tool,
                    status: 'done',
                    duration_ms: ev.duration_ms,
                    engine: ev.engine,
                    completion: ev.completion,
                  }
                );
              }
            } else if (ev.type === 'end') {
              if (ev.session_id) set({ chatSessionId: ev.session_id });
            }
          });
          if (!streamedOk) throw new Error('stream finished without done');
          get().loadChatHistory();
          get().loadWorkspace();
          return true;
        } catch (err) {
          // Stream UZILDI (tarmoq xatosi, idle timeout, backend xatosi).
          if (ctrl.signal.aborted) {
            // Foydalanuvchi YANGI xabar yuborib, bu oqimni ATAYIN to'xtatgan —
            // xabarlarga tegmaymiz va buffered fallback qilmaymiz (eski oqimning
            // qisman matni yangi oqimning xabarini ustiga yozib buzmasin). Faqat
            // shu oqimning o'z kursorini to'xtatamiz.
            if (streamingIdx >= 0) {
              set((state) => {
                const msgs = [...state.messages];
                const target = msgs[streamingIdx];
                if (target?.role === 'agent' && target.streaming) {
                  msgs[streamingIdx] = { ...target, streaming: false };
                }
                return { messages: msgs };
              });
            }
            return true;
          }
          if (finalContent.trim()) {
            // QISMAN javob kelgan — uni saqlab qolamiz va qayta generatsiya
            // QILMAYMIZ (dublikat yozuv + "javob g'oyib bo'ldi" hissi bo'lmasin).
            // Xatolik aniq ko'rsatiladi — foydalanuvchi qayta yuborishi mumkin.
            set((state) => {
              const msgs = [...state.messages];
              const last = msgs[msgs.length - 1];
              if (last?.role === 'agent' && last.streaming) {
                msgs[msgs.length - 1] = {
                  role: 'agent',
                  text: `${finalContent.trim()}\n\n⚠️ Javob to'liq emas — ulanish uzildi. Qayta yuboring.`,
                  thinking: finalThinking || last.thinking,
                } as ChatMessage;
              }
              return { messages: msgs };
            });
            return true;
          }
          if (err instanceof StreamError) {
            // Backend ANIQ xato yuborgan — generatsiya serverda boshlangan,
            // buffered re-run tarixga dublikat yozuv yozardi. Xatoni ko'rsatamiz.
            set((state) => ({
              messages: [
                ...state.messages.filter((m) => !(m.role === 'agent' && m.streaming)),
                { role: 'agent', text: `✗ Javob olinmadi — stream xatosi: ${err.message}` } as ChatMessage,
              ],
            }));
            return true;
          }
          // Umumiy tarmoq xatosi — backend so'rovni umuman ko'rmagan bo'lishi
          // mumkin; buffered /api/chat'ga qaytamiz (javob yo'qolmaydi).
          set((state) => ({
            messages: state.messages.filter((m) => !(m.role === 'agent' && m.streaming)),
          }));
          return false;
        } finally {
          if (activeStreamCtrl === ctrl) setActiveStreamCtrl(null);
        }
      })();
      if (streamed) return;

      // BUFFERED fallback: sinxron /api/chat (stream backend'da yo'q bo'lsa)
      const response = await bridgeChat(text, history, get().chatSessionId);
      if (response.session_id) set({ chatSessionId: response.session_id });
      // Chat davomida bajarilgan tool'lar — kartalar (art__draw_object_png kabi)
      const toolMsgs: ChatMessage[] = (response.tool_calls || []).map((tc) => ({
        kind: 'toolcall',
        name: tc.tool,
        status: tc.result && tc.result.ok ? 'done' : 'error',
        detail: typeof tc.args === 'object' && tc.args ? JSON.stringify(tc.args).slice(0, 90) : '',
        diff: tc.result && tc.result.ok && tc.output_preview
          ? tc.output_preview.split('\n').slice(0, 12).map((l) => `  ${l}`)
          : undefined,
      }));
      // Agent chatda rasm chizgan bo'lsa — inline live-build karta
      const drawMsgs: ChatMessage[] = response.image
        ? [{ kind: 'drawing', path: response.image, caption: 'agent bu chizmani chatda yaratdi — ▶ qurilishni tomosha qilish' }]
        : [];
      set((state) => ({
        backendOnline: true,
        messages: [
          ...state.messages,
          ...toolMsgs,
          ...drawMsgs,
          {
            role: 'agent',
            text: response.content,
            engine: response.engine,
            model: response.model,
            duration_ms: response.duration_ms,
            // AGENTIK completion — ish yakuni konversatsiyaga to'ldiriladi
            completion: response.completion || undefined,
          } as ChatMessage,
        ],
      }));
      get().loadChatHistory();
    } catch {
      // backend offline: fall back to Tauri invoke or demo/mock mode
      set({ backendOnline: false });
      try {
        if (tauriInvoke) {
          const response = await tauriInvoke('send_chat_message', { message: text });
          set((state) => ({
            messages: [...state.messages, { role: 'agent', text: response.content }],
          }));
        } else {
          // Yolg'on muvaffaqiyat simulyatsiya qilmaymiz — halol xato ko'rsatamiz
          set((state) => ({
            messages: [
              ...state.messages,
              {
                role: 'agent',
                text: 'Brain offline — chat javob olinmadi. Bridge\'ni ishga tushiring: `python server.py` (Igris_brain).',
              },
            ],
          }));
        }
      } catch (error) {
        console.error('Failed to send message:', error);
      }
    } finally {
      // Chat tugadi — progress poll to'xtatiladi, stepper idle holatga qaytadi
      stopProgress?.();
      set({ taskRunning: false, stage: 0, stageDetail: '' });
    }
  },
}));
