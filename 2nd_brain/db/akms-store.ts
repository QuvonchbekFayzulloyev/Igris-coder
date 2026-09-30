/**
 * AKMS Store — In-memory database for Agent Knowledge & Memory System
 * 
 * Handles:
 *   Entity CRUD
 *   Relation management
 *   Evidence/Verification
 *   BFS neighbor queries
 *   AI interface (getNeighborhood, getActiveTasks, etc.)
 *   Event audit logging
 *   Domain-based queries
 *   Memory queries
 */

import type {
  Entity, EntityType, EntityState, Relation, RelationType,
  Evidence, Event, KnowledgeNode, KnowledgeEdge,
  AIQuery, AIResponse, FocusState, SemanticZoomConfig,
  KnowledgeDomain, MemoryType, VerificationStatus, SourceType,
} from './akms-schema';

import {
  ENTITY_TYPE_CONFIG, RELATION_TYPE_CONFIG, STATE_CONFIG,
  VERIFICATION_CONFIG, DOMAIN_CONFIG,
} from './akms-schema';

// ═══════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `akms_${Date.now().toString(36)}_${_nextId}`;
}

function now(): number {
  return Date.now();
}

// ═══════════════════════════════════════════════
// AKMS STORE
// ═══════════════════════════════════════════════

export class AKMSStore {
  private entities: Map<string, Entity> = new Map();
  private relations: Map<string, Relation> = new Map();
  private evidence: Map<string, Evidence> = new Map();
  private events: Event[] = [];
  private listeners: Array<() => void> = [];

  // ─── Entity CRUD ───────────────────────────

  createEntity(
    type: EntityType,
    name: string,
    content: string,
    domain: KnowledgeDomain = 'general',
    properties: Record<string, unknown> = {},
    state: EntityState = 'active',
    memoryType?: MemoryType,
    confidence: number = 0.8,
    verification: VerificationStatus = 'unverified',
    tags: string[] = [],
    createdBy: string = 'user',
  ): Entity {
    const id = uid();
    const t = now();
    const entity: Entity = {
      id, type, name, content, properties, state, domain,
      tags, created_at: t, updated_at: t,
      created_by: createdBy, confidence, verification,
      memory_type: memoryType,
    };
    this.entities.set(id, entity);
    this.logEvent(id, 'created', `Entity "${name}" created`, createdBy);
    this.notify();
    return entity;
  }

  getEntity(id: string): Entity | undefined {
    return this.entities.get(id);
  }

  getAllEntities(): Entity[] {
    return Array.from(this.entities.values());
  }

  updateEntity(id: string, updates: Partial<Entity>): Entity | undefined {
    const e = this.entities.get(id);
    if (!e) return undefined;
    const updated = { ...e, ...updates, updated_at: now() };
    this.entities.set(id, updated);
    this.logEvent(id, 'updated', `Entity updated: ${Object.keys(updates).join(', ')}`, e.created_by);
    this.notify();
    return updated;
  }

  deleteEntity(id: string): boolean {
    const e = this.entities.get(id);
    if (!e) return false;
    this.entities.delete(id);
    // Remove related relations
    for (const [rId, r] of this.relations) {
      if (r.source === id || r.target === id) {
        this.relations.delete(rId);
      }
    }
    // Remove related evidence
    for (const [evId, ev] of this.evidence) {
      if (ev.claim_id === id) {
        this.evidence.delete(evId);
      }
    }
    this.logEvent(id, 'deleted', `Entity "${e.name}" deleted`, e.created_by);
    this.notify();
    return true;
  }

  findEntities(filter: {
    type?: EntityType;
    domain?: KnowledgeDomain;
    state?: EntityState;
    memoryType?: MemoryType;
    verification?: VerificationStatus;
    tags?: string[];
    search?: string;
  }): Entity[] {
    return this.getAllEntities().filter(e => {
      if (filter.type && e.type !== filter.type) return false;
      if (filter.domain && e.domain !== filter.domain) return false;
      if (filter.state && e.state !== filter.state) return false;
      if (filter.memoryType && e.memory_type !== filter.memoryType) return false;
      if (filter.verification && e.verification !== filter.verification) return false;
      if (filter.tags && !filter.tags.some(t => e.tags.includes(t))) return false;
      if (filter.search) {
        const q = filter.search.toLowerCase();
        if (!e.name.toLowerCase().includes(q) && !e.content.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }

  // ─── Relation CRUD ─────────────────────────

  addRelation(
    source: string,
    target: string,
    type: RelationType,
    weight: number = 1.0,
    metadata: Record<string, unknown> = {},
    confidence: number = 0.8,
  ): Relation | null {
    if (!this.entities.has(source) || !this.entities.has(target)) return null;
    const id = uid();
    const relation: Relation = {
      id, source, target, type, weight, metadata,
      created_at: now(), confidence,
    };
    this.relations.set(id, relation);
    this.logEvent(source, 'relation_added', `${type} → ${target}`, 'system');
    this.notify();
    return relation;
  }

  getRelation(id: string): Relation | undefined {
    return this.relations.get(id);
  }

  getAllRelations(): Relation[] {
    return Array.from(this.relations.values());
  }

  removeRelation(id: string): boolean {
    const r = this.relations.get(id);
    if (!r) return false;
    this.relations.delete(id);
    this.notify();
    return true;
  }

  getNeighbors(entityId: string, depth: number = 1): { entity: Entity; relation: Relation }[] {
    const result: { entity: Entity; relation: Relation }[] = [];
    const visited = new Set<string>([entityId]);
    let frontier = [entityId];

    for (let d = 0; d < depth; d++) {
      const nextFrontier: string[] = [];
      for (const nodeId of frontier) {
        for (const [, r] of this.relations) {
          let neighborId: string | null = null;
          if (r.source === nodeId && !visited.has(r.target)) {
            neighborId = r.target;
          } else if (r.target === nodeId && !visited.has(r.source)) {
            neighborId = r.source;
          }
          if (neighborId) {
            const entity = this.entities.get(neighborId);
            if (entity) {
              result.push({ entity, relation: r });
              visited.add(neighborId);
              nextFrontier.push(neighborId);
            }
          }
        }
      }
      frontier = nextFrontier;
    }
    return result;
  }

  // ─── Evidence CRUD ─────────────────────────

  addEvidence(
    claimId: string,
    sourceType: SourceType,
    sourceText: string,
    extractedFact: string,
    reasoning: string = '',
    testResult: string = '',
    sourceUrl?: string,
    confidence: number = 0.8,
  ): Evidence {
    const id = uid();
    const ev: Evidence = {
      id, claim_id: claimId, source_type: sourceType,
      source_url: sourceUrl, source_text: sourceText,
      extracted_fact: extractedFact, reasoning,
      test_result: testResult || undefined,
      confidence,
    };
    this.evidence.set(id, ev);
    this.logEvent(claimId, 'evidence_added', `Evidence: ${sourceType}`, 'system');
    this.notify();
    return ev;
  }

  getEvidenceFor(claimId: string): Evidence[] {
    return Array.from(this.evidence.values()).filter(e => e.claim_id === claimId);
  }

  verifyEntity(entityId: string, status: VerificationStatus): Entity | undefined {
    return this.updateEntity(entityId, { verification: status });
  }

  // ─── Event Logging ────────────────────────

  private logEvent(entityId: string, action: string, result: string, actor: string): void {
    this.events.push({
      id: uid(), entity_id: entityId, action,
      timestamp: now(), actor, result, metadata: {},
    });
  }

  getEventsFor(entityId: string): Event[] {
    return this.events.filter(e => e.entity_id === entityId);
  }

  getRecentEvents(count: number = 50): Event[] {
    return this.events.slice(-count);
  }

  // ─── Listeners ────────────────────────────

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(): void {
    for (const l of this.listeners) l();
  }

  // ─── AI Interface ─────────────────────────

  getNeighborhood(entityId: string, depth: number = 2): AIResponse {
    const entity = this.entities.get(entityId);
    if (!entity) {
      return {
        entity: {} as Entity, neighbors: [], evidence: [],
        memory: [], context: '', confidence: 0, sources: [],
      };
    }
    const neighbors = this.getNeighbors(entityId, depth);
    const evidence = this.getEvidenceFor(entityId);
    const memory = neighbors
      .filter(n => ['experience', 'failure', 'lesson', 'decision', 'session', 'observation'].includes(n.entity.type))
      .map(n => n.entity);
    const sources = evidence.map(e => e.source_type);

    // Build context string for AI
    const contextParts: string[] = [];
    contextParts.push(`Entity: ${entity.name} (${entity.type})`);
    contextParts.push(`Domain: ${entity.domain}`);
    contextParts.push(`State: ${entity.state}`);
    contextParts.push(`Content: ${entity.content}`);
    if (entity.memory_type) contextParts.push(`Memory type: ${entity.memory_type}`);
    contextParts.push(`Verification: ${entity.verification}`);
    contextParts.push(`Confidence: ${entity.confidence}`);
    contextParts.push('');
    contextParts.push('Neighbors:');
    for (const n of neighbors.slice(0, 20)) {
      contextParts.push(`  - ${n.entity.name} (${n.entity.type}) via ${n.relation.type}`);
    }
    if (evidence.length > 0) {
      contextParts.push('');
      contextParts.push('Evidence:');
      for (const ev of evidence) {
        contextParts.push(`  - [${ev.source_type}] ${ev.extracted_fact}`);
      }
    }

    return {
      entity, neighbors, evidence, memory,
      context: contextParts.join('\n'),
      confidence: entity.confidence,
      sources,
    };
  }

  getActiveTasks(): Entity[] {
    return this.findEntities({ type: 'task', state: 'executing' });
  }

  getAgentState(): { tasks: Entity[]; activeSessions: Entity[]; recentEvents: Event[]; totalEntities: number } {
    return {
      tasks: this.findEntities({ type: 'task' }),
      activeSessions: this.findEntities({ type: 'session', state: 'active' }),
      recentEvents: this.getRecentEvents(20),
      totalEntities: this.entities.size,
    };
  }

  // ─── Domain Queries ───────────────────────

  getDomainEntities(domain: KnowledgeDomain): Entity[] {
    return this.findEntities({ domain });
  }

  getDomainStats(): Record<KnowledgeDomain, number> {
    const stats: Record<string, number> = {};
    for (const e of this.entities) {
      const d = e[1].domain;
      stats[d] = (stats[d] || 0) + 1;
    }
    return stats as Record<KnowledgeDomain, number>;
  }

  // ─── Memory Queries ───────────────────────

  getMemoryEntities(memoryType: MemoryType): Entity[] {
    return this.findEntities({ memoryType });
  }

  getExperienceForDomain(domain: KnowledgeDomain): Entity[] {
    return this.findEntities({ domain, memoryType: 'experience' });
  }

  getFailuresForDomain(domain: KnowledgeDomain): Entity[] {
    return this.findEntities({ domain, memoryType: 'failure' });
  }

  getLessonsLearned(): Entity[] {
    return this.findEntities({ memoryType: 'lesson' });
  }

  getDecisionHistory(): Entity[] {
    return this.findEntities({ memoryType: 'decision' });
  }

  // ─── BFS for Graph ────────────────────────

  buildGraph(centerId: string, depth: number): { nodes: KnowledgeNode[]; edges: KnowledgeEdge[] } {
    const nodes: KnowledgeNode[] = [];
    const edges: KnowledgeEdge[] = [];
    const visited = new Set<string>();
    let frontier = [centerId];
    let currentDepth = 0;

    while (frontier.length > 0 && currentDepth < depth) {
      const nextFrontier: string[] = [];
      for (const nodeId of frontier) {
        const entity = this.entities.get(nodeId);
        if (!entity || visited.has(nodeId)) continue;
        visited.add(nodeId);

        nodes.push({
          id: nodeId,
          entity,
          x: 0, y: 0, // computed by layout
          depth: currentDepth,
          visible: true,
          expanded: currentDepth < depth - 1,
          highlighted: currentDepth === 0,
          focused: currentDepth === 0,
          children: [],
          evidence: this.getEvidenceFor(nodeId),
        });

        for (const [, r] of this.relations) {
          let neighborId: string | null = null;
          if (r.source === nodeId && !visited.has(r.target)) {
            neighborId = r.target;
          } else if (r.target === nodeId && !visited.has(r.source)) {
            neighborId = r.source;
          }
          if (neighborId && !visited.has(neighborId)) {
            const neighbor = this.entities.get(neighborId);
            if (neighbor) {
              edges.push({
                id: r.id,
                relation: r,
                sourceNode: nodes[nodes.length - 1],
                targetNode: { id: neighborId } as KnowledgeNode,
                visible: true,
                highlighted: false,
                label: RELATION_TYPE_CONFIG[r.type]?.label || r.type,
              });
              nextFrontier.push(neighborId);
              // Update parent's children
              nodes[nodes.length - 1].children.push(neighborId);
            }
          }
        }
      }
      frontier = nextFrontier;
      currentDepth++;
    }

    return { nodes, edges };
  }

  // ─── Import/Export ────────────────────────

  exportJSON(): string {
    return JSON.stringify({
      entities: Array.from(this.entities.values()),
      relations: Array.from(this.relations.values()),
      evidence: Array.from(this.evidence.values()),
      events: this.events,
    }, null, 2);
  }

  importJSON(json: string): void {
    const data = JSON.parse(json);
    if (data.entities) {
      for (const e of data.entities) this.entities.set(e.id, e);
    }
    if (data.relations) {
      for (const r of data.relations) this.relations.set(r.id, r);
    }
    if (data.evidence) {
      for (const ev of data.evidence) this.evidence.set(ev.id, ev);
    }
    if (data.events) {
      this.events = data.events;
    }
    this.notify();
  }

  // ─── Stats ────────────────────────────────

  getStats() {
    return {
      entities: this.entities.size,
      relations: this.relations.size,
      evidence: this.evidence.size,
      events: this.events.length,
      domains: this.getDomainStats(),
    };
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const akms = new AKMSStore();
