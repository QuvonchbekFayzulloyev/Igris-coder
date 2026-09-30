import { TreeNode } from './constants';

/** Flat backend listing -> nested TreeNode tree used by the sidebar. */
export function buildTree(entries: { path: string; type: 'dir' | 'file' }[]): TreeNode[] {
  const root: TreeNode = { type: 'folder', name: '', children: [] };
  for (const e of entries || []) {
    const parts = e.path.split('/').filter(Boolean);
    let node = root;
    parts.forEach((part, i) => {
      if (!node.children) node.children = [];
      const existing = node.children.find((c) => c.name === part);
      const isLast = i === parts.length - 1;
      if (!existing) {
        const child: TreeNode = {
          type: isLast ? (e.type === 'dir' ? 'folder' : 'file') : 'folder',
          name: part,
        };
        node.children.push(child);
        node = child;
      } else {
        node = existing;
      }
    });
  }
  return root.children || [];
}
