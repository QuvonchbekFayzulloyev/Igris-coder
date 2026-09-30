/**
 * Binary Tree Storage — Fast hierarchical storage for 2nd Brain
 * 
 * Architecture:
 *   BINARY TREE = Actual Storage (fast lookup)
 *   SEMANTIC INDEX = Semantic mapping
 *   SEMANTIC FATHER = Subtree center
 *   RADIUS = Visualization layers
 *   SEMANTIC GRAPH = Relationship layer
 * 
 * Philosophy:
 *   - Binary tree for fast O(log n) lookup
 *   - Semantic father for semantic grouping
 *   - Radius for visualization (not physical storage)
 *   - Separate relationship layer for semantic connections
 */

import type { KnowledgeDomain } from './akms-schema';

// ═══════════════════════════════════════════════
// BINARY TREE NODE
// ═══════════════════════════════════════════════

export type TreeNodeType =
  | 'root'
  | 'semantic_father'
  | 'concept'
  | 'fact'
  | 'task'
  | 'artifact'
  | 'memory'
  | 'evidence'
  | 'session'
  | 'experience'
  | 'other';

export type TreeNodeStatus = 'active' | 'archived' | 'deprecated' | 'draft';

export interface TreeNode {
  id: string;
  parentId: string | null;
  leftChildId: string | null;
  rightChildId: string | null;
  
  // Content
  type: TreeNodeType;
  semanticRole: string;
  content: string;
  label: string;
  
  // Metadata
  domain: KnowledgeDomain;
  tags: string[];
  status: TreeNodeStatus;
  confidence: number;
  
  // Timestamps
  createdAt: number;
  updatedAt: number;
  
  // Size (for balanced tree)
  size: number;
  
  // Metadata
  metadata: Record<string, unknown>;
}

// ═══════════════════════════════════════════════
// SEMANTIC FATHER
// ═══════════════════════════════════════════════

export interface SemanticFather {
  id: string;
  nodeId: string;              // The actual tree node
  label: string;
  domain: KnowledgeDomain;
  
  // Semantic scope
  semanticRadius: number;      // How many levels of related nodes
  subtreeSize: number;         // Number of nodes in subtree
  
  // Children by semantic role
  childrenByRole: Record<string, string[]>;
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// SEMANTIC RELATIONSHIP
// ═══════════════════════════════════════════════

export type SemanticRelationType =
  | 'related_to'
  | 'derived_from'
  | 'continues'
  | 'depends_on'
  | 'updates'
  | 'contradicts'
  | 'verifies'
  | 'produces'
  | 'contains'
  | 'part_of'
  | 'similar_to'
  | 'opposite_of'
  | 'example_of'
  | 'generalizes'
  | 'specializes';

export interface SemanticRelation {
  id: string;
  sourceId: string;
  targetId: string;
  type: SemanticRelationType;
  weight: number;              // 0..1
  description: string;
  
  // Metadata
  createdAt: number;
  confidence: number;
}

// ═══════════════════════════════════════════════
// RADIUS CONFIGURATION
// ═══════════════════════════════════════════════

export interface RadiusConfig {
  fatherId: string;
  radii: RadiusLevel[];
}

export interface RadiusLevel {
  level: number;               // 1, 2, 3, 4
  radius: number;              // Visual radius
  nodeIds: string[];           // Nodes at this level
  label: string;               // "Direct", "Related", "Context", "History"
  color: string;
}

// ═══════════════════════════════════════════════
// TREE TRAVERSAL
// ═══════════════════════════════════════════════

export interface TreeTraversalResult {
  nodes: TreeNode[];
  path: string[];
  depth: number;
}

// ═══════════════════════════════════════════════
// SEMANTIC PROJECTION
// ═══════════════════════════════════════════════

export interface SemanticProjection {
  fatherId: string;
  nodes: {
    id: string;
    x: number;
    y: number;
    radius: number;            // Which radius level
    label: string;
    type: TreeNodeType;
    domain: KnowledgeDomain;
  }[];
  edges: {
    source: string;
    target: string;
    type: SemanticRelationType;
    weight: number;
  }[];
}

// ═══════════════════════════════════════════════
// TREE STATS
// ═══════════════════════════════════════════════

export interface TreeStats {
  totalNodes: number;
  totalFathers: number;
  totalRelations: number;
  avgDepth: number;
  avgSubtreeSize: number;
  byType: Record<TreeNodeType, number>;
  byDomain: Record<string, number>;
}

// ═══════════════════════════════════════════════
// VISUAL CONFIG
// ═══════════════════════════════════════════════

export const NODE_TYPE_CONFIG: Record<TreeNodeType, { color: string; icon: string; label: string }> = {
  root:            { color: '#f59e0b', icon: '🌳', label: 'Root' },
  semantic_father: { color: '#8b5cf6', icon: '👤', label: 'Father' },
  concept:         { color: '#3b82f6', icon: '💡', label: 'Concept' },
  fact:            { color: '#10b981', icon: '📊', label: 'Fact' },
  task:            { color: '#ef4444', icon: '⚡', label: 'Task' },
  artifact:        { color: '#06b6d4', icon: '📦', label: 'Artifact' },
  memory:          { color: '#ec4899', icon: '🧠', label: 'Memory' },
  evidence:        { color: '#14b8a6', icon: '✅', label: 'Evidence' },
  session:         { color: '#f97316', icon: '💬', label: 'Session' },
  experience:      { color: '#a855f7', icon: '💭', label: 'Experience' },
  other:           { color: '#6b7280', icon: '❓', label: 'Other' },
};

export const RELATION_TYPE_CONFIG: Record<SemanticRelationType, { color: string; icon: string; label: string }> = {
  related_to:     { color: '#6b7280', icon: '🔗', label: 'Related' },
  derived_from:   { color: '#3b82f6', icon: '←', label: 'Derived' },
  continues:      { color: '#10b981', icon: '→', label: 'Continues' },
  depends_on:     { color: '#ef4444', icon: '⬆', label: 'Depends' },
  updates:        { color: '#f59e0b', icon: '🔄', label: 'Updates' },
  contradicts:    { color: '#dc2626', icon: '⚔', label: 'Contradicts' },
  verifies:       { color: '#059669', icon: '✓', label: 'Verifies' },
  produces:       { color: '#7c3aed', icon: '→', label: 'Produces' },
  contains:       { color: '#0891b2', icon: '⊃', label: 'Contains' },
  part_of:        { color: '#be185d', icon: '⊂', label: 'Part of' },
  similar_to:     { color: '#65a30d', icon: '≈', label: 'Similar' },
  opposite_of:    { color: '#dc2626', icon: '≠', label: 'Opposite' },
  example_of:     { color: '#2563eb', icon: '📝', label: 'Example' },
  generalizes:    { color: '#9333ea', icon: '↑', label: 'Generalizes' },
  specializes:    { color: '#c026d3', icon: '↓', label: 'Specializes' },
};

export const RADIUS_CONFIG = {
  level1: { radius: 60, color: '#3b82f6', label: 'Direct' },
  level2: { radius: 120, color: '#10b981', label: 'Related' },
  level3: { radius: 180, color: '#f59e0b', label: 'Context' },
  level4: { radius: 240, color: '#6b7280', label: 'History' },
} as const;
