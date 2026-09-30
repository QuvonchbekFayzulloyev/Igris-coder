/**
 * Runtime Store — Context management, selective retrieval, shared capabilities
 * 
 * Implements:
 *   - HOT/WARM/COLD context tiers
 *   - Selective graph traversal
 *   - Task-specific subgraph extraction
 *   - Shared capability registry
 *   - Evidence status tracking
 *   - Lightweight inference support
 */

import type {
  ContextTier, ContextItem, ContextSnapshot, RetrievalQuery, RetrievalResult,
  SharedCapability, TaskContext, EvidenceStatus, GraphTraversalOptions, TraversalResult,
  RuntimeStats, VerificationStep,
} from './runtime-schema';

import {
  RUNTIME_LIMITS, EVIDENCE_STATUS_CONFIG,
} from './runtime-schema';

import type { KnowledgeDomain, Entity, Relation } from './akms-schema';
import type { Task } from './pcm-schema';
import { akms } from './akms-store';
import { pcm } from './pcm-store';
import { gcm } from './gcm-store';

// ═══════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `rt_${Date.now().toString(36)}_${_nextId}`;
}

function now(): number {
  return Date.now();
}

// ═══════════════════════════════════════════════
// CONTEXT MANAGER
// ═══════════════════════════════════════════════

export class ContextManager {
  private hot: Map<string, ContextItem> = new Map();
  private warm: Map<string, ContextItem> = new Map();
  private cold: Map<string, ContextItem> = new Map();
  private snapshots: ContextSnapshot[] = [];
  private listeners: Array<() => void> = [];

  // ─── HOT Context ─────────────────────────

  addToHot(item: Omit<ContextItem, 'tier' | 'lastAccessed' | 'accessCount'>): ContextItem {
    const fullItem: ContextItem = {
      ...item,
      tier: 'hot',
      lastAccessed: now(),
      accessCount: 0,
    };
    this.hot.set(item.id, fullItem);
    this.evictExpired();
    this.notify();
    return fullItem;
  }

  getFromHot(id: string): ContextItem | undefined {
    const item = this.hot.get(id);
    if (item) {
      item.lastAccessed = now();
      item.accessCount++;
    }
    return item;
  }

  removeFromHot(id: string): void {
    this.hot.delete(id);
    this.notify();
  }

  // ─── WARM Context ────────────────────────

  addToWarm(item: Omit<ContextItem, 'tier' | 'lastAccessed' | 'accessCount'>): ContextItem {
    // Check if already in HOT
    if (this.hot.has(item.id)) {
      return this.hot.get(item.id)!;
    }
    
    const fullItem: ContextItem = {
      ...item,
      tier: 'warm',
      lastAccessed: now(),
      accessCount: 0,
    };
    this.warm.set(item.id, fullItem);
    this.evictExpired();
    this.notify();
    return fullItem;
  }

  getFromWarm(id: string): ContextItem | undefined {
    const item = this.warm.get(id);
    if (item) {
      item.lastAccessed = now();
      item.accessCount++;
      // Promote to HOT if frequently accessed
      if (item.accessCount >= 3) {
        this.hot.set(id, { ...item, tier: 'hot' });
        this.warm.delete(id);
      }
    }
    return item;
  }

  // ─── COLD Context ────────────────────────

  addToCold(item: Omit<ContextItem, 'tier' | 'lastAccessed' | 'accessCount'>): ContextItem {
    const fullItem: ContextItem = {
      ...item,
      tier: 'cold',
      lastAccessed: now(),
      accessCount: 0,
    };
    this.cold.set(item.id, fullItem);
    this.notify();
    return fullItem;
  }

  getFromCold(id: string): ContextItem | undefined {
    const item = this.cold.get(id);
    if (item) {
      item.lastAccessed = now();
      item.accessCount++;
      // Promote to WARM if accessed
      if (item.accessCount >= 2) {
        this.warm.set(id, { ...item, tier: 'warm' });
        this.cold.delete(id);
      }
    }
    return item;
  }

  // ─── Unified Access ──────────────────────

  get(id: string): ContextItem | undefined {
    return this.getFromHot(id) || this.getFromWarm(id) || this.getFromCold(id);
  }

  // ─── Eviction ────────────────────────────

  private evictExpired(): void {
    const t = now();
    
    // Evict expired HOT items to WARM
    for (const [id, item] of this.hot) {
      if (t - item.lastAccessed > RUNTIME_LIMITS.HOT_TTL) {
        this.hot.delete(id);
        this.warm.set(id, { ...item, tier: 'warm' });
      }
    }
    
    // Evict expired WARM items to COLD
    for (const [id, item] of this.warm) {
      if (t - item.lastAccessed > RUNTIME_LIMITS.WARM_TTL) {
        this.warm.delete(id);
        this.cold.set(id, { ...item, tier: 'cold' });
      }
    }
    
    // Evict expired COLD items
    for (const [id, item] of this.cold) {
      if (t - item.lastAccessed > RUNTIME_LIMITS.COLD_TTL) {
        this.cold.delete(id);
      }
    }
    
    // Enforce size limits
    this.enforceLimits();
  }

  private enforceLimits(): void {
    // HOT limit
    if (this.hot.size > RUNTIME_LIMITS.MAX_HOT_ITEMS) {
      const sorted = Array.from(this.hot.entries())
        .sort((a, b) => a[1].lastAccessed - b[1].lastAccessed);
      const toEvict = sorted.slice(0, this.hot.size - RUNTIME_LIMITS.MAX_HOT_ITEMS);
      for (const [id, item] of toEvict) {
        this.hot.delete(id);
        this.warm.set(id, { ...item, tier: 'warm' });
      }
    }
    
    // WARM limit
    if (this.warm.size > RUNTIME_LIMITS.MAX_WARM_ITEMS) {
      const sorted = Array.from(this.warm.entries())
        .sort((a, b) => a[1].lastAccessed - b[1].lastAccessed);
      const toEvict = sorted.slice(0, this.warm.size - RUNTIME_LIMITS.MAX_WARM_ITEMS);
      for (const [id, item] of toEvict) {
        this.warm.delete(id);
        this.cold.set(id, { ...item, tier: 'cold' });
      }
    }
    
    // COLD limit
    if (this.cold.size > RUNTIME_LIMITS.MAX_COLD_ITEMS) {
      const sorted = Array.from(this.cold.entries())
        .sort((a, b) => a[1].lastAccessed - b[1].lastAccessed);
      const toEvict = sorted.slice(0, this.cold.size - RUNTIME_LIMITS.MAX_COLD_ITEMS);
      for (const [id] of toEvict) {
        this.cold.delete(id);
      }
    }
  }

  // ─── Snapshot ────────────────────────────

  createSnapshot(taskId: string): ContextSnapshot {
    const snapshot: ContextSnapshot = {
      timestamp: now(),
      taskId,
      hot: Array.from(this.hot.values()),
      warm: Array.from(this.warm.values()),
      cold: Array.from(this.cold.values()),
      totalSize: this.hot.size + this.warm.size + this.cold.size,
      retrievalTime: 0,
    };
    this.snapshots.push(snapshot);
    return snapshot;
  }

  // ─── Stats ───────────────────────────────

  getStats(): { hot: number; warm: number; cold: number; total: number } {
    return {
      hot: this.hot.size,
      warm: this.warm.size,
      cold: this.cold.size,
      total: this.hot.size + this.warm.size + this.cold.size,
    };
  }

  // ─── Listeners ───────────────────────────

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(): void {
    for (const l of this.listeners) l();
  }
}

// ═══════════════════════════════════════════════
// SELECTIVE RETRIEVAL ENGINE
// ═══════════════════════════════════════════════

export class RetrievalEngine {
  private contextManager: ContextManager;

  constructor(contextManager: ContextManager) {
    this.contextManager = contextManager;
  }

  /**
   * Retrieve task-specific context from the knowledge graph.
   * Only loads relevant subgraph, not entire DB.
   */
  retrieve(query: RetrievalQuery): RetrievalResult {
    const startTime = now();
    const items: ContextItem[] = [];
    const visited = new Set<string>();
    const nodeIds: string[] = [];
    const edges: [string, string][] = [];

    // 1. Get task entity
    const taskEntity = akms.getEntity(query.taskId);
    if (taskEntity) {
      items.push(this.createContextItem(query.taskId, 'entity', taskEntity, 1.0));
      nodeIds.push(query.taskId);
      visited.add(query.taskId);
    }

    // 2. Get related entities (BFS up to depth)
    let frontier = [query.taskId];
    for (let d = 0; d < query.depth && frontier.length < query.maxItems; d++) {
      const nextFrontier: string[] = [];
      for (const nodeId of frontier) {
        const neighbors = akms.getNeighbors(nodeId, 1);
        for (const { entity, relation } of neighbors) {
          if (visited.has(entity.id) || items.length >= query.maxItems) continue;
          
          // Calculate relevance
          const relevance = this.calculateRelevance(entity, query);
          if (relevance < RUNTIME_LIMITS.MIN_RELEVANCE) continue;
          
          visited.add(entity.id);
          nodeIds.push(entity.id);
          edges.push([nodeId, entity.id]);
          items.push(this.createContextItem(entity.id, 'entity', entity, relevance));
          nextFrontier.push(entity.id);
          
          // Add to appropriate context tier
          if (relevance > 0.8) {
            this.contextManager.addToHot({
              id: entity.id, type: 'entity',
              data: entity, relevance,
              ttl: RUNTIME_LIMITS.HOT_TTL,
            });
          } else if (relevance > 0.5) {
            this.contextManager.addToWarm({
              id: entity.id, type: 'entity',
              data: entity, relevance,
              ttl: RUNTIME_LIMITS.WARM_TTL,
            });
          }
        }
      }
      frontier = nextFrontier;
    }

    // 3. Get evidence if requested
    if (query.includeEvidence) {
      for (const nodeId of nodeIds.slice(0, 10)) {  // Limit evidence queries
        const evidence = akms.getEvidenceFor(nodeId);
        for (const ev of evidence) {
          items.push(this.createContextItem(ev.id, 'evidence', ev, 0.8));
        }
      }
    }

    // 4. Get memories if requested
    if (query.includeMemory) {
      const memories = akms.findEntities({ memoryType: 'experience' })
        .filter(m => m.domain === query.domain)
        .slice(0, 5);
      for (const mem of memories) {
        items.push(this.createContextItem(mem.id, 'memory', mem, 0.7));
      }
    }

    const retrievalTime = now() - startTime;

    return {
      items,
      subgraph: { nodes: nodeIds, edges },
      confidence: this.calculateOverallConfidence(items),
      retrievalTime,
    };
  }

  private createContextItem(id: string, type: ContextItem['type'], data: unknown, relevance: number): ContextItem {
    return {
      id, tier: 'warm', type, data, relevance,
      lastAccessed: now(), accessCount: 0,
      ttl: RUNTIME_LIMITS.WARM_TTL,
    };
  }

  private calculateRelevance(entity: Entity, query: RetrievalQuery): number {
    let score = 0;
    
    // Domain match
    if (entity.domain === query.domain) score += 0.4;
    
    // Keyword match
    for (const keyword of query.keywords) {
      if (entity.name.toLowerCase().includes(keyword.toLowerCase())) score += 0.2;
      if (entity.content.toLowerCase().includes(keyword.toLowerCase())) score += 0.1;
      if (entity.tags.some(t => t.toLowerCase().includes(keyword.toLowerCase()))) score += 0.1;
    }
    
    // Type match
    if (entity.type === query.taskType) score += 0.1;
    
    // Confidence bonus
    score += entity.confidence * 0.1;
    
    return Math.min(1.0, score);
  }

  private calculateOverallConfidence(items: ContextItem[]): number {
    if (items.length === 0) return 0;
    const sum = items.reduce((acc, item) => acc + item.relevance, 0);
    return sum / items.length;
  }
}

// ═══════════════════════════════════════════════
// SHARED CAPABILITY REGISTRY
// ═══════════════════════════════════════════════

export class SharedCapabilityRegistry {
  private capabilities: Map<string, SharedCapability> = new Map();

  /**
   * Register a capability as shared across professions.
   */
  register(
    name: string,
    type: SharedCapability['type'],
    domain: KnowledgeDomain,
    usedByProfessions: string[],
  ): SharedCapability {
    const id = uid();
    const cap: SharedCapability = {
      id, name, type, domain,
      usedByProfessions,
      referenceCount: usedByProfessions.length,
      lastUsed: now(),
      avgRelevance: 0.5,
    };
    this.capabilities.set(id, cap);
    return cap;
  }

  /**
   * Find shared capabilities for a given domain.
   */
  findByDomain(domain: KnowledgeDomain): SharedCapability[] {
    return Array.from(this.capabilities.values())
      .filter(c => c.domain === domain);
  }

  /**
   * Find capabilities used by a specific profession.
   */
  findByProfession(professionId: string): SharedCapability[] {
    return Array.from(this.capabilities.values())
      .filter(c => c.usedByProfessions.includes(professionId));
  }

  /**
   * Get most referenced capabilities.
   */
  getMostReferenced(limit: number = 10): SharedCapability[] {
    return Array.from(this.capabilities.values())
      .sort((a, b) => b.referenceCount - a.referenceCount)
      .slice(0, limit);
  }

  /**
   * Calculate deduplication savings.
   */
  getDeduplicationStats(): {
    totalReferences: number;
    uniqueCapabilities: number;
    savingsPercent: number;
  } {
    const caps = Array.from(this.capabilities.values());
    const totalReferences = caps.reduce((sum, c) => sum + c.referenceCount, 0);
    const uniqueCapabilities = caps.length;
    const savingsPercent = totalReferences > 0
      ? ((totalReferences - uniqueCapabilities) / totalReferences) * 100
      : 0;
    return { totalReferences, uniqueCapabilities, savingsPercent };
  }
}

// ═══════════════════════════════════════════════
// TASK CONTEXT BUILDER
// ═══════════════════════════════════════════════

export class TaskContextBuilder {
  private contextManager: ContextManager;
  private retrievalEngine: RetrievalEngine;
  private capabilityRegistry: SharedCapabilityRegistry;

  constructor(
    contextManager: ContextManager,
    retrievalEngine: RetrievalEngine,
    capabilityRegistry: SharedCapabilityRegistry,
  ) {
    this.contextManager = contextManager;
    this.retrievalEngine = retrievalEngine;
    this.capabilityRegistry = capabilityRegistry;
  }

  /**
   * Build complete context for a task.
   * This is the main entry point for task execution.
   */
  buildContext(taskId: string): TaskContext | null {
    const task = pcm.getTask(taskId);
    if (!task) return null;

    // 1. Create retrieval query
    const query: RetrievalQuery = {
      taskId,
      domain: task.domain,
      taskType: task.complexity,
      keywords: [task.name, task.description],
      depth: 2,
      maxItems: RUNTIME_LIMITS.MAX_SUBGRAPH_NODES,
      includeEvidence: true,
      includeMemory: true,
      includeProfessions: true,
    };

    // 2. Retrieve context
    const result = this.retrievalEngine.retrieve(query);

    // 3. Get subgraph
    const subgraph = this.getSubgraph(taskId, RUNTIME_LIMITS.MAX_SUBGRAPH_DEPTH);

    // 4. Build verification chain
    const verificationChain = this.buildVerificationChain(task);

    // 5. Calculate evidence status
    const evidenceStatus = this.calculateEvidenceStatus(task);

    // 6. Create snapshot
    const snapshot = this.contextManager.createSnapshot(taskId);

    return {
      taskId,
      taskName: task.name,
      domain: task.domain,
      requiredKnowledge: task.requiredKnowledge,
      requiredSkills: task.requiredSkills,
      requiredTools: task.requiredTools,
      context: snapshot,
      subgraph,
      evidenceStatus,
      verificationChain,
      confidence: result.confidence,
    };
  }

  private getSubgraph(taskId: string, depth: number): { nodes: Entity[]; relations: Relation[] } {
    const nodes: Entity[] = [];
    const relations: Relation[] = [];
    const visited = new Set<string>();
    let frontier = [taskId];

    for (let d = 0; d < depth && frontier.length > 0; d++) {
      const next: string[] = [];
      for (const nodeId of frontier) {
        const entity = akms.getEntity(nodeId);
        if (!entity || visited.has(nodeId)) continue;
        visited.add(nodeId);
        nodes.push(entity);

        const neighbors = akms.getNeighbors(nodeId, 1);
        for (const { entity: neighbor, relation } of neighbors) {
          if (!visited.has(neighbor.id)) {
            relations.push(relation);
            next.push(neighbor.id);
          }
        }
      }
      frontier = next;
    }

    return { nodes, relations };
  }

  private buildVerificationChain(task: Task): VerificationStep[] {
    const chain: VerificationStep[] = [];
    
    for (const v of task.verification) {
      chain.push({
        order: chain.length + 1,
        name: v.name,
        method: v.method,
        status: 'pending',
      });
    }

    return chain;
  }

  private calculateEvidenceStatus(task: Task): EvidenceStatus {
    // Check task's own verification
    if (task.verification.length === 0) return 'unverified';
    
    // Check if any verification has passed
    const hasPassed = task.verification.some(v => v.checkType !== '');
    if (!hasPassed) return 'claimed';
    
    // Check for evidence
    const evidence = akms.getEvidenceFor(task.id);
    if (evidence.length === 0) return 'sourced';
    
    // Check evidence verification status
    const verified = evidence.filter(e => e.confidence > 0.8);
    if (verified.length === evidence.length) return 'verified';
    
    return 'cross_checked';
  }

  /**
   * Get context summary for LLM prompt.
   * This is what gets sent to the LLM — minimal and relevant.
   */
  getContextSummary(context: TaskContext): string {
    const parts: string[] = [];
    
    parts.push(`Task: ${context.taskName}`);
    parts.push(`Domain: ${context.domain}`);
    parts.push(`Confidence: ${(context.confidence * 100).toFixed(0)}%`);
    parts.push(`Evidence Status: ${context.evidenceStatus}`);
    parts.push('');
    
    parts.push('Required Knowledge:');
    for (const k of context.requiredKnowledge) {
      const knowledge = pcm.getKnowledge(k);
      if (knowledge) parts.push(`  - ${knowledge.name}`);
    }
    
    parts.push('Required Skills:');
    for (const s of context.requiredSkills) {
      const skill = pcm.getSkill(s);
      if (skill) parts.push(`  - ${skill.name}`);
    }
    
    parts.push('Required Tools:');
    for (const t of context.requiredTools) {
      const tool = pcm.getTool(t);
      if (tool) parts.push(`  - ${tool.name}`);
    }
    
    parts.push('');
    parts.push('Verification Chain:');
    for (const v of context.verificationChain) {
      parts.push(`  ${v.order}. ${v.name} (${v.method}) - ${v.status}`);
    }
    
    parts.push('');
    parts.push(`Subgraph: ${context.subgraph.nodes.length} nodes, ${context.subgraph.relations.length} relations`);
    
    return parts.join('\n');
  }
}

// ═══════════════════════════════════════════════
// RUNTIME STORE
// ═══════════════════════════════════════════════

export class RuntimeStore {
  contextManager: ContextManager;
  retrievalEngine: RetrievalEngine;
  capabilityRegistry: SharedCapabilityRegistry;
  taskContextBuilder: TaskContextBuilder;

  constructor() {
    this.contextManager = new ContextManager();
    this.retrievalEngine = new RetrievalEngine(this.contextManager);
    this.capabilityRegistry = new SharedCapabilityRegistry();
    this.taskContextBuilder = new TaskContextBuilder(
      this.contextManager,
      this.retrievalEngine,
      this.capabilityRegistry,
    );
    this.registerSharedCapabilities();
  }

  private registerSharedCapabilities(): void {
    // Register shared capabilities across professions
    const professions = pcm.getAllProfessions();
    
    // Find shared knowledge
    const knowledgeMap = new Map<string, string[]>();
    const skillMap = new Map<string, string[]>();
    const toolMap = new Map<string, string[]>();
    
    for (const prof of professions) {
      // Get all tasks for this profession
      const capMap = pcm.getProfessionCapabilityMap(prof.id);
      if (!capMap) continue;
      
      for (const task of capMap.tasks) {
        for (const k of task.requiredKnowledge) {
          const list = knowledgeMap.get(k) || [];
          if (!list.includes(prof.id)) list.push(prof.id);
          knowledgeMap.set(k, list);
        }
        for (const s of task.requiredSkills) {
          const list = skillMap.get(s) || [];
          if (!list.includes(prof.id)) list.push(prof.id);
          skillMap.set(s, list);
        }
        for (const t of task.requiredTools) {
          const list = toolMap.get(t) || [];
          if (!list.includes(prof.id)) list.push(prof.id);
          toolMap.set(t, list);
        }
      }
    }
    
    // Register shared capabilities
    for (const [kId, profIds] of knowledgeMap) {
      if (profIds.length > 1) {
        const knowledge = pcm.getKnowledge(kId);
        if (knowledge) {
          this.capabilityRegistry.register(knowledge.name, 'knowledge', knowledge.domain, profIds);
        }
      }
    }
    
    for (const [sId, profIds] of skillMap) {
      if (profIds.length > 1) {
        const skill = pcm.getSkill(sId);
        if (skill) {
          this.capabilityRegistry.register(skill.name, 'skill', skill.domain, profIds);
        }
      }
    }
    
    for (const [tId, profIds] of toolMap) {
      if (profIds.length > 1) {
        const tool = pcm.getTool(tId);
        if (tool) {
          this.capabilityRegistry.register(tool.name, 'tool', 'general', profIds);
        }
      }
    }
  }

  /**
   * Get runtime statistics.
   */
  getStats(): RuntimeStats {
    const contextStats = this.contextManager.getStats();
    const dedupStats = this.capabilityRegistry.getDeduplicationStats();
    
    return {
      totalEntities: akms.getAllEntities().length,
      totalRelations: akms.getAllRelations().length,
      totalTasks: pcm.getAllTasks().length,
      totalProfessions: pcm.getAllProfessions().length,
      totalCompetencies: 0,  // Would need to count
      totalArtifacts: gcm.getAllArtifacts().length,
      hotContextSize: contextStats.hot,
      warmContextSize: contextStats.warm,
      coldContextSize: contextStats.cold,
      avgRetrievalTime: 0,
      avgConfidence: 0,
      sharedCapabilities: dedupStats.uniqueCapabilities,
      crossProfessionReferences: dedupStats.totalReferences,
    };
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const runtime = new RuntimeStore();
