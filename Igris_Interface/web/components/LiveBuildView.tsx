import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { workspaceFileText, workspaceFileUrl, drawingEdit, agentRunStatus } from '../backend';
import { useAgentConsoleStore } from '../../shared/store';
import { LiveBuildHTML } from './LiveBuildHTML';

const SVG_EXT = /\.svg$/i;
const UB_EXT = /\.uibuild\.json$/i;
// SVG ichida chiziladigan elementlar (defs/script tashqari)
const SHAPE_SELECTOR = 'rect,circle,ellipse,line,polyline,polygon,path,text,image,use,arc';

// ---------------------------------------------------------------------- //
// Part M (WS-A): bir vaqtda ko'pi bilan shuncha LIVE BUILD animatsiyasi
// ishlashi mumkin â€” 5-6 karta montajda qolsa ham GPU/compositor
// yuklanmaydi (qora ekranning oldini oladi).
// ---------------------------------------------------------------------- //
const MAX_ACTIVE_ANIMATORS = 2;
let activeAnimatorCount = 0;
function acquireAnimatorSlot(): boolean {
  if (activeAnimatorCount >= MAX_ACTIVE_ANIMATORS) return false;
  activeAnimatorCount += 1;
  return true;
}
function releaseAnimatorSlot(): void {
  if (activeAnimatorCount > 0) activeAnimatorCount -= 1;
}

// Faqat BIRTA aktiv video yozuv (MediaRecorder) â€” bir nechta yozuv
// xotira/GPU bosimi beradi (qora ekran omillaridan biri).
const _activeRecorders = new Set<MediaRecorder>();
function stopOtherRecorders(exclude: MediaRecorder | null): void {
  for (const rec of Array.from(_activeRecorders)) {
    if (rec === exclude) continue;
    try { if (rec.state !== 'inactive') rec.stop(); } catch { /* ignore */ }
  }
}

/** Element viewportda ko'rinadimi (IntersectionObserver) â€” off-screen kartalar
 *  animatsiya boshlamaydi/pauza bo'ladi (Part M, M-A1). */
function useInViewport<T extends HTMLElement>(ref: React.RefObject<T | null>): boolean {
  // Default TRUE — kuzatuvchi hali ishlamagan bo'lsa ham autoplay boshlansin
  // (false-negative "umuman boshlamaydi" xatosining oldini oladi). Ekrandan
  // chiqqanda observer FALSE berib pauza qiladi.
  const [inView, setInView] = useState(true);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') { setInView(true); return; }
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), {
      rootMargin: '120px',
    });
    io.observe(el);
    return () => io.disconnect();
  }, [ref]);
  return inView;
}

interface LiveBuildViewProps {
  path: string;
  /** Chaqui chat'ga xabar berish uchun â€” tahrir muvaffaqiyatli qo'llanganda chaqiriladi. */
  onEdited?: (path: string) => void;
}

type Phase = 'loading' | 'svg' | 'png' | 'error';

// ---------------------------------------------------------------------- //
// Part M (WS-B): HAQIQIY qurilish bosqichlari â€” rassom jarayoni:
//   Poydevor (canvas/fon) -> Taxminiy joylash (wireframe) ->
//   Takomillashtirish (tafsilotlar) -> Rang berish (fill) -> Tekshiruv.
// Bu "soxta fade/pop" emas â€” fidelity qatlamma-qatlam oshadi.
// ---------------------------------------------------------------------- //
type BuildStage = 'foundation' | 'sketch' | 'rough' | 'refine' | 'color' | 'done';
const BUILD_STAGE_ORDER: BuildStage[] = ['foundation', 'sketch', 'refine', 'color', 'done'];
const BUILD_STAGE_LABEL: Record<BuildStage, string> = {
  foundation: 'Poydevor',
  sketch: 'Taxminiy joylash',
  rough: 'Taxminiy joylash',
  refine: 'Takomillashtirish',
  color: 'Rang berish',
  done: 'Tekshiruv',
};

export function LiveBuildView({ path, onEdited }: LiveBuildViewProps) {
  const loadWorkspace = useAgentConsoleStore((s) => s.loadWorkspace);
  const [phase, setPhase] = useState<Phase>('loading');
  const [error, setError] = useState<string | null>(null);
  // SVG qurilish holati
  const [total, setTotal] = useState(0);
  const [revealed, setRevealed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [frozen, setFrozen] = useState(false);
  // PNG progress (0..1)
  const [pngProgress, setPngProgress] = useState(0);
  // Tahrir oynasi
  const [editOpen, setEditOpen] = useState(false);
  const [editRequest, setEditRequest] = useState('');
  const [editing, setEditing] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [version, setVersion] = useState(0); // fayl yangilanganda reload
  // Video yozib olish (WebM)
  const [recording, setRecording] = useState(false);
  const mediaRecRef = useRef<MediaRecorder | null>(null);
  const recChunksRef = useRef<Blob[]>([]);
  const recCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const recFrameRef = useRef(0); // mirror race'ni oldini olish uchun token

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pngImgRef = useRef<HTMLImageElement | null>(null);
  const rafRef = useRef<number>(0);
  const lastTsRef = useRef(0);
  const intervalRef = useRef<number | null>(null);
  const revealedRef = useRef(0);
  const [svgHtml, setSvgHtml] = useState<string | null>(null);

  // Part M (WS-A): ko'rinish + global animator chegarasi + watchdog
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inView = useInViewport(rootRef);
  const userPausedRef = useRef(false);
  const lastTickRef = useRef(performance.now());

  // Part M (WS-B): bosqichli haqiqiy qurilish holati.
  const [buildStage, setBuildStage] = useState<BuildStage>('foundation');
  const buildStageRef = useRef<BuildStage>('foundation');
  useEffect(() => { buildStageRef.current = buildStage; }, [buildStage]);
  // Har bir [data-build] elementning qurilish bosqichi + asl fill/stroke.
  const stageMapRef = useRef<Record<number, BuildStage>>({});
  const origStyleRef = useRef<Record<number, { fill?: string; stroke?: string; strokeWidth?: string }>>({});

  const finished = phase === 'png' ? pngProgress >= 1 : buildStage === 'done';

  // ------------------------------------------------------------------ //
  // 0. .uibuild.json -> REAL construction mode (LiveBuildHTML)
  // ------------------------------------------------------------------ //
  if (UB_EXT.test(path)) {
    return <LiveBuildHTML path={path} onEdited={onEdited} />;
  }

// Ko'rinish bo'yicha autoplay boshqaruvi (M-A1): karta ko'rinmasa pauza;
  // qayta ko'rinsa — foydalanuvchi qo'lda pauza qilmagan bo'lsa davom etadi.
  useEffect(() => {
    if (!inView) {
      setPlaying(false);
      return;
    }
    if (userPausedRef.current) return;
    if (!finished && !frozen && !editing) setPlaying(true);
  }, [inView, finished, frozen, editing, playing]);

  // Tab yashiringanda barcha animatsiyalar pauza (M-A5).
  useEffect(() => {
    const onVis = () => { if (document.hidden) setPlaying(false); };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

  // Watchdog (M-A8): qurilish "tick" bermay qotsa (~1.5s) avto-pauza â€”
  // compositor yuklanib qotgan bo'lsa ham oyna qoraymaydi.
  useEffect(() => {
    const wd = window.setInterval(() => {
      if (playing && performance.now() - lastTickRef.current > 1500) setPlaying(false);
    }, 1000);
    return () => window.clearInterval(wd);
  }, [playing]);

  // ------------------------------------------------------------------ //
  // 1. Faylni yuklash: SVG -> elementlar, PNG -> rasm
  // ------------------------------------------------------------------ //
  useEffect(() => {
    let cancelled = false;
    setPhase('loading');
    setError(null);
    setRevealed(0);
    setPngProgress(0);
    setFrozen(false);
    setEditing(false);
    setEditError(null);
    setBuildStage('foundation');
    buildStageRef.current = 'foundation';
    revealedRef.current = 0;
    stageMapRef.current = {};
    origStyleRef.current = {};

    if (!SVG_EXT.test(path)) {
      // PNG / boshqa raster
      const img = new Image();
      img.onload = () => {
        if (cancelled) return;
        pngImgRef.current = img;
        setTotal(100);
        setPhase('png');
        setPlaying(inView && !userPausedRef.current);
      };
      img.onerror = () => {
        if (cancelled) return;
        setPhase('error');
        setError('image not found on backend');
      };
      img.src = workspaceFileUrl(path);
      return () => { cancelled = true; };
    }

    workspaceFileText(path)
      .then((text) => {
        if (cancelled) return;
        const { html, count } = buildSvgHtml(text);
        if (!html || count === 0) {
          setPhase('error');
          setError('no drawable elements found in SVG');
          return;
        }
        setSvgHtml(html);
        setTotal(count);
        setPhase('svg');
        setPlaying(inView && !userPausedRef.current);
      })
      .catch(() => {
        if (cancelled) return;
        setPhase('error');
        setError('cannot load file from backend');
      });
    return () => { cancelled = true; };
  }, [path, version]);

  // ------------------------------------------------------------------ //
  // 2. SVG HAQIQIY qurilish â€” bosqich bo'yicha fidelity qo'llanadi.
  //    Poydevor -> wireframe (taxminiy joylash) -> tafsilot -> rang ->
  //    hammasi bo'yalgan. "Soxta fade/pop" effekti YO'Q â€” har bosqich
  //    shaklning REAL holatini o'zgartiradi (kontur yoki bo'yalgan).
  // ------------------------------------------------------------------ //
  useEffect(() => {
    if (phase !== 'svg' || !containerRef.current) return;
    const svg = containerRef.current.querySelector('svg');
    const els = svg ? Array.from(svg.querySelectorAll<SVGElement>('[data-build]')) : [];
    if (!els.length) return;

    // Birinchi marta: har elementni bosqichga ajratamiz + asl uslubni saqlaymiz.
    if (Object.keys(stageMapRef.current).length === 0) {
      const vw = svg?.viewBox?.baseVal?.width || 512;
      const vh = svg?.viewBox?.baseVal?.height || 512;
      const canvasArea = Math.max(1, vw * vh);
      const areas = els.map((el) => {
        try { const b = (el as SVGGraphicsElement).getBBox(); return Math.max(0, b.width * b.height); } catch { return 0; }
      });
      const maxArea = Math.max(1, ...areas);
      const map: Record<number, BuildStage> = {};
      els.forEach((el, i) => {
        const tag = el.tagName.toLowerCase();
        const ratio = areas[i] / canvasArea;
        const rel = areas[i] / maxArea;
        if (i === 0 && ratio >= 0.2) map[i] = 'foundation';
        else if (tag === 'text') map[i] = 'refine';
        else if (rel >= 0.18) map[i] = 'rough';
        else map[i] = 'refine';
      });
      if (!Object.values(map).some((s) => s === 'foundation')) map[0] = 'foundation';
      if (!Object.values(map).some((s) => s === 'rough')) {
        const first = els.findIndex((_, i) => map[i] !== 'foundation');
        if (first >= 0) map[first] = 'rough';
      }
      stageMapRef.current = map;
      origStyleRef.current = {};
      els.forEach((el, i) => {
        origStyleRef.current[i] = {
          fill: el.getAttribute('fill') ?? undefined,
          stroke: el.getAttribute('stroke') ?? undefined,
          strokeWidth: el.getAttribute('stroke-width') ?? undefined,
        };
      });
    }

    const map = stageMapRef.current;
    // Rang berishgacha: faqat foundation+rough(+refine) â€” kontur (wireframe).
    const admitted = new Set<BuildStage>(['foundation']);
    if (buildStage === 'sketch' || buildStage === 'refine' || buildStage === 'color' || buildStage === 'done') admitted.add('rough');
    if (buildStage === 'refine' || buildStage === 'color' || buildStage === 'done') admitted.add('refine');
    const painting = buildStage === 'color' || buildStage === 'done';

    els.forEach((el, i) => {
      const elSvg = el as SVGElement;
      const stage = map[i] ?? 'refine';
      const shown = painting || admitted.has(stage);
      elSvg.style.opacity = shown ? '1' : '0';
      elSvg.style.pointerEvents = shown ? 'auto' : 'none';
      if (!shown) return;
      // Foundation doim bo'yalgan; qolganlar rang berishgacha wireframe.
      const painted = painting ? i < revealed : stage === 'foundation';
      const orig = origStyleRef.current[i] ?? {};
      if (painted) {
        elSvg.style.fill = orig.fill ?? '#f59e0b';
        if (orig.stroke) elSvg.style.stroke = orig.stroke;
        if (orig.strokeWidth) elSvg.style.strokeWidth = orig.strokeWidth;
        elSvg.style.transition = '';
      } else {
        elSvg.style.fill = 'none';
        elSvg.style.stroke = '#a1a1aa';
        elSvg.style.strokeWidth = '2';
        elSvg.style.transition = 'none';
      }
    });
  }, [buildStage, revealed, phase, svgHtml]);

  // Part M (WS-B/B3): Tekshiruv checklisti â€” qurilish tugagach o'lcham/qamrov/
  // to'liqlik tekshiriladi (rassom "hajm va shakl talab darajasidami" tekshiruvi).
  const [verifyItems, setVerifyItems] = useState<{ ok: boolean; label: string }[] | null>(null);
  useEffect(() => {
    if (phase !== 'svg' || buildStage !== 'done' || !containerRef.current) return;
    const svg = containerRef.current.querySelector('svg');
    const els = svg ? Array.from(svg.querySelectorAll<SVGElement>('[data-build]')) : [];
    if (!svg || !els.length) { setVerifyItems([{ ok: false, label: 'hech qanday element topilmadi' }]); return; }
    const vw = svg.viewBox?.baseVal?.width || 512;
    const vh = svg.viewBox?.baseVal?.height || 512;
    const items: { ok: boolean; label: string }[] = [
      { ok: els.length === total, label: `${els.length}/${total} element qurildi` },
    ];
    let inBounds = 0;
    els.forEach((el) => {
      try {
        const b = (el as SVGGraphicsElement).getBBox();
        if (b.x >= -1 && b.y >= -1 && b.x + b.width <= vw + 1 && b.y + b.height <= vh + 1) inBounds += 1;
      } catch { /* skip */ }
    });
    items.push({ ok: inBounds === els.length, label: `${inBounds}/${els.length} element viewBox chegarasida (hajm tekshiruvi)` });
    items.push({ ok: els.length >= 3, label: 'kompozitsiya yetarli (3+ element)' });
    setVerifyItems(items);
  }, [phase, buildStage, total]);

  // ------------------------------------------------------------------ //
  // 3. Qurilish soati (SVG + PNG)
  // ------------------------------------------------------------------ //
  useEffect(() => {
    if (!playing || frozen || editing) return;
    // Part M (A5): global animator chegarasi â€” bo'sh slot bo'lmasa navbatda
    // turamiz (har 250ms qayta urinish). Slot shu componentga tegishli.
    let acquired = false;
    let retryTimer: number | null = null;
    const start = () => {
      if (acquired) return;
      if (!acquireAnimatorSlot()) {
        retryTimer = window.setTimeout(start, 250);
        return;
      }
      acquired = true;
      lastTickRef.current = performance.now();
      if (phase === 'svg' && total > 0) {
        // Part M (WS-B): bosqichli dvigatel â€” Poydevor -> Taxminiy joylash ->
        // Takomillashtirish -> Rang berish (elementma-element) -> Tekshiruv.
        const iv = window.setInterval(() => {
          lastTickRef.current = performance.now();
          const bs = buildStageRef.current;
          if (bs === 'color') {
            const next = Math.min(total, revealedRef.current + 1);
            revealedRef.current = next;
            setRevealed(next);
            if (next >= total) setBuildStage('done');
          } else if (bs === 'foundation') {
            setBuildStage('sketch');
          } else if (bs === 'sketch') {
            setBuildStage('refine');
          } else if (bs === 'refine') {
            setBuildStage('color');
          } else {
            setPlaying(false); // done
          }
        }, Math.max(140, 700 / speed));
        intervalRef.current = iv;
        return;
      }
      if (phase === 'png') {
        lastTsRef.current = performance.now();
        const step = (ts: number) => {
          lastTickRef.current = performance.now();
          const dt = ts - lastTsRef.current;
          lastTsRef.current = ts;
          setPngProgress((p) => {
            const np = p + (dt / 1000) * (0.35 * speed);
            if (np >= 1) { setPlaying(false); return 1; }
            return np;
          });
          rafRef.current = requestAnimationFrame(step);
        };
        rafRef.current = requestAnimationFrame(step);
      }
    };
    start();
    return () => {
      if (retryTimer) window.clearTimeout(retryTimer);
      if (intervalRef.current) { window.clearInterval(intervalRef.current); intervalRef.current = null; }
      cancelAnimationFrame(rafRef.current);
      if (acquired) releaseAnimatorSlot();
    };
  }, [playing, frozen, editing, phase, speed, total]);

  // ------------------------------------------------------------------ //
  // 4. PNG canvas chizish (progressive wipe)
  // ------------------------------------------------------------------ //
  // PNG uchun elementma-element ko'rinish: markazdan spiral bo'ylab plitkalar
  // (bir tomondan ikkinchi tomonga "aralash wipe" o'rniga)
  const PNG_TILE = 40;
  const spiralOrder = useMemo(() => {
    const cols = Math.ceil(512 / PNG_TILE);
    const rows = Math.ceil(512 / PNG_TILE);
    const order: number[] = [];
    const seen = new Set<string>();
    const add = (x: number, y: number) => {
      if (x < 0 || y < 0 || x >= cols || y >= rows) return;
      const k = `${x},${y}`;
      if (seen.has(k)) return;
      seen.add(k);
      order.push(y * cols + x);
    };
    let x = Math.floor(cols / 2);
    let y = Math.floor(rows / 2);
    add(x, y);
    let dx = 1, dy = 0, len = 1, moved = 0;
    const total = cols * rows;
    while (seen.size < total) {
      for (let i = 0; i < len && seen.size < total; i++) { x += dx; y += dy; add(x, y); }
      moved++;
      if (moved === 2) { len++; moved = 0; }
      const ndx = -dy, ndy = dx;
      dx = ndx; dy = ndy;
    }
    return order;
  }, []);

  useEffect(() => {
    if (phase !== 'png' || !canvasRef.current || !pngImgRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = pngImgRef.current;
    if (!ctx) return;
    const W = canvas.width;
    const H = canvas.height;
    // oq fon (video yozishda ham to'g'ri ko'rinadi)
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, W, H);
    const cols = Math.ceil(W / PNG_TILE);
    const visible = Math.floor(pngProgress * spiralOrder.length);
    for (let k = 0; k < visible; k++) {
      const idx = spiralOrder[k];
      const tx = idx % cols;
      const ty = Math.floor(idx / cols);
      ctx.drawImage(img, tx * PNG_TILE, ty * PNG_TILE, PNG_TILE, PNG_TILE,
        tx * PNG_TILE, ty * PNG_TILE, PNG_TILE, PNG_TILE);
    }
    // faol plitka atrofida yumshoq "cho'tka" nuri
    if (pngProgress < 1 && visible > 0) {
      const idx = spiralOrder[Math.min(visible, spiralOrder.length - 1)];
      const tx = (idx % cols) * PNG_TILE + PNG_TILE / 2;
      const ty = Math.floor(idx / cols) * PNG_TILE + PNG_TILE / 2;
      const gx = ctx.createRadialGradient(tx, ty, 4, tx, ty, PNG_TILE * 1.5);
      gx.addColorStop(0, 'rgba(251,191,36,0.45)');
      gx.addColorStop(1, 'rgba(251,191,36,0)');
      ctx.fillStyle = gx;
      ctx.fillRect(0, 0, W, H);
    }
  }, [pngProgress, phase, spiralOrder]);

  // ------------------------------------------------------------------ //
  // 5. Safe-freeze + tahrirni backendga yuborish va davom etish
  // ------------------------------------------------------------------ //
  const freeze = useCallback(() => {
    userPausedRef.current = true;
    setFrozen(true);
    setPlaying(false);
  }, []);

  const resume = useCallback(() => {
    userPausedRef.current = false;
    setFrozen(false);
    setEditOpen(false);
    setEditRequest('');
    setEditError(null);
    if (finished) { setRevealed(0); revealedRef.current = 0; setPngProgress(0); setBuildStage('foundation'); }
    setPlaying(true);
  }, [finished]);

  const step = useCallback((delta: number) => {
    if (phase === 'svg') {
      // Bosqichli qurilishda "qadam" â€” rang berish bosqichida element bo'yicha.
      const r = Math.min(Math.max(0, revealedRef.current + delta), total);
      revealedRef.current = r;
      setRevealed(r);
      if (delta > 0) setBuildStage((bs) => (bs === 'done' ? 'done' : 'color'));
      else setBuildStage((bs) => (bs === 'done' ? 'color' : bs));
    } else {
      setPngProgress((p) => Math.min(1, Math.max(0, p + delta / 100)));
    }
  }, [phase, total]);

  const applyEdit = useCallback(async () => {
    const req = editRequest.trim();
    if (!req || editing) return;
    setEditing(true);
    setEditError(null);
    let before = '';
    try {
      const frozenCtx = {
        revealed,
        total,
        elements: phase === 'svg'
          ? Array.from(containerRef.current?.querySelectorAll('[data-build]') || [])
              .slice(0, revealed)
              .map((el) => el.tagName.toLowerCase())
          : [],
      };
      if (phase === 'svg') {
        try { before = await workspaceFileText(path); } catch { /* keep empty */ }
      }
      const { run_id } = await drawingEdit(path, req, frozenCtx);
      // run tugashini kutamiz (poll) â€” mahalliy LLM sekin, 8 daqiqagacha kutamiz
      let runState;
      for (let i = 0; i < 160; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        try {
          runState = await agentRunStatus(run_id);
        } catch {
          continue;
        }
        if (runState.status === 'done' || runState.status === 'error') break;
      }
      if (runState?.status === 'error') {
        setEditError(runState.error || 'agent edit failed');
        setEditing(false);
        return;
      }
      // Fayl haqiqatan o'zgarganmi? (agent ba'zan faqat o'qib, yozmaydi)
      let after = before;
      if (phase === 'svg') {
        try { after = await workspaceFileText(path); } catch { /* keep */ }
      }
      if (phase === 'svg' && after === before) {
        setEditError('agent faylni o zgartirmadi â€” so rovni aniqroq yozib qayta urinib ko ring (masalan: "tom rangini yashil qil")');
        setEditing(false);
        return;
      }
      // Fayl yangilandi â€” qayta yuklab, proporsional nuqtadan davom etamiz
      loadWorkspace();
      setFrozen(false);
      setEditOpen(false);
      setEditRequest('');
      setEditing(false);
      setVersion((v) => v + 1);
      setPlaying(true);
      // Chat'da inline karta ham ko'rinishi uchun (Preview'da tahrirlanganda)
      onEdited?.(path);
    } catch (exc) {
      setEditError(exc instanceof Error ? exc.message : 'edit request failed');
      setEditing(false);
    }
  }, [editRequest, editing, revealed, total, phase, path, loadWorkspace, onEdited]);

  // ------------------------------------------------------------------ //
  // 6. Video generatsiya â€” animatsiyani WebM videoga yozib olish
  // ------------------------------------------------------------------ //

  const saveVideo = useCallback(() => {
    const mime = mediaRecRef.current?.mimeType || 'video/webm';
    const ext = mime.includes('mp4') ? 'mp4' : 'webm';
    const blob = new Blob(recChunksRef.current, { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `drawing_${Date.now()}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    setRecording(false);
    mediaRecRef.current = null;
  }, []);

  const stopRecord = useCallback(() => {
    const rec = mediaRecRef.current;
    if (rec && rec.state !== 'inactive') {
      try { rec.stop(); } catch { saveVideo(); }
    }
  }, [saveVideo]);

  const startRecord = useCallback(() => {
    if (recording) return;
    // SVG uchun mirror-canvas yaratamiz (DOM holatini rasterga chizamiz)
    let W = 512, H = 512;
    if (phase === 'svg') {
      const svg = containerRef.current?.querySelector('svg');
      if (svg) {
        const r = (svg as SVGSVGElement).getBoundingClientRect();
        if (r.width > 0 && r.height > 0) { W = Math.round(r.width); H = Math.round(r.height); }
      }
    }
    const scale = 2;
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(64, W * scale);
    canvas.height = Math.max(64, H * scale);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    recCanvasRef.current = canvas;

    // capture stream: SVG -> mirror canvas; PNG -> asl ko'rinishdagi canvas
    const src = phase === 'png' && canvasRef.current ? canvasRef.current : canvas;
    const stream = src.captureStream(30);
    const mime = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
      .find((c) => window.MediaRecorder && MediaRecorder.isTypeSupported(c));
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime, videoBitsPerSecond: 6_000_000 } : undefined);
    // Part M (A6): faqat BIRTA aktiv yozuv â€” avvalgi yozuvlar to'xtatiladi.
    stopOtherRecorders(rec);
    _activeRecorders.add(rec);
    recChunksRef.current = [];
    rec.ondataavailable = (e) => { if (e.data && e.data.size > 0) recChunksRef.current.push(e.data); };
    rec.onstop = () => { _activeRecorders.delete(rec); saveVideo(); };
    mediaRecRef.current = rec;
    rec.start(100);
    setRecording(true);
    recFrameRef.current = 0;
    // boshidan qurish (yozuv toza blankadan boshlanadi)
    setRevealed(0);
    setPngProgress(0);
    setBuildStage('foundation');
    setFrozen(false);
    setPlaying(true);
  }, [phase, recording, saveVideo]);

  // Yozuv paytida SVG holatini mirror-canvasga har bir kadrda chizamiz.
  // Token yordamida eski (kechikkan) kadr yangisini ustiga yozmasligi ta'minlanadi.
  useEffect(() => {
    if (!recording || phase !== 'svg' || !recCanvasRef.current) return;
    const svg = containerRef.current?.querySelector('svg');
    if (!svg) return;
    const token = ++recFrameRef.current;
    drawSvgToCanvas(svg as SVGSVGElement, recCanvasRef.current, recFrameRef, token);
  }, [revealed, buildStage, recording, phase]);

  // Qurilish tugagach yozuvni avtomatik to'xtatamiz
  useEffect(() => {
    if (!recording || !finished) return;
    const t = setTimeout(() => {
      const rec = mediaRecRef.current;
      if (rec && rec.state === 'recording') { try { rec.stop(); } catch { saveVideo(); } }
    }, 600);
    return () => clearTimeout(t);
  }, [recording, finished, saveVideo]);

  // Komponent yopilganda yozuvni tozalaymiz
  useEffect(() => {
    return () => {
      const rec = mediaRecRef.current;
      if (rec && rec.state !== 'inactive') { try { rec.stop(); } catch { /* ignore */ } }
      _activeRecorders.delete(rec!);
    };
  }, []);

  // ------------------------------------------------------------------ //
  // Render
  // ------------------------------------------------------------------ //
  const pct = phase === 'svg'
    ? Math.round(((BUILD_STAGE_ORDER.indexOf(buildStage) + (buildStage === 'color' ? revealed / Math.max(1, total) : 0)) / BUILD_STAGE_ORDER.length) * 100)
    : Math.round(pngProgress * 100);

  return (
    <div ref={rootRef} className="flex-1 min-h-0 flex">
      {phase === 'loading' ? (
        <div className="w-full h-full flex items-center justify-center text-zinc-600 font-ui text-sm">
          <span className="animate-pulse">loading drawingâ€¦</span>
        </div>
      ) : phase === 'error' ? (
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-zinc-600 font-ui text-sm">// {error || 'cannot preview this file'}</div>
        </div>
      ) : (
      <div className="flex-1 min-h-0 flex flex-col">
      <div className="flex-1 min-h-0 flex items-center justify-center p-4 bg-zinc-950 relative overflow-hidden">
        {phase === 'svg' && svgHtml && (
          <div
            ref={containerRef}
            className="live-build max-w-full max-h-full [&_svg]:max-w-full [&_svg]:max-h-full [&_svg]:w-auto [&_svg]:h-auto"
            dangerouslySetInnerHTML={{ __html: svgHtml }}
          />
        )}
        {phase === 'png' && (
          <canvas ref={canvasRef} width={512} height={512} className="max-w-full max-h-full rounded-md border border-zinc-800 shadow-2xl bg-white" />
        )}
        {/* build status */}
        <div className="absolute top-3 left-3 flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${playing ? 'bg-amber-400 animate-pulse' : frozen ? 'bg-sky-400' : finished ? 'bg-teal-400' : 'bg-zinc-600'}`} />
          <span className="text-[10px] font-mono text-zinc-500">
            {editing ? 'EDITINGâ€¦' : frozen ? 'SAFE FREEZE' : finished ? 'BUILD COMPLETE' : phase === 'svg' ? BUILD_STAGE_LABEL[buildStage] : 'BUILDING'}
          </span>
          {recording && (
            <span className="ml-1.5 text-[10px] font-mono text-rose-400 animate-pulse">â— REC</span>
          )}
        </div>
        <div className="absolute top-3 right-3 text-[10px] font-mono text-zinc-500">
          {phase === 'svg'
            ? `${BUILD_STAGE_LABEL[buildStage]} Â· ${pct}%${buildStage === 'color' ? ` Â· ${revealed}/${total} bo'yaldi` : ''}`
            : `${pct}%`}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-zinc-800 shrink-0">
        <div
          className={`h-full transition-[width] duration-200 ${finished ? 'bg-teal-400' : frozen ? 'bg-sky-400' : 'bg-amber-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Bosqich indikatorlari (Part M, B5) â€” haqiqiy qurilish jarayoni */}
      {phase === 'svg' && (
        <div className="flex items-center gap-1 px-3 py-1.5 border-b border-zinc-800/60 shrink-0 flex-wrap">
          {BUILD_STAGE_ORDER.map((s, i) => {
            const idx = BUILD_STAGE_ORDER.indexOf(buildStage);
            const active = i === idx;
            const doneStage = i < idx || buildStage === 'done';
            return (
              <span
                key={s}
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border transition-colors ${
                  active ? 'bg-amber-400/15 border-amber-500/50 text-amber-300'
                    : doneStage ? 'bg-teal-950/40 border-teal-800/40 text-teal-400/80'
                    : 'border-zinc-800 text-zinc-600'
                }`}
              >
                {doneStage ? 'âœ“' : i + 1} {BUILD_STAGE_LABEL[s]}
              </span>
            );
          })}
        </div>
      )}

      {/* Tekshiruv checklisti (Part M, B3) â€” hajm/shakl standart tekshiruvi */}
      {phase === 'svg' && buildStage === 'done' && verifyItems && (
        <div className="px-3 py-1.5 border-b border-zinc-800/60 shrink-0 flex flex-wrap gap-x-4 gap-y-0.5">
          {verifyItems.map((v, i) => (
            <span key={i} className={`text-[10px] font-mono ${v.ok ? 'text-teal-400' : 'text-rose-400'}`}>
              {v.ok ? 'âœ“' : 'âœ—'} {v.label}
            </span>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-t border-zinc-800 shrink-0 flex-wrap">
        {playing ? (
          <button onClick={freeze} title="Safe freeze â€” pauza" className="w-7 h-7 rounded-md bg-sky-400/20 border border-sky-500/40 text-sky-300 hover:bg-sky-400/30 flex items-center justify-center transition-colors">
            â¸
          </button>
        ) : (
          <button onClick={resume} title="Davom etish" className="w-7 h-7 rounded-md bg-amber-400 text-zinc-950 hover:bg-amber-300 flex items-center justify-center transition-colors">
            â–¶
          </button>
        )}
        <button onClick={() => { userPausedRef.current = false; setRevealed(0); revealedRef.current = 0; setPngProgress(0); setBuildStage('foundation'); setFrozen(false); setPlaying(true); }} title="Boshidan qurish" className="w-7 h-7 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 flex items-center justify-center transition-colors">
          â†º
        </button>
        <button onClick={() => step(-1)} title="Orqaga qadam" disabled={playing || (phase === 'svg' && revealed === 0)} className="w-7 h-7 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 flex items-center justify-center transition-colors disabled:opacity-30">
          â—€
        </button>
        <button onClick={() => step(1)} title="Oldinga qadam" disabled={playing || (phase === 'svg' && revealed >= total)} className="w-7 h-7 rounded-md text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 flex items-center justify-center transition-colors disabled:opacity-30">
          â–¶|
        </button>
        <button onClick={() => setSpeed((s) => (s >= 4 ? 0.5 : s * 2))} title="Tezlik" className="text-[10px] font-mono px-2 py-1 rounded text-zinc-400 hover:text-amber-300 hover:bg-zinc-800 transition-colors">
          {speed}Ã—
        </button>
        <button
          onClick={recording ? stopRecord : startRecord}
          title={recording ? "To'xtatish va videoni saqlash (WebM)" : 'Animatsiyani videoga yozib olish (WebM)'}
          className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors ${recording ? 'bg-rose-500 text-white animate-pulse' : 'text-zinc-400 hover:text-rose-300 hover:bg-zinc-800'}`}
        >
          {recording ? 'â¹' : 'ðŸŽ¬'}
        </button>
        <div className="flex-1" />
        {frozen && !editing && (
          <button onClick={() => setEditOpen((o) => !o)} className={`text-[10px] font-mono px-2 py-1 rounded border transition-colors ${editOpen ? 'bg-sky-400/20 border-sky-500/40 text-sky-300' : 'border-zinc-700 text-zinc-400 hover:text-sky-300 hover:border-sky-500/50'}`}>
            âœŽ o'zgartirish kiritish
          </button>
        )}
      </div>

      {/* Frozen edit panel */}
      {frozen && editOpen && (
        <div className="border-t border-sky-500/30 bg-sky-950/20 px-3 py-2.5 shrink-0">
          <div className="text-[10px] font-mono text-sky-300 mb-1.5 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />
            SAFE FREEZE â€” build paused. Faqat kerakli qism o'zgartiriladi, qolgani o'zgarishsiz qoladi.
          </div>
          <div className="flex gap-2">
            <textarea
              value={editRequest}
              onChange={(e) => setEditRequest(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); applyEdit(); } }}
              placeholder="Masalan: tomni yashil rangga bo'ya, lekin devorlarni o'zgartirma"
              rows={2}
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200 font-ui outline-none focus:border-sky-500 placeholder-zinc-600 resize-none"
            />
            <div className="flex flex-col gap-1.5 shrink-0">
              <button
                onClick={applyEdit}
                disabled={editing || !editRequest.trim()}
                className="px-3 py-1.5 rounded-md bg-sky-400 text-zinc-950 text-xs font-ui font-medium hover:bg-sky-300 disabled:opacity-40 transition-colors"
              >
                {editing ? 'tahrirlanmoqdaâ€¦' : 'qollash & davom etish'}
              </button>
              <button
                onClick={() => { setEditOpen(false); setEditRequest(''); setEditError(null); }}
                disabled={editing}
                className="px-3 py-1 rounded-md border border-zinc-700 text-zinc-400 text-xs font-ui hover:text-zinc-200 disabled:opacity-40 transition-colors"
              >
                bekor qilish
              </button>
            </div>
          </div>
          {editError && <div className="text-[11px] text-rose-400 font-ui mt-1.5">âœ— {editError}</div>}
        </div>
      )}
      </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------- //
// SVG -> data-build atributli, serialize qilingan hujjat
// ---------------------------------------------------------------------- //
// ---------------------------------------------------------------------- //
// SVG'ni video mirror-canvasga chizish (classlar inline style'ga aylantiriladi,
// chunki standalone SVG-rasmda sahifa CSS'lari ishlamaydi)
// ---------------------------------------------------------------------- //
function drawSvgToCanvas(
  svg: SVGSVGElement,
  canvas: HTMLCanvasElement,
  tokenRef?: React.MutableRefObject<number>,
  token = 0,
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.querySelectorAll<SVGElement>('[data-build]').forEach((el) => {
    // Part M (WS-B): hozirgi holat inline â€” bosqich engine style.opacity ni
    // boshqaradi (lb-visible emas). Yashirin element 0, ko'ringani 1.
    el.style.setProperty('opacity', el.style.opacity || '1');
    el.style.setProperty('transition', 'none');
    el.style.setProperty('animation', 'none');
    el.classList.remove('lb-pop');
  });
  const data = new XMLSerializer().serializeToString(clone);
  const img = new Image();
  img.onload = () => {
    // kechikkan eski kadr yangisini ustiga yozmasin
    if (tokenRef && tokenRef.current !== token) return;
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  };
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(data);
}

function buildSvgHtml(text: string): { html: string | null; count: number } {
  try {
    const parser = new DOMParser();
    const parsed = parser.parseFromString(text, 'image/svg+xml');
    const parserError = parsed.querySelector('parsererror');
    if (parserError) return { html: null, count: 0 };
    const svg = parsed.documentElement as unknown as SVGSVGElement;
    // script'larni olib tashlaymiz (xavfsizlik)
    svg.querySelectorAll('script,foreignObject').forEach((n) => n.remove());
    // XSS himoyasi: event-handler atributlari va javascript: href'larni olib tashlaymiz
    svg.querySelectorAll('*').forEach((n) => {
      for (const attr of Array.from(n.attributes)) {
        const name = attr.name.toLowerCase();
        if (name.startsWith('on')) {
          n.removeAttribute(attr.name);
        } else if ((name === 'href' || name === 'xlink:href' || name === 'src') &&
                   /^\s*javascript:/i.test(attr.value)) {
          n.removeAttribute(attr.name);
        }
      }
    });
    const shapes = Array.from(svg.querySelectorAll(SHAPE_SELECTOR))
      .filter((el) => !el.closest('defs,script,style,metadata,title,desc,clipPath,pattern,marker'));
    shapes.forEach((el, i) => el.setAttribute('data-build', String(i)));
    svg.setAttribute('data-live-build', '1');
    // Duplicate id'larni yagona qilamiz: bir sahifada bir nechta chizma bo'lsa
    // (chat karta + preview, yoki 2 ta karta) url(#tex) birinchisiga qarab
    // qolishi mumkin â€” har bir SVGeni o'ziga xos id bilan qayta nomlaymiz.
    let idSeq = 0;
    const idMap = new Map<string, string>();
    const stamp = Date.now().toString(36);
    svg.querySelectorAll<SVGElement>('[id]').forEach((el) => {
      const old = el.id;
      if (!old) return;
      const fresh = `lb${stamp}_${idSeq++}_${old}`;
      idMap.set(old, fresh);
      el.id = fresh;
    });
    if (idMap.size) {
      svg.querySelectorAll<SVGElement>('*').forEach((el) => {
        for (const attr of ['fill', 'stroke', 'filter', 'clip-path']) {
          const v = el.getAttribute(attr);
          if (!v || !v.includes('url(')) continue;
          el.setAttribute(attr, v.replace(/url\(#([^)]+)\)/g, (m, id) =>
            idMap.has(id) ? `url(#${idMap.get(id)})` : m));
        }
      });
    }
    const html = new XMLSerializer().serializeToString(svg);
    return { html, count: shapes.length };
  } catch {
    return { html: null, count: 0 };
  }
}


