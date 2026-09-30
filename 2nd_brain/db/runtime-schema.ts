/**
 * Runtime Architecture — Lightweight inference from deep knowledge
 * 
 * Principles:
 *   DEEP DATA → STRUCTURED KNOWLEDGE → GRAPH RELATIONS
 *   → SELECTIVE RETRIEVAL → TASK-SPECIFIC CONTEXT
 *   → MINIMAL REASONING → SPECIALIZED TOOL
 *   → OBJECTIVE VERIFICATION → EVIDENCE
 *   → TRUSTED ARTIFACT
 * 
 * Context Tiers:
 *   HOT: Current task, current project, active context
 *   WARM: Relevant knowledge, relevant skills, relevant memory
 *   COLD: Entire knowledge base, old projects, archived experiences
 * 
 * The agent NEVER loads the entire DB. It loads only what's needed.
 */

import type { KnowledgeDomain, Entity, Relation } from './akms-schema';
import type { Profession, Competency, Task, Skill, Tool, Knowledge } from './pcm-schema';
import type { Artifact } from './gcm-schema';

// ═══════════════════════════════════════════════
// EVIDENCE STATUS
// ═══════════════════════════════════════════════

export type EvidenceStatus =
  | 'unverified'        // No verification done
  | 'claimed'           // Agent claims it's true
  | 'sourced'           // Source provided
  | 'cross_checked'     // Multiple sources agree
  | 'calculated'        // Mathematical/algorithmic verification
  | 'tested'            // Unit/integration tests pass
  | 'simulated'         // Simulation confirms
  | 'verified'          // Formal verification
  | 'real_world_verified';  // Tested in real environment

export const EVIDENCE_STATUS_CONFIG: Record<EvidenceStatus, {
  color: string;
  icon: string;
  label: string;
  confidence: number;
  description: string;
}> = {
  unverified:          { color: '#71717a', icon: '?', label: 'Unverified', confidence: 0.3, description: 'No verification done' },
  claimed:             { color: '#f59e0b', icon: '💭', label: 'Claimed', confidence: 0.4, description: 'Agent claims true' },
  sourced:             { color: '#3b82f6', icon: '📖', label: 'Sourced', confidence: 0.6, description: 'Source provided' },
  cross_checked:       { color: '#8b5cf6', icon: '🔗', label: 'Cross-checked', confidence: 0.7, description: 'Multiple sources agree' },
  calculated:          { color: '#06b6d4', icon: '🔢', label: 'Calculated', confidence: 0.8, description: 'Mathematical verification' },
  tested:              { color: '#10b981', icon: '✓', label: 'Tested', confidence: 0.85, description: 'Tests pass' },
  simulated:           { color: '#14b8a6', icon: '🔬', label: 'Simulated', confidence: 0.85, description: 'Simulation confirms' },
  verified:            { color: '#059669', icon: '✅', label: 'Verified', confidence: 0.95, description: 'Formal verification' },
  real_world_verified: { color: '#047857', icon: '🏆', label: 'Real-world Verified', confidence: 0.99, description: 'Tested in real environment' },
};

// ═══════════════════════════════════════════════
// CONTEXT TIERS
// ═══════════════════════════════════════════════

export type ContextTier = 'hot' | 'warm' | 'cold';

export interface ContextItem {
  id: string;
  tier: ContextTier;
  type: 'task' | 'knowledge' | 'skill' | 'tool' | 'artifact' | 'entity' | 'memory' | 'evidence' | 'competency' | 'profession';
  data: unknown;
  relevance: number;        // 0..1
  lastAccessed: number;
  accessCount: number;
  ttl: number;              // Time to live in ms
}

export interface ContextSnapshot {
  timestamp: number;
  taskId: string;
  hot: ContextItem[];
  warm: ContextItem[];
  cold: ContextItem[];
  totalSize: number;        // Approximate token count
  retrievalTime: number;    // ms
}

// ═══════════════════════════════════════════════
// RETRIEVAL QUERY
// ═══════════════════════════════════════════════

export interface RetrievalQuery {
  taskId: string;
  domain: KnowledgeDomain;
  taskType: string;
  keywords: string[];
  depth: number;            // How deep to traverse
  maxItems: number;         // Max items to retrieve
  includeEvidence: boolean;
  includeMemory: boolean;
  includeProfessions: boolean;
}

export interface RetrievalResult {
  items: ContextItem[];
  subgraph: {
    nodes: string[];
    edges: [string, string][];
  };
  confidence: number;
  retrievalTime: number;
}

// ═══════════════════════════════════════════════
// SHARED CAPABILITY
// ═══════════════════════════════════════════════

export interface SharedCapability {
  id: string;
  name: string;
  type: 'knowledge' | 'skill' | 'tool' | 'competency';
  domain: KnowledgeDomain;
  
  // Shared across professions
  usedByProfessions: string[];  // Profession IDs
  
  // Reference count
  referenceCount: number;
  
  // Metadata
  lastUsed: number;
  avgRelevance: number;
}

// ═══════════════════════════════════════════════
// TASK CONTEXT
// ═══════════════════════════════════════════════

export interface TaskContext {
  taskId: string;
  taskName: string;
  domain: KnowledgeDomain;
  
  // Required capabilities (from PCM)
  requiredKnowledge: string[];
  requiredSkills: string[];
  requiredTools: string[];
  
  // Retrieved context
  context: ContextSnapshot;
  
  // Subgraph for this task
  subgraph: {
    nodes: Entity[];
    relations: Relation[];
  };
  
  // Evidence status
  evidenceStatus: EvidenceStatus;
  
  // Verification chain
  verificationChain: VerificationStep[];
  
  // Confidence
  confidence: number;
}

export interface VerificationStep {
  order: number;
  name: string;
  method: string;
  status: 'pending' | 'passed' | 'failed' | 'skipped';
  evidence?: string;
}

// ═══════════════════════════════════════════════
// GRAPH TRAVERSAL
// ═══════════════════════════════════════════════

export interface GraphTraversalOptions {
  startNode: string;
  maxDepth: number;
  maxNodes: number;
  relationTypes: string[];
  domainFilter?: KnowledgeDomain[];
  typeFilter?: string[];
  relevanceThreshold: number;
}

export interface TraversalResult {
  nodes: { id: string; depth: number; relevance: number }[];
  edges: { source: string; target: string; type: string; weight: number }[];
}

// ═══════════════════════════════════════════════
// RUNTIME STATS
// ═══════════════════════════════════════════════

export interface RuntimeStats {
  totalEntities: number;
  totalRelations: number;
  totalTasks: number;
  totalProfessions: number;
  totalCompetencies: number;
  totalArtifacts: number;
  
  hotContextSize: number;
  warmContextSize: number;
  coldContextSize: number;
  
  avgRetrievalTime: number;
  avgConfidence: number;
  
  sharedCapabilities: number;
  crossProfessionReferences: number;
}

// ═══════════════════════════════════════════════
// OPTIMIZATION CONSTANTS
// ═══════════════════════════════════════════════

export const RUNTIME_LIMITS = {
  /** Maximum items in HOT context */
  MAX_HOT_ITEMS: 20,
  /** Maximum items in WARM context */
  MAX_WARM_ITEMS: 50,
  /** Maximum items in COLD context (lazy loaded) */
  MAX_COLD_ITEMS: 200,
  
  /** HOT tier TTL (5 minutes) */
  HOT_TTL: 5 * 60 * 1000,
  /** WARM tier TTL (30 minutes) */
  WARM_TTL: 30 * 60 * 1000,
  /** COLD tier TTL (24 hours) */
  COLD_TTL: 24 * 60 * 60 * 1000,
  
  /** Maximum subgraph nodes for task */
  MAX_SUBGRAPH_NODES: 50,
  /** Maximum subgraph depth */
  MAX_SUBGRAPH_DEPTH: 3,
  
  /** Minimum relevance threshold */
  MIN_RELEVANCE: 0.3,
  
  /** Maximum context tokens (approximate) */
  MAX_CONTEXT_TOKENS: 8000,
  
  /** Graph traversal branching factor */
  BRANCHING_FACTOR: 10,
} as const;

// ═══════════════════════════════════════════════
// VISUAL CONFIG
// ═══════════════════════════════════════════════

export const CONTEXT_TIER_CONFIG: Record<ContextTier, { color: string; icon: string; label: string; description: string }> = {
  hot:   { color: '#dc2626', icon: '🔴', label: 'HOT', description: 'Current task, project, active context' },
  warm:  { color: '#f59e0b', icon: '🟡', label: 'WARM', description: 'Relevant knowledge, skills, memory' },
  cold:  { color: '#3b82f6', icon: '🔵', label: 'COLD', description: 'Entire knowledge base, archived data' },
};
