import React, { useState, useEffect, useCallback } from 'react';
import { useAgentConsoleStore } from '../../shared/store';

/**
 * PromptScroller — o'ng tomondagi tayoqchali scroll.
 *
 * Sessiyadagi har bir user prompt'ini ko'rsatadi:
 *   - Tayoqcha (bar) — har bir prompt uchun bitta, rang turiga qarab
 *   - Hover: to'liq prompt matnini tooltip ko'rinishida ko'rsatadi
 *   - Click: shu prompt'ga scroll qiladi (chat ichida)
 *   - Keyboard: Up/Down strelkalar bilan navigatsiya, Enter — scroll
 *   - Collapse/expand toggle — yig'ish/ochish tugmasi
 */

type PromptType = 'code' | 'draw' | 'web' | 'data' | 'file' | 'chat' | 'task';

interface PromptTypeConfig {
  color: string;
  hoverColor: string;
  bg: string;
  border: string;
  label: string;
  icon: string;
}

const PROMPT_TYPES: Record<PromptType, PromptTypeConfig> = {
  code: {
    color: 'bg-teal-500',
    hoverColor: 'hover:bg-teal-400',
    bg: 'bg-teal-950/90',
    border: 'border-teal-700',
    label: 'Kod',
    icon: '💻',
  },
  draw: {
    color: 'bg-purple-500',
    hoverColor: 'hover:bg-purple-400',
    bg: 'bg-purple-950/90',
    border: 'border-purple-700',
    label: 'Rasm',
    icon: '🎨',
  },
  web: {
    color: 'bg-sky-500',
    hoverColor: 'hover:bg-sky-400',
    bg: 'bg-sky-950/90',
    border: 'border-sky-700',
    label: 'Web',
    icon: '🌐',
  },
  data: {
    color: 'bg-amber-500',
    hoverColor: 'hover:bg-amber-400',
    bg: 'bg-amber-950/90',
    border: 'border-amber-700',
    label: "Ma'lumot",
    icon: '📊',
  },
  file: {
    color: 'bg-orange-500',
    hoverColor: 'hover:bg-orange-400',
    bg: 'bg-orange-950/90',
    border: 'border-orange-700',
    label: 'Fayl',
    icon: '📁',
  },
  task: {
    color: 'bg-rose-500',
    hoverColor: 'hover:bg-rose-400',
    bg: 'bg-rose-950/90',
    border: 'border-rose-700',
    label: 'Task',
    icon: '⚡',
  },
  chat: {
    color: 'bg-zinc-500',
    hoverColor: 'hover:bg-zinc-400',
    bg: 'bg-zinc-800/90',
    border: 'border-zinc-600',
    label: 'Suhbat',
    icon: '💬',
  },
};

function detectPromptType(text: string): PromptType {
  const lower = text.toLowerCase();

  if (text.startsWith('⚡') || lower.startsWith('run ') || lower.startsWith('execute ')) {
    return 'task';
  }

  if (
    lower.includes('dastur') || lower.includes('kod') || lower.includes('code') ||
    lower.includes('yoz') || lower.includes('create') || lower.includes('build') ||
    lower.includes('qur') || lower.includes('app') || lower.includes('ilova') ||
    lower.includes('react') || lower.includes('vue') || lower.includes('angular') ||
    lower.includes('flask') || lower.includes('fastapi') || lower.includes('django') ||
    lower.includes('function') || lower.includes('class') || lower.includes('import') ||
    lower.includes('npm') || lower.includes('pip') || lower.includes('install') ||
    lower.includes('fix') || lower.includes('tuzat') || lower.includes('refactor') ||
    lower.includes('debug') || lower.includes('test') || lower.includes('pytest')
  ) {
    return 'code';
  }

  if (
    lower.includes('rasm') || lower.includes('chiz') || lower.includes('draw') ||
    lower.includes('svg') || lower.includes('image') || lower.includes('picture') ||
    lower.includes('logo') || lower.includes('icon') || lower.includes('avatar') ||
    lower.includes('poster') || lower.includes('banner') || lower.includes('design') ||
    lower.includes('ui') || lower.includes('ux') || lower.includes('mockup')
  ) {
    return 'draw';
  }

  if (
    lower.includes('web') || lower.includes('internet') || lower.includes('browse') ||
    lower.includes('search') || lower.includes('qidir') || lower.includes('google') ||
    lower.includes('open') || lower.includes('och') || lower.includes('navigate') ||
    lower.includes('url') || lower.includes('http') || lower.includes('website') ||
    lower.includes('sayt') || lower.includes('sahifa') || lower.includes('page')
  ) {
    return 'web';
  }

  if (
    lower.includes('hisobla') || lower.includes('calculate') || lower.includes('analiz') ||
    lower.includes('data') || lower.includes('stat') || lower.includes('tahlil') ||
    lower.includes('chart') || lower.includes('graph') || lower.includes('plot') ||
    lower.includes('csv') || lower.includes('json') || lower.includes('excel') ||
    lower.includes('database') || lower.includes('baza') || lower.includes('sql')
  ) {
    return 'data';
  }

  if (
    lower.includes('fayl') || lower.includes('file') || lower.includes('directory') ||
    lower.includes('papka') || lower.includes('list') || lower.includes("o'qish") ||
    lower.includes('read') || lower.includes("ko'rish") || lower.includes('look') ||
    lower.includes('delete') || lower.includes("o'chir") || lower.includes('copy') ||
    lower.includes('move') || lower.includes('kochir')
  ) {
    return 'file';
  }

  return 'chat';
}

function getPromptTypeConfig(text: string): PromptTypeConfig {
  const type = detectPromptType(text);
  return PROMPT_TYPES[type];
}

export function PromptScroller() {
  const messages = useAgentConsoleStore((s) => s.messages);
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [collapsed, setCollapsed] = useState(false);

  const userPrompts = messages
    .map((msg, idx) => ({ msg, idx }))
    .filter(({ msg }) => msg.role === 'user' && msg.text && !msg.text.startsWith('↳'));

  const scrollToMessage = useCallback((targetIdx: number) => {
    const scrollContainer = document.querySelector('[data-chat-scroll]');
    if (!scrollContainer) return;

    const msgs = scrollContainer.querySelectorAll('[data-chat-message]');
    if (msgs[targetIdx]) {
      msgs[targetIdx].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Faqat prompt scroller focus bo'lganda ishlaydi
    const target = e.target as HTMLElement;
    if (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT') return;

    if (e.key === 'ArrowDown' || e.key === 'j') {
      e.preventDefault();
      setSelectedIndex((prev) => {
        if (prev === null || prev >= userPrompts.length - 1) return 0;
        return prev + 1;
      });
    } else if (e.key === 'ArrowUp' || e.key === 'k') {
      e.preventDefault();
      setSelectedIndex((prev) => {
        if (prev === null || prev <= 0) return userPrompts.length - 1;
        return prev - 1;
      });
    } else if (e.key === 'Enter' && selectedIndex !== null) {
      e.preventDefault();
      scrollToMessage(userPrompts[selectedIndex].idx);
    } else if (e.key === 'Escape') {
      setSelectedIndex(null);
    }
  }, [userPrompts, selectedIndex, scrollToMessage]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // selectedIndex o'zgarganda — avtomatik scroll
  useEffect(() => {
    if (selectedIndex !== null && collapsed) {
      setCollapsed(false);
    }
  }, [selectedIndex, collapsed]);

  if (userPrompts.length === 0) return null;

  const handleMouseEnter = (idx: number, e: React.MouseEvent) => {
    setHoveredIdx(idx);
    setTooltipPos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (hoveredIdx !== null) {
      setTooltipPos({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseLeave = () => {
    setHoveredIdx(null);
  };

  // Collapse holatida
  if (collapsed) {
    return (
      <div className="w-8 shrink-0 flex flex-col items-center py-2 bg-zinc-950/50 border-l border-zinc-800/50">
        <button
          onClick={() => setCollapsed(false)}
          className="w-5 h-5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 flex items-center justify-center transition-colors group"
          title={`Ochish (${userPrompts.length} prompt)`}
        >
          <span className="text-[10px] text-zinc-500 group-hover:text-zinc-300">◀</span>
        </button>
        <div className="mt-1 text-[9px] font-mono text-zinc-600">
          {userPrompts.length}
        </div>
      </div>
    );
  }

  return (
    <div className="w-8 shrink-0 flex flex-col items-center py-2 bg-zinc-950/50 border-l border-zinc-800/50 overflow-y-auto">
      {/* Toggle tugma */}
      <button
        onClick={() => setCollapsed(true)}
        className="w-5 h-5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 flex items-center justify-center transition-colors group mb-2 shrink-0"
        title="Yig'ish"
      >
        <span className="text-[10px] text-zinc-500 group-hover:text-zinc-300">▶</span>
      </button>

      {/* Prompt tayoqchalari */}
      {userPrompts.map(({ msg, idx }, i) => {
        const text = msg.text || '';
        const config = getPromptTypeConfig(text);
        const isHovered = hoveredIdx === i;
        const isSelected = selectedIndex === i;

        return (
          <div
            key={idx}
            className="relative group"
            onMouseEnter={(e) => handleMouseEnter(i, e)}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            onClick={() => {
              setSelectedIndex(i);
              scrollToMessage(idx);
            }}
          >
            {/* Tayoqcha (bar) — rang turiga qarab */}
            <button
              className={`w-1.5 h-6 rounded-full transition-all duration-150 cursor-pointer ${
                isSelected
                  ? `${config.color} scale-y-125 ring-2 ring-white/30`
                  : isHovered
                    ? `${config.color} scale-y-125`
                    : `${config.color}/60 ${config.hoverColor}`
              }`}
              title={`${config.icon} ${config.label}: ${text.slice(0, 50)}`}
            />

            {/* Tooltip — hover yoki selected'da */}
            {(isHovered || isSelected) && (
              <div
                className={`fixed z-50 max-w-xs px-2.5 py-1.5 rounded-md ${config.bg} border ${config.border} shadow-xl text-[11px] font-ui text-zinc-200 leading-relaxed pointer-events-none`}
                style={{
                  left: tooltipPos.x + 12,
                  top: tooltipPos.y - 8,
                  transform: 'translateY(-100%)',
                }}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-[9px] font-mono text-zinc-500">
                    #{i + 1}
                  </span>
                  <span className={`text-[9px] font-mono px-1 py-0.5 rounded ${config.color}/30`}>
                    {config.icon} {config.label}
                  </span>
                  {isSelected && (
                    <span className="text-[8px] font-mono text-zinc-400 ml-1">
                      ↵ Enter
                    </span>
                  )}
                </div>
                <div className="break-words">{text}</div>
              </div>
            )}
          </div>
        );
      })}

      {/* Keyboard hint — pastda */}
      {userPrompts.length > 0 && (
        <div className="mt-auto pt-2 shrink-0">
          <div className="text-[8px] font-mono text-zinc-700 text-center leading-tight">
            ↑↓
          </div>
        </div>
      )}
    </div>
  );
}
