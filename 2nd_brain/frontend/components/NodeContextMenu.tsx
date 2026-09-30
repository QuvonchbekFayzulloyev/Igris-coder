import React, { useEffect, useRef } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

interface ContextMenuItem {
  label: string;
  icon: string;
  action: () => void;
  danger?: boolean;
  disabled?: boolean;
}

interface NodeContextMenuProps {
  node: BrainGraphNode;
  position: { x: number; y: number };
  onClose: () => void;
  onFocus: (node: BrainGraphNode) => void;
  onOpen: (node: BrainGraphNode) => void;
  onResetPos?: (id: string) => void;
  onHighlightPath?: (node: BrainGraphNode) => void;
  onCopyId?: (id: string) => void;
  hasCustomPos?: boolean;
}

export function NodeContextMenu({
  node,
  position,
  onClose,
  onFocus,
  onOpen,
  onResetPos,
  onHighlightPath,
  onCopyId,
  hasCustomPos,
}: NodeContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  const items: ContextMenuItem[] = [
    {
      label: 'Focus',
      icon: '⛶',
      action: () => { onFocus(node); onClose(); },
    },
    {
      label: 'Open detail',
      icon: '📖',
      action: () => { onOpen(node); onClose(); },
    },
    {
      label: 'Highlight path',
      icon: '🔗',
      action: () => { onHighlightPath?.(node); onClose(); },
    },
    {
      label: 'Copy ID',
      icon: '📋',
      action: () => { onCopyId?.(node.id); onClose(); },
    },
    ...(hasCustomPos ? [{
      label: 'Reset position',
      icon: '⟲',
      action: () => { onResetPos?.(node.id); onClose(); },
    }] : []),
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl py-1 min-w-[160px] backdrop-blur-sm"
      style={{ left: position.x, top: position.y }}
    >
      {/* Node header */}
      <div className="px-3 py-1.5 border-b border-zinc-800">
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${KIND_COLOR_TAILWIND[node.kind as keyof typeof KIND_COLOR_TAILWIND]?.dot || 'bg-zinc-500'}`} />
          <span className="text-[11px] font-ui font-medium text-zinc-200 truncate max-w-[140px]">
            {node.label}
          </span>
        </div>
        <div className="text-[9px] font-mono text-zinc-600 mt-0.5">{node.kind}</div>
      </div>

      {/* Menu items */}
      {items.map((item, idx) => (
        <button
          key={idx}
          onClick={item.action}
          disabled={item.disabled}
          className={`w-full text-left px-3 py-1.5 text-[11px] font-ui flex items-center gap-2 transition-colors ${
            item.disabled
              ? 'text-zinc-700 cursor-not-allowed'
              : item.danger
              ? 'text-red-400 hover:bg-red-950/50 hover:text-red-300'
              : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
          }`}
        >
          <span className="text-[12px] w-4 text-center">{item.icon}</span>
          {item.label}
        </button>
      ))}
    </div>
  );
}
