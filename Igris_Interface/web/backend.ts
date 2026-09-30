// IGRIS web bridge client — talks to the Igris_brain FastAPI server.
// Gracefully falls back to the legacy Tauri invoke / mock path when offline.

export interface BridgeChatToolCall {
  tool: string;
  args: Record<string, unknown>;
  result?: { ok?: boolean; error?: string };
  output_preview?: string;
}

export interface BridgeChatResult {
  ok: boolean;
  content: string;
  engine: string;
  model?: string;
  memory?: { recall_hits: number; context_chars: number };
  duration_ms?: number;
  api_ms?: number;
  /** Server tomonidan belgilangan (yoki qaytarilgan) chat suhbat id. */
  session_id?: string;
  /** Chat davomida bajarilgan tool chaqiruvlari (rasm chizish, sahifa ochish...). */
  tool_calls?: BridgeChatToolCall[];
  /** Agent yaratgan rasmning workspace'dagi nisbiy yo'li (masalan 'blue_apple.png'). */
  image?: string;
  /** AGENTIK completion — zarurat turiga qarab qurilgan pipeline ish yakuni
   * (qaysi pipeline, bosqichlar, tool'lar...). Konversatsiya shu bilan to'ldiriladi. */
  completion?: ChatCompletion;
}

/** Agentik work completion record — chat yakunida konversatsiyaga to'ldiriladi. */
export interface ChatCompletion {
  pipeline?: string;
  label?: string;
  stages?: string[];
  engine?: string;
  tools?: string[];
  subject?: string;
  framework?: string;
  language?: string;
  database?: string;
  planned_tools?: string[];
  status?: string;
  duration_ms?: number;
  image?: string;
  sub_pipelines?: string[];
}

export interface BridgeResolveResult {
  ok: boolean;
  query: string;
  status: string;
  confidence: number;
  engine: string;
  output: string;
  trace: string[];
  memory?: { recall_hits: number; context_chars: number };
  duration_ms?: number;
}

const DEFAULT_BACKEND = 'http://127.0.0.1:8765';
const TIMEOUT_MS = 90_000;

function backendUrl(): string {
  try {
    return localStorage.getItem('igris:backend') || DEFAULT_BACKEND;
  } catch {
    return DEFAULT_BACKEND;
  }
}

export function setBackendUrl(url: string): void {
  try {
    localStorage.setItem('igris:backend', url || DEFAULT_BACKEND);
  } catch {
    /* ignore */
  }
}

export function getBackendUrl(): string {
  return backendUrl();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${backendUrl()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`backend ${res.status}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export async function chat(
  message: string,
  history: { role: string; content: string }[],
  sessionId?: string,
): Promise<BridgeChatResult> {
  return post<BridgeChatResult>('/api/chat', {
    message,
    history,
    use_memory: true,
    session_id: sessionId || '',
  });
}

export interface ChatStreamEvent {
  type: 'meta' | 'stage' | 'thinking' | 'token' | 'done' | 'end' | 'error' | 'clarify' | 'layer_start' | 'layer_done' | 'tool_start' | 'tool_done' | 'mcp_start' | 'mcp_done' | 'skill_start' | 'skill_done' | 'final_result';
  /** stage voqealari: real pipeline bosqichi. */
  stage?: string;
  stage_detail?: string;
  detail?: string;
  /** thinking/token voqealari: fikrlash yoki javob bo'lagi. */
  content?: string;
  /** done voqeasi: to'liq chat natijasi (chat() bilan bir xil shakl). */
  engine?: string;
  /** done voqeasi: to'liq fikrlash (thinking) matni — stream qismlari tushib qolsa ham ishonchli. */
  thinking?: string;
  model?: string;
  memory?: { recall_hits: number; context_chars: number };
  duration_ms?: number;
  api_ms?: number;
  session_id?: string;
  tool_calls?: BridgeChatToolCall[];
  image?: string | null;
  /** done voqeasi: structure_check fail bo'lsa transcript ogohlantirishi. */
  warning?: string;
  /** done voqeasi: AGENTIK completion — pipeline ish yakuni konversatsiyaga to'ldiriladi. */
  completion?: ChatCompletion;
  /** clarify voqeasi: agent userdan qo'shimcha ma'lumot so'ramoqda. */
  question?: string;
  /** clarify: qaysi tur (1-based) va max tur soni. */
  turn?: number;
  max_turns?: number;
  /** layer events: layer nomi (layer_start/layer_done). */
  layer?: string;
  /** layer_done: qatlam holati. */
  status?: string;
  /** tool/mcp/skill events: vosita nomi. */
  tool?: string;
  mcp?: string;
  skill?: string;
  /** tool/mcp/skill_start: bajarilayotgan amal tavsifi (LayeredAgent). */
  description?: string;
  /** tool/mcp/skill_done: natija ko'rinishi (200 belgigacha). */
  result?: string;
  /** final_result: yakuniy natija. */
  layers_executed?: string[];
  reprompt?: { role?: string; complexity?: string };
  error?: string;
}

/** SSE stream'dagi xato — backend`dan xabar + aniq tur (swallow qilinmaydi). */
export class StreamError extends Error {
  constructor(message: string) {
    super(message || 'stream error');
    this.name = 'StreamError';
  }
}

/**
 * TOKEN-USTALI chat — /api/chat/stream SSE oqimini o'qiydi.
 *
 * Agent javobini bir necha daqiqa kutish o'rniga token-ketma-token oladi:
 * har `stage` voqeasi stepper'ni, har `token` voqeasi matn bo'lagini,
 * `done` esa yakuniy to'liq natijani beradi. `onEvent` har voqea uchun
 * chaqiriladi; stream tugagach resolve bo'ladi (xatoda reject).
 */
export async function chatStream(
  message: string,
  history: { role: string; content: string }[],
  sessionId: string | undefined,
  onEvent: (ev: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${backendUrl()}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, use_memory: true, session_id: sessionId || '' }),
    signal,
  });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  if (!res.body) throw new Error('no response body');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  // JONLI himoya: stream belgilangan vaqt ichida hech qanday bayt yubormasa
  // (uzilgan ulanish, backend qulashi, proxy osilishi) — reader bekor qilinadi
  // va read() xato bilan tugaydi. Sekin modelning uzoq sukutlari (buffered
  // kreativ/tool yo'llari, dastlabki token) ham hisobga olingan — 90s.
  // Foydalanuvchi abadiy "yozilmoqda" kursorida qolib ketmaydi.
  const IDLE_TIMEOUT_MS = 90_000;
  for (;;) {
    if (signal?.aborted) break;
    const timer = setTimeout(() => {
      // cancel() promise qaytaradi — u rad etsa ham (allaqachon bekor
      // qilingan) unhandled rejection bo'lmasligi uchun yutib yuboramiz.
      reader.cancel('stream idle').catch(() => {});
    }, IDLE_TIMEOUT_MS);
    let r: ReadableStreamReadResult<Uint8Array>;
    try {
      r = await reader.read();
    } finally {
      clearTimeout(timer);
    }
    if (r.done) break;
    buf += decoder.decode(r.value, { stream: true });
    // SSE: voqealar bo'sh qator bilan ajratiladi (data: {...}\n\n)
    let sep = buf.indexOf('\n\n');
    while (sep >= 0) {
      const chunk = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ')) continue;
        let ev: ChatStreamEvent;
        try {
          ev = JSON.parse(line.slice(6)) as ChatStreamEvent;
        } catch {
          continue; // malformed chunk — o'tkazib yuboramiz
        }
        if (ev.type === 'error') {
          // Backend xatosi — aniq StreamError sifatida yuqoriga uzatiladi
          throw new StreamError(ev.error || 'stream error');
        }
        onEvent(ev);
      }
      sep = buf.indexOf('\n\n');
    }
  }
}

export interface ChatProgressResult {
  ok: boolean;
  /** Chat hozir ishlayaptimi (progress buferida yozuv bormi). */
  active: boolean;
  /** REAL pipeline bosqichi: plan | read | edit | test | review. */
  stage?: string;
  /** Jonli detal — bajarilayotgan tool ("read_file → src/main.py"). */
  stage_detail?: string;
  ts?: number;
}

// ------------------------------------------------------------------ //
// Clarification flow — layered agent clarification layer
// ------------------------------------------------------------------ //

export interface ClarifyResult {
  ok: boolean;
  message?: string;
}

export interface ClarifyStatusResult {
  ok: boolean;
  pending: boolean;
  question?: string;
  answer?: string;
  status?: string;
}

/**
 * Clarification javobi — layered agent clarification layer kutayotgan javob.
 * Frontend clarify eventini olgandan keyin user javobini shu endpointga
 * POST qiladi.
 */
export async function clarifyChat(sessionId: string, answer: string): Promise<ClarifyResult> {
  return post<ClarifyResult>('/api/chat/clarify', { session_id: sessionId, answer });
}

/**
 * Clarification sessiyasi holati — frontend polling uchun.
 */
export async function clarifyStatus(sessionId: string): Promise<ClarifyStatusResult> {
  const res = await fetch(
    `${backendUrl()}/api/chat/clarify/status?session_id=${encodeURIComponent(sessionId || '')}`,
    { signal: AbortSignal.timeout(5000) },
  );
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ClarifyStatusResult;
}

// ------------------------------------------------------------------ //
// Clarification analytics — RefactorView uchun
// ------------------------------------------------------------------ //

export interface ClarificationAnalytics {
  ok: boolean;
  enabled: boolean;
  total_clarifications: number;
  total_questions: number;
  avg_questions_per_session: number;
  common_questions: { question: string; count: number }[];
  common_answers: { answer: string; count: number }[];
  clarification_rate?: number;
  success_rate?: number;
  error?: string;
}

/**
 * Clarification tahlili — chastota, naqshlar, samaradorlik.
 * RefactorView uchun clarification analytics ma'lumotlari.
 */
export async function clarificationAnalytics(): Promise<ClarificationAnalytics> {
  const res = await fetch(
    `${backendUrl()}/api/memory/clarification-analytics`,
    { signal: AbortSignal.timeout(8000) },
  );
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ClarificationAnalytics;
}

/**
 * Chat run davomidagi JONLI pipeline bosqichi — frontend har ~1.2s so'raydi.
 * /api/chat sinxron ishlayotganda stepper shu manbadan real progress oladi
 * (soxta/bezak emas — agentning haqiqiy bosqichi).
 */
export async function chatProgress(sessionId: string): Promise<ChatProgressResult> {
  const res = await fetch(
    `${backendUrl()}/api/chat/progress?session_id=${encodeURIComponent(sessionId || '')}`,
    { signal: AbortSignal.timeout(5000) },
  );
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ChatProgressResult;
}

export interface ChatHistoryItem {
  id: string;
  title: string;
  /** Epoch soniya (updated_at) — frontend nisbiy vaqtga aylantiradi. */
  time: number;
  preview: string;
  messages: number;
  starred: boolean;
  unread: boolean;
}

export interface ChatHistoryResult {
  ok: boolean;
  conversations: ChatHistoryItem[];
}

/** REAL chat tarixi — sidebar recents va 2nd Brain grafi uchun. */
export async function chatHistory(limit = 30): Promise<ChatHistoryResult> {
  const res = await fetch(`${backendUrl()}/api/chat/history?limit=${limit}`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ChatHistoryResult;
}

export async function resolveQuery(query: string): Promise<BridgeResolveResult> {
  return post<BridgeResolveResult>('/api/resolve', { query, allow_llm: true, use_memory: true });
}

// --------------------------------------------------------------------- //
// Chat history actions (star / rename / delete / open conversation)
// --------------------------------------------------------------------- //

export interface ChatActionResponse {
  ok: boolean;
  id?: string;
  title?: string;
  starred?: boolean;
  deleted?: boolean;
  error?: string;
}

export interface ChatConversationResult {
  ok: boolean;
  conversation?: {
    id: string;
    title: string;
    starred: boolean;
    messages: { role: string; text: string; ts: number; warning?: string }[];
  };
  error?: string;
}

export async function chatStar(id: string, starred: boolean): Promise<ChatActionResponse> {
  return post<ChatActionResponse>('/api/chat/star', { id, starred });
}

export async function chatRename(id: string, title: string): Promise<ChatActionResponse> {
  return post<ChatActionResponse>('/api/chat/rename', { id, title });
}

export async function chatDelete(id: string): Promise<ChatActionResponse> {
  return post<ChatActionResponse>('/api/chat/delete', { id });
}

/** BARCHA suhbatlar + CAG keshni tozalaydi ("oldingi natijalarni tozala"). */
export async function chatClear(): Promise<{ ok: boolean; removed: number }> {
  return post<{ ok: boolean; removed: number }>('/api/chat/clear', {});
}

/** Bitta suhbatni to'liq yuklaydi (sidebar'dan chat ochilganda). */
export async function chatConversation(id: string): Promise<ChatConversationResult> {
  const res = await fetch(`${backendUrl()}/api/chat/${encodeURIComponent(id)}`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ChatConversationResult;
}

// --------------------------------------------------------------------- //
// System services (backend / ollama status + restart from the UI)
// --------------------------------------------------------------------- //

export interface SystemServicesResult {
  ok: boolean;
  backend?: { running: boolean; host?: string; port?: number; version?: string };
  ollama?: { running: boolean };
  /** Watchdog (auto-restart qo'riqchisi) — backend qulab tushsa avtomatik qayta ishga tushiradi. */
  watchdog?: {
    running: boolean;
    backend_up?: boolean;
    ollama_up?: boolean;
    /** Watchdog tomonidan qilingan backend restarts soni. */
    backend_restarts?: number;
    ollama_restarts?: number;
    last_restart?: number | null;
    checked_at?: number | null;
    last_error?: string | null;
  };
  mcp?: { connected: boolean; servers?: string[]; degraded?: boolean };
  /** S3: silent-degradation registry — komponent jim zaif rejimga o'tganda mark bo'ladi. */
  degradations?: DegradationEntry[];
  /** So'nggi 10 daqiqada mark qilingan degradatsiyalar soni (0 = hammasi sog'lom). */
  degradations_active?: number;
  timestamp?: number;
  error?: string;
}

/** S3: bitta silent-fallback yozuvi (logs/degradations.json). */
export interface DegradationEntry {
  /** Qayerda: "mcp.web_ai_bridge", "memory.keyword-index", "agent.cag"... */
  component: string;
  /** Nega: import xatosi / ulanmadi / timeout... (qisqa matn). */
  reason: string;
  /** Nimaga qaytdi: "BM25Index", "no-tools", "disabled"... */
  fallback?: string;
  /** Unix timestamp (so'nggi mark vaqti). */
  ts: number;
  /** Necha marta mark qilingan (bir xil component+fallback). */
  count?: number;
}

export async function systemServices(): Promise<SystemServicesResult> {
  const res = await fetch(`${backendUrl()}/api/system/services`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as SystemServicesResult;
}

/** Backend'ni o'zini qayta ishga tushiradi (javob darhol qaytadi). */
export async function systemRestart(): Promise<{ ok: boolean; restarting?: boolean; port?: number; error?: string }> {
  return post<{ ok: boolean; restarting?: boolean; port?: number; error?: string }>('/api/system/restart', {});
}

/** S3: silent-degradation registry tozalash (UI Settings→Services 'clear'). */
export async function clearDegradations(): Promise<{ ok: boolean; cleared?: number; error?: string }> {
  return post<{ ok: boolean; cleared?: number; error?: string }>('/api/system/degradations/clear', {});
}

/** Ollama serve'ni ishga tushiradi (agar ishlamayotgan bo'lsa). */
export async function ollamaStart(): Promise<{ ok: boolean; running?: boolean; started?: boolean; note?: string; error?: string }> {
  return post<{ ok: boolean; running?: boolean; started?: boolean; note?: string; error?: string }>('/api/system/ollama/start', {});
}

/** Ollama serve'ni qayta ishga tushiradi (eski jarayon o'ldirilib, yangisi ochiladi). */
export async function ollamaRestart(): Promise<{ ok: boolean; running?: boolean; started?: boolean; note?: string; error?: string }> {
  return post<{ ok: boolean; running?: boolean; started?: boolean; note?: string; error?: string }>('/api/system/ollama/restart', {});
}

/** LLM qayta sinab ko'radi — circuit breaker reset + avtomatik tekshirish. */
export async function retryLLM(): Promise<{ ok: boolean; available?: boolean; model?: string; error?: string }> {
  return post<{ ok: boolean; available?: boolean; model?: string; error?: string }>('/api/circuit/reset', {});
}

/** Agent'ni majburiy qayta yaratadi — circuit reset + agent rebuild. */
export async function rebuildAgent(): Promise<{ ok: boolean; model?: string; circuit?: { state: string }; error?: string }> {
  return post<{ ok: boolean; model?: string; circuit?: { state: string }; error?: string }>('/api/agent/rebuild', {});
}

export interface AgentStep {
  id: number;
  title: string;
  tools: string[];
  detail: string;
}

export interface AgentPlan {
  ok: boolean;
  goal: string;
  steps: AgentStep[];
  engine?: string;
}

export interface AgentRunResult {
  ok: boolean;
  task: string;
  status: string;
  plan: AgentPlan;
  steps: {
    id: number;
    title: string;
    tools: string[];
    status: string;
    result: unknown;
  }[];
  tool_calls: {
    step: number;
    step_title: string;
    tool: string;
    args: Record<string, unknown>;
    result: { ok?: boolean; error?: string };
    output_preview?: string;
  }[];
  stats: { steps: number; tool_calls: number; corrections: number; duration_ms: number };
}

export async function agentPlan(task: string): Promise<AgentPlan> {
  return post<AgentPlan>('/api/agent/plan', { task });
}

export async function agentRun(task: string): Promise<AgentRunResult> {
  return post<AgentRunResult>('/api/agent/run', { task });
}

export interface HITLTaskResult {
  ok: boolean;
  run_id: string;
}

export interface HITLRunState {
  ok: boolean;
  id: string;
  status: 'running' | 'awaiting_human' | 'done' | 'error' | 'not_found';
  question?: string | null;
  task?: string;
  error?: string | null;
  /** REAL pipeline progress — executor jonli yuboradi (plan/read/edit/test/review). */
  stage?: string | null;
  stage_detail?: string | null;
  last_tool?: string | null;
  tool_count?: number;
  /** RUN DAVOMIDA bajarilgan tool'lar (qisman) — jonli chizma kartalari uchun. */
  tool_calls?: {
    tool: string;
    args: Record<string, unknown>;
    result: { ok?: boolean; error?: string };
    output_preview?: string;
  }[];
  result?: {
    status: string;
    engine?: string;
    final?: string;
    tool_calls?: {
      tool: string;
      args: Record<string, unknown>;
      result: { ok?: boolean; error?: string };
      output_preview?: string;
    }[];
    stats?: { steps: number; tool_calls: number; corrections: number; duration_ms: number };
  } | null;
}

export async function agentTask(task: string, sessionId?: string): Promise<HITLTaskResult> {
  return post<HITLTaskResult>('/api/agent/task', {
    task,
    session_id: sessionId || '',
  });
}

export async function agentRunStatus(runId: string): Promise<HITLRunState> {
  const res = await fetch(`${backendUrl()}/api/agent/run/${runId}`, { signal: AbortSignal.timeout(8000) });
  // 404 = run endi mavjud emas (backend restart/quiymat yo'qolgan). Throw o'rniga
  // aniq status qaytaramiz — frontend poll cheksiz aylanib qolmaydi va foydalanuvchi
  // "task chala qoldi" holatida qolmaydi.
  if (res.status === 404) {
    return { ok: false, id: runId, status: 'not_found' } as HITLRunState;
  }
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as HITLRunState;
}

export async function agentRespond(runId: string, answer: string): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>('/api/agent/respond', { run_id: runId, answer });
}

export interface DrawingEditStart {
  ok: boolean;
  run_id: string;
}

/**
 * Paused live-build uchun surgikal chizma tahriri.
 * frozen: { revealed, total, elements } — qaysi elementlar allaqachon chizilgan.
 */
export async function drawingEdit(
  path: string,
  request: string,
  frozen: { revealed?: number; total?: number; elements?: string[] },
): Promise<DrawingEditStart> {
  return post<DrawingEditStart>('/api/agent/drawing/edit', {
    path,
    request,
    frozen: frozen || {},
  });
}

export interface BrainGraphNode {
  id: string;
  label: string;
  kind: 'fact' | 'session' | 'pattern' | 'architecture';
  x: number;
  y: number;
  detail?: string;
  /** Suhbat (session) node'larida: oxirgi yangilanish vaqti (epoch sekund). */
  updated_at?: number;
}

export interface BrainGraphResult {
  ok: boolean;
  nodes: BrainGraphNode[];
  links: [string, string][];
  /** Link sabablari: 'a|b' -> umumiy so'zlar (zoom'da "nima uchun bog'langan"). */
  link_reasons?: Record<string, string[]>;
  stats?: {
    vault_files: number;
    persistent_entries: number;
    runtime_entries: number;
    chat_sessions: number;
    nodes: number;
    links: number;
  };
}

/**
 * Fetch the REAL 2nd Brain knowledge graph from Igris_Memory.
 * `shares` — ixtiyoriy kvota ulushlari (vault, chat, persistent, runtime) —
 * `maxNodes` — ixtiyoriy graf node chegarasi. Sozlamalar panelidan yuboriladi;
 * bo'lmasa backend diskdagi/default'ini ishlatadi (graph_shares.json'da
 * saqlangan sozlamalar avtomatik qo'llanadi).
 */
export async function brainGraph(shares?: number[], maxNodes?: number, signal?: AbortSignal): Promise<BrainGraphResult> {
  const q = new URLSearchParams();
  if (shares && shares.length === 4) q.set('shares', shares.map((s) => s.toFixed(2)).join(','));
  if (maxNodes && maxNodes > 0) q.set('max_nodes', String(maxNodes));
  const qs = q.toString();
  const ctrl = new AbortController();
  const timer = signal ? undefined : setTimeout(() => ctrl.abort(), 8000);
  if (signal) signal.addEventListener('abort', () => ctrl.abort());
  try {
    const res = await fetch(`${backendUrl()}/api/brain/graph${qs ? `?${qs}` : ''}`, {
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`backend ${res.status}`);
    return (await res.json()) as BrainGraphResult;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/** Server'da saqlangan graf sozlamalari (restart'da ham qoladi). */
export interface BrainGraphSharesResult {
  ok: boolean;
  shares: number[];
  /** Graf node'larining yuqori chegarasi (max_nodes) — panel slider'dan sozlanadi. */
  max_nodes?: number | null;
  /** Oxirgi o'zgarish vaqti (epoch sekund) — panelda "qachon o'zgargan". */
  updated_at?: number | null;
  /** O'zgarishlar tarixi: [{ts, shares, max_nodes}] — qachon, qaysi qiymatga. */
  history?: { ts: number; shares: number[]; max_nodes?: number | null }[];
}

/**
 * 2nd Brain graf sozlamalarini server'dan oladi — localStorage emas, backend
 * graph_shares.json faylida persist qilinadi (restart'da yo'qolmaydi).
 */
export async function brainGraphShares(): Promise<BrainGraphSharesResult> {
  const res = await fetch(`${backendUrl()}/api/brain/graph/shares`, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as BrainGraphSharesResult;
}

/**
 * Graf sozlamalarini server'da saqlaydi — keyingi yuklanishda qo'llaniladi.
 * Ikkala parametr ham ixtiyoriy: berilmagani server'da joriy qiymatini
 * saqlaydi (qisman yangilash — masalan faqat max_nodes o'zgartirilsa
 * ulushlar buzilmaydi).
 */
export async function saveBrainGraphShares(shares?: number[], maxNodes?: number): Promise<BrainGraphSharesResult> {
  const body: Record<string, unknown> = {};
  if (shares && shares.length === 4) body.shares = shares;
  if (maxNodes && maxNodes > 0) body.max_nodes = maxNodes;
  return post<BrainGraphSharesResult>('/api/brain/graph/shares', body);
}

export interface BrainGraphVersionResult {
  ok: boolean;
  /** Deterministik fingerprint — manba fayllar o'zgarsa raqam o'zgaradi. */
  version: number;
  sources?: number;
  /** So'nggi SEZILARLI o'zgarish sababi (masalan "yangi xotira moduli:
   *  03-new-module.jsonl" yoki "yangi suhbat: ...") — graf nega yangilangani
   *  shu maydondan ko'rsatiladi (real sabab). O'zgarish bo'lmasa null. */
  reason?: string | null;
  /** So'nggi SEZILARLI o'zgarish vaqti (epoch sekund) — graf qachondan beri
   *  turg'un (yoki qachon yangilangani). O'zgarish bo'lmagan bo'lsa null. */
  changed_at?: number | null;
}

/**
 * Graf manbalari versiyasi — REAL VAQT yangilanishi uchun engil polling.
 * Frontend har ~8 soniyada shuni so'raydi; grafik faqat versiya o'zgarganda
 * qayta yuklanadi (2nd Brain + memory update'lar deyarli oniy ko'rinadi).
 */
export async function brainGraphVersion(): Promise<BrainGraphVersionResult> {
  const res = await fetch(`${backendUrl()}/api/brain/graph/version`, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as BrainGraphVersionResult;
}

export interface SpeedSettingsResult {
  ok: boolean;
  /** Universal tez rejim (TURBO) — barcha modellarga birdek qo'llanadi. */
  turbo: boolean;
  fast_model: string | null;
  model: string;
}

/** Universal TURBO rejim holati (BIR kalit — har qanday LLM tezlashadi). */
export async function speedSettings(): Promise<SpeedSettingsResult> {
  const res = await fetch(`${backendUrl()}/api/settings/speed`, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as SpeedSettingsResult;
}

export async function setSpeed(turbo: boolean): Promise<SpeedSettingsResult> {
  return post<SpeedSettingsResult>('/api/settings/speed', { turbo });
}

export async function ping(): Promise<boolean> {
  try {
    // Part N: yengil /api/health — agent/LLM'ga TEGMAYDI (status agent.status()
    // orqali Ollama'ni tekshirib, band bo'lganda bloklanib "offline" berardi).
    const res = await fetch(`${backendUrl()}/api/health`, { signal: AbortSignal.timeout(2500) });
    return res.ok;
  } catch {
    return false;
  }
}

export interface AgentStatusResult {
  ok: boolean;
  agent?: { bricks: number; rules: number; chains: string[] };
  llm?: {
    enabled: boolean;
    available: boolean;
    model: string;
    /** Nega LLM ishlamayapti — UI'da ko'rsatiladi (model topilmadi / offline). */
    error?: string | null;
    /** Universal tez rejim (TURBO). */
    turbo?: boolean;
    fast_model?: string | null;
    /** Graceful degradation holati. */
    degraded?: boolean;
    failure_count?: number;
  };
  memory?: { enabled: boolean; error?: string | null };
  /** 12 intellekt arxitekturasi (BuildIntalaganceInstructionRequest.md) holati. */
  intelligence?: { enabled: boolean; modules: string[] };
  /** Circuit breaker holati. */
  circuit?: {
    state: string;
    failure_count: number;
    last_failure: number;
    last_success: number;
    open_since: number | null;
  };
}

/** Real agent status — model, LLM mavjudligi, RAG memory holati. */
export async function agentStatus(): Promise<AgentStatusResult> {
  const res = await fetch(`${backendUrl()}/api/status`, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as AgentStatusResult;
}

/** INTELLEKT qatlami holati — har bir modulning real statistikasi. */
export interface IntelligenceStatus {
  ok: boolean;
  enabled: boolean;
  modules: string[];
  harm_filter?: { checks: number; blocks: number; rules: string[] };
  user_model?: { language: string; detail_level: string; tone: string };
  tone_detect?: { scans: number; last?: { emotion: string } | null };
  self_eval?: { evaluations: number };
  logic?: { structure_checks: number };
  spatial?: { analyses: number };
  creative?: { generations: number };
  naturalist?: { classifications: number };
  music?: { scans: number };
  timestamp?: number;
}

export async function intelligenceStatus(): Promise<IntelligenceStatus> {
  const res = await fetch(`${backendUrl()}/api/intelligence/status`, { signal: AbortSignal.timeout(4000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as IntelligenceStatus;
}

/** Ollama'dagi real mavjud modellar ro'yxati. */
export async function llmModels(): Promise<string[]> {
  const res = await fetch(`${backendUrl()}/api/llm/models`, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  const data = (await res.json()) as { ok: boolean; models?: string[] };
  return data.models || [];
}

export interface LlmModelDetail {
  name: string;
  parameter_size: string;
  quantization: string;
  size_gb: number;
}

/** Model nomi + hajm/o'lcham — Settings'da sifat bo'yicha tanlash uchun. */
export async function llmModelDetails(): Promise<LlmModelDetail[]> {
  const res = await fetch(`${backendUrl()}/api/llm/models/detail`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  const data = (await res.json()) as { ok: boolean; models?: LlmModelDetail[] };
  return data.models || [];
}

/** Ishlayotgan modelni jonli almashtiradi. */
export async function setModel(model: string): Promise<{ ok: boolean; model: string }> {
  return post<{ ok: boolean; model: string }>('/api/llm/model', { model });
}

export interface WebAITab {
  index: number;
  active: boolean;
  url: string;
  title: string;
}

export interface WebAIStatus {
  ok: boolean;
  connected: boolean;
  tabs: WebAITab[];
  browser?: { channel?: string | null; mode?: string | null };
  info?: string;
  error?: string;
}

/** Real web-ai-bridge holati (browser + ochiq tablar). */
export async function webaiStatus(): Promise<WebAIStatus> {
  const res = await fetch(`${backendUrl()}/api/webai/status`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as WebAIStatus;
}

export interface WebAIActionResult {
  ok: boolean;
  output?: string;
  content?: string;
  error?: string;
}

/** Whitelisted browser amali — navigate/back/forward/new_tab/switch_tab/close_tab/refresh/scroll/zoom/... */
export async function webaiAction(
  action: string,
  opts?: { url?: string; index?: number },
): Promise<WebAIActionResult> {
  return post<WebAIActionResult>('/api/webai/action', {
    action,
    url: opts?.url || '',
    index: opts?.index ?? 0,
  });
}

/**
 * Aktiv tabning real screenshot URL'i (har yangilanishda yangi t param).
 * full=true — scroll qilib bo'ladigan to'liq sahifa rasmi.
 */
export function webaiScreenshotUrl(full = false): string {
  const f = full ? '&full=1' : '';
  return `${backendUrl()}/api/webai/screenshot?t=${Date.now()}${f}`;
}

/** Aktiv tabning ko'rinadigan matni (ads/cookie banner tozalangan). */
export async function webaiPageText(): Promise<string> {
  const r = await webaiAction('page_text');
  if (!r.ok) throw new Error(r.error || 'page text unavailable');
  return r.output || r.content || '';
}

export interface WorkspaceEntry {
  path: string;
  type: 'dir' | 'file';
}

export interface WorkspaceListing {
  ok: boolean;
  root: string;
  entries: WorkspaceEntry[];
}

export async function agentWorkspace(ws?: string): Promise<WorkspaceListing> {
  const q = ws ? `?ws=${encodeURIComponent(ws)}` : '';
  const res = await fetch(`${backendUrl()}/api/agent/workspace${q}`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as WorkspaceListing;
}

/** URL that serves a workspace file (image / text) for the preview pane. */
export function workspaceFileUrl(path: string, root?: string): string {
  const q = new URLSearchParams({ path });
  if (root) q.set('ws', root);
  return `${backendUrl()}/api/agent/workspace/file?${q.toString()}`;
}

/** Fetch the text content of a workspace file (e.g. .py, .md, .json). */
export async function workspaceFileText(path: string): Promise<string> {
  const res = await fetch(workspaceFileUrl(path), { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return await res.text();
}

// --------------------------------------------------------------------- //
// Universal UI Composition — spec -> qavatlar / exec_order / overlap
// --------------------------------------------------------------------- //

export interface UiComposeResult {
  ok: boolean;
  errors?: string[];
  canvas?: { w: number; h: number };
  /** Puzzle qatlamlari (barglar -> ildiz). */
  layers?: string[][];
  /** To'liq yig'ish tartibi. */
  exec_order?: string[];
  stage_plan?: { stage: string; title: string; element_count: number; start_exec: number; end_exec: number }[];
  /** Bosh menyu kontentga xalaqit qiladimi — tekshiruv natijalari. */
  overlaps?: { stage_a: string; stage_b: string; el_a: unknown; el_b: unknown; severity: string; msg: string }[];
  bounds?: string[];
  bricks?: { total_elements: number; unique_bricks: number; reusable_bricks: number; reuse_ratio: number; top_bricks: unknown[] };
  issues_total?: number;
  spec?: unknown;
}

/** UI build spec uchun universal kompozitsiya rejasini oladi. */
export async function uiCompose(appName: string, theme = 'dark'): Promise<UiComposeResult> {
  const res = await fetch(`${backendUrl()}/api/ui/compose?app_name=${encodeURIComponent(appName)}&theme=${encodeURIComponent(theme)}`, {
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as UiComposeResult;
}

// --------------------------------------------------------------------- //
// Refactor Machine — real assessment / telemetry (aniqlik & sabablilik)
// --------------------------------------------------------------------- //

export interface RefactorInventory {
  items: number;
  by_category: Record<string, number>;
  avg_quality: number;
  dimension_averages: Record<string, number>;
}

export interface RefactorTelemetrySnapshot {
  window_size: number;
  total_events: number;
  ok_rate: number;
  partial_rate: number;
  failed_rate: number;
  avg_confidence: number;
  confidence_declining: boolean;
  llm_usage_rate: number;
  healed_rate: number;
  top_chains: Record<string, number>;
  suggestions: string[];
}

export interface RefactorTelemetryResult {
  ok: boolean;
  stats: {
    total_events: number;
    snapshots: number;
    last: RefactorTelemetrySnapshot | null;
  };
  trend: RefactorTelemetrySnapshot[];
}

export interface RefactorClassification {
  item_id: string;
  category: 'brick' | 'experience' | 'derived';
  brickness: number;
  experientiality: number;
  reasons: string[];
}

export interface RefactorLink {
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface RefactorReport {
  ok: boolean;
  standard?: string;
  inventory?: RefactorInventory;
  links?: { total_links: number; nodes: number; by_type: Record<string, number> };
  telemetry?: { total_events: number; snapshots: number; last?: RefactorTelemetrySnapshot | null };
  classifications?: RefactorClassification[];
  top_links?: RefactorLink[];
}

export interface RefactorAssessResult {
  ok: boolean;
  query: string;
  query_semantics?: {
    tokens: number;
    ambiguity: number;
    semantic_clarity: number;
    language: string;
  };
  resolution?: {
    status: string;
    confidence: number;
    engine?: string;
    output?: string;
    chains?: string[];
    duration_ms?: number;
  };
  telemetry_snapshot?: RefactorTelemetrySnapshot;
}

/** To'liq refactor hisoboti — inventory, tasniflar, aloqalar, telemetry. */
export async function refactorReport(): Promise<RefactorReport> {
  const res = await fetch(`${backendUrl()}/api/refactor/report`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as RefactorReport;
}

/** Jarayon telemetry — stats + oxirgi snapshotlar trendi. */
export async function refactorTelemetry(): Promise<RefactorTelemetryResult> {
  const res = await fetch(`${backendUrl()}/api/refactor/telemetry`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as RefactorTelemetryResult;
}

/** So'rovni baholash — query semantikasi + resolution + telemetry snapshot. */
export async function refactorAssess(query: string, lang = 'en'): Promise<RefactorAssessResult> {
  return post<RefactorAssessResult>('/api/refactor/assess', { query, lang });
}

// --------------------------------------------------------------------- //
// Decision-quality probe — real agent runs, reasoning scores
// --------------------------------------------------------------------- //

export interface ProbeScores {
  tool_selection: number;
  args_correctness: number;
  reasoning: number;
  recovery: number;
  outcome: number;
}

export interface ProbeTaskResult {
  id: string;
  task: string;
  scores: ProbeScores;
  trace?: {
    status: string;
    duration_s: number;
    tool_calls: { tool: string; ok: boolean; preview?: string }[];
    final_text: string;
  };
}

export interface ProbeReport {
  model: string;
  tasks: ProbeTaskResult[];
  aggregate?: Partial<ProbeScores>;
}

export interface ProbeRunResult {
  ok: boolean;
  run_id: string;
}

export interface ProbeRunState {
  ok: boolean;
  id: string;
  status: 'running' | 'done' | 'error';
  tasks?: string;
  completed?: string[];
  error?: string | null;
  report?: ProbeReport | null;
}

export interface ProbeReportResult {
  ok: boolean;
  exists: boolean;
  report?: ProbeReport | null;
  error?: string;
}

/** Decision-quality probe'ni fon thread'ida boshlaydi (server). */
export async function probeRun(tasks = 'all'): Promise<ProbeRunResult> {
  return post<ProbeRunResult>('/api/probe/run', { tasks });
}

export async function probeRunStatus(runId: string): Promise<ProbeRunState> {
  const res = await fetch(`${backendUrl()}/api/probe/run/${runId}`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ProbeRunState;
}

/** Eng so'nggi probe hisoboti (decision_probe.json). */
export async function probeReport(): Promise<ProbeReportResult> {
  const res = await fetch(`${backendUrl()}/api/probe/report`, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as ProbeReportResult;
}

// --------------------------------------------------------------------- //
// Agent State — real-time agent status for status panel
// --------------------------------------------------------------------- //

export interface AgentCapability {
  name: string;
  icon: string;
  description: string;
  enabled: boolean;
  tools: string[];
}

export interface AgentStateResult {
  ok: boolean;
  state: string;
  current_task?: string;
  current_step?: string;
  capabilities: AgentCapability[];
  task_queue: any[];
  completed_today: number;
  tools_available: number;
  memory_entries: number;
  uptime_seconds: number;
  auto_mode: boolean;
}

/** Agent real-time holati — status panel uchun. */
export async function agentState(): Promise<AgentStateResult> {
  const res = await fetch(`${backendUrl()}/api/agent/state`, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`backend ${res.status}`);
  return (await res.json()) as AgentStateResult;
}
