import React, { useEffect, useReducer, useCallback, useRef, useContext, createContext } from 'react';

/**
 * Global custom context menu (o'ng tugma menyusi) — native brauzer menyusini
 * BUTUN UI bo'ylab almashtiradi. Har bir sahifa menyuga o'z elementlarini
 * qo'shadi (menyu holati global store'da, React tree'dan mustaqil).
 *
 * API:
 *   useMenu().open(x, y, items)  — menyuni ko'rsatish
 *   useMenu().close()            — yopish
 */

export interface MenuItem {
  id?: string;
  label?: string;
  icon?: string;
  hint?: string;
  disabled?: boolean;
  danger?: boolean;
  separator?: boolean;
  action?: () => void;
}

interface MenuState {
  open: boolean;
  x: number;
  y: number;
  items: MenuItem[];
}

type MenuAction =
  | { type: 'open'; x: number; y: number; items: MenuItem[] }
  | { type: 'close' };

function menuReducer(state: MenuState, action: MenuAction): MenuState {
  switch (action.type) {
    case 'open':
      return { open: true, x: action.x, y: action.y, items: action.items };
    case 'close':
      return { ...state, open: false };
  }
}

const emptyState: MenuState = { open: false, x: 0, y: 0, items: [] };

const MenuCtx = createContext<{
  open: (x: number, y: number, items: MenuItem[]) => void;
  close: () => void;
}>({ open: () => {}, close: () => {} });

/** Menyuni istalgan komponentdan ochish uchun hook. */
export function useMenu() {
  return useContext(MenuCtx);
}

// ContextMenuLayer mount bo'lganda reducer dispatch'ini shu yerda saqlaymiz —
// shu tufayli document-level handler (React tashqarisidan) ham menyuni ochadi.
let layerDispatch: React.Dispatch<MenuAction> | null = null;

const MENU_W = 240;

export function ContextMenuLayer({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(menuReducer, emptyState);
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = React.useState({ x: 0, y: 0 });

  const close = useCallback(() => dispatch({ type: 'close' }), []);
  const open = useCallback((x: number, y: number, items: MenuItem[]) => {
    if (!items.length) return;
    dispatch({ type: 'open', x, y, items });
  }, []);

  // Reducer'ni document-level handler'larga ochib beramiz
  useEffect(() => {
    layerDispatch = dispatch;
    return () => { layerDispatch = null; };
  }, [dispatch]);

  // Menyu ekrandan chiqib ketmasligi — ochilganda joyini hisoblash
  useEffect(() => {
    if (!state.open) return;
    const el = menuRef.current;
    const h = el?.offsetHeight || 200;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    setPos({
      x: Math.max(6, Math.min(state.x, vw - MENU_W - 6)),
      y: Math.max(6, Math.min(state.y, vh - h - 6)),
    });
  }, [state.open, state.x, state.y, state.items]);

  // Tashqariga bosish / Escape / scroll — yopish
  useEffect(() => {
    if (!state.open) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && menuRef.current.contains(e.target as Node)) return;
      close();
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    const onWheel = () => close();
    window.addEventListener('mousedown', onDown, true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('wheel', onWheel, { passive: true });
    window.addEventListener('blur', close);
    return () => {
      window.removeEventListener('mousedown', onDown, true);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('blur', close);
    };
  }, [state.open, close]);

  return (
    <MenuCtx.Provider value={{ open, close }}>
      {children}
      {state.open && (
        <div
          ref={menuRef}
          style={{ left: pos.x, top: pos.y, width: MENU_W }}
          onContextMenu={(e) => e.preventDefault()}
          className="fixed z-[9999] bg-zinc-900/95 backdrop-blur border border-zinc-700 rounded-lg shadow-2xl shadow-black/60 py-1 select-none ctx-menu-pop"
        >
          {state.items.map((item, i) =>
            item.separator ? (
              <div key={`sep-${i}`} className="my-1 border-t border-zinc-800" />
            ) : (
              <button
                key={item.id || `${item.label}-${i}`}
                disabled={item.disabled}
                onClick={() => { close(); item.action?.(); }}
                className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs font-ui transition-colors disabled:opacity-40 disabled:cursor-default ${
                  item.danger
                    ? 'text-rose-400 hover:bg-rose-950/60 hover:text-rose-300'
                    : 'text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100'
                }`}
              >
                <span className="w-4 text-center shrink-0 text-sm leading-none">{item.icon || ''}</span>
                <span className="flex-1 truncate">{item.label}</span>
                {item.hint && <span className="text-[10px] font-mono text-zinc-600 shrink-0">{item.hint}</span>}
              </button>
            ),
          )}
        </div>
      )}
    </MenuCtx.Provider>
  );
}

/**
 * Tahrirlanadigan element (INPUT/TEXTAREA/contentEditable) uchun matn-tahrirlash
 * menyusi — native menyuning o'rniga ko'rsatiladi.
 */
function openTextEditMenu(el: HTMLElement, x: number, y: number) {
  if (!layerDispatch) return; // React hali mount bo'lmagan — faqat bloklaymiz
  const exec = (cmd: string) => {
    try { el.focus(); document.execCommand(cmd); } catch { /* ignore */ }
  };
  const items: MenuItem[] = [
    { id: 'tx-cut', label: 'Kesib olish', icon: '✂', hint: 'Ctrl+X', action: () => exec('cut') },
    { id: 'tx-copy', label: 'Nusxa olish', icon: '⧉', hint: 'Ctrl+C', action: () => exec('copy') },
    {
      id: 'tx-paste', label: 'Yopishtirish', icon: '📋', hint: 'Ctrl+V',
      action: () => {
        el.focus();
        // execCommand('paste') Chromium'da bloklangan — async Clipboard API ishlatamiz
        navigator.clipboard?.readText?.()
          .then((text) => { try { document.execCommand('insertText', false, text); } catch { /* ignore */ } })
          .catch(() => { /* ruxsat yo'q — hech narsa qilmaymiz */ });
      },
    },
    { id: 'tx-selall', label: 'Hammasini tanlash', icon: '▢', hint: 'Ctrl+A', action: () => exec('selectAll') },
  ];
  layerDispatch({ type: 'open', x, y, items });
}

/**
 * Global: native menu'ni BUTUN app bo'ylab bloklash (index.tsx'da ishlatiladi).
 * Matn inputlarida ham native menyu o'rniga custom matn-tahrirlash menyusi chiqadi.
 */
export function installGlobalMenuBlock(): () => void {
  const handler = (e: MouseEvent) => {
    e.preventDefault();
    const target = e.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
      openTextEditMenu(target, e.clientX, e.clientY);
    }
    // Qolgan hollarda App.tsx'dagi onGlobalContextMenu yoki view menyulari o'zini
    // ko'rsatadi (ular ham preventDefault qiladi) — bu yerda faqat bloklaymiz.
  };
  document.addEventListener('contextmenu', handler);
  return () => document.removeEventListener('contextmenu', handler);
}
