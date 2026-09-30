import React from 'react';
import { useAgentConsoleStore } from '../../shared/store';
import { TreeNode as TreeNodeType } from '../../shared/constants';
import { useMenu } from './ContextMenu';

interface TreeNodeProps {
  node: TreeNodeType;
  path: string;
  depth: number;
}

export function TreeNodeComponent({ node, path, depth }: TreeNodeProps) {
  const { expanded, toggleExpanded, selectedFile, setSelectedFile, setMainView } =
    useAgentConsoleStore();
  const menu = useMenu();

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

  // Workspace fayl/papka o'ng-tugma menyusi
  const onContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const openInPreview = () => {
      setSelectedFile(path);
      setMainView('preview');
    };
    menu.open(e.clientX, e.clientY, [
      ...(isFolder
        ? [
            { id: 'tog', label: isOpen ? 'Yopish' : 'Ochish', icon: isOpen ? '▾' : '▸', action: () => toggleExpanded(path) },
            { id: 'exp', label: 'Hammasini ochish', icon: '⧉', action: () => {
              // Bu papka va barcha bolalarini ochamiz (depth-first)
              const add = (p: string, n: TreeNodeType) => {
                useAgentConsoleStore.getState().toggleExpanded(p);
              };
              add(path, node);
              node.children?.forEach((c) => {
                if (c.type === 'folder') useAgentConsoleStore.getState().toggleExpanded(`${path}/${c.name}`);
              });
            } },
          ]
        : [
            { id: 'open', label: 'Preview’da ochish', icon: '👁', action: openInPreview },
            { id: 'cp', label: 'Yo‘lni nusxalash', icon: '⧉', action: () => {
              try { navigator.clipboard.writeText(path); } catch { /* ignore */ }
            } },
            { id: 'dn', label: 'Brauzerda ochish', icon: '↗', action: () => {
              import('../backend').then(({ workspaceFileUrl }) => {
                window.open(workspaceFileUrl(path), '_blank');
              });
            } },
          ]),
      { separator: true },
      { id: 'rf', label: 'Workspace‘ni yangilash', icon: '↻', action: () => useAgentConsoleStore.getState().loadWorkspace() },
    ]);
  };

  return (
    <div>
      <button
        onClick={handleClick}
        onContextMenu={onContextMenu}
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
