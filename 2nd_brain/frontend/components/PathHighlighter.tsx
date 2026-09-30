import { useMemo } from 'react';
import { BrainGraphNode } from '../../../Igris_Interface/web/backend';

interface PathHighlighterProps {
  nodes: BrainGraphNode[];
  links: [string, string][];
  nodeMap: Record<string, BrainGraphNode>;
  sourceId: string | null;
  onClear: () => void;
}

interface PathNode {
  id: string;
  depth: number;
}

/**
 * Finds shortest path between two nodes using BFS.
 * Returns null if no path exists.
 */
function findShortestPath(
  links: [string, string][],
  nodeMap: Record<string, BrainGraphNode>,
  sourceId: string,
): Map<string, PathNode> | null {
  const adj = new Map<string, string[]>();
  links.forEach(([a, b]) => {
    if (!adj.has(a)) adj.set(a, []);
    if (!adj.has(b)) adj.set(b, []);
    adj.get(a)!.push(b);
    adj.get(b)!.push(a);
  });

  // BFS from source
  const visited = new Map<string, PathNode>();
  visited.set(sourceId, { id: sourceId, depth: 0 });
  const queue = [sourceId];

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentDepth = visited.get(current)!.depth;

    for (const neighbor of (adj.get(current) || [])) {
      if (!visited.has(neighbor)) {
        visited.set(neighbor, { id: neighbor, depth: currentDepth + 1 });
        queue.push(neighbor);
      }
    }
  }

  return visited;
}

export function PathHighlighter({ nodes, links, nodeMap, sourceId, onClear }: PathHighlighterProps) {
  // Compute BFS distances from source
  const distances = useMemo(() => {
    if (!sourceId || !nodeMap[sourceId]) return null;
    return findShortestPath(links, nodeMap, sourceId);
  }, [sourceId, links, nodeMap]);

  if (!sourceId || !distances) return null;

  const maxDepth = Math.min(4, Math.max(...Array.from(distances.values()).map((d) => d.depth)));

  // Color nodes by distance from source
  const getNodeOpacity = (nodeId: string): number => {
    const dist = distances.get(nodeId);
    if (!dist) return 0.1;
    if (dist.depth === 0) return 1;
    return Math.max(0.15, 1 - dist.depth * 0.2);
  };

  const getNodeRadius = (nodeId: string): number => {
    const dist = distances.get(nodeId);
    if (!dist) return 2;
    if (dist.depth === 0) return 6;
    return Math.max(2, 5 - dist.depth);
  };

  const getLinkOpacity = (a: string, b: string): number => {
    const distA = distances.get(a);
    const distB = distances.get(b);
    if (!distA || !distB) return 0.05;
    // Link is on shortest path if both nodes are within 1 hop of each other in distance
    if (Math.abs(distA.depth - distB.depth) <= 1 && Math.max(distA.depth, distB.depth) <= maxDepth) {
      return Math.max(0.2, 1 - Math.max(distA.depth, distB.depth) * 0.2);
    }
    return 0.05;
  };

  return {
    getNodeOpacity,
    getNodeRadius,
    getLinkOpacity,
    sourceDepth: 0,
    maxDepth,
    nodeCount: Array.from(distances.values()).filter((d) => d.depth <= maxDepth).length,
  };
}
