/** Epoch soniya -> nisbiy vaqt ('just now', '5m', '3h', 'Yesterday', '2d'). */
export function relativeTime(ts: number): string {
  if (!ts) return '';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 172800) return 'Yesterday';
  return `${Math.floor(s / 86400)}d`;
}

/** Real chat suhbat id — har bir New Chat'da yangilanadi, backend'ga yuboriladi. */
export function newChatId(): string {
  return `conv-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/** Faol SSE chat stream'ining AbortController'i — yangi xabar eski oqimni to'xtatadi. */
export let activeStreamCtrl: AbortController | null = null;

/** ES modul importini qayta tayinlab bo'lmaydi — stream almashtirishda
 *  shu setter orqali yangilanadi (store.ts'dan chaqiriladi). */
export function setActiveStreamCtrl(ctrl: AbortController | null): void {
  activeStreamCtrl = ctrl;
}
