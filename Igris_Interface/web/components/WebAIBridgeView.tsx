import React, { useState, useEffect, useCallback } from 'react';
import { webaiStatus, webaiAction, webaiScreenshotUrl, WebAIStatus, WebAITab } from '../backend';

/**
 * Web AI Bridge — REAL browser automation.
 * Igris_brain /api/webai/* proxy orqali web_ai_bridge MCP serveri (Playwright +
 * real Chrome) boshqariladi: ochiq tablar, navigation, jonli screenshot.
 * Bridge ulanmagan bo'lsa — halol bo'sh holat ko'rsatiladi (soxta session yo'q).
 */
export function WebAIBridgeView() {
  const [status, setStatus] = useState<WebAIStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [urlDraft, setUrlDraft] = useState('');
  const [shotUrl, setShotUrl] = useState('');
  const [shotError, setShotError] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const st = await webaiStatus();
      setStatus(st);
      setError('');
      if (st.connected) {
        setShotUrl(webaiScreenshotUrl());
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
  }, []);

  useEffect(() => {
    refresh();
    // davriy yangilanish: brauzer holati o'zgarsa ko'rinadi
    const iv = setInterval(refresh, 6000);
    return () => clearInterval(iv);
  }, [refresh]);

  const doAction = async (action: string, opts?: { url?: string; index?: number }) => {
    setError('');
    try {
      const r = await webaiAction(action, opts);
      if (!r.ok && r.error) setError(r.error);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'action failed');
    }
    await refresh();
  };

  const navigate = (raw: string) => {
    const url = raw.trim();
    if (!url) return;
    const withProto = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    setUrlDraft('');
    doAction('navigate', { url: withProto });
  };

  const connected = Boolean(status?.connected);

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Tabs */}
      <div className="flex items-center border-b border-zinc-800 shrink-0 px-1 pt-1 gap-1 bg-zinc-900 bg-opacity-30 overflow-x-auto">
        {(status?.tabs || []).map((t: WebAITab) => (
          <button
            key={t.index}
            onClick={() => t.index >= 0 && !t.active && doAction('switch_tab', { index: t.index })}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-ui rounded-t-md border-t border-x max-w-44 ${
              t.active
                ? 'bg-zinc-950 border-zinc-800 text-zinc-100'
                : 'bg-transparent border-transparent text-zinc-500 hover:text-zinc-300'
            }`}
            title={t.url || '(blank tab)'}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-teal-400 shrink-0" />
            <span className="truncate">{t.title || t.url || `Tab ${t.index}`}</span>
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation();
                doAction('close_tab', { index: t.index });
              }}
              className="text-zinc-600 hover:text-zinc-200 ml-1"
            >
              ✕
            </span>
          </button>
        ))}
        <button
          onClick={() => doAction('new_tab')}
          className="px-2.5 py-1.5 text-xs font-ui text-zinc-500 hover:text-zinc-200 shrink-0"
          title="New tab"
        >
          +
        </button>
      </div>

      {/* Browser Controls */}
      <div className="flex items-center gap-2 px-2 py-1.5 border-b border-zinc-800 shrink-0">
        <button
          onClick={() => doAction('back')}
          disabled={!connected}
          className="text-zinc-600 hover:text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-default"
          title="Go back"
        >
          ←
        </button>
        <button
          onClick={() => doAction('forward')}
          disabled={!connected}
          className="text-zinc-600 hover:text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-default"
          title="Go forward"
        >
          →
        </button>
        <button
          onClick={() => doAction('refresh')}
          disabled={!connected}
          className="text-zinc-600 hover:text-zinc-300 transition-colors disabled:opacity-40 disabled:cursor-default"
          title="Reload"
        >
          ↻
        </button>
        <div className="flex-1 flex items-center gap-1.5 bg-zinc-900 border border-zinc-800 rounded-md px-2.5 py-1 min-w-0 focus-within:border-zinc-600">
          <span className="text-teal-400 shrink-0">🔒</span>
          <input
            value={urlDraft}
            onChange={(e) => setUrlDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') navigate(urlDraft);
            }}
            placeholder={connected ? 'https://…' : 'bridge ulanmagan'}
            disabled={!connected}
            className="bg-transparent outline-none text-xs font-mono text-zinc-300 flex-1 min-w-0 placeholder-zinc-600 disabled:opacity-50"
          />
        </div>
      </div>

      {/* Browser Content */}
      <div className="flex-1 relative overflow-hidden bg-zinc-900">
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
        ) : shotError || !shotUrl ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs font-ui text-zinc-600">
            screenshot olinmadi — brauzer holatini tekshiring
          </div>
        ) : (
          <img
            src={shotUrl}
            alt="Live browser screenshot"
            onError={() => setShotError(true)}
            className="w-full h-full object-contain"
          />
        )}
      </div>

      {/* Status Bar */}
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
          {error}
        </div>
      )}
    </div>
  );
}
