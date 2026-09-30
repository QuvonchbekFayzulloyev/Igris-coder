/**
 * Tree Store — Binary tree storage with semantic projection
 * 
 * Implements:
 *   - Binary tree CRUD (O(log n) lookup)
 *   - Semantic Father management
 *   - Radius-based traversal
 *   - Semantic relationship layer
 *   - Projection generation for visualization
 */

import type {
  TreeNode, TreeNodeType, TreeNodeStatus,
  SemanticFather, SemanticRelation, SemanticRelationType,
  RadiusConfig, RadiusLevel, TreeTraversalResult, SemanticProjection,
  TreeStats,
} from './tree-schema';

import {
  NODE_TYPE_CONFIG, RELATION_TYPE_CONFIG, RADIUS_CONFIG,
} from './tree-schema';

import type { KnowledgeDomain } from './akms-schema';

// ═══════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `tree_${Date.now().toString(36)}_${_nextId}`;
}

function now(): number {
  return Date.now();
}

// ═══════════════════════════════════════════════
// TREE STORE
// ═══════════════════════════════════════════════

export class TreeStore {
  private nodes: Map<string, TreeNode> = new Map();
  private fathers: Map<string, SemanticFather> = new Map();
  private relations: SemanticRelation[] = [];
  private listeners: Array<() => void> = [];

  // ─── NODE CRUD ───────────────────────────

  createNode(
    type: TreeNodeType,
    label: string,
    content: string,
    domain: KnowledgeDomain,
    options: {
      parentId?: string;
      semanticRole?: string;
      tags?: string[];
      metadata?: Record<string, unknown>;
    } = {},
  ): TreeNode {
    const id = uid();
    const t = now();
    
    const node: TreeNode = {
      id,
      parentId: options.parentId || null,
      leftChildId: null,
      rightChildId: null,
      type,
      semanticRole: options.semanticRole || type,
      content,
      label,
      domain,
      tags: options.tags || [],
      status: 'active',
      confidence: 0.5,
      createdAt: t,
      updatedAt: t,
      size: 1,
      metadata: options.metadata || {},
    };
    
    this.nodes.set(id, node);
    
    // Update parent
    if (options.parentId) {
      const parent = this.nodes.get(options.parentId);
      if (parent) {
        if (!parent.leftChildId) {
          parent.leftChildId = id;
        } else if (!parent.rightChildId) {
          parent.rightChildId = id;
        } else {
          // Both children occupied — insert as left child of left child
          this.insertUnder(parent.leftChildId, id);
        }
        parent.size++;
        this.updateAncestorSizes(parent.id);
      }
    }
    
    this.notify();
    return node;
  }

  private insertUnder(parentId: string, childId: string): void {
    const parent = this.nodes.get(parentId);
    if (!parent) return;
    
    if (!parent.leftChildId) {
      parent.leftChildId = childId;
    } else if (!parent.rightChildId) {
      parent.rightChildId = childId;
    } else {
      // Recurse
      this.insertUnder(parent.leftChildId, childId);
    }
    parent.size++;
  }

  private updateAncestorSizes(nodeId: string): void {
    let current = this.nodes.get(nodeId);
    while (current?.parentId) {
      const parent = this.nodes.get(current.parentId);
      if (parent) {
        parent.size = this.calculateSubtreeSize(parent.id);
      }
      current = parent;
    }
  }

  private calculateSubtreeSize(nodeId: string): number {
    const node = this.nodes.get(nodeId);
    if (!node) return 0;
    
    let size = 1;
    if (node.leftChildId) size += this.calculateSubtreeSize(node.leftChildId);
    if (node.rightChildId) size += this.calculateSubtreeSize(node.rightChildId);
    return size;
  }

  getNode(id: string): TreeNode | undefined {
    return this.nodes.get(id);
  }

  getChildren(id: string): TreeNode[] {
    const node = this.nodes.get(id);
    if (!node) return [];
    
    const children: TreeNode[] = [];
    if (node.leftChildId) {
      const left = this.nodes.get(node.leftChildId);
      if (left) children.push(left);
    }
    if (node.rightChildId) {
      const right = this.nodes.get(node.rightChildId);
      if (right) children.push(right);
    }
    return children;
  }

  getAncestors(id: string): TreeNode[] {
    const ancestors: TreeNode[] = [];
    let current = this.nodes.get(id);
    
    while (current?.parentId) {
      const parent = this.nodes.get(current.parentId);
      if (parent) {
        ancestors.push(parent);
        current = parent;
      } else {
        break;
      }
    }
    
    return ancestors;
  }

  getSubtree(id: string, maxDepth: number = 3): TreeNode[] {
    const result: TreeNode[] = [];
    const queue: { nodeId: string; depth: number }[] = [{ nodeId: id, depth: 0 }];
    
    while (queue.length > 0) {
      const { nodeId, depth } = queue.shift()!;
      if (depth > maxDepth) continue;
      
      const node = this.nodes.get(nodeId);
      if (!node) continue;
      
      result.push(node);
      
      if (node.leftChildId) queue.push({ nodeId: node.leftChildId, depth: depth + 1 });
      if (node.rightChildId) queue.push({ nodeId: node.rightChildId, depth: depth + 1 });
    }
    
    return result;
  }

  getAllNodes(): TreeNode[] {
    return Array.from(this.nodes.values());
  }

  findNodes(query: string): TreeNode[] {
    const q = query.toLowerCase();
    return Array.from(this.nodes.values()).filter(n =>
      n.label.toLowerCase().includes(q) ||
      n.content.toLowerCase().includes(q) ||
      n.tags.some(t => t.toLowerCase().includes(q))
    );
  }

  // ─── SEMANTIC FATHER ─────────────────────

  createFather(
    nodeId: string,
    label: string,
    domain: KnowledgeDomain,
    semanticRadius: number = 3,
  ): SemanticFather {
    const id = uid();
    const father: SemanticFather = {
      id,
      nodeId,
      label,
      domain,
      semanticRadius,
      subtreeSize: this.calculateSubtreeSize(nodeId),
      childrenByRole: {},
      createdAt: now(),
      updatedAt: now(),
    };
    
    this.fathers.set(id, father);
    this.notify();
    return father;
  }

  getFather(id: string): SemanticFather | undefined {
    return this.fathers.get(id);
  }

  getFatherByNodeId(nodeId: string): SemanticFather | undefined {
    return Array.from(this.fathers.values()).find(f => f.nodeId === nodeId);
  }

  getAllFathers(): SemanticFather[] {
    return Array.from(this.fathers.values());
  }

  // ─── SEMANTIC RELATIONS ──────────────────

  addRelation(
    sourceId: string,
    targetId: string,
    type: SemanticRelationType,
    weight: number = 0.5,
    description: string = '',
  ): SemanticRelation {
    const relation: SemanticRelation = {
      id: uid(),
      sourceId,
      targetId,
      type,
      weight,
      description,
      createdAt: now(),
      confidence: 0.8,
    };
    
    this.relations.push(relation);
    this.notify();
    return relation;
  }

  getRelations(nodeId: string): SemanticRelation[] {
    return this.relations.filter(r => r.sourceId === nodeId || r.targetId === nodeId);
  }

  getRelationsByType(type: SemanticRelationType): SemanticRelation[] {
    return this.relations.filter(r => r.type === type);
  }

  getAllRelations(): SemanticRelation[] {
    return this.relations;
  }

  // ─── RADIUS TRAVERSAL ────────────────────

  getRadiusConfig(fatherId: string): RadiusConfig | null {
    const father = this.fathers.get(fatherId);
    if (!father) return null;
    
    const radii: RadiusLevel[] = [];
    
    // Level 1: Direct children
    const directChildren = this.getChildren(father.nodeId);
    radii.push({
      level: 1,
      radius: RADIUS_CONFIG.level1.radius,
      nodeIds: directChildren.map(n => n.id),
      label: RADIUS_CONFIG.level1.label,
      color: RADIUS_CONFIG.level1.color,
    });
    
    // Level 2: Grandchildren
    const grandchildren: string[] = [];
    for (const child of directChildren) {
      const children = this.getChildren(child.id);
      grandchildren.push(...children.map(n => n.id));
    }
    radii.push({
      level: 2,
      radius: RADIUS_CONFIG.level2.radius,
      nodeIds: grandchildren,
      label: RADIUS_CONFIG.level2.label,
      color: RADIUS_CONFIG.level2.color,
    });
    
    // Level 3: Related through relations
    const relatedIds = new Set<string>();
    for (const child of directChildren) {
      const relations = this.getRelations(child.id);
      for (const rel of relations) {
        const relatedId = rel.sourceId === child.id ? rel.targetId : rel.sourceId;
        if (!directChildren.some(c => c.id === relatedId) && !grandchildren.includes(relatedId)) {
          relatedIds.add(relatedId);
        }
      }
    }
    radii.push({
      level: 3,
      radius: RADIUS_CONFIG.level3.radius,
      nodeIds: Array.from(relatedIds),
      label: RADIUS_CONFIG.level3.label,
      color: RADIUS_CONFIG.level3.color,
    });
    
    // Level 4: Ancestors (history)
    const ancestors = this.getAncestors(father.nodeId);
    radii.push({
      level: 4,
      radius: RADIUS_CONFIG.level4.radius,
      nodeIds: ancestors.map(n => n.id),
      label: RADIUS_CONFIG.level4.label,
      color: RADIUS_CONFIG.level4.color,
    });
    
    return { fatherId, radii };
  }

  // ─── SEMANTIC PROJECTION ─────────────────

  generateProjection(fatherId: string): SemanticProjection | null {
    const father = this.fathers.get(fatherId);
    if (!father) return null;
    
    const radiusConfig = this.getRadiusConfig(fatherId);
    if (!radiusConfig) return null;
    
    const nodes: SemanticProjection['nodes'] = [];
    const edges: SemanticProjection['edges'] = [];
    
    // Center node (father)
    const fatherNode = this.nodes.get(father.nodeId);
    if (fatherNode) {
      nodes.push({
        id: father.nodeId,
        x: 0,
        y: 0,
        radius: 0,
        label: fatherNode.label,
        type: fatherNode.type,
        domain: fatherNode.domain,
      });
    }
    
    // Nodes at each radius level
    for (const level of radiusConfig.radii) {
      const angleStep = (2 * Math.PI) / Math.max(level.nodeIds.length, 1);
      
      level.nodeIds.forEach((nodeId, index) => {
        const node = this.nodes.get(nodeId);
        if (!node) return;
        
        const angle = index * angleStep;
        const x = Math.cos(angle) * level.radius;
        const y = Math.sin(angle) * level.radius;
        
        nodes.push({
          id: nodeId,
          x,
          y,
          radius: level.radius,
          label: node.label,
          type: node.type,
          domain: node.domain,
        });
        
        // Add edge to father
        edges.push({
          source: father.nodeId,
          target: nodeId,
          type: 'related_to',
          weight: 0.5,
        });
      });
    }
    
    // Add semantic relations as edges
    for (const rel of this.relations) {
      if (nodes.some(n => n.id === rel.sourceId) && nodes.some(n => n.id === rel.targetId)) {
        edges.push({
          source: rel.sourceId,
          target: rel.targetId,
          type: rel.type,
          weight: rel.weight,
        });
      }
    }
    
    return { fatherId, nodes, edges };
  }

  // ─── STATS ───────────────────────────────

  getStats(): TreeStats {
    const nodes = Array.from(this.nodes.values());
    const fathers = Array.from(this.fathers.values());
    
    const byType: Record<string, number> = {};
    const byDomain: Record<string, number> = {};
    
    for (const node of nodes) {
      byType[node.type] = (byType[node.type] || 0) + 1;
      byDomain[node.domain] = (byDomain[node.domain] || 0) + 1;
    }
    
    return {
      totalNodes: nodes.length,
      totalFathers: fathers.length,
      totalRelations: this.relations.length,
      avgDepth: this.calculateAvgDepth(),
      avgSubtreeSize: fathers.length > 0
        ? fathers.reduce((sum, f) => sum + f.subtreeSize, 0) / fathers.length
        : 0,
      byType: byType as Record<TreeNodeType, number>,
      byDomain,
    };
  }

  private calculateAvgDepth(): number {
    const nodes = Array.from(this.nodes.values());
    if (nodes.length === 0) return 0;
    
    let totalDepth = 0;
    for (const node of nodes) {
      let depth = 0;
      let current = node;
      while (current.parentId) {
        depth++;
        const parent = this.nodes.get(current.parentId);
        if (parent) {
          current = parent;
        } else {
          break;
        }
      }
      totalDepth += depth;
    }
    
    return totalDepth / nodes.length;
  }

  // ─── LISTENERS ───────────────────────────

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(): void {
    for (const l of this.listeners) l();
  }

  // ─── IMPORT/EXPORT ───────────────────────

  exportData(): {
    nodes: TreeNode[];
    fathers: SemanticFather[];
    relations: SemanticRelation[];
  } {
    return {
      nodes: Array.from(this.nodes.values()),
      fathers: Array.from(this.fathers.values()),
      relations: this.relations,
    };
  }

  importData(data: {
    nodes: TreeNode[];
    fathers: SemanticFather[];
    relations: SemanticRelation[];
  }): void {
    this.nodes.clear();
    this.fathers.clear();
    this.relations = data.relations;
    
    for (const node of data.nodes) {
      this.nodes.set(node.id, node);
    }
    for (const father of data.fathers) {
      this.fathers.set(father.id, father);
    }
    
    this.notify();
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const treeStore = new TreeStore();
