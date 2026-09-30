/**
 * 2nd Brain — DB Schema
 * 
 * Architecture:
 *   DB (source of truth) → Graph API → Graph UI
 *   AI → DB/Graph (retrieve, reason, update, verify, act)
 * 
 * Core models: Entity + Relation + Event + State
 */

// ─────────────────────────────────────────────
// ENTITY — asosiy ma'lumot birligi
// ─────────────────────────────────────────────

export type EntityType =
  | 'project'
  | 'task'
  | 'memory'
  | 'agent'
  | 'decision'
  | 'action'
  | 'file'
  | 'event'
  | 'note'
  | 'group'
  | 'concept'
  | 'skill'
  | 'error'
  | 'session';

export type EntityState =
  | 'active'
  | 'inactive'
  | 'executing'
  | 'waiting'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'planning'
  | 'verifying'
  | 'reading'
  | 'writing'
  | 'idle';

export interface Entity {
  id: string;
  type: EntityType;
  name: string;
  content: string;
  properties: Record<string, unknown>;
  state: EntityState;
  created_at: number;   // epoch seconds
  updated_at: number;   // epoch seconds
  created_by: string;   // agent or user id
  tags: string[];
}

// ─────────────────────────────────────────────
// RELATION — entity'lar orasidagi bog'lanish
// ─────────────────────────────────────────────

export type RelationType =
  | 'depends_on'
  | 'uses'
  | 'contains'
  | 'belongs_to'
  | 'produced_by'
  | 'controls'
  | 'references'
  | 'executed_by'
  | 'created_by'
  | 'related_to'
  | 'triggers'
  | 'blocks'
  | 'extends'
  | 'implements'
  | 'monitors';

export interface Relation {
  id: string;
  source: string;      // entity id
  target: string;      // entity id
  type: RelationType;
  weight: number;      // 0..1 — kuchli bog'lanish
  metadata: Record<string, unknown>;
  created_at: number;
}

// ─────────────────────────────────────────────
// EVENT — o'zgarish tarixi (audit log)
// ─────────────────────────────────────────────

export type EventAction =
  | 'created'
  | 'updated'
  | 'deleted'
  | 'state_changed'
  | 'relation_added'
  | 'relation_removed'
  | 'executed'
  | 'completed'
  | 'failed'
  | 'queried';

export interface Event {
  id: string;
  entity_id: string;
  action: EventAction;
  timestamp: number;
  actor: string;       // agent id yoki 'user'
  result: string;
  metadata: Record<string, unknown>;
}

// ─────────────────────────────────────────────
// GRAPH NODE — UI uchun node (Entity + vizual)
// ─────────────────────────────────────────────

export interface GraphNode {
  id: string;
  entity: Entity;
  x: number;
  y: number;
  depth: number;       // focus depth (0 = markaz)
  visible: boolean;
  expanded: boolean;   // children ko'rinadimi
  highlighted: boolean;
  focused: boolean;
}

// ─────────────────────────────────────────────
// GRAPH EDGE — UI uchun link (Relation + vizual)
// ─────────────────────────────────────────────

export interface GraphEdge {
  id: string;
  relation: Relation;
  sourceNode: GraphNode;
  targetNode: GraphNode;
  visible: boolean;
  highlighted: boolean;
  label: string;
}

// ─────────────────────────────────────────────
// FOCUS STATE — qaysi node ga focus qilindi
// ─────────────────────────────────────────────

export interface FocusState {
  nodeId: string | null;
  depth: number;          // 1, 2, 3... nechta qatlam ko'rsatiladi
  neighbors: string[];    // focus langan node qo'shnilari
  path: string[];         // focus yo'li
}

// ─────────────────────────────────────────────
// SEMANTIC ZOOM — zoom darajasiga qarab nima ko'rinadi
// ─────────────────────────────────────────────

export type ZoomLevel = 'overview' | 'structure' | 'detail' | 'properties';

export interface SemanticZoomConfig {
  level: ZoomLevel;
  scale: number;          // 0..5
  showLabels: boolean;
  showStates: boolean;
  showEvents: boolean;
  showProperties: boolean;
  showRelations: boolean;
  nodeSize: 'small' | 'medium' | 'large';
}

// ─────────────────────────────────────────────
// GRAPH VIEW — to'liq vizual holat
// ─────────────────────────────────────────────

export interface GraphView {
  nodes: GraphNode[];
  edges: GraphEdge[];
  focus: FocusState;
  zoom: SemanticZoomConfig;
  camera: { x: number; y: number; scale: number };
  selectedNodes: Set<string>;
  hoveredNode: string | null;
}

// ─────────────────────────────────────────────
// GRAPH API — DB va UI orasidagi qatlam
// ─────────────────────────────────────────────

export interface GraphAPI {
  // CRUD
  getEntity(id: string): Entity | null;
  getEntities(filter?: { type?: EntityType; state?: EntityState; tags?: string[] }): Entity[];
  createEntity(entity: Omit<Entity, 'id' | 'created_at' | 'updated_at'>): Entity;
  updateEntity(id: string, updates: Partial<Entity>): Entity | null;
  deleteEntity(id: string): boolean;

  // Relations
  getRelations(entityId: string): Relation[];
  getNeighbors(entityId: string, depth?: number): { entity: Entity; relation: Relation }[];
  addRelation(relation: Omit<Relation, 'id' | 'created_at'>): Relation;
  removeRelation(id: string): boolean;

  // Query
  queryEntities(query: string): Entity[];
  getEntityHistory(id: string): Event[];
  getEntityState(id: string): EntityState;

  // AI interface
  getNeighborhood(entityId: string, depth: number): { entities: Entity[]; relations: Relation[] };
  getActiveTasks(): Entity[];
  getAgentState(agentId: string): Record<string, unknown>;

  // Events
  logEvent(event: Omit<Event, 'id' | 'timestamp'>): Event;
}

// ─────────────────────────────────────────────
// DEFAULT ENTITY TYPES — har bir tur uchun rang va ikonka
// ─────────────────────────────────────────────

export const ENTITY_TYPE_CONFIG: Record<EntityType, { color: string; icon: string; label: string }> = {
  project:    { color: '#8b5cf6', icon: '📁', label: 'Project' },
  task:       { color: '#f59e0b', icon: '📋', label: 'Task' },
  memory:     { color: '#06b6d4', icon: '🧠', label: 'Memory' },
  agent:      { color: '#10b981', icon: '🤖', label: 'Agent' },
  decision:   { color: '#ef4444', icon: '⚡', label: 'Decision' },
  action:     { color: '#f97316', icon: '▶', label: 'Action' },
  file:       { color: '#6366f1', icon: '📄', label: 'File' },
  event:      { color: '#ec4899', icon: '🕐', label: 'Event' },
  note:       { color: '#71717a', icon: '📝', label: 'Note' },
  group:      { color: '#3b82f6', icon: '📦', label: 'Group' },
  concept:    { color: '#a855f7', icon: '💡', label: 'Concept' },
  skill:      { color: '#14b8a6', icon: '🎯', label: 'Skill' },
  error:      { color: '#dc2626', icon: '❌', label: 'Error' },
  session:    { color: '#2dd4bf', icon: '💬', label: 'Session' },
};

// ─────────────────────────────────────────────
// DEFAULT RELATION TYPES — har bir tur uchun rang
// ─────────────────────────────────────────────

export const RELATION_TYPE_CONFIG: Record<RelationType, { color: string; label: string; dashed?: boolean }> = {
  depends_on:  { color: '#ef4444', label: 'depends on' },
  uses:        { color: '#3b82f6', label: 'uses' },
  contains:    { color: '#6366f1', label: 'contains', dashed: true },
  belongs_to:  { color: '#8b5cf6', label: 'belongs to' },
  produced_by: { color: '#10b981', label: 'produced by' },
  controls:    { color: '#f59e0b', label: 'controls' },
  references:  { color: '#71717a', label: 'references', dashed: true },
  executed_by: { color: '#f97316', label: 'executed by' },
  created_by:  { color: '#ec4899', label: 'created by' },
  related_to:  { color: '#a1a1aa', label: 'related', dashed: true },
  triggers:    { color: '#dc2626', label: 'triggers' },
  blocks:      { color: '#dc2626', label: 'blocks', dashed: true },
  extends:     { color: '#6366f1', label: 'extends' },
  implements:  { color: '#14b8a6', label: 'implements' },
  monitors:    { color: '#06b6d4', label: 'monitors' },
};

// ─────────────────────────────────────────────
// STATE COLORS — har bir state uchun vizual
// ─────────────────────────────────────────────

export const STATE_CONFIG: Record<EntityState, { color: string; pulse: boolean; label: string }> = {
  active:      { color: '#10b981', pulse: true,  label: 'Active' },
  inactive:    { color: '#71717a', pulse: false, label: 'Inactive' },
  executing:   { color: '#f59e0b', pulse: true,  label: 'Executing' },
  waiting:     { color: '#06b6d4', pulse: true,  label: 'Waiting' },
  completed:   { color: '#10b981', pulse: false, label: 'Completed' },
  failed:      { color: '#dc2626', pulse: true,  label: 'Failed' },
  paused:      { color: '#f97316', pulse: false, label: 'Paused' },
  planning:    { color: '#8b5cf6', pulse: true,  label: 'Planning' },
  verifying:   { color: '#a855f7', pulse: true,  label: 'Verifying' },
  reading:     { color: '#06b6d4', pulse: true,  label: 'Reading' },
  writing:     { color: '#f97316', pulse: true,  label: 'Writing' },
  idle:        { color: '#71717a', pulse: false, label: 'Idle' },
};
