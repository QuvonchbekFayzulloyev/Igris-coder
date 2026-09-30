import React, { useState, useEffect, useCallback, useRef } from 'react';
import { webaiStatus, webaiAction, webaiScreenshotUrl, webaiPageText, WebAIStatus, WebAITab } from '../backend';
import { useMenu } from './ContextMenu';

/**
 * Web AI Bridge — REAL browser automation view (brauzerga o'xshash to'liq UI).
 * Igris_brain /api/webai/* proxy orqali web_ai_bridge MCP serveri (Playwright +
 * real Chrome) boshqariladi: ochiq tablar, navigation, jonli screenshot,
 * zoom/scroll, yangi tab, tab yopish, cookie/popup yopish, matn olish.
 * Bridge ulanmagan bo'lsa — halol bo'sh holat ko'rsatiladi (soxta session yo'q).
 */

const ZOOM_STEPS = [50, 67, 75, 80, 90, 100, 110, 125, 150, 200];

export function WebAIBridgeView() {
  const [status, setStatus] = useState<WebAIStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [urlDraft, setUrlDraft] = useState('');
  const [shotUrl, setShotUrl] = useState('');
  const [shotError, setShotError] = useState(false);
  const [shotLoading, setShotLoading] = useState(false);
  const [fullPage, setFullPage] = useState(false);
  const [zoomIdx, setZoomIdx] = useState(5); // ZOOM_STEPS[5] = 100%
  const [busy, setBusy] = useState(false);
  const [lastAction, setLastAction] = useState('');
  const menu = useMenu();
  const viewRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const st = await webaiStatus();
      setStatus(st);
      setError('');
      if (st.connected) {
        setShotUrl(webaiScreenshotUrl(fullPage));
        setShotError(false);
      } else {
        setShotUrl('');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'bridge status unavailable');
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [fullPage]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 6000);
    return () => clearInterval(iv);
  }, [refresh]);

  // Aktiv tab URL'i — URL paneli bilan sinxron (foydalanuvchi tahrirlamayotganda)
  const activeTab = (status?.tabs || []).find((t) => t.active);
  const activeUrl = activeTab?.url || '';
  useEffect(() => {
    if (activeUrl) setUrlDraft(activeUrl);
  }, [activeUrl]);

  const doAction = useCallback(async (action: string, opts?: { url?: string; index?: number }) => {
    setBusy(true);
    setLastAction(action);
    setError('');
    try {
      const r = await webaiAction(action, opts);
      if (!r.ok && r.error) setError(r.error);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'action failed');
    } finally {
      setBusy(false);
    }
    await refresh();
  }, [refresh]);

  const runAndShoot = useCallback(async (action: string, opts?: { url?: string; index?: number }) => {
    await doAction(action, opts);
    // Amaldan keyin darhol yangi screenshot (kutish yo'q)
    setShotLoading(true);
    setShotUrl(webaiScreenshotUrl(fullPage));
    setShotError(false);
  }, [doAction, fullPage]);

  const navigate = useCallback((raw: string) => {
    const url = raw.trim();
    if (!url) return;
    const withProto = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    setUrlDraft(withProto);
    runAndShoot('navigate', { url: withProto });
  }, [runAndShoot]);

  const shootNow = useCallback(() => {
    setShotLoading(true);
    setShotError(false);
    setShotUrl(webaiScreenshotUrl(fullPage));
  }, [fullPage]);

  const zoom = (dir: 'in' | 'out' | 'reset') => {
    if (dir === 'reset') { setZoomIdx(5); runAndShoot('zoom_reset'); return; }
    setZoomIdx((i) => {
      const next = dir === 'in' ? Math.min(ZOOM_STEPS.length - 1, i + 1) : Math.max(0, i - 1);
      if (next !== i) runAndShoot(dir === 'in' ? 'zoom_in' : 'zoom_out');
      return next;
    });
  };

  const connected = Boolean(status?.connected);

  const copyText = (text: string) => {
    try { navigator.clipboard.writeText(text); } catch { /* ignore */ }
  };

  // Screenshot ustida o'ng tugma — brauzer menyusi
  const onShotContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    menu.open(e.clientX, e.clientY, [
      { id: 'rl', label: 'Yangilash', icon: '↻', hint: 'F5', action: () => runAndShoot('refresh') },
      { id: 'fw', label: 'Oldinga', icon: '→', disabled: !connected, action: () => runAndShoot('forward') },
      { id: 'bk', label: 'Orqaga', icon: '←', disabled: !connected, action: () => runAndShoot('back') },
      { separator: true },
      { id: 'scu', label: 'Yuqoriga scroll', icon: '↑', action: () => runAndShoot('scroll_up') },
      { id: 'scd', label: 'Pastga scroll', icon: '↓', action: () => runAndShoot('scroll_down') },
      { separator: true },
      { id: 'zi', label: 'Kattalashtirish', icon: '＋', action: () => zoom('in') },
      { id: 'zo', label: 'Kichiklashtirish', icon: '－', action: () => zoom('out') },
      { id: 'zr', label: 'Zoom 100%', icon: '⌂', disabled: zoomIdx === 5, action: () => zoom('reset') },
      { separator: true },
      { id: 'cp', label: 'URL ni nusxalash', icon: '⧉', disabled: !activeUrl, action: () => copyText(activeUrl) },
      { id: 'pt', label: 'Sahifa matnini olish', icon: '≡', action: () => { webaiPageText().then((t) => copyText(t.slice(0, 20000))); } },
      { id: 'ov', label: 'Cookie/popup yopish', icon: '✕', action: () => runAndShoot('dismiss_overlays') },
      { id: 'full', label: 'Yangi tab', icon: '＋', action: () => runAndShoot('new_tab', { url: '' }) },
    ]);
  };

  // Tab ustida o'ng tugma — tab menyusi
  const onTabContextMenu = (e: React.MouseEvent, t: WebAITab) => {
    e.preventDefault();
    e.stopPropagation();
    menu.open(e.clientX, e.clientY, [
      { id: 'sw', label: 'Shu tabga o‘tish', icon: '⇥', disabled: t.active, action: () => runAndShoot('switch_tab', { index: t.index }) },
      { id: 'rl', label: 'Yangilash', icon: '↻', action: () => runAndShoot('refresh') },
      { separator: true },
      { id: 'cp', label: 'URL ni nusxalash', icon: '⧉', disabled: !t.url, action: () => copyText(t.url) },
      { id: 'nt', label: 'URL ni yangi tabda ochish', icon: '↗', disabled: !t.url, action: () => runAndShoot('new_tab', { url: t.url }) },
      { separator: true },
      { id: 'cl', label: 'Tab yopish', icon: '✕', danger: true, action: () => runAndShoot('close_tab', { index: t.index }) },
    ]);
  };

  const zoomPct = ZOOM_STEPS[zoomIdx];

  // Screenshot ustida g'ildirak — REAL brauzerni scroll qiladi (bridge orqali).
  // Tez-tez uzilish bo'lmasligi uchun throttle qilingan (500ms).
  const lastWheelRef = useRef(0);
  const onShotWheel = useCallback((e: React.WheelEvent) => {
    if (!connected) return;
    const now = Date.now();
    if (now - lastWheelRef.current < 500) return;
    lastWheelRef.current = now;
    const act = e.deltaY < 0 ? 'scroll_up' : 'scroll_down';
    webaiAction(act).catch(() => { /* jim — keyingi tikka */ });
    setShotUrl(webaiScreenshotUrl(fullPage));
    setShotError(false);
  }, [connected, fullPage]);

  return (
    <div className="flex-1 min-h-0 flex flex-col" ref={viewRef}>
      {/* ---- Tab strip ---- */}
      <div className="flex items-center border-b border-zinc-800 shrink-0 px-1 pt-1 gap-0.5 bg-zinc-900 bg-opacity-30 overflow-x-auto">
        {(status?.tabs || []).map((t: WebAITab) => (
          <div
            key={t.index}
            onClick={() => t.index >= 0 && !t.active && doAction('switch_tab', { index: t.index })}
            onContextMenu={(e) => onTabContextMenu(e, t)}
            className={`group flex items-center gap-1.5 px-3 py-1.5 text-xs font-ui rounded-t-md border-t border-x cursor-pointer max-w-44 shrink-0 transition-colors ${
              t.active
                ? 'bg-zinc-950 border-zinc-800 text-zinc-100'
                : 'bg-transparent border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/60'
            }`}
            title={t.url || '(blank tab)'}
          >
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.active ? 'bg-teal-400' : 'bg-zinc-600'}`} />
            <span className="truncate">{t.title || t.url || `Tab ${t.index}`}</span>
            <button
              onClick={(e) => { e.stopPropagation(); runAndShoot('close_tab', { index: t.index }); }}
              className="w-4 h-4 flex items-center justify-center rounded text-zinc-600 hover:text-zinc-100 hover:bg-zinc-700 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
              title="Tab yopish"
            >
              ✕
            </button>
          </div>
        ))}
        <button
          onClick={() => runAndShoot('new_tab', { url: '' })}
          disabled={!connected}
          className="px-2.5 py-1.5 text-xs font-ui text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/60 rounded shrink-0 disabled:opacity-40 disabled:cursor-default transition-colors"
          title="Yangi tab (Ctrl+T)"
        >
          ＋
        </button>
      </div>

      {/* ---- Toolbar: nav + URL + zoom + actions ---- */}
      <div className="flex items-center gap-1.5 px-2 py-1.5 border-b border-zinc-800 shrink-0 bg-zinc-900/20">
        <div className="flex items-center rounded-md overflow-hidden border border-zinc-800">
          <button onClick={() => runAndShoot('back')} disabled={!connected} title="Orqaga (Alt+←)"
            className="px-2.5 py-1 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-default transition-colors">←</button>
          <button onClick={() => runAndShoot('forward')} disabled={!connected} title="Oldinga (Alt+→)"
            className="px-2.5 py-1 border-x border-zinc-800 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-default transition-colors">→</button>
          <button onClick={() => runAndShoot('refresh')} disabled={!connected} title="Yangilash (F5)"
            className={`px-2.5 py-1 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-default transition-colors ${busy ? 'animate-spin' : ''}`}>↻</button>
          <button onClick={() => runAndShoot('dismiss_overlays')} disabled={!connected} title="Cookie banner/popup yopish"
            className="px-2.5 py-1 border-l border-zinc-800 text-zinc-400 hover:text-teal-300 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-default transition-colors">🛡</button>
        </div>
        {/* URL panel */}
        <div className="flex-1 flex items-center gap-1.5 bg-zinc-950 border border-zinc-800 rounded-md px-2.5 py-1 min-w-0 focus-within:border-teal-600/70 transition-colors">
          <span className="shrink-0 text-xs" title="HTTPS">🔒</span>
          <input
            value={urlDraft}
            onChange={(e) => setUrlDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') navigate(urlDraft); if (e.key === 'Escape') setUrlDraft(activeUrl); }}
            placeholder={connected ? 'Qidiruv yoki manzil — Enter' : 'bridge ulanmagan'}
            disabled={!connected}
            spellCheck={false}
            className="bg-transparent outline-none text-xs font-mono text-zinc-200 flex-1 min-w-0 placeholder-zinc-600 disabled:opacity-50"
          />
          {urlDraft && urlDraft !== activeUrl && (
            <button onClick={() => navigate(urlDraft)} title="Ochish" className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 hover:bg-teal-500/30 shrink-0">↵</button>
          )}
        </div>
        {/* Zoom */}
        <div className="flex items-center rounded-md overflow-hidden border border-zinc-800 shrink-0">
          <button onClick={() => zoom('out')} disabled={!connected || zoomIdx === 0} title="Kichiklashtirish (Ctrl+-)"
            className="px-2 py-1 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-default transition-colors">－</button>
          <button onClick={() => zoom('reset')} disabled={!connected || zoomIdx === 5} title="Zoom 100% (Ctrl+0)"
            className="px-1.5 py-1 border-x border-zinc-800 text-[10px] font-mono text-zinc-400 hover:text-teal-300 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-default transition-colors min-w-10">{zoomPct}%</button>
          <button onClick={() => zoom('in')} disabled={!connected || zoomIdx === ZOOM_STEPS.length - 1} title="Kattalashtirish (Ctrl++)"
            className="px-2 py-1 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-default transition-colors">＋</button>
        </div>
        {/* Full page / reload shot */}
        <button
          onClick={() => setFullPage((f) => !f)}
          title={fullPage ? 'To‘liq sahifa rejimi yoniq — screenshot butun sahifani oladi' : 'Faqat ko‘rinadigan qism — screenshot viewportni oladi'}
          className={`px-2 py-1 rounded-md border text-[11px] font-mono shrink-0 transition-colors ${
            fullPage ? 'bg-teal-500/20 border-teal-600/50 text-teal-300' : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'
          }`}
        >
          ⬓ full
        </button>
        <button onClick={shootNow} disabled={!connected} title="Screenshotni yangilash"
          className="px-2 py-1 rounded-md border border-zinc-800 text-zinc-400 hover:text-teal-300 hover:border-teal-600/50 text-xs shrink-0 disabled:opacity-30 disabled:cursor-default transition-colors">⟳</button>
      </div>

      {/* ---- Content ---- */}
      <div className="flex-1 relative overflow-hidden bg-zinc-900" onContextMenu={onShotContextMenu} onWheel={onShotWheel}>
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs font-ui text-zinc-600">
            bridge holati tekshirilmoqda…
          </div>
        ) : !connected ? (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="max-w-sm text-center space-y-3">
              <div className="text-3xl">🌐</div>
              <div className="text-sm font-ui text-zinc-300">
                Web AI Bridge ulanmagan
              </div>
              <div className="text-xs font-ui text-zinc-600 leading-relaxed">
                Igris brain server (python server.py) ishlayotganida web_ai_bridge MCP
                serveri (real Chrome + Playwright) avtomatik ulanadi. Status:
                {error ? ` ${error}` : ' kutmoqda…'}
              </div>
            </div>
          </div>
        ) : (
          <>
            {shotLoading && (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 px-2 py-0.5 rounded bg-zinc-950/90 border border-zinc-700 text-[10px] font-mono text-teal-300">
                yangilanmoqda…
              </div>
            )}
            {shotError || !shotUrl ? (
              <div className="absolute inset-0 flex items-center justify-center text-xs font-ui text-zinc-600">
                screenshot olinmadi — ⟳ bosing yoki brauzer holatini tekshiring
              </div>
            ) : (
              <img
                key={shotUrl}
                src={shotUrl}
                alt="Live browser screenshot"
                onLoad={() => setShotLoading(false)}
                onError={() => { setShotError(true); setShotLoading(false); }}
                className="w-full h-full object-contain select-none"
                draggable={false}
              />
            )}
            {/* Busy overlay */}
            {busy && (
              <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-zinc-950/90 border border-zinc-700 text-[10px] font-mono text-amber-300 animate-pulse">
                {lastAction}…
              </div>
            )}
          </>
        )}
      </div>

      {/* ---- Status bar ---- */}
      <div className="flex items-center justify-between px-3 py-1.5 border-t border-zinc-800 text-xs font-ui text-zinc-500 shrink-0">
        <span
          className="flex items-center gap-1.5"
          title="Consequential actions (payments, deletions, account changes) require explicit confirmation before the bridge clicks them."
        >
          <span className="text-teal-400">🛡️</span> Consent gate: armed
        </span>
        <span className="flex items-center gap-2">
          {status?.browser?.channel && (
            <span className="font-mono text-zinc-600 truncate max-w-48">{status.browser.channel}</span>
          )}
          {status?.browser?.mode && (
            <span className="font-mono text-zinc-600">{status.browser.mode}</span>
          )}
          <span className={`flex items-center gap-1 ${connected ? 'text-teal-400' : 'text-zinc-600'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-teal-400' : 'bg-zinc-600'}`} />
            {connected ? `${status?.tabs?.length ?? 0} tab` : 'disconnected'}
          </span>
        </span>
      </div>
      {error && (
        <div className="px-3 py-1.5 border-t border-zinc-800 text-xs font-ui text-amber-400 shrink-0">
          ⚠ {error}
        </div>
      )}
    </div>
  );
}
