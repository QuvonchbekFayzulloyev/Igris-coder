import React from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { TreeNode as TreeNodeType } from '../../shared/constants';

interface TreeNodeProps {
  node: TreeNodeType;
  path: string;
  depth: number;
}

export function TreeNodeComponent({ node, path, depth }: TreeNodeProps) {
  const { expanded, toggleExpanded, selectedFile, setSelectedFile, setMainView } =
    useAgentConsoleStore();

  const isFolder = node.type === 'folder';
  const isOpen = expanded.has(path);
  const isSelected = !isFolder && path === selectedFile;
  const dot =
    node.status === 'modified' ? 'bg-amber-400' : node.status === 'new' ? 'bg-teal-400' : null;

  const handleClick = () => {
    if (isFolder) {
      toggleExpanded(path);
    } else {
      setSelectedFile(path);
      setMainView('preview');
    }
  };

  return (
    <div>
      <button
        onClick={handleClick}
        className={`w-full flex items-center gap-1.5 py-1 pr-2 rounded text-xs hover:bg-zinc-800 text-left ${
          isSelected
            ? 'bg-zinc-800 text-zinc-100'
            : node.special
              ? 'text-amber-300'
              : 'text-zinc-300'
        }`}
        style={{ paddingLeft: depth * 14 + 8 }}
      >
        {isFolder ? (
          isOpen ? (
            <span className="w-3.5 text-zinc-500 shrink-0">▾</span>
          ) : (
            <span className="w-3.5 text-zinc-500 shrink-0">▸</span>
          )
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        {isFolder ? (
          <span className="w-3.5 shrink-0 text-zinc-500">
            {isOpen ? '📂' : '📁'}
          </span>
        ) : (
          <span className="w-3.5 shrink-0 text-zinc-600">📄</span>
        )}
        <span className="truncate flex-1 font-mono">{node.name}</span>
        {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />}
      </button>
      {isFolder &&
        isOpen &&
        node.children?.map((child) => (
          <TreeNodeComponent
            key={`${path}/${child.name}`}
            node={child}
            path={`${path}/${child.name}`}
            depth={depth + 1}
          />
        ))}
    </div>
  );
}
