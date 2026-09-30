/**
 * 2nd Brain — In-Memory DB + Graph API
 * 
 * Entity + Relation + Event store.
 * SSS (Single Source of Truth) — hamma narsa shu yerda saqlanadi.
 */

import {
  Entity, EntityType, EntityState,
  Relation, RelationType,
  Event, EventAction,
  GraphAPI,
} from './schema';

// ─────────────────────────────────────────────
// ID Generator
// ─────────────────────────────────────────────
let _idCounter = 0;
function genId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${(++_idCounter).toString(36)}`;
}

// ─────────────────────────────────────────────
// In-Memory Store
// ─────────────────────────────────────────────
class EntityStore {
  private entities = new Map<string, Entity>();
  private relations = new Map<string, Relation>();
  private events: Event[] = [];

  // ── Entity CRUD ──

  getEntity(id: string): Entity | null {
    return this.entities.get(id) || null;
  }

  getEntities(filter?: { type?: EntityType; state?: EntityState; tags?: string[] }): Entity[] {
    let result = Array.from(this.entities.values());
    if (filter?.type) result = result.filter((e) => e.type === filter.type);
    if (filter?.state) result = result.filter((e) => e.state === filter.state);
    if (filter?.tags?.length) result = result.filter((e) => filter.tags!.some((t) => e.tags.includes(t)));
    return result;
  }

  createEntity(data: Omit<Entity, 'id' | 'created_at' | 'updated_at'>): Entity {
    const now = Math.floor(Date.now() / 1000);
    const entity: Entity = {
      ...data,
      id: genId(data.type),
      created_at: now,
      updated_at: now,
    };
    this.entities.set(entity.id, entity);
    this.logEvent({ entity_id: entity.id, action: 'created', actor: data.created_by, result: `Created ${data.type}: ${data.name}` });
    return entity;
  }

  updateEntity(id: string, updates: Partial<Entity>): Entity | null {
    const entity = this.entities.get(id);
    if (!entity) return null;
    const updated = { ...entity, ...updates, updated_at: Math.floor(Date.now() / 1000) };
    this.entities.set(id, updated);
    this.logEvent({ entity_id: id, action: 'updated', actor: 'system', result: `Updated: ${Object.keys(updates).join(', ')}` });
    return updated;
  }

  deleteEntity(id: string): boolean {
    const entity = this.entities.get(id);
    if (!entity) return false;
    this.entities.delete(id);
    // Remove related relations
    for (const [relId, rel] of this.relations) {
      if (rel.source === id || rel.target === id) {
        this.relations.delete(relId);
      }
    }
    this.logEvent({ entity_id: id, action: 'deleted', actor: 'system', result: `Deleted ${entity.type}: ${entity.name}` });
    return true;
  }

  // ── Relation CRUD ──

  getRelations(entityId: string): Relation[] {
    return Array.from(this.relations.values()).filter(
      (r) => r.source === entityId || r.target === entityId
    );
  }

  getNeighbors(entityId: string, depth: number = 1): { entity: Entity; relation: Relation }[] {
    const visited = new Set<string>([entityId]);
    const result: { entity: Entity; relation: Relation }[] = [];
    const queue = [{ id: entityId, d: 0 }];

    while (queue.length > 0) {
      const { id, d } = queue.shift()!;
      if (d >= depth) continue;

      for (const rel of this.getRelations(id)) {
        const neighborId = rel.source === id ? rel.target : rel.source;
        if (visited.has(neighborId)) continue;
        visited.add(neighborId);

        const neighbor = this.entities.get(neighborId);
        if (neighbor) {
          result.push({ entity: neighbor, relation: rel });
          queue.push({ id: neighborId, d: d + 1 });
        }
      }
    }

    return result;
  }

  addRelation(data: Omit<Relation, 'id' | 'created_at'>): Relation {
    const relation: Relation = {
      ...data,
      id: genId('rel'),
      created_at: Math.floor(Date.now() / 1000),
    };
    this.relations.set(relation.id, relation);
    this.logEvent({ entity_id: data.source, action: 'relation_added', actor: 'system', result: `${data.type} → ${data.target}` });
    return relation;
  }

  removeRelation(id: string): boolean {
    const rel = this.relations.get(id);
    if (!rel) return false;
    this.relations.delete(id);
    this.logEvent({ entity_id: rel.source, action: 'relation_removed', actor: 'system', result: `Removed ${rel.type} → ${rel.target}` });
    return true;
  }

  // ── Query ──

  queryEntities(query: string): Entity[] {
    const q = query.toLowerCase();
    return Array.from(this.entities.values()).filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.content.toLowerCase().includes(q) ||
        e.tags.some((t) => t.toLowerCase().includes(q))
    );
  }

  getEntityHistory(id: string): Event[] {
    return this.events.filter((e) => e.entity_id === id);
  }

  // ── AI Interface ──

  getNeighborhood(entityId: string, depth: number): { entities: Entity[]; relations: Relation[] } {
    const neighbors = this.getNeighbors(entityId, depth);
    const entities = neighbors.map((n) => n.entity);
    const sourceEntity = this.entities.get(entityId);
    if (sourceEntity) entities.unshift(sourceEntity);

    const entityIds = new Set(entities.map((e) => e.id));
    const relations = Array.from(this.relations.values()).filter(
      (r) => entityIds.has(r.source) && entityIds.has(r.target)
    );

    return { entities, relations };
  }

  getActiveTasks(): Entity[] {
    return this.getEntities({ type: 'task', state: 'executing' });
  }

  getAgentState(agentId: string): Record<string, unknown> {
    const agent = this.entities.get(agentId);
    if (!agent) return {};
    const relations = this.getRelations(agentId);
    const activeTask = relations
      .filter((r) => r.type === 'executed_by')
      .map((r) => this.entities.get(r.source))
      .find((e) => e?.state === 'executing');
    return {
      agent: agent.name,
      state: agent.state,
      current_task: activeTask?.name || null,
      last_event: this.events.filter((e) => e.entity_id === agentId).slice(-1)[0] || null,
    };
  }

  // ── Events ──

  logEvent(data: Omit<Event, 'id' | 'timestamp'>): Event {
    const event: Event = {
      ...data,
      id: genId('evt'),
      timestamp: Math.floor(Date.now() / 1000),
    };
    this.events.push(event);
    // Keep last 1000 events
    if (this.events.length > 1000) this.events.splice(0, this.events.length - 1000);
    return event;
  }

  // ── Stats ──

  stats() {
    return {
      entities: this.entities.size,
      relations: this.relations.size,
      events: this.events.length,
      byType: this.getEntities().reduce((acc, e) => { acc[e.type] = (acc[e.type] || 0) + 1; return acc; }, {} as Record<string, number>),
    };
  }
}

// ─────────────────────────────────────────────
// Singleton
// ─────────────────────────────────────────────
export const db = new EntityStore();

// ─────────────────────────────────────────────
// Graph API implementation
// ─────────────────────────────────────────────
export const graphAPI: GraphAPI = {
  getEntity: (id) => db.getEntity(id),
  getEntities: (filter) => db.getEntities(filter),
  createEntity: (data) => db.createEntity(data),
  updateEntity: (id, updates) => db.updateEntity(id, updates),
  deleteEntity: (id) => db.deleteEntity(id),
  getRelations: (entityId) => db.getRelations(entityId),
  getNeighbors: (entityId, depth) => db.getNeighbors(entityId, depth),
  addRelation: (data) => db.addRelation(data),
  removeRelation: (id) => db.removeRelation(id),
  queryEntities: (query) => db.queryEntities(query),
  getEntityHistory: (id) => db.getEntityHistory(id),
  getEntityState: (id) => db.getEntity(id)?.state || 'inactive',
  getNeighborhood: (entityId, depth) => db.getNeighborhood(entityId, depth),
  getActiveTasks: () => db.getActiveTasks(),
  getAgentState: (agentId) => db.getAgentState(agentId),
  logEvent: (data) => db.logEvent(data),
};
