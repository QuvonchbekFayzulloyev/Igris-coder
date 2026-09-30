const BRAIN_LOG_KEY = 'igris:brain:chatlogs';
/** Bitta suhbat uchun saqlanadigan loglar soni chegarasi. */
const BRAIN_LOG_CAP = 50;

interface BrainLogEntry {
  text: string;
  /** Epoch soniya — qachon yozilgan (kelajakda vaqt ko'rsatish uchun). */
  ts: number;
}

function readBrainLogs(): Record<string, BrainLogEntry[]> {
  try {
    const raw = localStorage.getItem(BRAIN_LOG_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, BrainLogEntry[]>)
      : {};
  } catch {
    return {};
  }
}

export function loadBrainLogs(sessionId: string): BrainLogEntry[] {
  const list = readBrainLogs()[sessionId];
  return Array.isArray(list) ? list : [];
}

export function appendBrainLog(sessionId: string, text: string): void {
  if (!sessionId) return;
  const map = readBrainLogs();
  const list = Array.isArray(map[sessionId]) ? map[sessionId] : [];
  if (list.length && list[list.length - 1].text === text) return;
  list.push({ text, ts: Math.floor(Date.now() / 1000) });
  map[sessionId] = list.slice(-BRAIN_LOG_CAP);
  try {
    localStorage.setItem(BRAIN_LOG_KEY, JSON.stringify(map));
  } catch {
    /* localStorage to'pa / yaroqsiz — log faqat xotirada qoladi */
  }
}

export function removeBrainLogs(sessionId: string): void {
  try {
    const map = readBrainLogs();
    if (map[sessionId]) {
      delete map[sessionId];
      localStorage.setItem(BRAIN_LOG_KEY, JSON.stringify(map));
    }
  } catch {
    /* ignore */
  }
}
