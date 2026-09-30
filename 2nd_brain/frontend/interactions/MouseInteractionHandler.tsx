import { useCallback, useRef, useEffect } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';

/**
 * Advanced mouse interaction handler for the 2nd Brain graph.
 *
 * Controls:
 * - Left click: Select node
 * - Double click: Focus/zoom to node
 * - Right click: Context menu (focus, open, path, copy id)
 * - Middle click / Shift+click: Toggle node expansion (show/hide neighbors)
 * - Ctrl+click: Multi-select node
 * - Shift+drag: Box selection
 * - Scroll wheel: Zoom (already handled)
 * - Alt+drag: Rotate view (future)
 */

export interface InteractionState {
  selectedNodes: Set<string>;
  expandedNodes: Set<string>;
  hoveredNode: string | null;
  contextMenu: { nodeId: string; x: number; y: number } | null;
  boxSelection: { startX: number; startY: number; endX: number; endY: number } | null;
  isPanning: boolean;
  isDraggingNode: boolean;
  lastClickTime: number;
  lastClickNode: string | null;
}

export interface InteractionHandlers {
  onNodeClick: (node: BrainGraphNode, event: React.MouseEvent) => void;
  onNodeDoubleClick: (node: BrainGraphNode, event: React.MouseEvent) => void;
  onNodeRightClick: (node: BrainGraphNode, event: React.MouseEvent) => void;
  onNodeMiddleClick: (node: BrainGraphNode, event: React.MouseEvent) => void;
  onNodeExpand: (nodeId: string) => void;
  onNodeCollapse: (nodeId: string) => void;
  onMultiSelect: (nodeIds: string[]) => void;
  onClearSelection: () => void;
  onBoxSelect: (nodeIds: string[]) => void;
  onCopyNodeId: (id: string) => void;
  onHighlightPath: (nodeId: string) => void;
}

export function useMouseInteraction({
  nodes,
  nodeMap,
  links,
  posOf,
  expandedNodes,
  setExpandedNodes,
  setSelected,
  selected,
}: {
  nodes: BrainGraphNode[];
  nodeMap: Record<string, BrainGraphNode>;
  links: [string, string][];
  posOf: (n: BrainGraphNode) => { x: number; y: number };
  expandedNodes: Set<string>;
  setExpandedNodes: React.Dispatch<React.SetStateAction<Set<string>>>;
  setSelected: (node: BrainGraphNode | null) => void;
  selected: BrainGraphNode | null;
}) {
  const multiSelectRef = useRef<Set<string>>(new Set());
  const lastClickRef = useRef<{ time: number; nodeId: string | null }>({ time: 0, nodeId: null });

  // Toggle node expansion (show/hide neighbors in tree view)
  const toggleExpansion = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, [setExpandedNodes]);

  // Get neighbors of a node
  const getNeighbors = useCallback((nodeId: string): BrainGraphNode[] => {
    const neighbors = new Set<string>();
    links.forEach(([a, b]) => {
      if (a === nodeId) neighbors.add(b);
      if (b === nodeId) neighbors.add(a);
    });
    return Array.from(neighbors)
      .map((id) => nodeMap[id])
      .filter(Boolean);
  }, [links, nodeMap]);

  // Get all descendants in tree (BFS, respecting expanded state)
  const getTreeNodes = useCallback((rootId: string): BrainGraphNode[] => {
    const visited = new Set<string>();
    const result: BrainGraphNode[] = [];
    const queue = [rootId];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (visited.has(current)) continue;
      visited.add(current);

      const node = nodeMap[current];
      if (node) result.push(node);

      // Only expand if this node is in expandedNodes
      if (expandedNodes.has(current)) {
        links.forEach(([a, b]) => {
          if (a === current && !visited.has(b)) queue.push(b);
          if (b === current && !visited.has(a)) queue.push(a);
        });
      }
    }
    return result;
  }, [nodeMap, links, expandedNodes]);

  // Node click handler — supports multi-select with Ctrl
  const onNodeClick = useCallback((node: BrainGraphNode, event: React.MouseEvent) => {
    event.stopPropagation();

    const now = Date.now();
    const last = lastClickRef.current;

    // Detect double click manually (faster than onDoubleClick event)
    if (last.nodeId === node.id && now - last.lastClickTime < 350) {
      // Double click — focus
      lastClickRef.current = { time: 0, nodeId: null };
      return; // Handled by onNodeDoubleClick
    }

    lastClickRef.current = { time: now, nodeId: node.id };

    if (event.ctrlKey || event.metaKey) {
      // Ctrl+click: toggle multi-select
      const next = new Set(multiSelectRef.current);
      if (next.has(node.id)) {
        next.delete(node.id);
      } else {
        next.add(node.id);
      }
      multiSelectRef.current = next;

      if (next.size > 0) {
        // Select first of multi-select
        const firstNode = nodeMap[Array.from(next)[0]];
        if (firstNode) setSelected(firstNode);
      } else {
        setSelected(null);
      }
    } else if (event.shiftKey) {
      // Shift+click: toggle expansion
      toggleExpansion(node.id);
    } else {
      // Normal click: select single node
      multiSelectRef.current = new Set([node.id]);
      setSelected(node);
    }
  }, [nodeMap, setSelected, toggleExpansion]);

  // Double click handler
  const onNodeDoubleClick = useCallback((node: BrainGraphNode, event: React.MouseEvent) => {
    event.stopPropagation();
    // Toggle expansion on double click
    toggleExpansion(node.id);
  }, [toggleExpansion]);

  // Right click handler — context menu
  const onNodeRightClick = useCallback((node: BrainGraphNode, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    // Context menu is handled by the ContextMenu component
    // This just prevents the default browser context menu
  }, []);

  // Middle click handler — expand neighbors
  const onNodeMiddleClick = useCallback((node: BrainGraphNode, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    toggleExpansion(node.id);
  }, [toggleExpansion]);

  // Box selection
  const onBoxSelect = useCallback((startX: number, startY: number, endX: number, endY: number) => {
    const minX = Math.min(startX, endX);
    const maxX = Math.max(startX, endX);
    const minY = Math.min(startY, endY);
    const maxY = Math.max(startY, endY);

    const selectedIds = nodes
      .filter((n) => {
        const p = posOf(n);
        return p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY;
      })
      .map((n) => n.id);

    if (selectedIds.length > 0) {
      multiSelectRef.current = new Set(selectedIds);
      const firstNode = nodeMap[selectedIds[0]];
      if (firstNode) setSelected(firstNode);
    }
  }, [nodes, nodeMap, posOf, setSelected]);

  // Copy node ID to clipboard
  const onCopyNodeId = useCallback((id: string) => {
    navigator.clipboard.writeText(id).catch(() => {});
  }, []);

  return {
    onNodeClick,
    onNodeDoubleClick,
    onNodeRightClick,
    onNodeMiddleClick,
    onBoxSelect,
    onCopyNodeId,
    toggleExpansion,
    getNeighbors,
    getTreeNodes,
    multiSelectRef,
  };
}
