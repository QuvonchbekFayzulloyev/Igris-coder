import React from 'react';
import { isTauri } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';

/**
 * Dp2 tuzatildi: app TAURI (Electron emas) — oyna tugmalari `getCurrentWindow()`
 * (Tauri v2 API) orqali ishlaydi. Brend ham "Anchor" o'rniga IGRIS.
 *
 * `isTauri()` Tauri v2 ning RASMIY tekshiruvi — `window.__TAURI__` faqat
 * `withGlobalTauri: true` bo'lganda paydo bo'ladi, shuning uchun unga tayanib
 * bo'lmaydi. Brauzerda (web) `isTauri()` false qaytaradi — tugmalar xavfsiz
 * no-op bo'ladi (desktop'da real ishlaydi).
 */
export function TitleBar() {
  const tauriAvailable = isTauri();

  const handleMinimize = () => {
    if (!tauriAvailable) return;
    getCurrentWindow().minimize();
  };
  const handleMaximize = () => {
    if (!tauriAvailable) return;
    getCurrentWindow().toggleMaximize();
  };
  const handleClose = () => {
    if (!tauriAvailable) return;
    getCurrentWindow().close();
  };

  return (
    <div className="h-9 flex items-center justify-between border-b border-zinc-800 bg-zinc-900 shrink-0 z-20 select-none drag-region">
      <div className="flex items-center h-full no-drag">
        <div className="flex items-center gap-1.5 px-3">
          <span className="w-5 h-5 rounded-md bg-amber-400 text-zinc-950 text-xs font-bold flex items-center justify-center font-ui">
            I
          </span>
          <span className="text-xs font-ui text-zinc-400">IGRIS</span>
        </div>
      </div>

      {/* Window Controls */}
      <div className="flex items-center h-full no-drag">
        <button
          onClick={handleMinimize}
          aria-label="Minimize window"
          className="w-11 h-9 flex items-center justify-center text-zinc-500 hover:bg-zinc-800 transition-colors"
        >
          <svg width="12" height="1" viewBox="0 0 12 1" fill="currentColor">
            <rect width="12" height="1" />
          </svg>
        </button>
        <button
          onClick={handleMaximize}
          aria-label="Maximize window"
          className="w-11 h-9 flex items-center justify-center text-zinc-500 hover:bg-zinc-800 transition-colors"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1">
            <rect x="0.5" y="0.5" width="9" height="9" />
          </svg>
        </button>
        <button
          onClick={handleClose}
          aria-label="Close window"
          className="w-11 h-9 flex items-center justify-center text-zinc-500 hover:bg-rose-600 hover:text-white transition-colors"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.2">
            <path d="M1 1L9 9M9 1L1 9" />
          </svg>
        </button>
      </div>
    </div>
  );
}
