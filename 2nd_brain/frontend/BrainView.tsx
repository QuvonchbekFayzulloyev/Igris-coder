import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { brainGraph, brainGraphVersion, brainGraphShares, saveBrainGraphShares, BrainGraphNode, BrainGraphResult } from '../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND as KIND_COLOR } from './colors';
import { useAgentConsoleStore } from '../../Igris_Interface/shared/store';
import { BranchingVisualizer } from './interactions/BranchingVisualizer';
import { NodeExpansionRing } from './interactions/NodeExpansionRing';
import { BranchPathTracer } from './interactions/BranchPathTracer';
import { GraphNavigationHUD } from './interactions/GraphNavigationHUD';
import { MouseControlsPanel } from './interactions/MouseControlsPanel';
import { TreeLayoutEngine } from './components/TreeLayoutEngine';
import { treeStore } from '../db/tree-store';
import { NodeIndicator, getDomainColor, getVerificationColor } from './akms/AKMSOverlay';

const SVG_W = 620;
const SVG_H = 380;
const MIN_SCALE = 0.3;
const MAX_SCALE = 4;
const ZOOM_STEP = 1.25;
/** REAL VAQT polling: engil version-fingerprint har 8 soniyada so'raladi;
 *  grafik FAQAT SEZILARLI o'zgarishda qayta yuklanadi — yangi modul, yangi
 *  xotira yozuvi yoki yangi suhbat (backend fingerprint'i faqat mazmunli
 *  o'zgarishda siljiydi; L1 runtime yozishlari/suhbat xabarlari shovqin). */
const VERSION_INTERVAL = 8_000;
/** QATIY SHART: avtomatik qayta yuklashlar orasidagi minimal tanaffus —
 *  versiya qanchalik tez siljisa ham grafik shuncha tez-tez ko'pi bilan bir
 *  marta yangilanadi (graf hech qachon 'sakrab' qolmaydi; o'tkazib yuborilgan
 *  o'zgarish keyingi imkoniyatda ko'rinadi). */
const MIN_RELOAD_GAP = 12_000;
/** Yangi node halqalari (fresh ring) asosiy ko'rinish muddati — badge bilan teng. */
const FRESH_RING_MS = 6_000;
/** Badge'ni bosib fresh node'larga fokuslangandan keyin halqalarning
 *  UZAYTIRILGAN muddati — zoom'da yangi node'lar yana bir necha soniya
 *  ko'rinib turadi (fokusdan so'ng ham darhol o'chib ketmaydi). */
const FRESH_RING_EXTEND_MS = 8_000;
const POS_KEY = 'igris:brain:pos';
/** Semantik joylashuv (TURBO layout) rejimlari. */
const LAYOUT_KEY = 'igris:brain:layout';
/** Kvota ulushlari: vault, chat, persistent, runtime (0..1, yig'indi 1.0). */
const DEFAULT_SHARES: number[] = [0.35, 0.25, 0.20, 0.20];
/** Graf node'larining standart yuqori chegarasi (backend default'iga mos). */
const DEFAULT_MAX_NODES = 240;
/** Panel'dagi max_nodes slider diapazoni. */
const MAX_NODES_MIN = 50;
const MAX_NODES_MAX = 600;
const MAX_NODES_STEP = 10;

/** Tarix yozuvini matnga: "30/30/20/20 · 240" (max_nodes ham ko'rinadi).
 *  Eski/chekka yozuvda shares bo'lmasa (masalan faqat max_nodes saqlangan) —
 *  faqat max_nodes ko'rsatiladi, crash bo'lmaydi. */
function fmtHistoryEntry(e: { shares: number[]; max_nodes?: number | null }): string {
  const s = e.shares ? e.shares.map((v) => Math.round(v * 100)).join('/') : '';
  if (!s) return e.max_nodes ? `· ${e.max_nodes}` : '';
  return e.max_nodes ? `${s} · ${e.max_nodes}` : s;
}
/** Graf statistikasi — backend /api/brain/graph stats (backend.ts'dagi tip). */
type BrainViewStats = NonNullable<BrainGraphResult['stats']>;

/** [kalit, label, stats'da manba soni maydoni] — panelda real statistika. */
const SHARE_LABELS: [string, string, keyof BrainViewStats | null][] = [
  ['vault', 'Vault (.md)', 'vault_files'],
  ['chat', 'Suhbatlar', 'chat_sessions'],
  ['persistent', 'L2 xotira', 'persistent_entries'],
  ['runtime', 'L1 runtime', 'runtime_entries'],
];

/** Tayyor kvota profillari — bir bosishda mos ulushlar. */
const SHARE_PRESETS: { label: string; emoji: string; shares: number[]; desc: string }[] = [
  { label: 'Balanslashgan', emoji: '⚖', shares: [0.35, 0.25, 0.20, 0.20], desc: 'standart nisbat' },
  { label: 'Vault-ustun', emoji: '📁', shares: [0.55, 0.15, 0.15, 0.15], desc: 'ko\'p .md fayllar' },
  { label: 'Chat-ustun', emoji: '💬', shares: [0.15, 0.55, 0.15, 0.15], desc: 'ko\'p suhbatlar' },
  { label: 'Xotira-ustun', emoji: '🧠', shares: [0.20, 0.15, 0.35, 0.30], desc: 'L1+L2 ko\'proq' },
];

/** Ulushlarni xavfsiz normallashtirish (yig'indi 1.0; manfiy/0 -> default). */
function normShares(s: number[]): number[] {
  const safe = s.map((x) => (Number.isFinite(x) && x > 0 ? x : 0));
  const total = safe.reduce((a, b) => a + b, 0);
  if (total <= 0) return [...DEFAULT_SHARES];
  return safe.map((x) => x / total);
}

interface View {
  scale: number;
  tx: number;
  ty: number;
}

/** Node joylashuvi override — foydalanuvchi node'larni sudrab ko'chiradi. */
type NodePos = Record<string, { x: number; y: number }>;

/** Nisbiy vaqt: "hozir", "5 daqiqa oldin", "2 soat oldin", "3 kun oldin". */
function relTime(epochSec?: number): string {
  if (!epochSec || !(epochSec > 0)) return '';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - epochSec));
  if (s < 45) return 'hozir';
  if (s < 90) return '1 daqiqa oldin';
  if (s < 3600) return `${Math.floor(s / 60)} daqiqa oldin`;
  if (s < 86400) return `${Math.floor(s / 3600)} soat oldin`;
  return `${Math.floor(s / 86400)} kun oldin`;
}

function loadSavedPos(): NodePos {
  try {
    const raw = localStorage.getItem(POS_KEY);
    return raw ? (JSON.parse(raw) as NodePos) : {};
  } catch {
    return {};
  }
}

/**
 * 2nd Brain — REAL interactive knowledge graph.
 * Igris_brain /api/brain/graph dan Igris_Memory ma'lumotlarini yuklaydi.
 *
 * Interaktiv:
 *  - node'larni SUDRAB ko'chirish (joylashuv xotirada saqlanadi)
 *  - zoom / pan / fit / reset, g'ildirak zoom, fokuslash
 *  - LIVE avto-yangilanish (yangi suhbat/xotira paydo bo'lganda graf jonlanadi,
 *    yangi node'lar oltin halqa bilan belgilanadi)
 *  - filter, tanlash + bog'langan node'lar paneli
 * Backend ulanmagan bo'lsa — halol bo'sh holat (demo mock yo'q).
 */
/** Keyboard help overlay — qator: tugma + tavsif. */
function ShortcutRow({ keys, desc }: { keys: string[]; desc: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-0.5">
        {keys.map((k, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="text-zinc-600 text-[8px]">+</span>}
            <kbd className="inline-block px-1.5 py-0.5 text-[10px] font-mono rounded bg-zinc-800 border border-zinc-700 text-zinc-200 min-w-[20px] text-center">
              {k}
            </kbd>
          </React.Fragment>
        ))}
      </div>
      <span className="text-[10px] font-mono text-zinc-400">{desc}</span>
    </div>
  );
}

export function BrainView() {
  /** Chat log'iga yangilanish sababini yozish — graf nega yangilangani chat
   *  tarixida doimiy qator sifatida qoladi (badge 6 soniyada o'chadi). */
  const pushBrainLog = useAgentConsoleStore((s) => s.pushBrainLog);
  /** Agent ishlamoqda (chat/task) — poll'ni pauza qilish uchun: xotira yozuvlari
   *  versiyani doimiy siljitadi, graf esa shu vaqtda TURG'UN turishi kerak. */
  const taskRunning = useAgentConsoleStore((s) => s.taskRunning);
  const [nodes, setNodes] = useState<BrainGraphNode[]>([]);
  const [links, setLinks] = useState<[string, string][]>([]);
  /** Link sabablari: 'a|b' -> umumiy so'zlar (zoom'da "nima uchun" ko'rsatadi).
   *  STATE emas, REF — applyGraph'da yangi ob'ekt set qilinsa callback zanjiri
   *  (linkReasonOf -> linkWeight -> computeSemanticLayout -> applySemanticIfOn
   *  -> applyGraph -> loadGraph -> useEffect) qayta-qayta ishga tushib CHEKSIZ
   *  qayta yuklash loop'iga olib borardi (2nd Brain 'sakrab' turadi, backend ham
   *  keraksiz bosim oladi). Ref'da saqlansa callback'lar turg'un bo'ladi. */
  const linkReasonsRef = useRef<Record<string, string[]>>({});
  const [stats, setStats] = useState<BrainViewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);
  /** Reload muvaffaqiyatsiz bo'lsa — eski graf qoladi, lekin status
   *  'stale (eski graf)' deb ko'rsatadi (yolg'on 'live' yorlig'i yo'q). */
  const [stale, setStale] = useState(false);
  const [liveRefresh, setLiveRefresh] = useState(true);
  /** Yangi node'lar (suhbatdan tashqari) — oltin halqa. */
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  /** Yangi SUHBAT (session) node'lari — teal halqa + pop (alohida ajralib turadi). */
  const [freshChat, setFreshChat] = useState<Set<string>>(new Set());
  /** Graf nega yangilangani — oxirgi sezilarli o'zgarish sababi (badge).
   *  Backend /api/brain/graph/version 'reason' maydoni orqali REAL sababni
   *  beradi (masalan "yangi xotira moduli: ...") — bezak emas. */
  const [liveReason, setLiveReason] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<BrainGraphNode | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  /** Hover qilingan link — sabab tooltip'ini ko'rsatish uchun. */
  const [hoveredLink, setHoveredLink] = useState<[string, string] | null>(null);
  /** Hover qilingan cluster — tooltip uchun. */
  const [hoveredCluster, setHoveredCluster] = useState<Cluster | null>(null);
  /** Kind filter — ko'rsatiladigan turlar to'plami (bo'sh = barchasi). */
  const [kindFilter, setKindFilter] = useState<Set<string>>(new Set());
  /** Expanded cluster — kengaytirilgan cluster (null = hech qanday cluster kengaytirilmagan). */
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);
  /** Merged clusters — qo'lda birlashtirilgan clusterlar (cluster_id -> birlashtirilgan cluster_id). */
  const [mergedClusters, setMergedClusters] = useState<Record<string, string>>({});
  /** Selected cluster for merge/split — tanlangan cluster. */
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [view, setView] = useState<View>({ scale: 1, tx: 0, ty: 0 });
  /** Layout scale — zoom qilganda node'lar markazdan uzoqlashadi,
   *  lekin asl pozitsiyalar saqlanadi (offsets o'zgarmaydi). */
  const [layoutScale, setLayoutScale] = useState(1);
  const [offsets, setOffsets] = useState<NodePos>(loadSavedPos);
  /** Semantik joylashuv: bog'langan node'lar tortish kuchi bilan yaqinlashadi. */
  const [semanticLayout, setSemanticLayout] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(LAYOUT_KEY);
      // Default: ON (birinchi marta ochilganda branching ko'rinsin)
      return saved === null ? true : saved === '1';
    } catch {
      return true;
    }
  });
  const svgRef = useRef<SVGSVGElement>(null);
  const dragRef = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const nodeDragRef = useRef<{ id: string; sx: number; sy: number; ox: number; oy: number } | null>(null);
  // Drag'dan keyin click'ni bostirish — pointerup click'dan OLDIN yonadi, shuning
  // uchun moved belgisi alohida ref'da saqlanadi va click handler'da o'chiriladi.
  const movedRef = useRef(false);
  const prevIdsRef = useRef<Set<string>>(new Set());
  const freshTimer = useRef<number | null>(null);
  /** Avvalgi taskRunning holati — ish tugagach darhol qo'lga olish uchun. */
  const prevTaskRunningRef = useRef(false);
  /** Graf kamida bir marta muvaffaqiyatli yuklanganmi — reload xatosi eski
   *  grafni o'chirib tashlamasligi uchun (qora ekran flash bo'lmaydi). */
  const hasLoadedRef = useRef(false);
  /** Graf yuklash ketma-ketligi — faqat ENG SO'NGGI boshlangan so'rov holatni
   *  boshqaradi (bekor qilingan so'rov `loading`ni o'zgartirib qo'ymaydi). */
  const graphSeqRef = useRef(0);
  /** Amaldagi graf so'rovini bekor qilish uchun AbortController. */
  const graphCtrlRef = useRef<AbortController | null>(null);
  /** O'zgarish sababi badge'ini avtomatik yopish uchun timer. */
  const liveReasonTimer = useRef<number | null>(null);
  /** REAL VAQT: so'nggi ko'rgan versiya — o'zgarsa grafik qayta yuklanadi. */
  const versionRef = useRef<number | null>(null);
  /** Kvota paneli ochiqligi + ulushlar (draft = slider'dagi jonli qiymat).
   *  Ulushlar SERVER'da saqlanadi (graph_shares.json) — mount'da backend'dan
   *  olinadi, o'zgarishda server'ga yuboriladi (localStorage emas).
   *  `shares` null — hali server'dan yuklanmagan: bu holda grafga query
   *  yuborilmaydi, backend O'ZI diskdagi ulushlarni ishlatadi (double-fetch
   *  va default'ning diskdagini aylanib o'tishi yo'q). */
  const [sharesPanel, setSharesPanel] = useState(false);
  const [shares, setShares] = useState<number[] | null>(null);
  const [sharesDraft, setSharesDraft] = useState<number[]>([...DEFAULT_SHARES]);
  /** Graf node chegarasi (null = hali server'dan yuklanmagan — default qo'llanadi). */
  const [maxNodes, setMaxNodes] = useState<number | null>(null);
  const [maxNodesDraft, setMaxNodesDraft] = useState<number>(DEFAULT_MAX_NODES);
  const [sharesMeta, setSharesMeta] = useState<{ updated_at?: number | null; history?: { ts: number; shares: number[]; max_nodes?: number | null }[] }>({});
  const sharesTimer = useRef<number | null>(null);
  const maxNodesTimer = useRef<number | null>(null);
  /** Foydalanuvchi slider'ga tegganmi — hydrate keyingi javobi uning
   *  o'zgarishini o'chirib tashlamasligi uchun (race himoyasi). */
  const sharesTouchedRef = useRef(false);
  /** ENG SO'NGGI qo'llangan qiymatlar — debounce timerlari closure'da eski
   *  qiymatni tutib qolmasligi uchun shu ref'dan o'qiydi (ikkala slider tez
   *  surilsa ham oxirgi save HAR IKKALA so'nggi qiymatni yozadi). */
  const settingsRef = useRef<{ shares: number[] | null; maxNodes: number | null }>({
    shares: null,
    maxNodes: null,
  });

  // ---- MOUSE INTERACTION STATE ----
  /** Kengaytirilgan node'lar (branching view uchun). */
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  /** O'ng tugma kontekst menyusi — node ID va pozitsiya. */
  const [contextMenu, setContextMenu] = useState<{ nodeId: string; x: number; y: number } | null>(null);
  /** Branch view — qaysi node'dan branching ko'rsatish. */
  const [branchViewNode, setBranchViewNode] = useState<string | null>(null);
  /** Path tracing — manzil va maqsad node ID'lari. */
  const [pathTarget, setPathTarget] = useState<{ source: string; target: string } | null>(null);
  /** Expansion ring — qaysi node ustida animation. */
  const [expansionSource, setExpansionSource] = useState<BrainGraphNode | null>(null);
  /** Mouse modifier tugmalari holati. */
  const [shiftDown, setShiftDown] = useState(false);
  const [ctrlDown, setCtrlDown] = useState(false);
  const [altDown, setAltDown] = useState(false);
  /** Multi-select to'plami. */
  const [multiSelected, setMultiSelected] = useState<Set<string>>(new Set());
  /** View mode: 'graph' yoki 'radial' (binary tree — DEFAULT). */
  const [viewMode, setViewMode] = useState<'graph' | 'radial'>('radial');
  /** Tanlangan semantic father (radial view uchun). */
  const [selectedFather, setSelectedFather] = useState<string | null>(null);
  /** Visual mode: 'kind' (default), 'domain', yoki 'verification' (AKMS). */
  const [visualMode, setVisualMode] = useState<'kind' | 'domain' | 'verification'>('kind');

  /** State + ref'ni BIRGALIKDA yangilaydi — timer callback'lari doim eng
   *  so'nggi qiymatni ko'radi (stale closure muammosi yo'q). */
  const commitSettings = (s: number[] | null, m: number | null) => {
    settingsRef.current = { shares: s, maxNodes: m };
    setShares(s);
    setMaxNodes(m);
  };

  // Mount'da server'dagi saqlangan sozlamalarni yuklaymiz (restart'da ham qoladi).
  useEffect(() => {
    let cancelled = false;
    brainGraphShares()
      .then((r) => {
        if (cancelled || !r.ok || !r.shares || r.shares.length !== 4) return;
        setSharesMeta({ updated_at: r.updated_at, history: r.history });
        // Foydalanuvchi allaqachon o'zgartirgan bo'lsa — state/ref'ni ham
        // server javobi bilan ustiga yozmaymiz (uning o'zgarishi qoladi).
        if (sharesTouchedRef.current) return;
        const normalized = normShares(r.shares);
        commitSettings(normalized, r.max_nodes ?? null);
        if (r.max_nodes != null) setMaxNodesDraft(r.max_nodes);
        setSharesDraft(normalized);
      })
      .catch(() => { /* backend offline — default sozlamalar */ });
    return () => { cancelled = true; };
  }, []);

  /** Sozlamalarni server'da saqlaydi — berilmagan maydon joriy qiymatini
   *  saqlaydi (qisman yangilash; masalan shares hali yuklanmagan bo'lsa
   *  faqat max_nodes yuboriladi va diskdagi ulushlar buzilmaydi). */
  const persistSettings = (sharesVal: number[] | null, mnVal: number | null) => {
    saveBrainGraphShares(sharesVal ?? undefined, mnVal ?? undefined)
      .then((r) => {
        setSharesMeta({ updated_at: r.updated_at, history: r.history });
        if (r.max_nodes != null) {
          settingsRef.current.maxNodes = r.max_nodes;
          setMaxNodes(r.max_nodes);
        }
      })
      .catch(() => { /* offline */ });
  };

  /** Slider harakatida draft'ni yangilaydi; to'xtagach (debounce) qo'llaydi
   *  va SERVER'da saqlaydi (keyingi yuklanishda ham qoladi). */
  const applySharesDraft = (next: number[]) => {
    sharesTouchedRef.current = true;
    setSharesDraft(next);
    if (sharesTimer.current) window.clearTimeout(sharesTimer.current);
    sharesTimer.current = window.setTimeout(() => {
      const normalized = normShares(next);
      commitSettings(normalized, settingsRef.current.maxNodes);
      setSharesDraft(normalized);
      persistSettings(normalized, settingsRef.current.maxNodes);
    }, 350);
  };

  /** max_nodes slider harakati — xuddi ulushlar kabi debounce + server saqlash. */
  const applyMaxNodesDraft = (next: number) => {
    sharesTouchedRef.current = true;
    setMaxNodesDraft(next);
    if (maxNodesTimer.current) window.clearTimeout(maxNodesTimer.current);
    maxNodesTimer.current = window.setTimeout(() => {
      commitSettings(settingsRef.current.shares, next);
      setMaxNodesDraft(next);
      persistSettings(settingsRef.current.shares, next);
    }, 350);
  };

  /** Standart qiymatlarni DARHOL qo'llaydi (debounce'siz — tugma bosilgan zahoti). */
  const resetShares = () => {
    sharesTouchedRef.current = true;
    const normalized = [...DEFAULT_SHARES];
    setSharesDraft(normalized);
    setMaxNodesDraft(DEFAULT_MAX_NODES);
    if (sharesTimer.current) window.clearTimeout(sharesTimer.current);
    if (maxNodesTimer.current) window.clearTimeout(maxNodesTimer.current);
    commitSettings(normalized, DEFAULT_MAX_NODES);
    persistSettings(normalized, DEFAULT_MAX_NODES);
  };

  /** Tayyor profilni DARHOL qo'llaydi + server'da saqlaydi (max_nodes o'zgarmaydi). */
  const applySharePreset = (preset: { shares: number[] }) => {
    sharesTouchedRef.current = true;
    const normalized = normShares(preset.shares);
    setSharesDraft(normalized);
    if (sharesTimer.current) window.clearTimeout(sharesTimer.current);
    commitSettings(normalized, settingsRef.current.maxNodes);
    persistSettings(normalized, settingsRef.current.maxNodes);
  };

  // Slider debounce + halqa timerlarini unmount'da tozalash — boshqa tabga
  // o'tilsa setState unmounted component'da yonib xabar bermasligi uchun.
  useEffect(() => {
    return () => {
      if (sharesTimer.current) window.clearTimeout(sharesTimer.current);
      if (maxNodesTimer.current) window.clearTimeout(maxNodesTimer.current);
      if (liveReasonTimer.current) window.clearTimeout(liveReasonTimer.current);
      if (freshTimer.current) window.clearTimeout(freshTimer.current);
    };
  }, []);

  /** O'zgarish sababini bir necha soniya ko'rsatadi (badge) — keyin o'chadi.
   *  `changedAt` berilsa (epoch sekund) nisbiy vaqt ham qo'shiladi:
   *  "yangi xotira moduli: ... · 2 daqiqa oldin". */
  const showLiveReason = (text: string, changedAt?: number | null) => {
    const t = changedAt && changedAt > 0 ? ` · ${relTime(changedAt)}` : '';
    setLiveReason(`${text}${t}`);
    if (liveReasonTimer.current) window.clearTimeout(liveReasonTimer.current);
    liveReasonTimer.current = window.setTimeout(() => setLiveReason(null), 6000);
  };

  const persistOffsets = (o: NodePos) => {
    try {
      localStorage.setItem(POS_KEY, JSON.stringify(o));
    } catch {
      /* ignore */
    }
  };

  /** Fresh halqa o'chirish timerini qayta ishga tushiradi — sababdan qat'i
   *  nazar (yangi yangilanish, fokuslash) halqalar yana to'liq muddat ko'rinib
   *  turadi. Eski timer tozalanadi — tez-tez chaqiruvlar muddatni cho'zadi. */
  const scheduleFreshClear = (delay: number) => {
    if (freshTimer.current) window.clearTimeout(freshTimer.current);
    freshTimer.current = window.setTimeout(() => {
      setFresh(new Set());
      setFreshChat(new Set());
    }, delay);
  };

  /** Yangi node'larni belgilaydi (faqat yangilanishda): haqiqiy chat suhbatlari
   *  (id `chat:` prefiksi) alohida teal halqa oladi, qolganlari oltin — qaysi
   *  suhbat yangi ekani darhol ko'rinadi. Eslatma: kind 'session' emas, balki
   *  id prefiksi tekshiriladi — L1 runtime yozuvlari (short-turn/session) ham
   *  kind='session' bo'ladi, ular chat emas. */
  const markFresh = (ns: BrainGraphNode[]) => {
    const prev = prevIdsRef.current;
    if (!prev.size) return;
    const added = ns.filter((n) => !prev.has(n.id));
    if (!added.length) return;
    setFreshChat(new Set(added.filter((n) => n.id.startsWith('chat:')).map((n) => n.id)));
    setFresh(new Set(added.filter((n) => !n.id.startsWith('chat:')).map((n) => n.id)));
    // Halqa muddati badge bilan teng — badge bosilganda fresh node'lar HAMON
    // belgilangan bo'ladi (focus har doim ishlaydi).
    scheduleFreshClear(FRESH_RING_MS);
  };

  /** Link sababini topish: 'a|b' yoki 'b|a' — ikkala yo'nalish ham ishlaydi.
   *  Ref'dan o'qiladi (dep yo'q) — callback turg'un, cheksiz reload loop'iga
   *  sabab bo'lmaydi. */
  const linkReasonOf = useCallback(
    (a: string, b: string): string[] => {
      const r = linkReasonsRef.current;
      return r[`${a}|${b}`] || r[`${b}|${a}`] || [];
    },
    [],
  );

  /** Link kuchi: umumiy so'zlar soni (semantik joylashuv va zoom uchun). */
  const linkWeight = useCallback(
    (a: string, b: string): number => {
      return linkReasonOf(a, b).length;
    },
    [linkReasonOf],
  );

  /**
   * BRANCHING LAYOUT — semantic kategoriyalar asosida shoxlanuvchi tree.
   * Har bir kind (session, fact, pattern, architecture) o'z branch'iga ega.
   * Bog'langan node'lar bir-biriga yaqin, lekin turlari bo'yicha ajralgan.
   * Barcha connection turlari saqlanadi.
   */
  const computeSemanticLayout = useCallback((ns: BrainGraphNode[], ls: [string, string][], start: NodePos, _zoomScale: number = 1): NodePos => {
    const w = 620, h = 380;
    const cx = w / 2, cy = h / 2;

    // 1. Node'larni kind bo'yicha guruhlash
    const kindGroups: Record<string, BrainGraphNode[]> = {};
    ns.forEach((n) => {
      if (!kindGroups[n.kind]) kindGroups[n.kind] = [];
      kindGroups[n.kind].push(n);
    });

    const kinds = Object.keys(kindGroups);
    if (kinds.length === 0) return {};

    // 2. Har bir kind uchun asosiy yo'nalish (branch direction)
    // 4 ta kind: yuqori, o'ng, past, chap tomonga shoxlanadi
    const BRANCH_ANGLES: Record<string, number> = {
      session:      -Math.PI / 2,     // yuqori
      fact:         0,                 // o'ng
      pattern:      Math.PI / 2,      // past
      architecture: Math.PI,          // chap
    };
    // Agar kind yo'q bo'lsa — teng taqsimlash
    const fallbackAngle = (i: number) => (i / kinds.length) * Math.PI * 2 - Math.PI / 2;

    // 3. Branch markazlarini aniqlash — har bir kind o'z yo'nalishida
    const branchCenters: Record<string, { x: number; y: number; angle: number }> = {};
    kinds.forEach((kind, i) => {
      const angle = BRANCH_ANGLES[kind] ?? fallbackAngle(i);
      const dist = 120; // markazdan uzoqligi
      branchCenters[kind] = {
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        angle,
      };
    });

    // 4. Initial positions — branch markazlaridan boshlash
    const pos: Record<string, { x: number; y: number }> = {};
    ns.forEach((n) => {
      const bc = branchCenters[n.kind];
      if (bc) {
        // Branch ichida sekin tarqalish
        const groupIdx = kindGroups[n.kind].indexOf(n);
        const groupSize = kindGroups[n.kind].length;
        const spread = Math.min(groupSize * 8, 80);
        const localAngle = bc.angle + ((groupIdx / Math.max(groupSize - 1, 1)) - 0.5) * 0.8;
        const localDist = (groupIdx / Math.max(groupSize, 1)) * spread;
        pos[n.id] = {
          x: bc.x + Math.cos(localAngle) * localDist,
          y: bc.y + Math.sin(localAngle) * localDist,
        };
      } else {
        pos[n.id] = { x: n.x, y: n.y };
      }
    });

    // 5. Force simulation — bog'langanlar tortiladi, boshqalar itariladi
    const ids = ns.map((n) => n.id);
    const nodeKind: Record<string, string> = {};
    ns.forEach((n) => { nodeKind[n.id] = n.kind; });

    // Springs: bog'langan node'lar
    const springs: { a: string; b: string; k: number }[] = [];
    for (const [a, b] of ls) {
      if (!pos[a] || !pos[b]) continue;
      const w = linkReasonOf(a, b).length;
      springs.push({ a, b, k: 0.003 + 0.001 * w });
    }

    const NODE_R = 9;
    const MIN_SEP = NODE_R * 2 + 8;
    const rep = 18000;

    for (let iter = 0; iter < 100; iter++) {
      const forces: Record<string, { x: number; y: number }> = {};
      ids.forEach((id) => (forces[id] = { x: 0, y: 0 }));

      // Itarish (barcha juftliklar)
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const a = ids[i], b = ids[j];
          let dx = pos[a].x - pos[b].x;
          let dy = pos[a].y - pos[b].y;
          let d2 = dx * dx + dy * dy;
          let d = Math.sqrt(d2);
          if (d < 0.001) {
            dx = ((i * 7 + j * 13) % 11) - 5;
            dy = ((i * 17 + j * 5) % 9) - 4;
            d2 = dx * dx + dy * dy;
            d = Math.sqrt(d2);
          }
          const f = rep / Math.max(d2, 200);
          const fx = (dx / d) * f, fy = (dy / d) * f;
          forces[a].x += fx; forces[a].y += fy;
          forces[b].x -= fx; forces[b].y -= fy;

          // To'qnashuvdan qochish
          if (d < MIN_SEP) {
            const overlap = MIN_SEP - d;
            const pushF = overlap * overlap * 0.5;
            forces[a].x += (dx / d) * pushF;
            forces[a].y += (dy / d) * pushF;
            forces[b].x -= (dx / d) * pushF;
            forces[b].y -= (dy / d) * pushF;
          }
        }
      }

      // Springs: bog'langanlar tortiladi
      for (const { a, b, k } of springs) {
        const dx = pos[a].x - pos[b].x;
        const dy = pos[a].y - pos[b].y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = k * Math.max(d - 40, 0);
        forces[a].x -= (dx / d) * f;
        forces[a].y -= (dy / d) * f;
        forces[b].x += (dx / d) * f;
        forces[b].y += (dy / d) * f;
      }

      // Branch gravity: o'z turining branch markaziga tortish
      const KIND_GRAVITY = 0.008;
      const damping = iter < 50 ? 0.08 : 0.04;
      for (const id of ids) {
        const kind = nodeKind[id];
        const bc = branchCenters[kind];
        if (bc) {
          forces[id].x += (bc.x - pos[id].x) * KIND_GRAVITY;
          forces[id].y += (bc.y - pos[id].y) * KIND_GRAVITY;
        }
        // Umumiy markazga kuchsiz tortish
        forces[id].x += (cx - pos[id].x) * 0.001;
        forces[id].y += (cy - pos[id].y) * 0.001;

        pos[id].x += forces[id].x * damping;
        pos[id].y += forces[id].y * damping;
      }
    }

    // 6. Post-processing: overlap tuzatish
    for (let pass = 0; pass < 15; pass++) {
      let anyOverlap = false;
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const a = ids[i], b = ids[j];
          const dx = pos[a].x - pos[b].x;
          const dy = pos[a].y - pos[b].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < MIN_SEP && d > 0.001) {
            anyOverlap = true;
            const overlap = (MIN_SEP - d) / 2 + 0.5;
            pos[a].x += (dx / d) * overlap;
            pos[a].y += (dy / d) * overlap;
            pos[b].x -= (dx / d) * overlap;
            pos[b].y -= (dy / d) * overlap;
          }
        }
      }
      if (!anyOverlap) break;
    }

    const out: NodePos = {};
    for (const n of ns) {
      out[n.id] = {
        x: Math.round(Math.min(w - 14, Math.max(14, pos[n.id].x))),
        y: Math.round(Math.min(h - 14, Math.max(14, pos[n.id].y))),
      };
    }
    return out;
  }, [linkReasonOf]);

  /** Yangi graf kelganda semantik rejim yoqilgan bo'lsa — joylashuvni qayta hisoblaymiz.
   *  `offsets` depda emas, lekin FUNKSIONAL setOffsets ishlatiladi — har doim
   *  ENG SO'NGGI offsets'dan hisoblanadi (stale closure muammosi yo'q). */
  const applySemanticIfOn = useCallback((g: { nodes?: BrainGraphNode[]; links?: [string, string][] }) => {
    if (!g.nodes?.length || !g.links?.length) return;
    if (!semanticLayout) return;
    // Guard'dan keyin TS closure ichida narrowing qilmaydi — lokal o'zgaruvchilar
    const ns = g.nodes;
    const ls = g.links;
    setOffsets((prev) => computeSemanticLayout(ns, ls, prev, view.scale));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [semanticLayout, computeSemanticLayout, view.scale]);

  const applyGraph = useCallback((g: { ok: boolean; nodes?: BrainGraphNode[]; links?: [string, string][]; link_reasons?: Record<string, string[]>; stats?: BrainViewStats | null }) => {
    if (!g.ok || !g.nodes?.length) return;
    markFresh(g.nodes);
    prevIdsRef.current = new Set(g.nodes.map((n) => n.id));
    setNodes(g.nodes);
    setLinks(g.links || []);
    linkReasonsRef.current = g.link_reasons || {};
    setStats(g.stats ?? null);
    setLive(true);
    setStale(false);
    applySemanticIfOn(g);
  }, [applySemanticIfOn]);

  const loadGraph = useCallback(() => {
    // Faqat ENG SO'NGGI boshlangan so'rov holatni boshqaradi: yangi yuklash
    // eski so'rovni bekor qiladi va ketma-ketlik (seq) oshiriladi. Bekor
    // qilingan / orqada qolgan so'rov na `loading`ni, na grafni o'zgartiradi —
    // aks holda mount paytida (StrictMode + shares hydrate) bir-biriga kirgan
    // so'rovlar tufayli `loading` "yuklanmoqda…" holatida qotib qolardi.
    const seq = ++graphSeqRef.current;
    graphCtrlRef.current?.abort();
    const ctrl = new AbortController();
    graphCtrlRef.current = ctrl;
    const alive = () => seq === graphSeqRef.current && !ctrl.signal.aborted;
    setLoading(true);
    // shares/maxNodes null bo'lsa query yuborilmaydi — backend diskdagi
    // sozlamalarni ishlatadi (double-fetch/default bilan ustiga yozish yo'q).
    brainGraph(shares ?? undefined, maxNodes ?? undefined, ctrl.signal)
      .then((g) => {
        if (!alive()) return;
        applyGraph(g);
        hasLoadedRef.current = true;
      })
      .catch(() => {
        if (!alive()) return;
        // FAQAT birinchi yuklash muvaffaqiyatsiz bo'lsa — halol offline holat
        // (soxta graf yo'q). Reload xatosi esa mavjud grafni O'CHIRMAYDI —
        // eski graf ko'rinib turadi, qora ekran flash bo'lmaydi. Ammo status
        // 'stale' bo'ladi — ma'lumotlar muzlatilgan, 'live' deb yolg'on emas.
        if (!hasLoadedRef.current) {
          setNodes([]);
          setLinks([]);
          setStats(null);
          setLive(false);
        } else {
          setStale(true);
        }
      })
      .finally(() => {
        if (alive()) setLoading(false);
      });
  }, [applyGraph, shares, maxNodes]);

  useEffect(() => loadGraph(), [loadGraph]);

  // REAL VAQT yangilanish: har 8 soniyada engil version-fingerprint so'raladi.
  // Grafik FAQAT SEZILARLI o'zgarishda qayta yuklanadi — yangi vault fayl,
  // L2 xotira yozuvi, yangi xotira moduli yoki yangi suhbat (backend'da qatiy
  // shart: runtime yozishlari va suhbat xabarlari versiyani o'zgartirmaydi).
  //
  // DEBOUNCE: xotira yozuvlari ketma-ket kelsa (agent run davomida) — har
  // yozuvda graf 'sakrab' qayta yuklanmasligi uchun, yangi versiya IKKI
  // ketma-ket tick'da takrorlansa (manba barqarorlashsa) qayta yuklaymiz.
  //
  // QATIY SHART (MIN_RELOAD_GAP): avtomatik qayta yuklashlar orasida minimal
  // tanaffus — versiya qayt-qayt siljisa ham grafik shuncha tez-tez ko'pi
  // bilan bir marta yangilanadi. Tanaffus tufayli o'tkazib yuborilgan o'zgarish
  // keyingi tick'lar davomida qayta uriniladi (hech narsa abadiy yo'qolmaydi).
  useEffect(() => {
    if (!liveRefresh) return;
    let cancelled = false;
    // Keyingi tick'da tasdiqlash uchun kutilayotgan versiya.
    let pendingVersion: number | null = null;
    // Kutilayotgan versiyaga tegishli O'ZGARISH SABABI + VAQTI (badge uchun).
    let pendingReason: string | null = null;
    let pendingChangedAt: number | null = null;
    let pendingReasonVersion: number | null = null;
    // Oxirgi AVTOMATIK qayta yuklash vaqti — qatiy minimal oraliq uchun.
    let lastAutoReload = 0;
    // Ish tugagach DARHOL qo'lga olish uchun avvalgi holatni kuzatamiz.
    const wasRunning = prevTaskRunningRef.current;
    prevTaskRunningRef.current = taskRunning;
    const tick = async () => {
      // AGENT ISHLAMOQDA — xotira yozuvlari versiyani tez-tez siljitadi;
      // graf shu vaqtda turg'un turadi (sababsiz 'sakrash'/'loading' flicker yo'q).
      if (taskRunning) return;
      try {
        const v = await brainGraphVersion();
        if (cancelled) return;
        if (versionRef.current === null) {
          versionRef.current = v.version;
          return;
        }
        if (v.version === versionRef.current) {
          pendingVersion = null; // barqaror — kutilgan versiya ham soz
          pendingReason = null;
          pendingChangedAt = null;
          pendingReasonVersion = null;
          return;
        }
        if (pendingVersion === v.version) {
          // IKKI ketma-ket tick bir xil YANGI versiyani ko'rdi — manba
          // barqarorlashdi, endi xavfsiz qayta yuklash mumkin.
          pendingVersion = null;
          // QATIY SHART: avtomatik qayta yuklashlar orasida minimal tanaffus
          // (shu tick'da ham yuklagan bo'lsak — keyingi tick'da qayta urinamiz).
          if (Date.now() - lastAutoReload < MIN_RELOAD_GAP) return;
          lastAutoReload = Date.now();
          versionRef.current = v.version;
          // Birinchi aniqlangan tick'da olingan sabab — yangilanish sababi
          // badge'da ko'rsatiladi (ikkinchi tick'da backend "o'zgarish yo'q"
          // qaytaradi, shuning uchun sababni oldindan saqlab qo'yganmiz).
          const reason = pendingReason;
          const changedAt = pendingChangedAt;
          pendingReason = null;
          pendingChangedAt = null;
          pendingReasonVersion = null;
          brainGraph(shares ?? undefined, maxNodes ?? undefined)
            .then((g) => {
              applyGraph(g);
              if (reason) {
                showLiveReason(reason, changedAt);
                // Chatda ham LOG qatori — sabab vaqtinchalik badge'dan tashqari
                // chat tarixida doimiy yozuv bo'lib qoladi (dublikatlar store'da
                // filtrlanadi — ketma-ket bir xil sabab takrorlanmaydi).
                pushBrainLog(reason);
              }
            })
            .catch(() => { /* offline */ });
        } else {
          // yangi versiya paydo bo'ldi — keyingi tick'da tasdiqlaymiz.
          // Sabab faqat YANGI versiya uchun olinadi; tanaffus tufayli qayta
          // tasdiqlanayotgan bir xil versiya sababini ustiga yozmaymiz.
          if (pendingReasonVersion !== v.version) {
            pendingReason = v.reason || null;
            pendingChangedAt = v.changed_at ?? null;
            pendingReasonVersion = v.version;
          }
          pendingVersion = v.version;
        }
      } catch {
        // offline — keyingi tick'da qayta uriniladi
      }
    };
    if (wasRunning && !taskRunning) {
      // Ish tugadi — pauza davomida to'plangan barcha o'zgarishlarni DARHOL,
      // debounce'siz qo'lga olamiz (pauza o'zi "barqarorlashish" bo'lgan;
      // backend bu vaqtda poll olmagan, shuning uchun reason TO'LIQ keladi).
      brainGraphVersion()
        .then((v) => {
          if (cancelled || versionRef.current === null) return;
          if (v.version === versionRef.current) return;
          versionRef.current = v.version;
          lastAutoReload = Date.now();
          brainGraph(shares ?? undefined, maxNodes ?? undefined)
            .then((g) => {
              applyGraph(g);
              if (v.reason) {
                showLiveReason(v.reason, v.changed_at ?? null);
                pushBrainLog(v.reason);
              }
            })
            .catch(() => { /* offline */ });
        })
        .catch(() => { /* offline — keyingi tick'da qayta uriniladi */ });
    }
    tick();
    const t = setInterval(tick, VERSION_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [liveRefresh, applyGraph, shares, maxNodes, taskRunning]);

  /** Semantik branch layout'ni yoqish/o'chirish — node'lar shoxlanuvchi tree tarzida joylashadi. */
  const toggleSemanticLayout = () => {
    setSemanticLayout((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(LAYOUT_KEY, next ? '1' : '0');
      } catch {
        /* ignore */
      }
      if (next && nodes.length) {
        setOffsets(computeSemanticLayout(nodes, links, offsets, view.scale));
      } else {
        setOffsets({});
        persistOffsets({});
      }
      return next;
    });
  };

  const nodeMap = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes]);
  const matches = (n: BrainGraphNode) => !query || n.label.toLowerCase().includes(query.toLowerCase());
  const posOf = (n: BrainGraphNode) => {
    const base = offsets[n.id] || { x: n.x, y: n.y };
    // Layout scale: node'lar markazdan uzoqlashadi (zoom effekti)
    if (layoutScale === 1) return base;
    const cx = SVG_W / 2, cy = SVG_H / 2;
    return {
      x: cx + (base.x - cx) * layoutScale,
      y: cy + (base.y - cy) * layoutScale,
    };
  };
  const neighborsOf = (id: string): BrainGraphNode[] =>
    links
      .filter(([a, b]) => a === id || b === id)
      .map(([a, b]) => (a === id ? b : a))
      .map((nid) => nodeMap[nid])
      .filter((n): n is BrainGraphNode => Boolean(n));

  // -------------------------------------------------------------- //
  // CLUSTER DETECTION — zich to'plamlarni aniqlash
  // -------------------------------------------------------------- //
  interface Cluster {
    id: string;
    cx: number;
    cy: number;
    radius: number;
    nodes: string[];
    kind: string;  // eng ko'p tarqalgan tur
    density: number; // zichlik (node soni / radius^2)
    dominance: number; // eng ko'p tur nisbati (0..1)
    kindBreakdown: Record<string, number>; // tur soni
  }

  const clusters = useMemo((): Cluster[] => {
    if (nodes.length < 3) return [];

    // 1. Har bir node uchun yaqin qo'shnilarni topish
    const CLUSTER_RADIUS = 65; // cluster aniqlash radiusi
    const MIN_CLUSTER_SIZE = 3; // kamida 3 ta node kerak
    const neighborMap: Record<string, Set<string>> = {};
    nodes.forEach((n) => { neighborMap[n.id] = new Set<string>(); });

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const pa = posOf(a), pb = posOf(b);
        const dx = pa.x - pb.x, dy = pa.y - pb.y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < CLUSTER_RADIUS) {
          neighborMap[a.id].add(b.id);
          neighborMap[b.id].add(a.id);
        }
      }
    }

    // 2. Connected components (Union-Find) orqali clusterlarni topish
    const parent: Record<string, string> = {};
    nodes.forEach((n) => { parent[n.id] = n.id; });

    const find = (x: string): string => {
      while (parent[x] !== x) {
        parent[x] = parent[parent[x]]; // path compression
        x = parent[x];
      }
      return x;
    };

    const union = (a: string, b: string) => {
      const ra = find(a), rb = find(b);
      if (ra !== rb) parent[ra] = rb;
    };

    // Bog'langan node'larni birlashtirish
    links.forEach(([a, b]) => {
      if (neighborMap[a]?.has(b)) {
        union(a, b);
      }
    });

    // Yaqin qo'shnilarni ham birlashtirish
    nodes.forEach((n) => {
      neighborMap[n.id].forEach((nid) => {
        union(n.id, nid);
      });
    });

    // 3. Har bir component uchun cluster hisoblash
    const componentMap: Record<string, string[]> = {};
    nodes.forEach((n) => {
      const root = find(n.id);
      if (!componentMap[root]) componentMap[root] = [];
      componentMap[root].push(n.id);
    });

    const result: Cluster[] = [];
    Object.entries(componentMap).forEach(([root, nodeIds]) => {
      if (nodeIds.length < MIN_CLUSTER_SIZE) return;

      // Cluster markazi va radiusini hisoblash
      let sumX = 0, sumY = 0;
      const positions = nodeIds.map((id) => {
        const p = posOf(nodeMap[id]);
        sumX += p.x;
        sumY += p.y;
        return p;
      });
      const cx = sumX / nodeIds.length;
      const cy = sumY / nodeIds.length;

      // Radius — markazdan eng uzoq node masofasi + padding
      let maxDist = 0;
      positions.forEach((p) => {
        const d = Math.sqrt((p.x - cx) ** 2 + (p.y - cy) ** 2);
        if (d > maxDist) maxDist = d;
      });
      const radius = maxDist + 20; // 20px padding

      // Density — node soni / (radius^2)
      const density = nodeIds.length / (Math.PI * radius * radius / 1000);

      // Kind — eng ko'p tarqalgan tur + dominance
      const kindCounts: Record<string, number> = {};
      nodeIds.forEach((id) => {
        const kind = nodeMap[id]?.kind || 'unknown';
        kindCounts[kind] = (kindCounts[kind] || 0) + 1;
      });
      const sortedKinds = Object.entries(kindCounts).sort((a, b) => b[1] - a[1]);
      const kind = sortedKinds[0]?.[0] || 'unknown';
      const dominance = sortedKinds[0] ? sortedKinds[0][1] / nodeIds.length : 0;

      result.push({
        id: `cluster-${root}`,
        cx, cy, radius,
        nodes: nodeIds,
        kind,
        density,
        dominance,
        kindBreakdown: kindCounts,
      });
    });

    return result.sort((a, b) => b.nodes.length - a.nodes.length);
  }, [nodes, links, nodeMap]);

  // -------------------------------------------------------------- //
  // KIND STATISTICS — har bir tur uchun statistika
  // -------------------------------------------------------------- //
  interface KindStat {
    kind: string;
    count: number;
    percentage: number;
    avgConnections: number;
    density: number;
    color: string;
  }

  const kindStats = useMemo((): KindStat[] => {
    if (nodes.length === 0) return [];

    // Har bir tur uchun node sonini hisoblash
    const kindCounts: Record<string, number> = {};
    nodes.forEach((n) => {
      kindCounts[n.kind] = (kindCounts[n.kind] || 0) + 1;
    });

    // Har bir tur uchun bog'lanishlar sonini hisoblash
    const kindConnections: Record<string, number> = {};
    links.forEach(([a, b]) => {
      const na = nodeMap[a], nb = nodeMap[b];
      if (na && nb) {
        kindConnections[na.kind] = (kindConnections[na.kind] || 0) + 1;
        if (na.kind !== nb.kind) {
          kindConnections[nb.kind] = (kindConnections[nb.kind] || 0) + 1;
        }
      }
    });

    // Har bir tur uchun zichlikni hisoblash (node soni / maydon)
    const kindDensityMap: Record<string, number> = {};
    const kindPositions: Record<string, { x: number; y: number }[]> = {};
    nodes.forEach((n) => {
      const p = posOf(n);
      if (!kindPositions[n.kind]) kindPositions[n.kind] = [];
      kindPositions[n.kind].push(p);
    });
    Object.entries(kindPositions).forEach(([kind, positions]) => {
      if (positions.length < 2) { kindDensityMap[kind] = 0; return; }
      let sumX = 0, sumY = 0;
      positions.forEach((p) => { sumX += p.x; sumY += p.y; });
      const cx = sumX / positions.length, cy = sumY / positions.length;
      let maxR = 0;
      positions.forEach((p) => { maxR = Math.max(maxR, Math.hypot(p.x - cx, p.y - cy)); });
      kindDensityMap[kind] = positions.length / (Math.PI * maxR * maxR / 1000 + 1);
    });

    const total = nodes.length;
    const result: KindStat[] = Object.entries(kindCounts).map(([kind, count]) => ({
      kind,
      count,
      percentage: (count / total) * 100,
      avgConnections: count > 0 ? (kindConnections[kind] || 0) / count : 0,
      density: kindDensityMap[kind] || 0,
      color: KIND_COLOR[kind as keyof typeof KIND_COLOR]?.fill || '#71717a',
    }));

    return result.sort((a, b) => b.count - a.count);
  }, [nodes, links, nodeMap]);

  // Statistika paneli ochiq/yopiq holati
  const [showStats, setShowStats] = useState(false);
  // Keyboard help overlay holati
  const [showHelp, setShowHelp] = useState(false);

  // Cluster bosilganda — zoom qilish yoki kengaytirish/yig'ish
  const focusCluster = useCallback((cluster: Cluster) => {
    if (expandedCluster === cluster.id) {
      // Agar allaqachon kengaytirilgan bo'lsa — yig'ish va barchasini ko'rsatish
      setExpandedCluster(null);
      fitView();
      return;
    }
    // Cluster ni kengaytirish
    setExpandedCluster(cluster.id);
    // Cluster atrofida zoom qilish
    const padding = 60;
    const minX = cluster.cx - cluster.radius - padding;
    const maxX = cluster.cx + cluster.radius + padding;
    const minY = cluster.cy - cluster.radius - padding;
    const maxY = cluster.cy + cluster.radius + padding;
    const bw = maxX - minX;
    const bh = maxY - minY;
    const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.min((SVG_W - 40) / bw, (SVG_H - 40) / bh)));
    setView({
      scale,
      tx: SVG_W / 2 - cluster.cx * scale,
      ty: SVG_H / 2 - cluster.cy * scale,    });
  }, [expandedCluster]);

  // -------------------------------------------------------------- //
  // CLUSTER MERGE/SPLIT — clusterlarni birlashtirish/ajratish
  // -------------------------------------------------------------- //

  /** Ikkita cluster'ni birlashtirish. */
  const mergeClusters = useCallback((clusterA: string, clusterB: string) => {
    if (clusterA === clusterB) return;
    setMergedClusters((prev) => {
      const next = { ...prev };
      // Ikki cluster'ni ham bitta ID ga birlashtirish
      const mergedId = `merged-${clusterA}-${clusterB}`;
      next[clusterA] = mergedId;
      next[clusterB] = mergedId;
      return next;
    });
    setSelectedCluster(null);
  }, []);

  /** Cluster'ni ajratish (merge'ni bekor qilish). */
  const splitCluster = useCallback((clusterId: string) => {
    setMergedClusters((prev) => {
      const next = { ...prev };
      // Shu cluster'ga bog'langan barcha merge'larni o'chirish
      Object.keys(next).forEach((key) => {
        if (next[key] === clusterId || key === clusterId) {
          delete next[key];
        }
      });
      return next;
    });
  }, []);

  /** Barcha merge'larni bekor qilish. */
  const resetMerges = useCallback(() => {
    setMergedClusters({});
  }, []);

  // Merge qilingan clusterlarni qayta hisoblash
  const mergedClusterNodes = useMemo(() => {
    const result: Record<string, string[]> = {};
    (Object.entries(mergedClusters) as [string, string][]).forEach(([clusterId, mergedId]) => {
      if (!result[mergedId]) result[mergedId] = [];
      // Cluster ID dan node'lar topiladi
      const cluster = clusters.find((c) => c.id === clusterId);
      if (cluster) {
        result[mergedId].push(...cluster.nodes);
      }
    });
    return result;
  }, [mergedClusters, clusters]);


  // -------------------------------------------------------------- //
  // Visual actions — zoom / pan / fit / reset / refresh
  // -------------------------------------------------------------- //

  /** Markaz (viewBox koordinatada) atrofida zoom. */
  const zoomAt = useCallback((cx: number, cy: number, factor: number) => {
    setView((v) => {
      const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor));
      const k = scale / v.scale;
      return { scale, tx: cx - (cx - v.tx) * k, ty: cy - (cy - v.ty) * k };
    });
  }, []);

  const zoomIn = () => {
    zoomAt(SVG_W / 2, SVG_H / 2, ZOOM_STEP);
    setLayoutScale((prev) => Math.min(5, prev * 1.12));
  };
  const zoomOut = () => {
    zoomAt(SVG_W / 2, SVG_H / 2, 1 / ZOOM_STEP);
    setLayoutScale((prev) => Math.max(0.3, prev / 1.12));
  };
  const resetView = () => { setView({ scale: 1, tx: 0, ty: 0 }); setLayoutScale(1); };

  /** Node'lar to'plamiga mos zoom/pan hisoblaydi — barcha ko'rsatilgan
   *  node'lar ko'rinadigan bo'ladi (bo'sh ro'yxat -> null). fitView ham,
   *  fresh-node fokusi ham shu helper'ni ishlatadi (matematika takrorlanmaydi). */
  const fitBounds = (list: BrainGraphNode[]): View | null => {
    if (!list.length) return null;
    // Layout scale ni reset qilish — fit view asl holatga qaytaradi
    setLayoutScale(1);
    const xs = list.map((n) => posOf(n).x);
    const ys = list.map((n) => posOf(n).y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const bw = Math.max(maxX - minX, 60), bh = Math.max(maxY - minY, 60);
    const pad = 70;
    const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.min((SVG_W - pad) / bw, (SVG_H - pad) / bh)));
    return {
      scale,
      tx: SVG_W / 2 - ((minX + maxX) / 2) * scale,
      ty: SVG_H / 2 - ((minY + maxY) / 2) * scale,
    };
  };

  const fitView = () => {
    setView(fitBounds(nodes) || { scale: 1, tx: 0, ty: 0 });
  };

  const focusNode = (n: BrainGraphNode) => {
    const p = posOf(n);
    const scale = Math.min(MAX_SCALE, Math.max(1.5, view.scale >= 2 ? view.scale : 1.6));
    setView({ scale, tx: SVG_W / 2 - p.x * scale, ty: SVG_H / 2 - p.y * scale });
  };

  /** KIND-BASED ZOOM — faqat shu turdagi node'larni ko'rsatish va zoom qilish. */
  const focusKind = (kind: string) => {
    const newFilter = new Set(kindFilter);
    if (newFilter.has(kind)) {
      // Agar shu tur allaqachon tanlangan bo'lsa — olib tashlash
      newFilter.delete(kind);
    } else {
      // Yangi tur qo'shish
      newFilter.add(kind);
    }
    setKindFilter(newFilter);
    // Tanlangan turlardagi node'larni topish va zoom qilish
    if (newFilter.size > 0) {
      const kindNodes = nodes.filter((n) => newFilter.has(n.kind));
      if (kindNodes.length > 0) {
        const newView = fitBounds(kindNodes);
        if (newView) setView(newView);
      }
    } else {
      // Hech narsa tanlanmagan — barchasini ko'rsatish
      fitView();
    }
  };

  /** Barcha kind filterlarni tozalash. */
  const clearKindFilter = () => {
    setKindFilter(new Set());
    fitView();
  };

  /** Fresh (yangi) node'larga ZOOM — o'zgarish sababi badge'ini bosganda graf
   *  aynan yangi node'larga fokuslanadi (yangi suhbat teal, boshqalari oltin)
   *  va ENG YANGI node avtomatik TANLANADI (details paneli ochiladi).
   *  Halqalar hali yoqilgan bo'lsa — fokuslashdan keyin yana bir necha soniya
   *  UZAYTIRILADI (zoom'da yangi node'lar ko'rinib turadi); o'chgan bo'lsa
   *  (FRESH_RING_MS o'tdi) — butun grafikka fit qilamiz. */
  const focusFreshNodes = () => {
    const freshIds = new Set<string>([...fresh, ...freshChat]);
    const freshNodes = nodes.filter((n) => freshIds.has(n.id));
    if (freshNodes.length) {
      // Fokusdan keyin halqalar yana bir necha soniya qoladi — foydalanuvchi
      // zoom'da qaysi node'lar yangi ekanini aniq ko'radi (tez o'chib ketmaydi).
      scheduleFreshClear(FRESH_RING_EXTEND_MS);
      // ENG YANGI fresh node'ni avtomatik tanlash — details paneli ochiladi.
      // updated_at (epoch soniya) eng yuqori node eng yangi hisoblanadi;
      // hech birida bo'lmasa birinchisi tanlanadi (panel doim ochiladi).
      let newest = freshNodes[0];
      for (const n of freshNodes) {
        if ((n.updated_at ?? 0) > (newest.updated_at ?? 0)) newest = n;
      }
      setSelected(newest);
    }
    setView(fitBounds(freshNodes.length ? freshNodes : nodes) || { scale: 1, tx: 0, ty: 0 });
  };

  /** Node'ni asl radar joylashuviga qaytaradi. */
  const resetNodePos = (id: string) => {
    setOffsets((prev) => {
      const next = { ...prev };
      delete next[id];
      persistOffsets(next);
      return next;
    });
  };

  // G'ildirak bilan zoom — cursor joyida kattalashadi
  // node'lar orasidagi masofa ham kattalashadi (layoutScale)
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const mouseX = ((e.clientX - rect.left) / rect.width) * SVG_W;
      const mouseY = ((e.clientY - rect.top) / rect.height) * SVG_H;
      const zoomIn = e.deltaY < 0;
      const factor = zoomIn ? 1.12 : 1 / 1.12;

      // 1) Layout scale — node'lar orasidagi masofa kattalashadi
      setLayoutScale((prev) => {
        const next = Math.min(5, Math.max(0.3, prev * factor));
        // 2) View transform — cursor joyida qolishi uchun tx/ty ni moslashtirish
        setView((v) => {
          const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.scale * factor));
          // Cursor nuqtasi world koordinatada qolishi kerak
          // world = (screen - tx) / scale
          // Yangi world = (screen - newTx) / newScale = old world
          // newTx = screen - world * newScale
          const worldX = (mouseX - v.tx) / v.scale;
          const worldY = (mouseY - v.ty) / v.scale;
          const newTx = mouseX - worldX * newScale;
          const newTy = mouseY - worldY * newScale;
          return { scale: newScale, tx: newTx, ty: newTy };
        });
        return next;
      });
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, []);

  // KEYBOARD SHORTCUTS — 1-4 tugmalari kind filter uchun
  useEffect(() => {
    const KIND_KEYS: Record<string, string> = {
      '1': 'session',
      '2': 'fact',
      '3': 'pattern',
      '4': 'architecture',
    };

    const onKeyDown = (e: KeyboardEvent) => {
      // Input/textarea ichida bo'lsa — ishlamasin
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      const kind = KIND_KEYS[e.key];
      if (kind) {
        e.preventDefault();
        focusKind(kind);
      } else if (e.key === '0') {
        // 0 — barcha filterlarni tozalash
        e.preventDefault();
        clearKindFilter();
      } else if (e.key === 'f' || e.key === 'F') {
        // F — fit view
        e.preventDefault();
        fitView();
      } else if (e.key === 'r' || e.key === 'R') {
        // R — reset view
        e.preventDefault();
        resetView();
      } else if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
        // ? — keyboard help overlay
        e.preventDefault();
        setShowHelp((v) => !v);
      } else if (e.key === 'Escape') {
        // Escape — yordam panelini yopish
        if (showHelp) {
          e.preventDefault();
          setShowHelp(false);
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [focusKind, clearKindFilter, fitView, resetView, showHelp]);

  // ---- MODIFIER KEY TRACKING ----
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Shift') setShiftDown(true);
      if (e.key === 'Control' || e.key === 'Meta') setCtrlDown(true);
      if (e.key === 'Alt') setAltDown(true);
      // Escape — context menu yopish
      if (e.key === 'Escape') {
        setContextMenu(null);
        setBranchViewNode(null);
        setPathTarget(null);
        setExpansionSource(null);
        setMultiSelected(new Set());
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Shift') setShiftDown(false);
      if (e.key === 'Control' || e.key === 'Meta') setCtrlDown(false);
      if (e.key === 'Alt') setAltDown(false);
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, []);

  // ---- NODE NEIGHBORS HELPER ----
  const getNeighbors = useCallback((nodeId: string): BrainGraphNode[] => {
    const neighbors = new Set<string>();
    links.forEach(([a, b]) => {
      if (a === nodeId) neighbors.add(b);
      if (b === nodeId) neighbors.add(a);
    });
    return Array.from(neighbors).map((id) => nodeMap[id]).filter(Boolean);
  }, [links, nodeMap]);

  // ---- NODE RIGHT-CLICK HANDLER ----
  const onNodeContextMenu = useCallback((e: React.MouseEvent, n: BrainGraphNode) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ nodeId: n.id, x: e.clientX, y: e.clientY });
  }, []);

  // ---- NODE MIDDLE-CLICK HANDLER (EXPAND) ----
  const onNodeMiddleClick = useCallback((e: React.MouseEvent, n: BrainGraphNode) => {
    e.preventDefault();
    e.stopPropagation();
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(n.id)) next.delete(n.id); else next.add(n.id);
      return next;
    });
    setExpansionSource(n);
    setTimeout(() => setExpansionSource(null), 1500);
  }, []);

  // ---- NODE DOUBLE-CLICK (BRANCH VIEW) ----
  const onNodeDoubleClick = useCallback((e: React.MouseEvent, n: BrainGraphNode) => {
    e.preventDefault();
    e.stopPropagation();
    setBranchViewNode(branchViewNode === n.id ? null : n.id);
  }, [branchViewNode]);

  // ---- CONTEXT MENU ACTIONS ----
  const contextMenuNode = contextMenu ? nodeMap[contextMenu.nodeId] : null;
  const contextMenuNeighbors = contextMenu ? getNeighbors(contextMenu.nodeId) : [];

  const ctxFocus = useCallback(() => {
    if (contextMenuNode) focusNode(contextMenuNode);
    setContextMenu(null);
  }, [contextMenuNode, focusNode]);

  const ctxExpand = useCallback(() => {
    if (contextMenu) {
      setExpandedNodes((prev) => {
        const next = new Set(prev);
        if (next.has(contextMenu.nodeId)) next.delete(contextMenu.nodeId); else next.add(contextMenu.nodeId);
        return next;
      });
      setExpansionSource(contextMenuNode);
      setTimeout(() => setExpansionSource(null), 1500);
    }
    setContextMenu(null);
  }, [contextMenu, contextMenuNode]);

  const ctxBranchView = useCallback(() => {
    if (contextMenu) {
      setBranchViewNode(contextMenu.nodeId);
    }
    setContextMenu(null);
  }, [contextMenu]);

  const ctxTracePath = useCallback((targetId: string) => {
    if (contextMenu) {
      setPathTarget({ source: contextMenu.nodeId, target: targetId });
    }
    setContextMenu(null);
  }, [contextMenu]);

  const ctxCopyId = useCallback(() => {
    if (contextMenu) {
      navigator.clipboard.writeText(contextMenu.nodeId).catch(() => {});
    }
    setContextMenu(null);
  }, [contextMenu]);

  const ctxMultiSelect = useCallback(() => {
    if (contextMenu) {
      setMultiSelected((prev) => {
        const next = new Set(prev);
        if (next.has(contextMenu.nodeId)) next.delete(contextMenu.nodeId); else next.add(contextMenu.nodeId);
        return next;
      });
    }
    setContextMenu(null);
  }, [contextMenu]);

  // ---- EXPAND/COLLAPSE ALL ----
  const expandAll = useCallback(() => {
    const allIds = new Set(nodes.map((n) => n.id));
    setExpandedNodes(allIds);
  }, [nodes]);

  const collapseAll = useCallback(() => {
    setExpandedNodes(new Set());
  }, []);

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    const t = e.target as Element;
    // Node / label ustida bosish — tanlash/drag uchun, pan emas
    if (t.closest && t.closest('g')) return;
    svgRef.current?.setPointerCapture?.(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty };
  };

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = dragRef.current;
    if (!d) return;
    setView((v) => ({ ...v, tx: d.tx + (e.clientX - d.x), ty: d.ty + (e.clientY - d.y) }));
  };

  const endDrag = () => { dragRef.current = null; };

  // -------------------------------------------------------------- //
  // Node drag — node'larni sudrab ko'chirish (joylashuv saqlanadi)
  // -------------------------------------------------------------- //

  const onNodePointerDown = (e: React.PointerEvent, n: BrainGraphNode) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    const off = posOf(n);
    nodeDragRef.current = { id: n.id, sx: e.clientX, sy: e.clientY, ox: off.x, oy: off.y };
  };

  const onNodePointerMove = (e: React.PointerEvent) => {
    const d = nodeDragRef.current;
    if (!d) return;
    const dx = e.clientX - d.sx;
    const dy = e.clientY - d.sy;
    if (!movedRef.current && Math.hypot(dx, dy) < 4) return; // kichik tebranish — drag emas
    movedRef.current = true;
    setOffsets((prev) => {
      const next = { ...prev, [d.id]: { x: Math.round(d.ox + dx), y: Math.round(d.oy + dy) } };
      persistOffsets(next);
      return next;
    });
  };

  const onNodePointerUp = () => {
    nodeDragRef.current = null;
    // click pointerup'dan keyin keladi — moved belgisini click'ni o'zi tozalaydi;
    // click bo'lmasa (tashqarida qo'yib yuborilsa) keyingi turn'da tozalanadi.
    window.setTimeout(() => { movedRef.current = false; }, 0);
  };

  const toolbarBtn =
    'w-6 h-6 flex items-center justify-center rounded text-xs text-zinc-400 hover:text-amber-300 hover:bg-zinc-800 transition-colors';

  return (
    <div className="flex-1 min-h-0 flex">
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 shrink-0">
          <span className="text-zinc-600">🔍</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter notes..."
            className="bg-transparent outline-none text-xs text-zinc-200 font-ui flex-1 placeholder-zinc-600"
          />
          <div className="flex items-center gap-2">
            {Object.entries(KIND_COLOR).map(([kind, c]) => (
              <button
                key={kind}
                onClick={() => focusKind(kind)}
                className={`flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded transition-colors ${
                  kindFilter.has(kind)
                    ? `${c.dot} text-white`
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
                }`}
                title={`${kind} toggle — ${nodes.filter((n) => n.kind === kind).length} ta node`}
              >
                <span className={`w-2 h-2 rounded-full ${c.dot}`} /> {kind}
                <span className="text-zinc-600">({nodes.filter((n) => n.kind === kind).length})</span>
              </button>
            ))}
            {kindFilter.size > 0 && (
              <button
                onClick={clearKindFilter}
                className="text-[10px] font-mono px-1.5 py-0.5 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                title="Barcha node'larni ko'rsatish"
              >
                ✕ clear ({kindFilter.size})
              </button>
            )}
            <button
              onClick={() => setShowStats(!showStats)}
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded transition-colors ${
                showStats
                  ? 'bg-zinc-700 text-zinc-200'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
              }`}
              title="Statistika paneli"
            >
              📊
            </button>
          </div>
        </div>
        {/* KIND STATISTICS PANEL */}
        {showStats && kindStats.length > 0 && (
          <div className="px-4 py-2 border-b border-zinc-800/60 bg-zinc-900/30 shrink-0">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono text-zinc-500">📊 KIND STATISTICS</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    const exportData = {
                      exported_at: new Date().toISOString(),
                      total_nodes: nodes.length,
                      total_links: links.length,
                      stats: kindStats.map((s) => ({
                        kind: s.kind,
                        count: s.count,
                        percentage: Math.round(s.percentage * 10) / 10,
                        avg_connections: Math.round(s.avgConnections * 10) / 10,
                        density: Math.round(s.density * 100) / 100,
                      })),
                      clusters: clusters.map((c) => ({
                        id: c.id,
                        kind: c.kind,
                        node_count: c.nodes.length,
                        density: Math.round(c.density * 100) / 100,
                        dominance: Math.round(c.dominance * 100),
                        kind_breakdown: c.kindBreakdown,
                      })),
                    };
                    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `brain-stats-${Date.now()}.json`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 hover:text-amber-300 hover:bg-zinc-700 transition-colors"
                  title="Export stats to JSON"
                >
                  ↓ JSON
                </button>
                <button
                  onClick={() => {
                    // CSV header
                    const csvRows: string[] = [];
                    csvRows.push('kind,count,percentage,avg_connections,density');
                    kindStats.forEach((s) => {
                      csvRows.push([
                        s.kind,
                        s.count,
                        (Math.round(s.percentage * 10) / 10).toString(),
                        (Math.round(s.avgConnections * 10) / 10).toString(),
                        (Math.round(s.density * 100) / 100).toString(),
                      ].join(','));
                    });
                    // Blank line + clusters section
                    csvRows.push('');
                    csvRows.push('cluster_id,dominant_kind,node_count,density,dominance%,session,fact,pattern,architecture');
                    clusters.forEach((c) => {
                      csvRows.push([
                        c.id,
                        c.kind,
                        c.nodes.length,
                        (Math.round(c.density * 100) / 100).toString(),
                        Math.round(c.dominance * 100).toString(),
                        (c.kindBreakdown['session'] || 0).toString(),
                        (c.kindBreakdown['fact'] || 0).toString(),
                        (c.kindBreakdown['pattern'] || 0).toString(),
                        (c.kindBreakdown['architecture'] || 0).toString(),
                      ].join(','));
                    });
                    const csv = csvRows.join('\n');
                    const blob = new Blob([csv], { type: 'text/csv' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `brain-stats-${Date.now()}.csv`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 hover:text-amber-300 hover:bg-zinc-700 transition-colors"
                  title="Export stats to CSV"
                >
                  ↓ CSV
                </button>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {kindStats.map((stat) => (
                <div
                  key={stat.kind}
                  className="px-2 py-1.5 rounded bg-zinc-950/60 border border-zinc-800 cursor-pointer hover:border-zinc-600 transition-colors"
                  onClick={() => focusKind(stat.kind)}
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: stat.color }} />
                    <span className="text-[10px] font-mono text-zinc-300">{stat.kind}</span>
                  </div>
                  <div className="text-[11px] font-mono text-zinc-200">
                    {stat.count} <span className="text-zinc-500">({stat.percentage.toFixed(0)}%)</span>
                  </div>
                  <div className="text-[9px] font-mono text-zinc-600 mt-0.5">
                    bog'lanish: {stat.avgConnections.toFixed(1)} · zichlik: {stat.density.toFixed(2)}
                  </div>
                  {/* Density bar */}
                  <div className="mt-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(100, stat.density * 20)}%`,
                        backgroundColor: stat.color,
                        opacity: 0.6,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="relative flex items-center gap-2 px-4 py-1.5 border-b border-zinc-800/60 shrink-0">
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${live ? 'bg-teal-900/50 text-teal-300' : 'bg-zinc-800 text-zinc-500'}`}>
            {loading ? 'yuklanmoqda…' : stale ? '○ offline — eski graf ko\'rinib turibdi' : live ? '● real ma\'lumotlar' : '○ offline (backend ulangan emas)'}
          </span>
          {stats && (
            <span className="text-[10px] font-mono text-zinc-600">
              {stats.nodes} node · {stats.links} link · {stats.vault_files} vault fayl
            </span>
          )}
          {freshChat.size > 0 && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-teal-950/60 text-teal-300 animate-pulse">
              ✦ {freshChat.size} yangi suhbat
            </span>
          )}
          {fresh.size > 0 && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-950/60 text-amber-300 animate-pulse">
              ✦ {fresh.size} yangi node
            </span>
          )}
          {liveReason && (
            <button
              onClick={focusFreshNodes}
              title="Graf nega yangilandi (backend real sabab). Bosing: yangi node'larga zoom"
              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-950/60 text-sky-300 animate-pulse max-w-[240px] truncate cursor-pointer hover:bg-sky-900/70 hover:text-sky-200 transition-colors"
            >
              🆕 {liveReason}
            </button>
          )}
          {live && sharesPanel && (
            <div className="absolute top-full right-2 z-30 mt-1 w-64 px-3 py-2.5 rounded-md bg-zinc-950/95 border border-zinc-700 shadow-2xl">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono text-zinc-400">KVOTA ULUSHLARI</span>
                <button onClick={resetShares} className="text-[10px] font-mono text-amber-400 hover:text-amber-300" title="Standart qiymatlarga qaytarish">↺ standart</button>
              </div>
              {/* Tayyor profillar — bir bosishda mos ulushlar */}
              <div className="grid grid-cols-2 gap-1 mb-2">
                {SHARE_PRESETS.map((p) => {
                  const active = shares && normShares(p.shares).every((v, i) => Math.abs(v - shares[i]) < 0.005);
                  return (
                    <button
                      key={p.label}
                      onClick={() => applySharePreset(p)}
                      title={p.desc}
                      className={`flex items-center gap-1 px-1.5 py-1 rounded text-[9px] font-mono border transition-colors ${active ? 'bg-amber-950/50 border-amber-600/50 text-amber-300' : 'border-zinc-800 text-zinc-400 hover:text-amber-300 hover:border-zinc-600'}`}
                    >
                      <span>{p.emoji}</span> {p.label}
                    </button>
                  );
                })}
              </div>
              {SHARE_LABELS.map(([key, label, countKey], i) => (
                <div key={key} className="mb-1.5">
                  <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                    <span className="text-zinc-400">{label}</span>
                    <span className="text-zinc-200">
                      {Math.round(sharesDraft[i] * 100)}%{stats && countKey && stats[countKey] != null && (
                        <span className="text-zinc-600 ml-1">· jami {stats[countKey]}</span>
                      )}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={Math.round(sharesDraft[i] * 100)}
                    onChange={(e) => {
                      const next = [...sharesDraft];
                      next[i] = Number(e.target.value) / 100;
                      applySharesDraft(next);
                    }}
                    className="w-full h-1 accent-amber-400 cursor-pointer"
                  />
                </div>
              ))}
              {/* Graf node chegarasi — ulushlar bilan birga serverda saqlanadi */}
              <div className="mt-2 pt-2 border-t border-zinc-800">
                <div className="flex items-center justify-between text-[10px] font-mono mb-0.5">
                  <span className="text-zinc-400">Maks node'lar</span>
                  <span className="text-zinc-200">
                    {maxNodesDraft} <span className="text-zinc-600">ta</span>
                  </span>
                </div>
                <input
                  type="range"
                  min={MAX_NODES_MIN}
                  max={MAX_NODES_MAX}
                  step={MAX_NODES_STEP}
                  value={maxNodesDraft}
                  onChange={(e) => applyMaxNodesDraft(Number(e.target.value))}
                  className="w-full h-1 accent-amber-400 cursor-pointer"
                />
              </div>
              <div className="text-[9px] font-mono text-zinc-600 mt-1.5 leading-snug">
                Ulushlar yig'indisi avtomatik 100% ga normallashadi. Har manba
                o'z kvotasidan tashqariga chiqmaydi — churn yo'q.
              </div>
              {sharesMeta.updated_at ? (
                <div className="text-[9px] font-mono text-zinc-600 mt-1.5 border-t border-zinc-800 pt-1.5">
                  🕒 oxirgi o'zgarish: <span className="text-zinc-400">{relTime(sharesMeta.updated_at)}</span>
                  {(sharesMeta.history?.length ?? 0) > 1 && (
                    <span className="ml-1">· {sharesMeta.history!.length} ta o'zgarish</span>
                  )}
                  {sharesMeta.history && sharesMeta.history.length >= 2 && (
                    <div className="text-zinc-500 mt-0.5 leading-snug">
                      {fmtHistoryEntry(sharesMeta.history[sharesMeta.history.length - 2])}
                      <span className="text-amber-400/80"> → </span>
                      {fmtHistoryEntry(sharesMeta.history[sharesMeta.history.length - 1])}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-[9px] font-mono text-zinc-600 mt-1.5 border-t border-zinc-800 pt-1.5">
                  Hali o'zgartirilmagan (default ulushlar).
                </div>
              )}
            </div>
          )}
          {live && (
            <div className="ml-auto flex items-center gap-1 shrink-0">
              <button
                onClick={() => setLiveRefresh((v) => !v)}
                title={liveRefresh ? 'Live yangilanishni pauza qilish' : 'Live yangilanishni davom ettirish'}
                className={`${toolbarBtn} ${liveRefresh ? 'text-teal-400' : 'text-zinc-500'}`}
              >
                {liveRefresh ? '◉' : '◌'}
              </button>
              <span className="text-[10px] font-mono text-zinc-600 w-14 select-none">
                {liveRefresh ? 'live ~8s' : 'paused'}
              </span>
              <button
                onClick={() => setSharesPanel((v) => !v)}
                title="Kvota ulushlari — vault/chat/xotira nisbatini sozlash"
                className={`${toolbarBtn} ${sharesPanel ? 'text-amber-300 bg-zinc-800' : 'text-zinc-400'}`}
              >
                ⚖
              </button>
              <span className="w-px h-4 bg-zinc-800 mx-0.5" />
              <button
                onClick={toggleSemanticLayout}
                title={semanticLayout
                  ? 'Semantik joylashuv ON — bog\'langan node\'lar bir-biriga tortiladi (nega yaqinligi ko\'rinadi). Bosing: radar holatiga qaytish.'
                  : 'Semantik joylashuv — node\'lar umumiy so\'zlarga ko\'ra yaqinlashadi (zoom\'da nega bog\'langanligi ko\'rinadi).'}
                className={`${toolbarBtn} ${semanticLayout ? 'text-amber-300 bg-zinc-800' : 'text-zinc-400'}`}
              >
                ⚡
              </button>
              <span className="w-px h-4 bg-zinc-800 mx-0.5" />
              <button onClick={zoomOut} title="Zoom out" className={toolbarBtn}>−</button>
              <span className="text-[10px] font-mono text-zinc-400 w-9 text-center select-none" title={`Layout spread: ${Math.round(layoutScale * 100)}%`}>
                {Math.round(view.scale * 100)}%
              </span>
              <button onClick={zoomIn} title="Zoom in" className={toolbarBtn}>+</button>
              {layoutScale > 1.05 && (
                <span className="text-[8px] font-mono text-zinc-600" title="Node spread factor">
                  ×{layoutScale.toFixed(1)}
                </span>
              )}
              <span className="w-px h-4 bg-zinc-800 mx-0.5" />
              <button onClick={resetView} title="Reset view" className={toolbarBtn}>⟲</button>
              <button onClick={fitView} title="Fit to content" className={toolbarBtn}>⛶</button>
              <span className="w-px h-4 bg-zinc-800 mx-0.5" />
              <button
                onClick={() => setViewMode(viewMode === 'graph' ? 'radial' : 'graph')}
                title={viewMode === 'graph' ? 'Switch to Radial View (Binary Tree)' : 'Switch to Graph View'}
                className={`${toolbarBtn} ${viewMode === 'radial' ? 'text-amber-300 bg-zinc-800' : 'text-zinc-400'}`}
              >
                {viewMode === 'graph' ? '⊙' : '◎'}
              </button>
              <button
                onClick={() => setVisualMode(visualMode === 'kind' ? 'domain' : visualMode === 'domain' ? 'verification' : 'kind')}
                title={`Visual mode: ${visualMode} (click to cycle)`}
                className={`${toolbarBtn} ${visualMode !== 'kind' ? 'text-amber-300 bg-zinc-800' : 'text-zinc-400'}`}
              >
                {visualMode === 'kind' ? '◉' : visualMode === 'domain' ? '◆' : '✓'}
              </button>
              <button
                onClick={() => setShowHelp((v) => !v)}
                title="Keyboard shortcuts (?)"
                className={`${toolbarBtn} ${showHelp ? 'text-amber-300 bg-zinc-800' : 'text-zinc-400'}`}
              >
                ?
              </button>
              <button
                onClick={() => { loadGraph(); }}
                title="Refresh graph"
                className={`${toolbarBtn} ${loading ? 'animate-spin pointer-events-none opacity-50' : ''}`}
              >
                ↻
              </button>
            </div>
          )}
        </div>
        {!live && loading && (
          <div className="flex-1 flex items-center justify-center px-6">
            <div className="text-center space-y-2">
              <div className="text-2xl animate-pulse">🧠</div>
              <div className="text-xs font-mono text-zinc-600">yuklanmoqda…</div>
            </div>
          </div>
        )}
        {!live && !loading && (
          <div className="flex-1 flex items-center justify-center px-6">
            <div className="text-center space-y-2 max-w-sm">
              <div className="text-2xl">🧠</div>
              <div className="text-sm font-ui text-zinc-300">2nd Brain offline</div>
              <div className="text-xs font-ui text-zinc-600 leading-relaxed">
                Graf Igris_Memory'dan real ma'lumotlar bilan quriladi. Backend'ni
                ishga tushiring: <code className="font-mono text-zinc-500">python server.py</code> (Igris_brain).
              </div>
            </div>
          </div>
        )}
        {live && (
          <div className="flex-1 overflow-hidden relative">
            {/* Reload paytida eski graf KO'RINIB turadi — qora ekran flash yo'q;
                tepada yengil 'yangilanmoqda' belgisi (interaktsiyaga xalaqit qilmaydi). */}
            {loading && (
              <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none">
                <div className="text-[10px] font-mono px-2 py-1 rounded bg-zinc-950/85 border border-zinc-700 text-zinc-400">
                  ↻ yangilanmoqda…
                </div>
              </div>
            )}
            {viewMode === 'radial' ? (
              <TreeLayoutEngine
                width={800}
                height={600}
                nodes={nodes}
                links={links}
                nodeMap={nodeMap}
                selectedFatherId={selectedFather}
                onNodeSelect={(nodeId) => {
                  const node = nodes.find(n => n.id === nodeId);
                  if (node) setSelected(node);
                }}
                onFatherSelect={(fatherId) => {
                  setSelectedFather(fatherId);
                }}
              />
            ) : (
            <svg
              ref={svgRef}
              viewBox={`0 0 ${SVG_W} ${SVG_H}`}
              className="w-full h-full cursor-grab active:cursor-grabbing touch-none select-none"
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={endDrag}
              onPointerLeave={endDrag}
            >
              <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
                {/* CLUSTER BOUNDARIES — zich to'plamlarning chegaralari */}
                {clusters.map((cluster) => {
                  const kindColor = KIND_COLOR[cluster.kind as keyof typeof KIND_COLOR];
                  const fillColor = kindColor ? kindColor.fill : '#71717a';
                  const isExpanded = expandedCluster === cluster.id;
                  // Dominance asosida opacity — 100% dominant = to'liq rang, aralash = sust
                  const baseOpacity = 0.04 + cluster.dominance * 0.08; // 0.04..0.12
                  const strokeOpacity = 0.15 + cluster.dominance * 0.35; // 0.15..0.5
                  return (
                    <g
                      key={cluster.id}
                      onClick={() => focusCluster(cluster)}
                      onMouseEnter={() => setHoveredCluster(cluster)}
                      onMouseLeave={() => setHoveredCluster(null)}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* Cluster boundary circle — dominance asosida rang intensivligi */}
                      <circle
                        cx={cluster.cx}
                        cy={cluster.cy}
                        r={cluster.radius}
                        fill={fillColor}
                        fillOpacity={isExpanded ? baseOpacity * 2 : baseOpacity}
                        stroke={fillColor}
                        strokeWidth={isExpanded ? 2.5 : 1.5}
                        strokeOpacity={isExpanded ? Math.min(strokeOpacity * 1.5, 0.7) : strokeOpacity}
                        strokeDasharray={isExpanded ? 'none' : cluster.dominance > 0.7 ? '6 3' : '4 2'}
                        style={{ transition: 'cx 0.3s ease-out, cy 0.3s ease-out, r 0.3s ease-out, fill-opacity 0.3s ease, stroke-width 0.3s ease, stroke-opacity 0.3s ease' }}
                      />
                      {/* Expanded indicator — pulsating glow */}
                      {isExpanded && (
                        <circle
                          cx={cluster.cx}
                          cy={cluster.cy}
                          r={cluster.radius + 4}
                          fill="none"
                          stroke={fillColor}
                          strokeWidth={1}
                          strokeOpacity={0.3}
                          className="brain-fresh-ring"
                        />
                      )}
                      {/* Cluster label */}
                      {cluster.nodes.length >= 4 && view.scale < 2 && (
                        <text
                          x={cluster.cx}
                          y={cluster.cy - cluster.radius - 6}
                          textAnchor="middle"
                          fontSize="7"
                          fill={fillColor}
                          fillOpacity={isExpanded ? 0.8 : 0.5}
                          fontFamily="IBM Plex Mono, monospace"
                          fontWeight={isExpanded ? 'bold' : 'normal'}
                          style={{ pointerEvents: 'none', transition: 'fill-opacity 0.3s ease' }}
                        >
                          {isExpanded ? '▼' : '▶'} {cluster.kind} ({cluster.nodes.length})
                        </text>
                      )}
                    </g>
                  );
                })}
                {links.map(([a, b], i) => {
                  const na = nodeMap[a];
                  const nb = nodeMap[b];
                  if (!na || !nb) return null;
                  const pa = posOf(na);
                  const pb = posOf(nb);
                  const dim = !(matches(na) && matches(nb));
                  const linkedToSelected = selected && (a === selected.id || b === selected.id);
                  const isHoveredLink = hoveredLink && ((hoveredLink[0] === a && hoveredLink[1] === b) || (hoveredLink[0] === b && hoveredLink[1] === a));
                  const reason = linkReasonOf(a, b);
                  // Zoom'da (yuqori scale) linklar SEMANTIK sabab bilan ko'rsatiladi
                  // — kuchli bog'langan node'lar qalin chiziq bilan ajralib turadi
                  // (nega yaqinlashayotgani vizual ko'rinadi).
                  const weight = Math.min(reason.length, 4);
                  const strokeW = (isHoveredLink ? 2.6 : linkedToSelected ? 1.6 : 1) + weight * 0.35;
                  return (
                    <g key={i}>
                      <line
                        x1={pa.x}
                        y1={pa.y}
                        x2={pb.x}
                        y2={pb.y}
                        stroke={isHoveredLink ? '#f59e0b' : linkedToSelected ? '#b45309' : '#71717a'}
                        strokeWidth={strokeW}
                        opacity={dim ? 0.15 : isHoveredLink ? 1 : linkedToSelected ? 0.9 : 0.8}
                        onMouseEnter={() => setHoveredLink([a, b])}
                        onMouseLeave={() => setHoveredLink((h) => (h && h[0] === a && h[1] === b ? null : h))}
                        style={{ cursor: 'pointer', transition: 'cx 0.3s ease-out, cy 0.3s ease-out, stroke 0.15s ease, stroke-width 0.15s ease, opacity 0.4s ease-out' }}
                      />
                      {/* hover uchun keng ko'rinmas maydon — kichik chiziqni bosish oson */}
                      <line
                        x1={pa.x}
                        y1={pa.y}
                        x2={pb.x}
                        y2={pb.y}
                        stroke="transparent"
                        strokeWidth={12}
                        onMouseEnter={() => setHoveredLink([a, b])}
                        onMouseLeave={() => setHoveredLink((h) => (h && h[0] === a && h[1] === b ? null : h))}
                        style={{ cursor: 'pointer' }}
                      />
                      {/* Yuqori zoom'da link sababi yozuvi — nega bog'langanligi ko'rinadi */}
                      {view.scale >= 1.6 && reason.length > 0 && !dim && (
                        <text
                          x={(pa.x + pb.x) / 2}
                          y={(pa.y + pb.y) / 2 - 3}
                          textAnchor="middle"
                          fontSize="5.5"
                          fill={isHoveredLink ? '#fbbf24' : '#a1a1aa'}
                          fontFamily="IBM Plex Mono, monospace"
                          style={{ pointerEvents: 'none', transition: 'fill 0.15s ease' }}
                        >
                          {reason.slice(0, 3).join(' · ')}
                        </text>
                      )}
                    </g>
                  );
                })}
                {nodes.map((n) => {
                  const dim = !matches(n) || (kindFilter.size > 0 && !kindFilter.has(n.kind));
                  const p = posOf(n);
                  const r = n.kind === 'architecture' ? 9 : 7;
                  const isSelected = selected?.id === n.id;
                  const isHovered = hovered === n.id;
                  const isFresh = fresh.has(n.id);
                  const isFreshChat = freshChat.has(n.id);
                  const isMultiSelected = multiSelected.has(n.id);
                  const isExpanded = expandedNodes.has(n.id);
                  return (
                    <g
                      key={n.id}
                      opacity={dim ? 0.15 : 1}
                      onClick={(e) => {
                        if (movedRef.current) { movedRef.current = false; return; }
                        // Ctrl+click: multi-select
                        if (e.ctrlKey || e.metaKey) {
                          e.stopPropagation();
                          setMultiSelected((prev) => {
                            const next = new Set(prev);
                            if (next.has(n.id)) next.delete(n.id); else next.add(n.id);
                            return next;
                          });
                          return;
                        }
                        // Shift+click: toggle expand
                        if (e.shiftKey) {
                          e.stopPropagation();
                          setExpandedNodes((prev) => {
                            const next = new Set(prev);
                            if (next.has(n.id)) next.delete(n.id); else next.add(n.id);
                            return next;
                          });
                          setExpansionSource(n);
                          setTimeout(() => setExpansionSource(null), 1500);
                          return;
                        }
                        setSelected(n);
                      }}
                      onDoubleClick={(e) => onNodeDoubleClick(e, n)}
                      onContextMenu={(e) => onNodeContextMenu(e, n)}
                      onMouseDown={(e) => {
                        if (e.button === 1) { onNodeMiddleClick(e, n); return; }
                      }}
                      onPointerDown={(e) => onNodePointerDown(e, n)}
                      onPointerMove={onNodePointerMove}
                      onPointerUp={onNodePointerUp}
                      onMouseEnter={() => setHovered(n.id)}
                      onMouseLeave={() => setHovered((h) => (h === n.id ? null : h))}
                      className="cursor-pointer"
                      style={{ cursor: 'grab', transition: 'opacity 0.4s ease-out' }}
                    >
                      {/* YANGI SUHBAT — teal halqa + pop (joyida ajralib turadi) */}
                      {isFreshChat && (
                        <circle
                          cx={p.x}
                          cy={p.y}
                          r={r + 5}
                          fill="none"
                          stroke="#2dd4bf"
                          strokeWidth="2"
                          className="brain-fresh-chat-ring"
                        />
                      )}
                      {/* Yangi node (suhbat emas) — oltin halqa pulsatsiyasi */}
                      {isFresh && !isFreshChat && (
                        <circle
                          cx={p.x}
                          cy={p.y}
                          r={r + 6}
                          fill="none"
                          stroke="#f59e0b"
                          strokeWidth="1.5"
                          className="brain-fresh-ring"
                        />
                      )}
                      {/* Multi-select indicator — sky ring */}
                      {isMultiSelected && (
                        <circle
                          cx={p.x}
                          cy={p.y}
                          r={r + 4}
                          fill="none"
                          stroke="#38bdf8"
                          strokeWidth="1.5"
                          opacity={0.7}
                        />
                      )}
                      {/* Expanded indicator — dashed ring */}
                      {isExpanded && (
                        <circle
                          cx={p.x}
                          cy={p.y}
                          r={r + 7}
                          fill="none"
                          stroke={KIND_COLOR[n.kind].fill}
                          strokeWidth="1"
                          strokeDasharray="3 2"
                          opacity={0.5}
                        />
                      )}
                      <circle
                        cx={p.x}
                        cy={p.y}
                        r={(isSelected || isHovered) ? r + 3 : r}
                        fill={visualMode === 'domain' ? getDomainColor(n.id) : visualMode === 'verification' ? getVerificationColor(n.id) : KIND_COLOR[n.kind].fill}
                        stroke={isSelected ? '#f59e0b' : isHovered ? '#e4e4e7' : '#09090b'}
                        strokeWidth={isSelected ? 2.5 : 2}
                        className={isFreshChat ? 'brain-fresh-pop' : undefined}
                        style={{ transition: 'cx 0.3s ease-out, cy 0.3s ease-out, r 0.15s ease, stroke 0.15s ease' }}
                      />
                      <title>{n.label}</title>
                      <text
                        x={p.x}
                        y={p.y - r - 5}
                        textAnchor="middle"
                        fontSize="10"
                        fill={isHovered || isSelected ? '#e4e4e7' : '#d4d4d8'}
                        fontFamily="IBM Plex Sans, sans-serif"
                      >
                        {n.label.length > 22 ? n.label.slice(0, 20) + '…' : n.label}
                      </text>
                      {/* Suhbat node'i: oxirgi yangilanish vaqti (kichik, teal) */}
                      {n.kind === 'session' && relTime(n.updated_at) && (
                        <text
                          x={p.x}
                          y={p.y + r + 7}
                          textAnchor="middle"
                          fontSize="6"
                          fill="#2dd4bf"
                          opacity={isHovered || isSelected ? 0.9 : 0.55}
                          fontFamily="IBM Plex Mono, monospace"
                        >
                          {relTime(n.updated_at)}
                        </text>
                      )}
                      {/* AKMS Node Indicator — verification badge, evidence count, domain icon */}
                      <NodeIndicator
                        nodeId={n.id}
                        x={p.x}
                        y={p.y}
                        radius={r}
                        visualMode={visualMode}
                      />
                    </g>
                  );
                })}
              </g>
            </svg>
            )}

            {/* ---- BRANCH VIEWER ---- */}
            {branchViewNode && (
              <BranchingVisualizer
                nodes={nodes}
                links={links}
                nodeMap={nodeMap}
                rootId={branchViewNode}
                expandedNodes={expandedNodes}
                onToggleExpand={(id) => {
                  setExpandedNodes((prev) => {
                    const next = new Set(prev);
                    if (next.has(id)) next.delete(id); else next.add(id);
                    return next;
                  });
                }}
                onSelectNode={(n) => setSelected(n)}
                onFocusNode={(n) => focusNode(n)}
                onClose={() => setBranchViewNode(null)}
                position={{ x: SVG_W / 2, y: SVG_H / 2 }}
              />
            )}

            {/* ---- EXPANSION RING ---- */}
            <NodeExpansionRing
              sourceNode={expansionSource}
              neighbors={expansionSource ? getNeighbors(expansionSource.id) : []}
              nodeMap={nodeMap}
              position={expansionSource ? posOf(expansionSource) : { x: 0, y: 0 }}
              isExpanding={!!expansionSource}
              onSelectNode={(n) => setSelected(n)}
            />

            {/* ---- PATH TRACER ---- */}
            <BranchPathTracer
              nodes={nodes}
              links={links}
              nodeMap={nodeMap}
              posOf={posOf}
              sourceId={pathTarget?.source ?? null}
              targetId={pathTarget?.target ?? null}
              isActive={!!pathTarget}
              onComplete={() => setPathTarget(null)}
            />

            {/* ---- GRAPH NAVIGATION HUD ---- */}
            <GraphNavigationHUD
              zoom={view.scale}
              selectedNode={selected}
              expandedCount={expandedNodes.size}
              multiSelectCount={multiSelected.size}
              totalNodes={nodes.length}
              totalLinks={links.length}
              onFitView={fitView}
              onResetView={resetView}
              onToggleHelp={() => setShowHelp((v) => !v)}
            />

            {/* ---- MOUSE CONTROLS PANEL ---- */}
            <MouseControlsPanel
              isShiftDown={shiftDown}
              isCtrlDown={ctrlDown}
              isAltDown={altDown}
              onToggleShift={() => setShiftDown((v) => !v)}
              onToggleCtrl={() => setCtrlDown((v) => !v)}
              onToggleAlt={() => setAltDown((v) => !v)}
              onClearModifiers={() => { setShiftDown(false); setCtrlDown(false); setAltDown(false); }}
              expandedNodes={expandedNodes}
              onToggleExpandAll={expandAll}
              onCollapseAll={collapseAll}
            />

            {/* ---- CONTEXT MENU ---- */}
            {contextMenu && contextMenuNode && (
              <div
                className="fixed z-50 pointer-events-auto"
                style={{ left: contextMenu.x, top: contextMenu.y }}
              >
                <div
                  className="bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl overflow-hidden min-w-[180px]"
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Node info header */}
                  <div className="px-2.5 py-1.5 border-b border-zinc-800">
                    <div className="text-[10px] font-ui text-zinc-200 truncate">{contextMenuNode.label}</div>
                    <div className="text-[8px] font-mono text-zinc-600">{contextMenuNode.kind}</div>
                  </div>
                  {/* Actions */}
                  <div className="py-0.5">
                    <button onClick={ctxFocus} className="w-full text-left px-2.5 py-1 text-[10px] font-mono text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors flex items-center gap-2">
                      <span>⛶</span> Focus node
                    </button>
                    <button onClick={ctxExpand} className="w-full text-left px-2.5 py-1 text-[10px] font-mono text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors flex items-center gap-2">
                      <span>⊕</span> {expandedNodes.has(contextMenu.nodeId) ? 'Collapse' : 'Expand'} neighbors
                    </button>
                    <button onClick={ctxBranchView} className="w-full text-left px-2.5 py-1 text-[10px] font-mono text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors flex items-center gap-2">
                      <span>🌳</span> Branch view
                    </button>
                    <button onClick={ctxMultiSelect} className="w-full text-left px-2.5 py-1 text-[10px] font-mono text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors flex items-center gap-2">
                      <span>{multiSelected.has(contextMenu.nodeId) ? '✓' : '☐'}</span> {multiSelected.has(contextMenu.nodeId) ? 'Deselect' : 'Multi-select'}
                    </button>
                    <div className="border-t border-zinc-800 my-0.5" />
                    <button onClick={ctxCopyId} className="w-full text-left px-2.5 py-1 text-[10px] font-mono text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors flex items-center gap-2">
                      <span>📋</span> Copy ID
                    </button>
                  </div>
                  {/* Trace path submenu */}
                  {contextMenuNeighbors.length > 0 && (
                    <div className="border-t border-zinc-800 py-0.5">
                      <div className="px-2.5 py-0.5 text-[8px] font-mono text-zinc-600 uppercase">Trace path to</div>
                      {contextMenuNeighbors.slice(0, 5).map((n) => (
                        <button
                          key={n.id}
                          onClick={() => ctxTracePath(n.id)}
                          className="w-full text-left px-2.5 py-0.5 text-[9px] font-mono text-zinc-500 hover:text-amber-300 hover:bg-zinc-800 transition-colors flex items-center gap-1.5"
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${KIND_COLOR[n.kind]?.dot || 'bg-zinc-600'}`} />
                          {n.label.length > 18 ? n.label.slice(0, 16) + '…' : n.label}
                        </button>
                      ))}
                      {contextMenuNeighbors.length > 5 && (
                        <div className="px-2.5 py-0.5 text-[8px] font-mono text-zinc-600">+{contextMenuNeighbors.length - 5} more</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ---- BOTTOM HINTS ---- */}
            <div className="absolute bottom-2 left-2 text-[10px] font-mono text-zinc-600 select-none pointer-events-none">
              drag node · move &nbsp;|&nbsp; wheel · zoom &nbsp;|&nbsp; double-click · branch &nbsp;|&nbsp; r-click · menu &nbsp;|&nbsp; shift+click · expand &nbsp;|&nbsp; <button onClick={() => setShowHelp(true)} className="text-zinc-500 hover:text-amber-300 pointer-events-auto transition-colors" title="Keyboard shortcuts">? shortcuts</button>
            </div>
            {/* KEYBOARD HELP OVERLAY */}
            {showHelp && (
              <div
                className="absolute inset-0 z-30 flex items-center justify-center bg-black/60 backdrop-blur-sm pointer-events-auto"
                onClick={() => setShowHelp(false)}
              >
                <div
                  className="bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl px-6 py-5 max-w-lg w-full mx-4"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-ui font-medium text-zinc-200">⌨️ Keyboard Shortcuts</h3>
                    <button
                      onClick={() => setShowHelp(false)}
                      className="text-zinc-500 hover:text-zinc-300 text-xs font-mono"
                    >
                      ✕ Esc
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
                    {/* Navigation */}
                    <div className="col-span-2 text-[10px] font-mono text-zinc-500 uppercase tracking-wider mb-1">Navigation</div>
                    <ShortcutRow keys={['Scroll']} desc="Zoom in/out" />
                    <ShortcutRow keys={['Click + drag']} desc="Pan canvas" />
                    <ShortcutRow keys={['Dbl-click']} desc="Focus node" />
                    <ShortcutRow keys={['F']} desc="Fit all nodes" />
                    <ShortcutRow keys={['R']} desc="Reset view" />
                    {/* Filters */}
                    <div className="col-span-2 text-[10px] font-mono text-zinc-500 uppercase tracking-wider mt-2 mb-1">Kind Filters</div>
                    <ShortcutRow keys={['1']} desc="Toggle session" />
                    <ShortcutRow keys={['2']} desc="Toggle fact" />
                    <ShortcutRow keys={['3']} desc="Toggle pattern" />
                    <ShortcutRow keys={['4']} desc="Toggle architecture" />
                    <ShortcutRow keys={['0']} desc="Clear all filters" />
                    {/* Clusters */}
                    <div className="col-span-2 text-[10px] font-mono text-zinc-500 uppercase tracking-wider mt-2 mb-1">Clusters</div>
                    <ShortcutRow keys={['Click cluster']} desc="Zoom to cluster" />
                    <ShortcutRow keys={['?']} desc="Toggle this help" />
                    <ShortcutRow keys={['Esc']} desc="Close overlays" />
                  </div>
                  <div className="mt-3 pt-2 border-t border-zinc-800 text-[9px] font-mono text-zinc-600">
                    cluster tooltip: ⊕ select → 🔗 merge &nbsp;|&nbsp; ✂ split &nbsp;|&nbsp; node: ⟲ reset pos
                  </div>
                </div>
              </div>
            )}
            {hovered && nodeMap[hovered] && !hoveredLink && (
              <div className="absolute bottom-7 left-2 max-w-[260px] px-2 py-1.5 rounded bg-zinc-950/90 border border-zinc-700 text-[10px] font-mono text-zinc-300 pointer-events-none">
                <span className={KIND_COLOR[nodeMap[hovered].kind].text}>{nodeMap[hovered].label}</span>
                {nodeMap[hovered].kind === 'session' && relTime(nodeMap[hovered].updated_at) && (
                  <span className="text-teal-400/80 ml-1.5">· {relTime(nodeMap[hovered].updated_at)}</span>
                )}
                {nodeMap[hovered].detail && <div className="text-zinc-500 mt-0.5 leading-snug line-clamp-2">{nodeMap[hovered].detail}</div>}
              </div>
            )}
            {hoveredLink && nodeMap[hoveredLink[0]] && nodeMap[hoveredLink[1]] && (
              <div className="absolute bottom-7 left-2 max-w-[300px] px-2 py-1.5 rounded bg-zinc-950/90 border border-amber-700/50 text-[10px] font-mono text-zinc-300 pointer-events-none">
                <div className="text-amber-300 mb-0.5">
                  {nodeMap[hoveredLink[0]].label.slice(0, 24)} ↔ {nodeMap[hoveredLink[1]].label.slice(0, 24)}
                </div>
                {linkReasonOf(hoveredLink[0], hoveredLink[1]).length > 0 ? (
                  <div className="text-zinc-500 leading-snug">
                    <span className="text-zinc-400">nega bog\'langan:</span> {linkReasonOf(hoveredLink[0], hoveredLink[1]).join(', ')}
                  </div>
                ) : (
                  <div className="text-zinc-600">wikilink / umumiy so\'zlar</div>
                )}
              </div>
            )}
            {hoveredCluster && (
              <div className="absolute bottom-7 left-2 max-w-[280px] px-2.5 py-2 rounded bg-zinc-950/95 border border-zinc-700 text-[10px] font-mono text-zinc-300 pointer-events-none shadow-xl">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className={`w-2 h-2 rounded-full ${KIND_COLOR[hoveredCluster.kind as keyof typeof KIND_COLOR]?.dot || 'bg-zinc-500'}`} />
                  <span className="text-zinc-200 font-medium">{hoveredCluster.kind}</span>
                  <span className="text-zinc-600">cluster</span>
                  <span className="text-zinc-500 ml-auto">{(hoveredCluster.dominance * 100).toFixed(0)}%</span>
                </div>
                <div className="text-zinc-400 mb-1">
                  {hoveredCluster.nodes.length} ta node · zichlik: {hoveredCluster.density.toFixed(2)}
                </div>
                {/* Kind breakdown — qancha tur aralashgan */}
                {Object.keys(hoveredCluster.kindBreakdown).length > 1 && (
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {(Object.entries(hoveredCluster.kindBreakdown) as [string, number][])
                      .sort((a, b) => b[1] - a[1])
                      .map(([k, count]) => (
                        <span key={k} className="flex items-center gap-0.5 text-[9px]">
                          <span className={`w-1.5 h-1.5 rounded-full ${KIND_COLOR[k as keyof typeof KIND_COLOR]?.dot || 'bg-zinc-600'}`} />
                          <span className="text-zinc-500">{k}</span>
                          <span className="text-zinc-600">{count}</span>
                        </span>
                      ))}
                  </div>
                )}
                <div className="text-zinc-500 leading-snug max-h-24 overflow-y-auto">
                  {hoveredCluster.nodes.slice(0, 8).map((id) => {
                    const n = nodeMap[id];
                    return n ? (
                      <div key={id} className="flex items-center gap-1">
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${KIND_COLOR[n.kind]?.dot || 'bg-zinc-600'}`} />
                        <span className="truncate">{n.label}</span>
                      </div>
                    ) : null;
                  })}
                  {hoveredCluster.nodes.length > 8 && (
                    <div className="text-zinc-600">... va {hoveredCluster.nodes.length - 8} ta boshqa</div>
                  )}
                </div>                <div className="flex items-center gap-1.5 mt-2 pt-1.5 border-t border-zinc-800">
                  <button
                    onClick={() => {
                      if (selectedCluster && selectedCluster !== hoveredCluster.id) {
                        mergeClusters(selectedCluster, hoveredCluster.id);
                      } else {
                        setSelectedCluster(hoveredCluster.id);
                      }
                    }}
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded transition-colors ${
                      selectedCluster === hoveredCluster.id
                        ? 'bg-amber-900/50 text-amber-300'
                        : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                    }`}
                    title={selectedCluster ? 'Birlashtirish' : 'Tanlash (birlashtirish uchun)'}
                  >
                    {selectedCluster && selectedCluster !== hoveredCluster.id ? '🔗 merge' : selectedCluster === hoveredCluster.id ? '✓ selected' : '⊕ select'}
                  </button>
                  {mergedClusters[hoveredCluster.id] && (
                    <button
                      onClick={() => splitCluster(hoveredCluster.id)}
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 hover:text-rose-300 transition-colors"
                      title="Ajratish (merge'ni bekor qilish)"
                    >
                      ✂ split
                    </button>
                  )}
                  <span className="text-[9px] text-zinc-600 ml-auto">click · zoom</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      {selected && (
        <div className="w-64 border-l border-zinc-800 bg-zinc-900 bg-opacity-40 p-3 shrink-0 overflow-y-auto">
          <div className="flex items-center justify-between mb-2">
            <span className={`text-xs font-ui font-medium ${KIND_COLOR[selected.kind].text}`}>
              {selected.kind}
            </span>
            <button onClick={() => setSelected(null)} className="text-zinc-600 hover:text-zinc-300">
              ✕
            </button>
          </div>
          <div className="text-sm font-ui text-zinc-100 mb-3 leading-snug">{selected.label}</div>
          {selected.kind === 'session' && relTime(selected.updated_at) && (
            <div className="text-[10px] font-mono text-teal-400/80 mb-3 -mt-2">
              🕒 oxirgi yangilanish: {relTime(selected.updated_at)}
            </div>
          )}
          {selected.detail && (
            <div className="text-[11px] font-ui text-zinc-500 mb-3 leading-relaxed border-l-2 border-zinc-800 pl-2">
              {selected.detail}
            </div>
          )}
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="text-xs font-ui text-zinc-500">Linked notes</span>
            <button
              onClick={() => focusNode(selected)}
              className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
              title="Zoom to this node"
            >
              ⛶ focus
            </button>
            {offsets[selected.id] && (
              <button
                onClick={() => resetNodePos(selected.id)}
                className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
                title="Asl joylashuviga qaytarish"
              >
                ⟲ pos
              </button>
            )}
          </div>
          <div className="space-y-1">
            {neighborsOf(selected.id).map((n) => (
              <button
                key={n.id}
                onClick={() => setSelected(n)}
                className="w-full text-left text-xs font-ui text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded hover:bg-zinc-800 flex items-center gap-1.5 transition-colors"
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${KIND_COLOR[n.kind].dot}`} /> {n.label}
              </button>
            ))}
            {neighborsOf(selected.id).length === 0 && (
              <div className="text-[11px] font-ui text-zinc-600">no links</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
