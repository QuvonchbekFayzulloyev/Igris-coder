import React, { useMemo } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';
import { KIND_COLOR_TAILWIND } from '../colors';

interface NodeDetailPanelProps {
  node: BrainGraphNode;
  neighbors: BrainGraphNode[];
  nodeMap: Record<string, BrainGraphNode>;
  onClose: () => void;
  onSelect: (node: BrainGraphNode) => void;
  onFocus: (node: BrainGraphNode) => void;
  onHighlightPath?: (nodeId: string) => void;
  onCopyId?: (id: string) => void;
  hasCustomPos?: boolean;
  onResetPos?: (id: string) => void;
}

/** Simple markdown-to-JSX renderer for node details. */
function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let codeLang = '';

  lines.forEach((line, idx) => {
    // Code blocks
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={`code-${idx}`} className="bg-zinc-800/50 border border-zinc-700 rounded p-2 my-1.5 overflow-x-auto">
            <code className="text-[10px] font-mono text-zinc-300">{codeLines.join('\n')}</code>
          </pre>
        );
        codeLines = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
        codeLang = line.slice(3).trim();
      }
      return;
    }
    if (inCodeBlock) {
      codeLines.push(line);
      return;
    }

    // Headers
    if (line.startsWith('### ')) {
      elements.push(<h4 key={idx} className="text-[11px] font-ui font-semibold text-zinc-300 mt-2 mb-1">{line.slice(4)}</h4>);
    } else if (line.startsWith('## ')) {
      elements.push(<h3 key={idx} className="text-[12px] font-ui font-semibold text-zinc-200 mt-2 mb-1">{line.slice(3)}</h3>);
    } else if (line.startsWith('# ')) {
      elements.push(<h2 key={idx} className="text-[13px] font-ui font-bold text-zinc-100 mt-2 mb-1">{line.slice(2)}</h2>);
    }
    // Lists
    else if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(
        <div key={idx} className="flex gap-1.5 text-[10px] font-ui text-zinc-400 ml-2">
          <span className="text-zinc-600">•</span>
          <span>{renderInline(line.slice(2))}</span>
        </div>
      );
    }
    // Numbered lists
    else if (/^\d+\.\s/.test(line)) {
      const match = line.match(/^(\d+)\.\s(.+)/);
      if (match) {
        elements.push(
          <div key={idx} className="flex gap-1.5 text-[10px] font-ui text-zinc-400 ml-2">
            <span className="text-zinc-600 w-3 text-right shrink-0">{match[1]}.</span>
            <span>{renderInline(match[2])}</span>
          </div>
        );
      }
    }
    // Horizontal rule
    else if (line.trim() === '---' || line.trim() === '***') {
      elements.push(<hr key={idx} className="border-zinc-800 my-1.5" />);
    }
    // Empty line
    else if (line.trim() === '') {
      elements.push(<div key={idx} className="h-1" />);
    }
    // Paragraph
    else {
      elements.push(
        <p key={idx} className="text-[10px] font-ui text-zinc-400 leading-relaxed">
          {renderInline(line)}
        </p>
      );
    }
  });

  return elements;
}

/** Render inline markdown (bold, italic, code, links). */
function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*(.+?)\*\*|`(.+?)`|\[\[([^\]|]+)(?:\|[^\]]*)?\]\]|_(.+?)_)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    // Text before match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      // Bold
      parts.push(<strong key={match.index} className="font-semibold text-zinc-300">{match[2]}</strong>);
    } else if (match[3]) {
      // Inline code
      parts.push(
        <code key={match.index} className="bg-zinc-800/60 px-1 py-0.5 rounded text-[9px] font-mono text-amber-300">
          {match[3]}
        </code>
      );
    } else if (match[4]) {
      // Wiki link
      parts.push(
        <span key={match.index} className="text-sky-400 hover:text-sky-300 cursor-pointer">
          [[{match[4]}]]
        </span>
      );
    } else if (match[5]) {
      // Italic
      parts.push(<em key={match.index} className="italic text-zinc-400">{match[5]}</em>);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

export function NodeDetailPanel({
  node,
  neighbors,
  nodeMap,
  onClose,
  onSelect,
  onFocus,
  onHighlightPath,
  onCopyId,
  hasCustomPos,
  onResetPos,
}: NodeDetailPanelProps) {
  const kindColor = KIND_COLOR_TAILWIND[node.kind as keyof typeof KIND_COLOR_TAILWIND];

  // Group neighbors by kind
  const groupedNeighbors = useMemo(() => {
    const groups: Record<string, BrainGraphNode[]> = {};
    neighbors.forEach((n) => {
      if (!groups[n.kind]) groups[n.kind] = [];
      groups[n.kind].push(n);
    });
    return Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
  }, [neighbors]);

  return (
    <div className="w-72 border-l border-zinc-800 bg-zinc-900/50 backdrop-blur-sm flex flex-col h-full overflow-hidden shrink-0">
      {/* Header */}
      <div className="p-3 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${kindColor?.dot || 'bg-zinc-500'}`} />
            <span className={`text-[11px] font-ui font-medium ${kindColor?.text || 'text-zinc-400'}`}>
              {node.kind}
            </span>
          </div>
          <button onClick={onClose} className="text-zinc-600 hover:text-zinc-300 text-[11px] transition-colors">
            ✕
          </button>
        </div>
        <div className="text-sm font-ui font-medium text-zinc-100 leading-snug">
          {node.label}
        </div>
        {node.kind === 'session' && node.updated_at && (
          <div className="text-[9px] font-mono text-teal-400/70 mt-1">
            🕒 {relTime(node.updated_at)}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="px-3 py-2 border-b border-zinc-800 flex flex-wrap gap-1">
        <button
          onClick={() => onFocus(node)}
          className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
          title="Focus this node"
        >
          ⛶ focus
        </button>
        {onHighlightPath && (
          <button
            onClick={() => onHighlightPath(node.id)}
            className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
            title="Highlight connections"
          >
            🔗 path
          </button>
        )}
        {onCopyId && (
          <button
            onClick={() => onCopyId(node.id)}
            className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
            title="Copy node ID"
          >
            📋 id
          </button>
        )}
        {hasCustomPos && onResetPos && (
          <button
            onClick={() => onResetPos(node.id)}
            className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-zinc-700 text-zinc-500 hover:text-amber-300 hover:border-amber-500/50 transition-colors"
            title="Reset position"
          >
            ⟲ pos
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {node.detail && (
          <div className="mb-3">
            {renderMarkdown(node.detail)}
          </div>
        )}

        {!node.detail && (
          <div className="text-[10px] font-ui text-zinc-600 italic mb-3">
            No description available
          </div>
        )}

        {/* Linked notes */}
        <div className="mb-2">
          <div className="text-[10px] font-ui font-medium text-zinc-500 mb-1.5">
            Connections ({neighbors.length})
          </div>
          {groupedNeighbors.map(([kind, nodes]) => (
            <div key={kind} className="mb-2">
              <div className="flex items-center gap-1 mb-1">
                <span className={`w-1.5 h-1.5 rounded-full ${KIND_COLOR_TAILWIND[kind as keyof typeof KIND_COLOR_TAILWIND]?.dot || 'bg-zinc-600'}`} />
                <span className="text-[9px] font-mono text-zinc-600 uppercase">{kind}</span>
                <span className="text-[9px] font-mono text-zinc-700">({nodes.length})</span>
              </div>
              <div className="space-y-0.5 ml-1">
                {nodes.slice(0, 5).map((n) => (
                  <button
                    key={n.id}
                    onClick={() => onSelect(n)}
                    className="w-full text-left text-[10px] font-ui text-zinc-500 hover:text-zinc-200 px-1.5 py-0.5 rounded hover:bg-zinc-800/50 flex items-center gap-1.5 transition-colors"
                  >
                    <span className="truncate">{n.label}</span>
                  </button>
                ))}
                {nodes.length > 5 && (
                  <div className="text-[9px] font-mono text-zinc-700 pl-1.5">
                    + {nodes.length - 5} more
                  </div>
                )}
              </div>
            </div>
          ))}
          {neighbors.length === 0 && (
            <div className="text-[10px] font-ui text-zinc-600 italic">No connections</div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-2 border-t border-zinc-800">
        <div className="text-[8px] font-mono text-zinc-700 text-center">
          {node.id.length > 20 ? node.id.slice(0, 18) + '...' : node.id}
        </div>
      </div>
    </div>
  );
}

function relTime(epochSec?: number): string {
  if (!epochSec || !(epochSec > 0)) return '';
  const s = Math.max(0, Math.floor(Date.now() / 1000 - epochSec));
  if (s < 45) return 'hozir';
  if (s < 90) return '1 daqiqa oldin';
  if (s < 3600) return `${Math.floor(s / 60)} daqiqa oldin`;
  if (s < 86400) return `${Math.floor(s / 3600)} soat oldin`;
  return `${Math.floor(s / 86400)} kun oldin`;
}
