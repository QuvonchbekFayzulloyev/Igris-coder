/**
 * 2nd Brain — Focus System
 * 
 * Focus: node'ni markazga olib kelish + atrofidagi qo'shnilarni ko'rsatish
 * Depth: nechta qatlam ko'rsatiladi (1, 2, 3...)
 * Semantic Zoom: zoom darajasiga qarab nima ko'rinadi
 */

import { Entity, Relation, EntityType, GraphNode, GraphEdge, FocusState, SemanticZoomConfig, ZoomLevel } from './db/schema';
import { db } from './db/store';

// ─────────────────────────────────────────────
// Focus Engine
// ─────────────────────────────────────────────

export class FocusEngine {
  private focusState: FocusState = { nodeId: null, depth: 1, neighbors: [], path: [] };
  private zoomConfig: SemanticZoomConfig = {
    level: 'overview',
    scale: 1,
    showLabels: true,
    showStates: false,
    showEvents: false,
    showProperties: false,
    showRelations: true,
    nodeSize: 'medium',
  };

  get focus(): FocusState { return this.focusState; }
  get zoom(): SemanticZoomConfig { return this.zoomConfig; }

  /**
   * Focus on a node — markazga olib kelish + qo'shnilarni ko'rsatish
   */
  focusOn(entityId: string, depth: number = 1): { nodes: GraphNode[]; edges: GraphEdge[] } {
    const entity = db.getEntity(entityId);
    if (!entity) return { nodes: [], edges: [] };

    // Get neighborhood from DB
    const { entities, relations } = db.getNeighborhood(entityId, depth);

    // Build graph nodes
    const nodes: GraphNode[] = entities.map((e, i) => {
      const isCenter = e.id === entityId;
      const distance = isCenter ? 0 : this.getDistance(entityId, e.id, relations);
      return {
        id: e.id,
        entity: e,
        x: 0, y: 0, // Will be computed by layout
        depth: distance,
        visible: true,
        expanded: false,
        highlighted: isCenter,
        focused: isCenter,
      };
    });

    // Build graph edges
    const edges: GraphEdge[] = relations.map((r) => {
      const sourceNode = nodes.find((n) => n.id === r.source);
      const targetNode = nodes.find((n) => n.id === r.target);
      if (!sourceNode || !targetNode) return null;
      return {
        id: r.id,
        relation: r,
        sourceNode,
        targetNode,
        visible: true,
        highlighted: r.source === entityId || r.target === entityId,
        label: r.type.replace(/_/g, ' '),
      };
    }).filter(Boolean) as GraphEdge[];

    // Update focus state
    this.focusState = {
      nodeId: entityId,
      depth,
      neighbors: entities.map((e) => e.id),
      path: [...this.focusState.path, entityId],
    };

    // Layout: radial from center
    this.layoutRadial(nodes, entityId);

    return { nodes, edges };
  }

  /**
   * Increase focus depth — ko'proq qatlam ko'rsatish
   */
  zoomIn(): void {
    if (this.focusState.nodeId) {
      this.focusState.depth = Math.min(5, this.focusState.depth + 1);
    }
    this.zoomConfig.scale = Math.min(5, this.zoomConfig.scale * 1.2);
    this.updateZoomLevel();
  }

  /**
   * Decrease focus depth — kamroq qatlam ko'rsatish
   */
  zoomOut(): void {
    if (this.focusState.nodeId) {
      this.focusState.depth = Math.max(1, this.focusState.depth - 1);
    }
    this.zoomConfig.scale = Math.max(0.2, this.zoomConfig.scale / 1.2);
    this.updateZoomLevel();
  }

  /**
   * Go back in focus path — oldingi node'ga qaytish
   */
  unfocus(): string | null {
    this.focusState.path.pop();
    const prevId = this.focusState.path[this.focusState.path.length - 1] || null;
    if (prevId) {
      return this.focusOn(prevId, this.focusState.depth).nodes.length > 0 ? prevId : null;
    }
    this.focusState = { nodeId: null, depth: 1, neighbors: [], path: [] };
    return null;
  }

  /**
   * Get all visible nodes and edges for current focus state
   */
  getVisible(): { nodes: GraphNode[]; edges: GraphEdge[] } {
    if (!this.focusState.nodeId) {
      // No focus — show all entities
      return this.showAll();
    }
    return this.focusOn(this.focusState.nodeId, this.focusState.depth);
  }

  /**
   * Show all entities (no focus)
   */
  private showAll(): { nodes: GraphNode[]; edges: GraphEdge[] } {
    const entities = db.getEntities();
    const nodes: GraphNode[] = entities.map((e) => ({
      id: e.id,
      entity: e,
      x: 0, y: 0,
      depth: 0,
      visible: true,
      expanded: false,
      highlighted: false,
      focused: false,
    }));

    const allRelations: Relation[] = [];
    for (const e of entities) {
      allRelations.push(...db.getRelations(e.id));
    }
    // Deduplicate
    const seenRel = new Set<string>();
    const uniqueRelations = allRelations.filter((r) => {
      if (seenRel.has(r.id)) return false;
      seenRel.add(r.id);
      return true;
    });

    const edges: GraphEdge[] = uniqueRelations.map((r) => {
      const sourceNode = nodes.find((n) => n.id === r.source);
      const targetNode = nodes.find((n) => n.id === r.target);
      if (!sourceNode || !targetNode) return null;
      return {
        id: r.id,
        relation: r,
        sourceNode,
        targetNode,
        visible: true,
        highlighted: false,
        label: r.type.replace(/_/g, ' '),
      };
    }).filter(Boolean) as GraphEdge[];

    return { nodes, edges };
  }

  /**
   * Radial layout: center node in middle, neighbors around it
   */
  private layoutRadial(nodes: GraphNode[], centerId: string): void {
    const center = nodes.find((n) => n.id === centerId);
    if (!center) return;

    // Center node at origin
    center.x = 0;
    center.y = 0;

    // Group by depth
    const byDepth = new Map<number, GraphNode[]>();
    for (const node of nodes) {
      if (node.id === centerId) continue;
      const d = node.depth || 1;
      if (!byDepth.has(d)) byDepth.set(d, []);
      byDepth.get(d)!.push(node);
    }

    // Position each depth ring
    for (const [depth, depthNodes] of byDepth) {
      const radius = depth * 100;
      const angleStep = (Math.PI * 2) / depthNodes.length;
      depthNodes.forEach((node, i) => {
        const angle = angleStep * i - Math.PI / 2;
        node.x = Math.cos(angle) * radius;
        node.y = Math.sin(angle) * radius;
      });
    }
  }

  /**
   * Get distance between two entities (BFS)
   */
  private getDistance(fromId: string, toId: string, relations: Relation[]): number {
    const adj = new Map<string, string[]>();
    for (const r of relations) {
      if (!adj.has(r.source)) adj.set(r.source, []);
      if (!adj.has(r.target)) adj.set(r.target, []);
      adj.get(r.source)!.push(r.target);
      adj.get(r.target)!.push(r.source);
    }

    const visited = new Set<string>([fromId]);
    const queue = [{ id: fromId, d: 0 }];

    while (queue.length > 0) {
      const { id, d } = queue.shift()!;
      if (id === toId) return d;
      for (const neighbor of (adj.get(id) || [])) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push({ id: neighbor, d: d + 1 });
        }
      }
    }

    return 999; // Not connected
  }

  /**
   * Update zoom level based on scale
   */
  private updateZoomLevel(): void {
    const s = this.zoomConfig.scale;
    if (s < 0.5) {
      this.zoomConfig.level = 'overview';
      this.zoomConfig.showLabels = true;
      this.zoomConfig.showStates = false;
      this.zoomConfig.showEvents = false;
      this.zoomConfig.showProperties = false;
      this.zoomConfig.nodeSize = 'small';
    } else if (s < 1.5) {
      this.zoomConfig.level = 'structure';
      this.zoomConfig.showLabels = true;
      this.zoomConfig.showStates = true;
      this.zoomConfig.showEvents = false;
      this.zoomConfig.showProperties = false;
      this.zoomConfig.nodeSize = 'medium';
    } else if (s < 3) {
      this.zoomConfig.level = 'detail';
      this.zoomConfig.showLabels = true;
      this.zoomConfig.showStates = true;
      this.zoomConfig.showEvents = true;
      this.zoomConfig.showProperties = true;
      this.zoomConfig.nodeSize = 'large';
    } else {
      this.zoomConfig.level = 'properties';
      this.zoomConfig.showLabels = true;
      this.zoomConfig.showStates = true;
      this.zoomConfig.showEvents = true;
      this.zoomConfig.showProperties = true;
      this.zoomConfig.nodeSize = 'large';
    }
  }
}

export const focusEngine = new FocusEngine();
