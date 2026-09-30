import React from 'react';

interface EmptyGraphStateProps {
  isOffline: boolean;
  onRefresh: () => void;
}

export function EmptyGraphState({ isOffline, onRefresh }: EmptyGraphStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8">
      {/* Icon */}
      <div className="mb-4 text-4xl opacity-30">
        {isOffline ? '🔌' : '🧠'}
      </div>

      {/* Title */}
      <h3 className="text-sm font-ui font-medium text-zinc-400 mb-1.5">
        {isOffline ? 'Backend offline' : 'No data yet'}
      </h3>

      {/* Description */}
      <p className="text-[11px] font-ui text-zinc-600 max-w-[280px] leading-relaxed mb-4">
        {isOffline ? (
          'Igris brain serveriga ulanib bo\'lmadi. Serverni ishga tushiring.'
        ) : (
          'Knowledge graph bo\'sh. Suhbat boshlang yoki xotira fayllarini qo\'shing.'
        )}
      </p>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onRefresh}
          className="text-[11px] font-mono px-3 py-1.5 rounded border border-zinc-700 text-zinc-500 hover:text-zinc-200 hover:border-zinc-500 transition-colors"
        >
          ↻ Refresh
        </button>
        {!isOffline && (
          <div className="text-[10px] font-mono text-zinc-700">
            or start a chat →
          </div>
        )}
      </div>

      {/* Tips */}
      {!isOffline && (
        <div className="mt-6 text-[9px] font-mono text-zinc-700 max-w-[300px] leading-relaxed">
          <div className="mb-1 text-zinc-600">Tips:</div>
          <div>• Chat boshlang — avtomatik graph node paydo bo'ladi</div>
          <div>• Igris_Memory/ papkasiga .md fayllar qo'shing</div>
          <div>• [[wikilink]] formatida fayllarni bog'lang</div>
        </div>
      )}
    </div>
  );
}
