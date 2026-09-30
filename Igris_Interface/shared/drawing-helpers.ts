// Chizma/UI spec karta sifatida ko'rsatiladigan fayllar: SVG/PNG rasm + uibuild spec
export const DRAWING_EXT = /\.(svg|png|jpe?g|gif|webp|bmp|ico|uibuild\.json)$/i;

export function drawingPathsFromRun(r: {
  tool_calls?: { tool?: string; args?: unknown; result?: { ok?: boolean } | null; output_preview?: string }[];
} | null | undefined): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const add = (path: string) => {
    if (typeof path === 'string' && DRAWING_EXT.test(path) && !seen.has(path)) {
      seen.add(path);
      out.push(path);
    }
  };
  for (const tc of r?.tool_calls || []) {
    if (!tc.result || !tc.result.ok) continue;
    const args = tc.args;
    const path =
      args && typeof args === 'object' && !Array.isArray(args)
        ? (args as Record<string, unknown>).path
        : undefined;
    if (typeof path === 'string') add(path);
    if (args && typeof args === 'object' && !Array.isArray(args)) {
      const a = args as Record<string, unknown>;
      const inner = a.args as Record<string, unknown> | undefined;
      if (inner && typeof inner.output === 'string') add(inner.output);
      if (inner && typeof inner.path === 'string') add(inner.path);
    }
    const preview = tc.output_preview || '';
    const m = preview.match(/(?:image\s+saved\s+to|saved)\s+([^\s\n]+(?:\.(?:svg|png|jpe?g|gif|webp|bmp|ico|uibuild\.json)))/i);
    if (m) add(m[1].replace(/['"`.,;]$/g, ''));
  }
  return out;
}

export function drawingMessages(r: {
  tool_calls?: { tool?: string; args?: unknown; result?: { ok?: boolean } | null }[];
} | null | undefined): { kind: 'drawing'; path: string; caption: string }[] {
  return drawingPathsFromRun(r).map((path) => ({
    kind: 'drawing' as const,
    path,
    caption: 'agent bu chizmani yaratdi — ▶ qurilishni tomosha qilish, ⏸ pauza qilib o\'zgartirish kiritish mumkin',
  }));
}
