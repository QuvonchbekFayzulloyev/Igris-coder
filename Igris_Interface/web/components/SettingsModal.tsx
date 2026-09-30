import React, { useState, useEffect } from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import type { LlmModelDetail, SystemServicesResult } from '../backend';

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

/** Sifat bo'yicha tavsiya tartibi — foydalanuvchiga to'g'ri model tanlashda yordam. */
const MODEL_QUALITY: { name: string; rank: number; note: string }[] = [
  { name: 'qwen3:8b', rank: 1, note: 'Eng yaxshi — haqiqiy fikrlash + ishonchli tool-calling (≥8 GB RAM)' },
  { name: 'qwen2.5-coder:7b', rank: 2, note: 'Kodga ixtisoslashgan, o‘rtacha tool-calling' },
  { name: 'qwen3:4b', rank: 3, note: 'qwen3 fikrlashi, kichik — RAM kam bo‘lsa (4-6 GB)' },
  { name: 'qwen2.5:7b', rank: 4, note: 'Universal, o‘rtacha' },
  { name: 'qwen3:1.7b', rank: 5, note: 'Kichik, zaif apparat uchun' },
  { name: 'qwen2.5-coder:1.5b', rank: 6, note: 'Faqat juda zaif apparatda — sifat pasayadi' },
  { name: 'qwen2.5:1.5b', rank: 7, note: 'Faqat juda zaif apparatda — sifat pasayadi' },
];

function modelNote(name: string): string | null {
  const m = MODEL_QUALITY.find((x) => name === x.name);
  return m ? m.note : null;
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [tab, setTab] = useState<'model' | 'backend' | 'providers' | 'services'>('model');
  const [models, setModels] = useState<string[]>([]);
  const [modelDetails, setModelDetails] = useState<LlmModelDetail[]>([]);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [ctx, setCtx] = useState(60);
  const [trim, setTrim] = useState(true);
  const backendUrl = useAgentConsoleStore((s) => s.backendUrl);
  const setBackendUrl = useAgentConsoleStore((s) => s.setBackendUrl);
  const agentInfo = useAgentConsoleStore((s) => s.agentInfo);
  const backendOnline = useAgentConsoleStore((s) => s.backendOnline);
  const llmError = useAgentConsoleStore((s) => s.llmError);
  const switchModel = useAgentConsoleStore((s) => s.switchModel);
  const restartBackend = useAgentConsoleStore((s) => s.restartBackend);
  const startOllama = useAgentConsoleStore((s) => s.startOllama);
  const restartOllama = useAgentConsoleStore((s) => s.restartOllama);
  const rebuildAgent = useAgentConsoleStore((s) => s.rebuildAgent);
  const resetCircuit = useAgentConsoleStore((s) => s.resetCircuit);
  const retryLLM = useAgentConsoleStore((s) => s.retryLLM);
  // Universal TURBO rejim — barcha modellarga birdek qo'llanadi.
  const turbo = useAgentConsoleStore((s) => s.turbo);
  const fastModel = useAgentConsoleStore((s) => s.fastModel);
  const setSpeed = useAgentConsoleStore((s) => s.setSpeed);
  const [backendDraft, setBackendDraft] = useState(backendUrl);
  const [switching, setSwitching] = useState(false);
  // Services tab holati
  const [services, setServices] = useState<SystemServicesResult | null>(null);
  const [servicesLoaded, setServicesLoaded] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [ollamaBusy, setOllamaBusy] = useState(false);
  const [circuitBusy, setCircuitBusy] = useState(false);

  const refreshServices = async () => {
    setServicesLoaded(false);
    try {
      const { systemServices } = await import('../backend');
      setServices(await systemServices());
    } catch {
      setServices(null);
    } finally {
      setServicesLoaded(true);
    }
  };

  // Real Ollama modellarini yuklash (backend online bo'lsa)
  useEffect(() => {
    if (!open) return;
    setModelsLoaded(false);
    (async () => {
      try {
        const { llmModels, llmModelDetails } = await import('../backend');
        // Detail endpoint eski serverda bo'lmasa ham model ro'yxati YO'QOLMAYDI
        // (Promise.allSettled — biri tushsa ham ikkinchisi saqlanadi).
        const [listR, detailR] = await Promise.allSettled([llmModels(), llmModelDetails()]);
        setModels(listR.status === 'fulfilled' ? listR.value : []);
        setModelDetails(detailR.status === 'fulfilled' ? detailR.value : []);
      } catch {
        setModels([]);
        setModelDetails([]);
      } finally {
        setModelsLoaded(true);
      }
    })();
  }, [open]);

  // Services holatini modal ochilganda yangilaymiz
  useEffect(() => {
    if (!open) return;
    refreshServices();
    // TURBO sozlamasini backend'dan yuklaymiz (real holat)
    useAgentConsoleStore.getState().loadSpeedSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  const currentModel = agentInfo?.model || '';
  const currentDetail = modelDetails.find((d) => d.name === currentModel);
  // Tavsiya: ro'yxatdagi eng yuqori o'rinli model (hali tanlanmagan bo'lsa).
  const recommended =
    models
      .map((m) => ({ m, rank: MODEL_QUALITY.find((x) => x.name === m)?.rank ?? 99 }))
      .sort((a, b) => a.rank - b.rank)[0]?.m || '';

  const handleModelChange = async (model: string) => {
    if (!model || model === currentModel) return;
    setSwitching(true);
    try {
      await switchModel(model);
    } finally {
      setSwitching(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black bg-opacity-60" />
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-md mx-4 bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <span className="text-sm font-ui font-medium text-zinc-200">Settings</span>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200 transition-colors">
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-zinc-800 px-4">
          {(['model', 'backend', 'providers', 'services'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 text-xs font-ui capitalize border-b-2 -mb-px ${
                tab === t ? 'text-amber-300 border-amber-400' : 'text-zinc-500 border-transparent hover:text-zinc-300'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Content */}
        {tab === 'model' ? (
          <div className="p-4 space-y-5">
            <div>
              <label className="text-xs font-ui text-zinc-500 block mb-1.5">Local model</label>
              {modelsLoaded && !backendOnline ? (
                <div className="text-xs font-ui text-zinc-600 border border-zinc-800 rounded px-2.5 py-2">
                  Backend offline — model ro'yxati olinmadi. Bridge'ni ishga tushiring: <code className="font-mono text-zinc-500">python server.py</code>
                </div>
              ) : models.length === 0 && modelsLoaded ? (
                <div className="text-xs font-ui text-zinc-600 border border-zinc-800 rounded px-2.5 py-2">
                  Ollama'da model topilmadi (yoki Ollama ishlamayapti).
                </div>
              ) : (
                <select
                  value={currentModel}
                  onChange={(e) => handleModelChange(e.target.value)}
                  disabled={switching}
                  className="w-full bg-zinc-950 border border-zinc-700 rounded px-2.5 py-1.5 text-sm text-zinc-200 font-mono outline-none disabled:opacity-60"
                >
                  {currentModel && !models.includes(currentModel) && <option value={currentModel}>{currentModel}</option>}
                  {models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              )}
              {switching && (
                <div className="text-xs font-ui text-amber-400 mt-1.5">Model almashtirilmoqda…</div>
              )}
              {currentModel && (
                <div className="text-[11px] font-ui text-zinc-600 mt-1.5">
                  Joriy model: <code className="font-mono text-zinc-500">{currentModel}</code>
                  {currentDetail && (
                    <span className="text-zinc-500">
                      {' · '}{currentDetail.parameter_size}{' · '}{currentDetail.quantization}{' · '}{currentDetail.size_gb} GB
                    </span>
                  )}
                </div>
              )}
              {/* Sifat tavsiyasi — qaysi model kuchliroq ekani ko'rinadi */}
              {models.length > 1 && recommended && (
                <div className="text-[11px] font-ui text-amber-400/90 mt-2 border border-amber-800/40 bg-amber-950/30 rounded px-2 py-1.5 leading-relaxed">
                  ✦ Sifat tavsiyasi: <code className="font-mono text-amber-300">{recommended}</code>
                  {modelNote(recommended) ? ` — ${modelNote(recommended)}` : ''}
                </div>
              )}
              {llmError && (
                <div className="text-[11px] font-ui text-rose-400/90 mt-2 border border-rose-900/50 bg-rose-950/30 rounded px-2 py-1.5 leading-relaxed">
                  ⚠ {llmError}
                </div>
              )}
            </div>
            {/* Universal TURBO rejim — BIR kalit, har qanday LLM tezlashadi */}
            <div className="border border-amber-800/40 bg-amber-950/20 rounded-md px-3 py-2.5">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-ui text-zinc-100">⚡ TURBO rejim</span>
                  <div className="text-[11px] font-ui text-zinc-500 mt-0.5 leading-relaxed">
                    Universal tezlashtirish — har bir model uchun alohida emas,
                    BIR kalit barcha modellarga qo\'llanadi.
                  </div>
                </div>
                <button
                  onClick={() => setSpeed(!turbo)}
                  className={`w-11 h-6 rounded-full relative transition-colors shrink-0 ${
                    turbo ? 'bg-amber-400' : 'bg-zinc-700'
                  }`}
                  title={turbo ? 'TURBO rejimni o\'chirish' : 'TURBO rejimni yoqish'}
                >
                  <span
                    className="absolute top-0.5 w-5 h-5 rounded-full bg-zinc-950 transition-all"
                    style={{ left: turbo ? '22px' : '2px' }}
                  />
                </button>
              </div>
              <ul className="text-[11px] font-ui text-zinc-400 mt-2 space-y-0.5 leading-relaxed">
                <li>• kichik kontekst/token — javob 2-4x tez keladi</li>
                <li>• oddiy savollar avtomatik tez modelga boradi (katta model murakkab vazifalarga qoladi)</li>
                <li>• fikrlash (thinking) o\'chiq, timeout qisqa — tutilish yo\'q</li>
              </ul>
              {fastModel && (
                <div className="text-[11px] font-ui text-teal-300/90 mt-2 font-mono">
                  tez model: {fastModel}
                </div>
              )}
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-ui text-zinc-500">Context window</label>
                <span className="text-xs font-mono text-zinc-400">{ctx}%</span>
              </div>
              <input
                type="range"
                min="10"
                max="100"
                value={ctx}
                onChange={(e) => setCtx(Number(e.target.value))}
                className="w-full accent-amber-400"
              />
              <p className="text-[11px] font-ui text-zinc-600 mt-1">
                Kontekst chegarasi agent tomonidan qo'llanadi (server sozlamasi).
              </p>
            </div>
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-xs font-ui text-zinc-500">RAM-safe history trimming</span>
              <span
                onClick={() => setTrim((t) => !t)}
                className={`w-9 h-5 rounded-full relative transition-colors ${
                  trim ? 'bg-amber-500' : 'bg-zinc-700'
                }`}
              >
                <span
                  className="absolute top-0.5 w-4 h-4 rounded-full bg-zinc-950 transition-all"
                  style={{ left: trim ? '18px' : '2px' }}
                />
              </span>
            </label>
          </div>
        ) : tab === 'backend' ? (
          <div className="p-4 space-y-4">
            <div>
              <label className="text-xs font-ui text-zinc-500 block mb-1.5">
                Igris brain bridge URL
              </label>
              <input
                value={backendDraft}
                onChange={(e) => setBackendDraft(e.target.value)}
                placeholder="http://127.0.0.1:8765"
                className="w-full bg-zinc-950 border border-zinc-700 rounded px-2.5 py-1.5 text-sm text-zinc-200 font-mono outline-none focus:border-amber-500"
              />
              <p className="text-[11px] font-ui text-zinc-600 mt-1.5">
                Run <code className="font-mono text-zinc-500">python -m server.server</code> from Igris_brain to start the bridge.
              </p>
            </div>
            <button
              onClick={() => setBackendUrl(backendDraft)}
              className="w-full rounded-md bg-amber-400 hover:bg-amber-300 text-zinc-950 text-sm font-ui font-medium py-1.5 transition-colors"
            >
              Save backend URL
            </button>
          </div>
        ) : tab === 'services' ? (
          <div className="p-4 space-y-3">
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-xs font-ui text-zinc-500">System services</span>
              <button
                onClick={refreshServices}
                disabled={!servicesLoaded}
                className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 disabled:opacity-50 transition-colors"
              >
                ↻ refresh
              </button>
            </div>

            {/* Backend */}
            <div className="border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-teal-400' : 'bg-rose-400 animate-pulse'}`} />
                  <span className="text-sm font-ui text-zinc-200">Igris backend</span>
                </div>
                <button
                  onClick={async () => {
                    setRestarting(true);
                    const ok = await restartBackend();
                    setRestarting(false);
                    if (ok) await refreshServices();
                  }}
                  disabled={restarting || !backendOnline}
                  className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-amber-300 hover:border-amber-500/50 disabled:opacity-40 transition-colors"
                >
                  {restarting ? 'restarting…' : backendOnline ? '⟳ restart' : 'offline'}
                </button>
              </div>
              <div className="text-[11px] font-ui text-zinc-600 mt-1">
                {backendOnline ? 'connected' : 'offline — run.bat bilan qayta ishga tushiring'} · <code className="font-mono text-zinc-500">{backendUrl}</code>
              </div>
              {restarting && (
                <div className="text-[11px] font-ui text-amber-400/90 mt-1.5">
                  Backend qayta ishga tushmoqda — UI avtomatik qayta ulanadi (~10s).
                </div>
              )}
              <div className="text-[10px] font-ui text-zinc-600/70 mt-1">
                restart yangi oyna OCHMAYDI — jarayon fonda qayta ishga tushadi (log: Igris_brain/logs/server.log)
              </div>
            </div>

            {/* Watchdog — backend qulab tushsa avtomatik qayta ishga tushiradi */}
            <div className="border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${services?.watchdog?.running ? 'bg-teal-400' : 'bg-zinc-600'}`} />
                  <span className="text-sm font-ui text-zinc-200">Watchdog (auto-restart)</span>
                </div>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500">
                  {services?.watchdog?.running ? '● active' : '○ off'}
                </span>
              </div>
              <div className="text-[11px] font-ui text-zinc-600 mt-1">
                {services?.watchdog?.running
                  ? `backend ${services.watchdog.backend_restarts ?? 0}× qayta ishga tushirilgan · ollama ${services.watchdog.ollama_restarts ?? 0}×`
                  : 'watchdog ishlamayapti — run.bat bilan qayta ishga tushiring'}
              </div>
              <div className="text-[10px] font-ui text-zinc-600/70 mt-1">
                Backend qulab tushsa yoki javob bermay qolsa, uni AVTOMATIK qayta ishga tushiradi —
                "birdan offline bo'lib qolish" oldini oladi (log: Igris_brain/logs/watchdog.log)
              </div>
            </div>

            {/* Ollama */}
            <div className="border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${services?.ollama?.running ? 'bg-teal-400' : 'bg-zinc-600'}`} />
                  <span className="text-sm font-ui text-zinc-200">Ollama (local LLM)</span>
                </div>
                <button
                  onClick={async () => {
                    setOllamaBusy(true);
                    try {
                      if (services?.ollama?.running) {
                        await restartOllama();
                      } else {
                        await startOllama();
                      }
                    } finally {
                      setOllamaBusy(false);
                      await refreshServices();
                    }
                  }}
                  disabled={ollamaBusy}
                  className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-teal-300 hover:border-teal-500/50 disabled:opacity-40 transition-colors"
                >
                  {ollamaBusy
                    ? services?.ollama?.running
                      ? 'restarting…'
                      : 'starting…'
                    : services?.ollama?.running
                      ? '⟳ restart'
                      : '▶ start'}
                </button>
              </div>
              <div className="text-[11px] font-ui text-zinc-600 mt-1">
                {servicesLoaded && services === null ? 'backend offline — holat olinmadi' : services?.ollama?.running ? 'running · localhost:11434' : 'stopped'}
                {' · model: '}<code className="font-mono text-zinc-500">{agentInfo?.model || '—'}</code>
              </div>
              <div className="text-[10px] font-ui text-zinc-600/70 mt-1">
                restart — eski jarayon o'ldirilib qayta ochiladi (oyna ochilmaydi, log: Igris_brain/logs/ollama.log)
              </div>
            </div>

            {/* Circuit Breaker — agent stabilizatsiya */}
            <div className="border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    agentInfo?.circuit?.state === 'closed' ? 'bg-teal-400'
                    : agentInfo?.circuit?.state === 'open' ? 'bg-rose-400 animate-pulse'
                    : 'bg-amber-400'
                  }`} />
                  <span className="text-sm font-ui text-zinc-200">Circuit Breaker</span>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    agentInfo?.circuit?.state === 'closed' ? 'bg-teal-950/50 text-teal-300'
                    : agentInfo?.circuit?.state === 'open' ? 'bg-rose-950/50 text-rose-300'
                    : 'bg-amber-950/50 text-amber-300'
                  }`}>
                    {agentInfo?.circuit?.state || 'closed'}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  {/* Retry LLM — darhol qayta sinash */}
                  <button
                    onClick={async () => {
                      setCircuitBusy(true);
                      await retryLLM();
                      setCircuitBusy(false);
                    }}
                    disabled={circuitBusy || (agentInfo?.circuit?.state || 'closed') === 'closed'}
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-teal-700 text-teal-400 hover:text-teal-200 hover:border-teal-400/50 disabled:opacity-40 transition-colors"
                    title="LLM qayta sinab ko'rish (circuit reset + avtomatik tekshirish)"
                  >
                    ↻ retry
                  </button>
                  <button
                    onClick={async () => {
                      setCircuitBusy(true);
                      await resetCircuit();
                      setCircuitBusy(false);
                    }}
                    disabled={circuitBusy || (agentInfo?.circuit?.state || 'closed') === 'closed'}
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-400 hover:text-amber-300 hover:border-amber-500/50 disabled:opacity-40 transition-colors"
                    title="Circuit breaker reset"
                  >
                    ↺ reset
                  </button>
                  <button
                    onClick={async () => {
                      setCircuitBusy(true);
                      await rebuildAgent();
                      setCircuitBusy(false);
                    }}
                    disabled={circuitBusy}
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-400 hover:text-amber-300 hover:border-amber-500/50 disabled:opacity-40 transition-colors"
                    title="Agent'ni majburiy qayta yaratish (circuit reset + agent rebuild)"
                  >
                    ⟳ rebuild
                  </button>
                </div>
              </div>
              <div className="text-[11px] font-ui text-zinc-600 mt-1">
                {agentInfo?.circuit?.state === 'open' ? (
                  <span className="text-rose-400/90">
                    Agent xatolari tufayli to'xtatilgan — avtomatik tiklanadi ({'>'}{agentInfo.circuit.failure_count}× xato)
                  </span>
                ) : agentInfo?.circuit?.state === 'half_open' ? (
                  <span className="text-amber-400/90">
                    Qayta tiklanmoqda — birinchi muvaffaqiyat kutilmoqda
                  </span>
                ) : (
                  <span>
                    Normal ishlayapti · xato: {agentInfo?.circuit?.failure_count || 0}
                    {agentInfo?.llmDegraded && (
                      <span className="text-amber-400/90 ml-1">· LLM degraded (bricks+RAG ishlayapti)</span>
                    )}
                  </span>
                )}
              </div>
              <div className="text-[10px] font-ui text-zinc-600/70 mt-1">
                ↻ retry: LLM qayta sinab ko'radi · ↺ reset: circuit breaker tozalaydi · ⟳ rebuild: agent qayta yaratadi
              </div>
            </div>

            {/* MCP servers */}
            <div className="border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${services?.mcp?.connected ? 'bg-teal-400' : 'bg-zinc-600'}`} />
                <span className="text-sm font-ui text-zinc-200">MCP servers</span>
                {services?.mcp?.degraded && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-950/50 text-rose-300 border border-rose-800/50">degraded</span>
                )}
              </div>
              <div className="text-[11px] font-ui text-zinc-600 mt-1 flex flex-wrap gap-1">
                {(services?.mcp?.servers?.length ? services.mcp.servers : ['(none connected)']).map((s) => (
                  <span key={s} className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono text-[10px]">{s}</span>
                ))}
              </div>
            </div>

            {/* S3: Silent degradation — komponentlar jim zaif rejimga o'tganda ko'rinadi */}
            <div className={`border rounded-md px-3 py-2 ${
              (services?.degradations_active ?? 0) > 0
                ? 'border-rose-800/60 bg-rose-950/20'
                : 'border-zinc-800'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    (services?.degradations_active ?? 0) > 0 ? 'bg-rose-400 animate-pulse' : 'bg-teal-400'
                  }`} />
                  <span className="text-sm font-ui text-zinc-200">Degradations (silent fallback)</span>
                  {(services?.degradations_active ?? 0) > 0 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-rose-950/50 text-rose-300 border border-rose-800/50">
                      {services?.degradations_active} active
                    </span>
                  )}
                </div>
                <button
                  onClick={async () => {
                    try {
                      const { clearDegradations } = await import('../backend');
                      await clearDegradations();
                    } catch { /* backend offline — refresh baribir ishlaydi */ }
                    await refreshServices();
                  }}
                  disabled={!servicesLoaded || !(services?.degradations?.length)}
                  className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-amber-300 hover:border-amber-500/50 disabled:opacity-40 transition-colors"
                  title="Degradation tarixini tozalash"
                >
                  ↺ clear
                </button>
              </div>
              {services?.degradations?.length ? (
                <div className="mt-1.5 space-y-1">
                  {services.degradations.slice(0, 5).map((d, i) => (
                    <div key={`${d.component}-${i}`} className="text-[11px] font-ui text-zinc-500 flex items-start gap-1.5">
                      <span className="font-mono text-[10px] text-rose-400/80 shrink-0">{d.component}</span>
                      <span className="shrink-0 text-zinc-700">→</span>
                      <span className="font-mono text-[10px] text-amber-400/80 shrink-0">{d.fallback || '?'}</span>
                      <span className="truncate" title={d.reason}>{d.reason}</span>
                      {(d.count ?? 1) > 1 && (
                        <span className="shrink-0 font-mono text-[10px] text-zinc-600">×{d.count}</span>
                      )}
                    </div>
                  ))}
                  {services.degradations.length > 5 && (
                    <div className="text-[10px] font-ui text-zinc-600">
                      +{services.degradations.length - 5} eski yozuv (log: Igris_brain/logs/degradations.json)
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-[11px] font-ui text-zinc-600 mt-1">
                  {servicesLoaded ? 'hammasi sog\'lom — jim fallback yo\'q' : 'backend offline — holat olinmadi'}
                </div>
              )}
              <div className="text-[10px] font-ui text-zinc-600/70 mt-1">
                Komponent ishlamayotganda zaif rejimga o'tishi (MCP→no-tools, FTS5→BM25...) bu yerda ko'rinadi — "jim sekinlik" yo'q
              </div>
            </div>

            {/* Frontend */}
            <div className="border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  <span className="text-sm font-ui text-zinc-200">Frontend UI</span>
                </div>
                <button
                  onClick={() => window.location.reload()}
                  className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
                >
                  ↻ reload
                </button>
              </div>
              <div className="text-[11px] font-ui text-zinc-600 mt-1">
                Web / desktop interfeysni qayta yuklaydi.
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-3">
            {/* OmniRoute Gateway */}
            <div className="border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${agentInfo?.omniroute?.connected ? 'bg-teal-400' : 'bg-zinc-600'}`} />
                  <span className="text-sm font-ui text-zinc-200">OmniRoute Gateway</span>
                  {agentInfo?.omniroute?.connected && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-teal-950/50 text-teal-300 border border-teal-800/50">
                      {agentInfo.omniroute.models_count || 0} models
                    </span>
                  )}
                </div>
                <span className="text-xs font-ui text-zinc-500">
                  {agentInfo?.omniroute?.connected ? 'connected' : 'not connected'}
                </span>
              </div>
              {agentInfo?.omniroute?.connected ? (
                <div className="mt-1.5 space-y-1">
                  <div className="text-[11px] font-ui text-zinc-600">
                    URL: <code className="font-mono text-zinc-500">{agentInfo.omniroute.url || 'http://localhost:20128/v1'}</code>
                  </div>
                  <div className="text-[11px] font-ui text-zinc-600">
                    Default model: <code className="font-mono text-zinc-500">{agentInfo.omniroute.default_model || 'openai/gpt-4o-mini'}</code>
                  </div>
                  {agentInfo.omniroute.providers?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {agentInfo.omniroute.providers.map((p: string) => (
                        <span key={p} className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono text-[10px]">{p}</span>
                      ))}
                    </div>
                  )}
                  <div className="text-[10px] font-ui text-zinc-600/70 mt-1">
                    352+ provider • OpenAI, Claude, Gemini, DeepSeek, Qwen va boshqalar
                  </div>
                </div>
              ) : (
                <div className="mt-1.5 space-y-2">
                  <div className="text-[11px] font-ui text-zinc-600">
                    OmniRoute — barcha LLM'larni bitta endpoint orqali ishlatish gateway'i.
                  </div>
                  <div className="text-[11px] font-ui text-zinc-500">
                    Setup: <code className="font-mono text-zinc-400">docker run -d -p 20128:20128 diegosouzapw/omniroute:latest</code>
                  </div>
                  <div className="text-[11px] font-ui text-zinc-500">
                    Dashboard: <code className="font-mono text-zinc-400">http://localhost:20129</code>
                  </div>
                  <div className="text-[10px] font-ui text-zinc-600/70">
                    .env faylga qo'shing: OMNIROUTE_URL, OMNIROUTE_API_KEY
                  </div>
                </div>
              )}
            </div>

            {/* Ollama (Local) */}
            <div className="flex items-center justify-between border border-zinc-800 rounded-md px-3 py-2">
              <div className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${agentInfo?.llmAvailable ? 'bg-teal-400' : 'bg-zinc-600'}`} />
                <span className="text-sm font-ui text-zinc-200">Ollama (local fallback)</span>
              </div>
              <span className="text-xs font-ui text-zinc-500">
                {agentInfo?.llmAvailable ? 'connected' : 'not connected'}
              </span>
            </div>

            {/* Igris_Memory (RAG) */}
            <div className="flex items-center justify-between border border-zinc-800 rounded-md px-3 py-2 opacity-70">
              <div className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${agentInfo?.memoryEnabled ? 'bg-amber-400' : 'bg-zinc-600'}`} />
                <span className="text-sm font-ui text-zinc-200">Igris_Memory (RAG)</span>
              </div>
              <span className="text-xs font-ui text-zinc-500">
                {agentInfo?.memoryEnabled ? 'on' : 'off'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
