import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { workspaceFileText } from '../backend';

// ---------------------------------------------------------------------- //
// Types (ui_builder.py spec formatiga mos)
// ---------------------------------------------------------------------- //

export interface UbElement {
  type: string;
  id?: string;
  parent?: string;
  x: number;
  y: number;
  w: number;
  h: number;
  fill?: string;
  stroke?: string;
  strokeW?: number;
  radius?: number;
  opacity?: number;
  shadow?: boolean;
  text?: string;
  color?: string;
  size?: number;
  weight?: number;
  align?: string;
  glyph?: string;
  placeholder?: string;
  bg?: string;
  border?: string;
  action?: { kind: string; target: string };
  target?: string;
  collapsedW?: number;
}

export interface UbInteraction {
  kind: string;
  trigger?: string;
  target?: string;
  collapsedW?: number;
  main?: string;
}

export interface UbStage {
  id: string;
  title: string;
  elements: UbElement[];
  interactions: UbInteraction[];
}

export interface UbSpec {
  version: number;
  app: string;
  theme: string;
  canvas: { w: number; h: number };
  vars: Record<string, string>;
  stages: UbStage[];
  plan?: {
    layers: string[][];
    exec_order: string[];
    stage_plan: { stage: string; title: string; element_count: number; start_exec: number; end_exec: number }[];
    overlaps: { stage_a: string; stage_b: string; severity: string; msg: string }[];
    bounds: string[];
    bricks: { total_elements: number; unique_bricks: number; reusable_bricks: number; reuse_ratio: number; top_bricks: { type: string; count: number }[] };
    issues_total: number;
  };
}

interface FlatEl {
  idx: number;
  stageIdx: number;
  stageTitle: string;
  el: UbElement;
}

// ---------------------------------------------------------------------- //
// Todo interaktivlik (spec.app === 'todo' da yoqiladi) — qo'shish, bajarish,
// o'chirish, filtrlar, ustuvorlik, localStorage'da saqlash. TodoMVC'dan kuchli.
// ---------------------------------------------------------------------- //

type TodoFilter = 'all' | 'active' | 'done';
type TodoPrio = 'low' | 'med' | 'high';

interface TodoItem {
  id: number;
  text: string;
  done: boolean;
  prio: TodoPrio;
}

const TODO_PRIO_COLOR: Record<TodoPrio, string> = {
  low: '#2f9e4f',
  med: '#f5a623',
  high: '#ef4444',
};

const TODO_PRIO_LABEL: Record<TodoPrio, string> = {
  low: 'Past',
  med: "O'rta",
  high: 'Yuqori',
};

function todoStorageKey(path: string): string {
  return `ub-todo:${path}`;
}

function loadTodos(path: string): TodoItem[] {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(todoStorageKey(path)) : null;
    if (raw !== null) {
      const arr = JSON.parse(raw) as TodoItem[];
      return Array.isArray(arr) ? arr.filter((t) => t && typeof t.text === 'string') : [];
    }
  } catch {
    /* localStorage band — namunalar bilan davom etamiz */
  }
  // Birinchi ochilish — namuna vazifalar (real qo'shish/o'chirish darhol ishlaydi)
  return [
    { id: 1, text: 'Hisobotni tayyorlash', done: false, prio: 'high' },
    { id: 2, text: "Do'kondan yashil olma olish", done: true, prio: 'low' },
    { id: 3, text: "Igris demo'ni mashq qilish", done: false, prio: 'med' },
  ];
}

// ---------------------------------------------------------------------- //
// Element quruvchi (hammasi INLINE style — foreignObject video capture ham
// bir xil ko'rinadi; Tailwind klasslari ishlatilmaydi)
// ---------------------------------------------------------------------- //

function buildElStyle(el: UbElement, collapsed: Set<string>, open: Set<string>): React.CSSProperties {
  const s: React.CSSProperties = {
    position: 'absolute',
    left: el.x,
    top: el.y,
    width: el.w,
    height: el.h,
    boxSizing: 'border-box',
    opacity: el.opacity ?? 1,
  };
  // Bosh menyu (sidebar) yopilganda — main section'ni uning o'rniga siljitamiz
  // (qavatlar bir-biriga xalaqit qilmasligi uchun). Yopilgan kenglik spec'dan
  // olinadi: sidebar rect'ning collapsedW atributi (yo'q bo'lsa 56 default).
  if (el.type === 'rect' && el.id === 'main' && collapsed.has('sidebar')) {
    const cw = typeof (el as { collapsedW?: number }).collapsedW === 'number'
      ? (el as { collapsedW?: number }).collapsedW as number
      : 56;
    const shift = (el.x ?? 0) - cw;
    s.left = cw;
    s.width = (el.w ?? 0) + Math.max(0, shift);
    s.transition = 'left 0.35s ease, width 0.35s ease';
  }
  if (el.radius !== undefined) s.borderRadius = el.radius;
  if (el.shadow) s.boxShadow = '0 18px 50px rgba(0,0,0,0.45)';
  if (el.type === 'rect' || el.type === 'modal' || el.type === 'avatar' || el.type === 'bar' || el.type === 'chip') {
    s.background = el.fill ?? 'transparent';
    if (el.stroke) { s.border = `${el.strokeW ?? 1}px solid ${el.stroke}`; }
  }
  if (el.type === 'modal') {
    s.display = open.has(el.id || '') ? 'block' : 'none';
    s.overflow = 'hidden';
  }
  if (el.type === 'text' || el.type === 'chip') {
    s.color = el.color;
    s.fontSize = el.size ?? 14;
    s.fontWeight = el.weight ?? 400;
    s.textAlign = (el.align as React.CSSProperties['textAlign']) ?? 'left';
    s.lineHeight = `${el.h}px`;
    s.overflow = 'hidden';
    s.whiteSpace = 'nowrap';
    if (el.type === 'chip') { s.textAlign = 'center'; s.color = el.color ?? '#fff'; s.lineHeight = `${el.h}px`; }
  }
  if (el.type === 'icon') {
    s.color = el.color;
    s.fontSize = el.size ?? 16;
    s.lineHeight = `${el.h}px`;
    s.textAlign = 'center';
    s.userSelect = 'none';
  }
  if (el.type === 'button') {
    s.background = el.bg;
    s.color = el.color;
    s.fontSize = el.size ?? 14;
    s.fontWeight = el.weight ?? 500;
    s.border = 'none';
    s.cursor = el.action ? 'pointer' : 'default';
    s.display = 'flex';
    s.alignItems = 'center';
    s.justifyContent = 'center';
  }
  if (el.type === 'toggle') {
    s.background = 'rgba(255,255,255,0.06)';
    s.color = el.color;
    s.fontSize = 18;
    s.border = '1px solid rgba(255,255,255,0.12)';
    s.cursor = 'pointer';
    s.display = 'flex';
    s.alignItems = 'center';
    s.justifyContent = 'center';
  }
  if (el.type === 'input') {
    s.background = el.bg ?? 'transparent';
    s.border = `1px solid ${el.border ?? 'rgba(255,255,255,0.15)'}`;
    s.color = el.color ?? '#e4e4e7';
    s.fontSize = 13;
    s.padding = '0 14px';
    s.outline = 'none';
  }
  if (el.type === 'avatar') {
    s.borderRadius = '50%';
    s.display = 'flex';
    s.alignItems = 'center';
    s.justifyContent = 'center';
    s.color = '#ffffff';
    s.fontSize = Math.max(8, Math.round(el.h * 0.32));
    s.fontWeight = 600;
  }
  if (el.type === 'rect' && el.id && collapsed.has(el.id)) {
    s.width = el.collapsedW ?? 56;
    s.transition = 'width 0.35s ease, left 0.35s ease';
  }
  if (el.type === 'rect' && el.id && open.has('x-' + el.id)) {
    // (reserved)
  }
  return s;
}

// ---------------------------------------------------------------------- //

export function LiveBuildHTML({ path, onEdited }: { path: string; onEdited?: (p: string) => void }) {
  const [spec, setSpec] = useState<UbSpec | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [builtTotal, setBuiltTotal] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [recording, setRecording] = useState(false);

  // Part M (A5): tab yashiringanda real HTML qurilishi ham pauza — bir nechta
  // .uibuild.json kartasi montajda qolsa GPU yuklanmaydi.
  useEffect(() => {
    const onVis = () => { if (document.hidden) setPlaying(false); };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

  // ----- Todo interaktivlik (spec.app == 'todo') -----
  const isTodo = spec?.app === 'todo';
  const [todos, setTodos] = useState<TodoItem[]>(() => loadTodos(path));
  const [filter, setFilter] = useState<TodoFilter>('all');
  const [prio, setPrio] = useState<TodoPrio>('med');
  const todoInputRef = useRef<HTMLInputElement>(null);
  const modalInputRef = useRef<HTMLInputElement>(null);
  const prioRef = useRef<TodoPrio>(prio);
  useEffect(() => { prioRef.current = prio; }, [prio]);
  // Path o'zgarganda (boshqa spec ochilganda) todo holatini qayta yuklaymiz —
  // `useState` init faqat mount'da ishlaydi, shuning uchun shu yerda sinxronlash.
  useEffect(() => {
    setTodos(loadTodos(path));
    setFilter('all');
    setPrio('med');
  }, [path]);
  useEffect(() => {
    try { localStorage.setItem(todoStorageKey(path), JSON.stringify(todos)); } catch { /* localStorage band */ }
  }, [todos, path]);

  const addTodo = useCallback((text: string) => {
    const t = (text || '').trim();
    if (!t) return;
    setTodos((prev) => [...prev, { id: Date.now() + Math.random(), text: t, done: false, prio: prioRef.current }]);
  }, []);

  const toggleTodo = useCallback((id: number) => {
    setTodos((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));
  }, []);

  const deleteTodo = useCallback((id: number) => {
    setTodos((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearDone = useCallback(() => {
    setTodos((prev) => prev.filter((t) => !t.done));
  }, []);

  const canvasRef = useRef<HTMLDivElement>(null);
  const pendingOpenRef = useRef<Set<string>>(new Set());
  const mediaRecRef = useRef<MediaRecorder | null>(null);
  const recChunksRef = useRef<Blob[]>([]);
  const recCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const recFrameRef = useRef(0);

  // ----- spec yuklash -----
  useEffect(() => {
    let cancelled = false;
    setError(null);
    setSpec(null);
    // Yangi spec ochilganda eski kutilayotgan ochishlar / holatlar qolib
    // ketmasligi uchun tozalanadi (boshqa karta ochilganda qolib qolgan
    // modal ochilishi yangi spec'ga oqib kelmasligi uchun).
    pendingOpenRef.current.clear();
    setOpen(new Set());
    setCollapsed(new Set());
    workspaceFileText(path)
      .then((text) => {
        if (cancelled) return;
        const parsed = JSON.parse(text) as UbSpec;
        if (!parsed.stages) throw new Error('not a build spec');
        setSpec(parsed);
        setBuiltTotal(0);
        setPlaying(true);
      })
      .catch((e) => { if (!cancelled) setError(String(e?.message || e)); });
    return () => { cancelled = true; };
  }, [path]);

  // ----- tekis elementlar ro'yxati -----
  const flat = useMemo<FlatEl[]>(() => {
    const out: FlatEl[] = [];
    (spec?.stages || []).forEach((st, si) => {
      st.elements.forEach((el) => out.push({ idx: out.length, stageIdx: si, stageTitle: st.title, el }));
    });
    return out;
  }, [spec]);

  const totalEls = flat.length;
  const currentStage = spec ? spec.stages[Math.min(flat[Math.max(0, builtTotal - 1)]?.stageIdx ?? 0, spec.stages.length - 1)] : null;

  // ----- qurilish soati -----
  useEffect(() => {
    if (!playing || !spec) return;
    const iv = setInterval(() => {
      setBuiltTotal((b) => {
        if (b >= totalEls) { setPlaying(false); return b; }
        return b + 1;
      });
    }, Math.max(120, 460 / speed));
    return () => clearInterval(iv);
  }, [playing, speed, totalEls, spec]);

  // ----- interaktivlik: tugmalar action'ini bog'lash -----
  const handleAction = useCallback((action: { kind: string; target?: string }, el?: UbElement) => {
    if (action.kind === 'open-modal') {
      // modal hali qurilmagan bo'lsa — qurilganda ochilishini kutadi
      const builtIds = new Set(flat.slice(0, builtTotal).map((f) => f.el.id).filter(Boolean));
      if (!action.target) return;
      if (!builtIds.has(action.target)) {
        pendingOpenRef.current.add(action.target);
        return;
      }
      setOpen((prev) => new Set(prev).add(action.target as string));
    } else if (action.kind === 'close-modal') {
      if (action.target) {
        setOpen((prev) => { const n = new Set(prev); n.delete(action.target as string); return n; });
      }
    } else if (action.kind === 'todo-add') {
      // Asosiy forma yoki modal'ga qarab tegishli input'dan o'qiymiz
      const fromModal = el?.parent === 'modal-add';
      const inputEl = fromModal ? modalInputRef.current : todoInputRef.current;
      const value = (inputEl?.value || '').trim();
      if (!value) return;
      addTodo(value);
      if (inputEl) inputEl.value = '';
      if (fromModal) setOpen((prev) => { const n = new Set(prev); n.delete('modal-add'); return n; });
    } else if (action.kind === 'todo-filter') {
      setFilter(action.target === 'active' || action.target === 'done' ? action.target : 'all');
    } else if (action.kind === 'todo-prio') {
      setPrio(action.target === 'low' || action.target === 'high' ? action.target : 'med');
    } else if (action.kind === 'todo-clear') {
      clearDone();
    }
  }, [flat, builtTotal, addTodo, clearDone]);

  // modal qurilgach kutilayotgan ochishlarni bajarish
  useEffect(() => {
    if (pendingOpenRef.current.size === 0) return;
    const builtIds = new Set(flat.slice(0, builtTotal).map((f) => f.el.id).filter(Boolean));
    let changed = false;
    const n = new Set(open);
    pendingOpenRef.current.forEach((id) => {
      if (builtIds.has(id)) { n.add(id); pendingOpenRef.current.delete(id); changed = true; }
    });
    if (changed) setOpen(n);
  }, [builtTotal, flat, open]);

  // ----- sidebar toggle -----
  const toggleSidebar = useCallback((interaction: UbInteraction) => {
    const trigger = interaction.trigger;
    if (!trigger) return;
    setCollapsed((prev) => {
      const n = new Set(prev);
      if (n.has(trigger)) n.delete(trigger); else n.add(trigger);
      return n;
    });
  }, []);

  // ----- interactionlar faqat o'z bosqichi qurilgach ishlaydi -----
  const activeInteractions = useMemo(() => {
    const out: Record<string, UbInteraction[]> = {};
    if (!spec) return out;
    let builtStages = new Set<number>();
    flat.slice(0, builtTotal).forEach((f) => builtStages.add(f.stageIdx));
    spec.stages.forEach((st, si) => {
      if (!builtStages.has(si)) return;
      st.interactions.forEach((it) => {
        const key = it.kind === 'toggle-sidebar' ? it.trigger : it.target;
        if (key) (out[key] ||= []).push(it);
      });
    });
    return out;
  }, [spec, flat, builtTotal]);

  // ----- Todo: dinamik vazifalar qatorlari (todo-list konteyneri ichida) -----
  const renderTodoRows = useCallback((listEl: UbElement): React.ReactNode => {
    const filtered = todos.filter((t) =>
      filter === 'all' ? true : filter === 'active' ? !t.done : t.done);
    if (filtered.length === 0) return null;
    const x0 = 12;
    const y0 = 8;
    const rowH = 46;
    const rowW = listEl.w - 24;
    const visible = Math.min(filtered.length, 4);
    const rows: React.ReactNode[] = [];
    for (let i = 0; i < visible; i += 1) {
      const t = filtered[i];
      rows.push(
        <div
          key={t.id}
          className="ub-todo-row"
          data-ub={`todo-item-${t.id}`}
          style={{
            position: 'absolute',
            left: x0,
            top: y0 + i * rowH,
            width: rowW,
            height: rowH - 8,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            cursor: 'pointer',
            borderBottom: i < visible - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
          }}
          onClick={() => toggleTodo(t.id)}
          title="Bajarilganini belgilash"
        >
          <div
            style={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 11,
              color: '#fff',
              border: t.done ? 'none' : `2px solid ${TODO_PRIO_COLOR[t.prio]}`,
              background: t.done ? '#2f9e4f' : 'transparent',
              transition: 'background 0.15s ease',
            }}
          >
            {t.done ? '✓' : ''}
          </div>
          <span
            style={{
              flex: 1,
              fontSize: 13,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              color: t.done ? 'rgba(255,255,255,0.35)' : '#e4e4e7',
              textDecoration: t.done ? 'line-through' : 'none',
            }}
          >
            {t.text}
          </span>
          <span
            title={`Muhimlik: ${TODO_PRIO_LABEL[t.prio]}`}
            style={{ width: 6, height: 6, borderRadius: '50%', flexShrink: 0, background: TODO_PRIO_COLOR[t.prio] }}
          />
          <button
            className="ub-todo-del"
            title="O'chirish"
            onClick={(e) => { e.stopPropagation(); deleteTodo(t.id); }}
            style={{
              width: 22,
              height: 22,
              borderRadius: 6,
              border: 'none',
              flexShrink: 0,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 12,
              color: 'rgba(255,255,255,0.55)',
              background: 'rgba(255,255,255,0.08)',
              opacity: 0,
              transition: 'opacity 0.15s ease, background 0.15s ease',
            }}
          >
            ✕
          </button>
        </div>,
      );
    }
    if (filtered.length > visible) {
      rows.push(
        <div
          key="more"
          style={{ position: 'absolute', left: x0, top: y0 + visible * rowH, width: rowW, fontSize: 11, color: 'rgba(255,255,255,0.4)' }}
        >
          +{filtered.length - visible} ta ko'proq
        </div>,
      );
    }
    return <>{rows}</>;
  }, [todos, filter, toggleTodo, deleteTodo]);

  // ----- elementlarni daraxt qilib render qilish -----
  // REAL qurilish: hali qurilmagan element (idx >= builtTotal) umuman
  // ko'rinmaydi — qurilish soati ularni navbat bilan paydo qiladi. Parent
  // har doim boladan oldinroq bosqichda, shuning uchun bola qurilganda
  // parent ham qurilgan bo'ladi.
  const renderEls = useCallback((els: FlatEl[], parentId?: string): React.ReactNode => {
    const accent = spec?.vars.accent || '#f5a623';
    const filteredTodo = isTodo
      ? todos.filter((t) => (filter === 'all' ? true : filter === 'active' ? !t.done : t.done))
      : [];
    return els
      .filter((f) => f.idx < builtTotal)
      .filter((f) => f.el.parent === parentId && f.el.id !== parentId)
      .map((f, i) => {
        const el = f.el;
        let style = buildElStyle(el, collapsed, open);
        // MUXIM: `id` bo'lmagan elementga bolalar izlash NOO'G'RI — `parentId`
        // undefined bo'lsa filter barcha root elementlarni qaytaradi va
        // cheksiz rekursiya (Maximum call stack) yuzaga keladi. Faqat aniq
        // `id` bor elementlar rekursiyaga kirishi mumkin (parent->bola grafigi).
        const children = el.id ? renderEls(els, el.id) : null;
        // Todo: ro'yxat konteyneri ichidagi dinamik qatorlar
        let extraChildren: React.ReactNode = null;
        if (isTodo && el.id === 'todo-list') {
          style = { ...style, overflow: 'hidden' };
          extraChildren = renderTodoRows(el);
        }
        // Todo: bo'sh holat xabari — vazifalar bor bo'lsa yashirinadi
        if (isTodo && el.id === 'todo-empty' && filteredTodo.length > 0) {
          style = { ...style, display: 'none' };
        }
        // data-ub: test/avtomatlashtirish uchun identifikator (id yoki tur)
        const ubId = el.id
          || (el.type === 'icon' && el.glyph ? `icon-${el.glyph}` : '')
          || (el.type === 'button' && el.text ? `btn-${el.text}` : '')
          || el.type;
        // key HAMMA VAQT yagona (f.idx) — spec'da dublikat id'lar bo'lishi
        // mumkin (masalan btn-modal-add 3 marta), React'da noyob key shart.
        const base: Record<string, unknown> = {
          'data-ub': ubId,
        };
        if (el.id) base.id = el.id;
        const textContent = isTodo && el.id === 'todo-count'
          ? `${todos.filter((t) => !t.done).length} ta qoldi`
          : el.text;
        const content = (
          <>
            {el.type === 'text' && textContent}
            {el.type === 'icon' && el.glyph}
            {el.type === 'button' && el.text}
            {el.type === 'toggle' && el.glyph}
            {el.type === 'chip' && el.text}
            {el.type === 'avatar' && el.glyph}
            {children}
            {extraChildren}
          </>
        );
        if (el.type === 'button') {
          let btnStyle = style;
          // Filtr tugmasi — faol filtr accent rangda
          if (isTodo && el.id && el.id.startsWith('filter-')) {
            const activeFilter =
              (el.id === 'filter-all' && filter === 'all') ||
              (el.id === 'filter-active' && filter === 'active') ||
              (el.id === 'filter-done' && filter === 'done');
            if (activeFilter) {
              btnStyle = { ...style, background: accent, color: '#fff', boxShadow: '0 4px 16px rgba(0,0,0,0.35)' };
            }
          }
          // Ustuvorlik tugmasi — tanlangan prio accent rangda
          if (isTodo && el.id && el.id.startsWith('prio-')) {
            const target = el.id === 'prio-low' ? 'low' : el.id === 'prio-high' ? 'high' : 'med';
            if (prio === target) btnStyle = { ...style, background: accent, color: '#fff' };
          }
          return (
            <button key={f.idx} {...base} style={btnStyle} onClick={() => el.action && handleAction(el.action, el)}>
              {content}
            </button>
          );
        }
        if (el.type === 'toggle') {
          // Toggle'da `id` yo'q — `target` orqali topiladi (sidebar ochish/yopish).
          // activeInteractions kaliti = interaction.trigger (sidebar id).
          const key = el.id || el.target || '';
          const interaction = (activeInteractions[key] || []).find((i) => i.kind === 'toggle-sidebar')
            || (activeInteractions[el.target || ''] || []).find((i) => i.kind === 'toggle-sidebar');
          return (
            <button key={f.idx} {...base} style={style} onClick={() => interaction ? toggleSidebar(interaction) : undefined}>
              {content}
            </button>
          );
        }
        if (el.type === 'input') {
          if (isTodo && (el.id === 'todo-input' || el.id === 'todo-input-modal')) {
            const elInputRef = el.id === 'todo-input' ? todoInputRef : modalInputRef;
            return (
              <input
                key={f.idx}
                {...base}
                ref={elInputRef}
                style={style}
                placeholder={el.placeholder}
                onKeyDown={(e) => {
                  if (e.key !== 'Enter') return;
                  const v = (elInputRef.current?.value || '').trim();
                  if (!v) return;
                  addTodo(v);
                  if (elInputRef.current) elInputRef.current.value = '';
                  if (el.id === 'todo-input-modal') {
                    setOpen((prev) => { const n = new Set(prev); n.delete('modal-add'); return n; });
                  }
                }}
              />
            );
          }
          return <input key={f.idx} {...base} style={style} placeholder={el.placeholder} />;
        }
        return <div key={f.idx} {...base} style={style}>{content}</div>;
      });
  }, [collapsed, open, activeInteractions, handleAction, toggleSidebar, builtTotal, isTodo, todos, filter, prio, addTodo, renderTodoRows, spec]);

  // ------------------------------------------------------------------ //
  // Video yozib olish (foreignObject mirror)
  // ------------------------------------------------------------------ //

  const drawHtmlToCanvas = useCallback((canvas: HTMLCanvasElement, tokenRef?: React.MutableRefObject<number>, token = 0) => {
    const root = canvasRef.current;
    if (!root) return;
    const clone = root.cloneNode(true) as HTMLElement;
    const W = spec?.canvas.w || 960;
    const H = spec?.canvas.h || 640;
    // MUXIM: foreignObject ichidagi HTML XHTML namespace'ida bo'lishi shart —
    // aks holda Chrome uni render qilmaydi (kadr bo'sh/oq qoladi).
    // `outerHTML` namespace'ni qo'shmaydi; XMLSerializer esa avtomatik
    // xmlns="http://www.w3.org/1999/xhtml" qo'shib beradi.
    const xhtml = new XMLSerializer().serializeToString(clone);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}">` +
      `<foreignObject width="${W}" height="${H}">${xhtml}</foreignObject></svg>`;
    const img = new Image();
    img.onload = () => {
      if (tokenRef && tokenRef.current !== token) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    };
    img.onerror = () => { /* SVG render bo'lmadi — kadr bo'sh qoladi */ };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }, [spec]);

  const saveVideo = useCallback(() => {
    const mime = mediaRecRef.current?.mimeType || 'video/webm';
    const ext = mime.includes('mp4') ? 'mp4' : 'webm';
    const blob = new Blob(recChunksRef.current, { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `uibuild_${Date.now()}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    setRecording(false);
    mediaRecRef.current = null;
  }, []);

  const stopRecord = useCallback(() => {
    const rec = mediaRecRef.current;
    if (rec && rec.state !== 'inactive') { try { rec.stop(); } catch { saveVideo(); } }
  }, [saveVideo]);

  const startRecord = useCallback(() => {
    if (recording || !spec) return;
    const W = spec.canvas.w;
    const H = spec.canvas.h;
    const scale = 2;
    const canvas = document.createElement('canvas');
    canvas.width = W * scale;
    canvas.height = H * scale;
    recCanvasRef.current = canvas;
    const stream = canvas.captureStream(30);
    const mime = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
      .find((c) => window.MediaRecorder && MediaRecorder.isTypeSupported(c));
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime, videoBitsPerSecond: 6_000_000 } : undefined);
    recChunksRef.current = [];
    rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) recChunksRef.current.push(e.data); };
    rec.onstop = () => saveVideo();
    mediaRecRef.current = rec;
    rec.start(100);
    setRecording(true);
    recFrameRef.current = 0;
    setBuiltTotal(0);
    setPlaying(true);
  }, [recording, spec, saveVideo]);

  // yozuv paytida har kadrda mirror
  useEffect(() => {
    if (!recording || !recCanvasRef.current) return;
    const token = ++recFrameRef.current;
    drawHtmlToCanvas(recCanvasRef.current, recFrameRef, token);
  }, [builtTotal, recording, open, collapsed, drawHtmlToCanvas]);

  // qurilish tugagach yozuvni to'xtatish
  useEffect(() => {
    if (!recording || builtTotal < totalEls) return;
    const t = setTimeout(() => {
      const rec = mediaRecRef.current;
      if (rec && rec.state === 'recording') { try { rec.stop(); } catch { saveVideo(); } }
    }, 600);
    return () => clearTimeout(t);
  }, [recording, builtTotal, totalEls, saveVideo]);

  // ------------------------------------------------------------------ //

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-full text-zinc-600 font-ui text-sm">
        <div className="max-w-md text-center px-4">// {error}</div>
      </div>
    );
  }
  if (!spec) {
    return (
      <div className="flex items-center justify-center min-h-full text-zinc-600 font-ui text-sm">
        <span className="animate-pulse">yuklanmoqda: {path}</span>
      </div>
    );
  }

  const W = spec.canvas.w;
  const H = spec.canvas.h;
  const pct = Math.round((builtTotal / Math.max(1, totalEls)) * 100);
  const finished = builtTotal >= totalEls;
  const stageTitle = currentStage?.title || '';

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <div className="flex-1 min-h-0 flex items-center justify-center p-3 bg-zinc-950 relative overflow-hidden">
        <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
          <div
            style={{
              width: W,
              height: H,
              transform: 'scale(var(--ub-scale, 0.6))',
              transformOrigin: 'center center',
            }}
            ref={(node) => {
              // canvasni qutichaga moslab masshtablash
              if (!node) return;
              const parent = node.parentElement;
              if (!parent) return;
              const pw = parent.clientWidth - 8;
              const ph = parent.clientHeight - 8;
              const s = Math.min(1, pw / W, ph / H);
              node.style.setProperty('--ub-scale', String(Math.max(0.1, s)));
            }}
          >
            <div
              ref={canvasRef}
              className="ub-canvas"
              style={{
                width: W,
                height: H,
                position: 'relative',
                background: spec.vars.bg || '#17171b',
                overflow: 'hidden',
                borderRadius: 8,
                boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
                fontFamily: 'system-ui, sans-serif',
              }}
            >
              {isTodo && (
                <style>{`
                  .ub-todo-row { animation: ub-todo-in 0.25s ease both; }
                  @keyframes ub-todo-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
                  .ub-todo-row:hover .ub-todo-del { opacity: 1 !important; }
                  .ub-todo-del:hover { background: rgba(239,68,68,0.4) !important; color: #fff !important; }
                `}</style>
              )}
              {renderEls(flat)}
            </div>
          </div>
        </div>
        {/* holat */}
        <div className="absolute top-3 left-3 flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${playing ? 'bg-amber-400 animate-pulse' : finished ? 'bg-teal-400' : 'bg-zinc-600'}`} />
          <span className="text-[10px] font-mono text-zinc-500">
            {finished ? 'QURILISH TUGADI' : playing ? 'QURILMOQDA' : 'PAUZA'}
          </span>
          {recording && <span className="text-[10px] font-mono text-rose-400 animate-pulse">● REC</span>}
        </div>
        <div className="absolute top-3 right-3 text-[10px] font-mono text-zinc-500 max-w-[55%] truncate">
          {stageTitle}
        </div>
        <div className="absolute bottom-2 right-3 text-[10px] font-mono text-zinc-600">
          {builtTotal}/{totalEls} element · {pct}%
        </div>
      </div>

      {/* progress */}
      <div className="h-1 bg-zinc-800 shrink-0">
        <div className={`h-full transition-[width] duration-200 ${finished ? 'bg-teal-400' : 'bg-amber-400'}`} style={{ width: `${pct}%` }} />
      </div>

      {/* controls */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-t border-zinc-800 shrink-0 flex-wrap">
        {playing ? (
          <button onClick={() => setPlaying(false)} title="Pauza" className="w-7 h-7 rounded-md bg-amber-400 text-zinc-950 hover:bg-amber-300 flex items-center justify-center transition-colors">⏸</button>
        ) : (
          <button onClick={() => { if (finished) { setBuiltTotal(0); pendingOpenRef.current.clear(); setOpen(new Set()); setCollapsed(new Set()); } setPlaying(true); }} title="Davom etish / boshidan" className="w-7 h-7 rounded-md bg-amber-400 text-zinc-950 hover:bg-amber-300 flex items-center justify-center transition-colors">▶</button>
        )}
        <button onClick={() => { setBuiltTotal((b) => Math.max(0, b - 3)); setPlaying(false); }} title="Orqaga qadam" className="w-7 h-7 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 flex items-center justify-center transition-colors">◀</button>
        <button onClick={() => { setBuiltTotal((b) => Math.min(totalEls, b + 3)); if (builtTotal >= totalEls) setPlaying(false); }} title="Oldinga qadam" className="w-7 h-7 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 flex items-center justify-center transition-colors">▶|</button>
        <button onClick={() => setSpeed((s) => (s >= 4 ? 0.5 : s * 2))} title="Tezlik" className="text-[10px] font-mono px-2 py-1 rounded text-zinc-400 hover:text-amber-300 hover:bg-zinc-800 transition-colors">{speed}×</button>
        <button
          onClick={recording ? stopRecord : startRecord}
          title={recording ? "To'xtatish va videoni saqlash (WebM)" : 'Qurilishni videoga yozib olish (WebM)'}
          className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors ${recording ? 'bg-rose-500 text-white animate-pulse' : 'text-zinc-400 hover:text-rose-300 hover:bg-zinc-800'}`}
        >
          {recording ? '⏹' : '🎬'}
        </button>
        <div className="flex-1" />
        <button
          onClick={() => setCollapsed((prev) => { const n = new Set(prev); n.has('sidebar') ? n.delete('sidebar') : n.add('sidebar'); return n; })}
          title="Sidebar ochish/yopish"
          className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 text-zinc-400 hover:text-sky-300 hover:border-sky-500/50 transition-colors"
        >
          ⇄ sidebar
        </button>
      </div>

      {/* universal reja paneli — qavatlar, puzzle tartibi, overlap tekshiruvi */}
      <div className="px-3 py-1.5 border-t border-zinc-800 text-[10px] font-mono text-zinc-600 shrink-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span>real qurilish — fon → section → nav → kontent → tugma → oyna</span>
          {spec.plan && (
            <>
              <span className="text-zinc-700">·</span>
              <span className="text-sky-400">plan: {spec.plan.layers.length} qavat</span>
              <span className="text-zinc-700">·</span>
              <span className="text-teal-400">brick reuse {Math.round(spec.plan.bricks.reuse_ratio * 100)}%</span>
              {spec.plan.overlaps.length > 0 ? (
                <span className="text-rose-400" title={spec.plan.overlaps.map((o) => o.msg).join('\n')}>
                  ⚠ {spec.plan.overlaps.length} xalaqit
                </span>
              ) : (
                <span className="text-teal-400">✓ qavatlar xalaqit qilmaydi</span>
              )}
            </>
          )}
          {onEdited && (
            <button
              onClick={() => onEdited(path)}
              title="Chat'ga yangi karta qo'shish (onEdited ulanishi)"
              className="ml-auto shrink-0 text-[10px] font-mono px-2 py-0.5 rounded border border-zinc-700 text-zinc-400 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
            >
              ✎ chat'ga qaytarish
            </button>
          )}
        </div>
        {spec.plan && spec.plan.stage_plan && spec.plan.stage_plan.length > 0 && (
          <div className="flex items-center gap-1 mt-1 flex-wrap">
            {spec.plan.stage_plan.map((sp, i) => {
              const active = currentStage && currentStage.id === sp.stage;
              const done = sp.end_exec < builtTotal;
              return (
                <span
                  key={sp.stage}
                  className={`px-1.5 py-0.5 rounded text-[9px] ${done ? 'bg-teal-950 text-teal-300' : active ? 'bg-sky-950 text-sky-300 border border-sky-500/40' : 'bg-zinc-900 text-zinc-600 border border-zinc-800'}`}
                >
                  {sp.title.split('·')[1]?.trim() || sp.title} ({sp.element_count})
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
