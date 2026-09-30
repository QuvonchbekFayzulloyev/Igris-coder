/**
 * Task Result Connector — Links task outputs to the broader knowledge system
 * 
 * Connects:
 *   - Task Outputs → GCM Artifacts
 *   - Task Verification → Evidence entries
 *   - Task Execution → Memory entries
 *   - Task Dependencies → Task graph
 *   - Task Results → Knowledge updates
 * 
 * Philosophy:
 *   Every task result must be traceable, verifiable, and connected
 *   to the knowledge graph. No isolated outputs.
 */

import type { KnowledgeDomain } from './akms-schema';
import type { ArtifactType, ArtifactFormat } from './gcm-schema';
import type { EvidenceStatus } from './runtime-schema';

// ═══════════════════════════════════════════════
// TASK RESULT TYPES
// ═══════════════════════════════════════════════

export type TaskResultStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';

export interface TaskResult {
  id: string;
  taskId: string;
  taskName: string;
  domain: KnowledgeDomain;
  
  // Execution
  status: TaskResultStatus;
  startedAt: number;
  completedAt?: number;
  durationMs?: number;
  
  // Outputs → Artifacts
  outputs: TaskOutput[];
  
  // Verification → Evidence
  verificationChain: VerificationResult[];
  evidenceStatus: EvidenceStatus;
  
  // Memory
  memoryEntry?: TaskMemoryEntry;
  
  // Learning
  lessonsLearned: string[];
  failureModesEncountered: string[];
  
  // Connections
  relatedArtifacts: string[];  // GCM artifact IDs
  relatedEvidence: string[];   // Evidence IDs
  relatedMemory: string[];     // Memory IDs
  
  // Quality
  qualityScore: number;        // 0..1
  confidence: number;          // 0..1
  
  // Context
  inputs: TaskInput[];
  toolsUsed: string[];
  skillsUsed: string[];
}

export interface TaskOutput {
  name: string;
  type: 'file' | 'data' | 'parameter' | 'decision';
  format?: string;
  description: string;
  
  // Link to artifact
  artifactId?: string;
  artifactPath?: string;
  
  // Quality
  quality: number;             // 0..1
  validated: boolean;
  
  // Metadata
  sizeBytes?: number;
  checksum?: string;
}

export interface TaskInput {
  name: string;
  type: string;
  source: string;              // Where it came from
  artifactId?: string;
}

export interface VerificationResult {
  order: number;
  name: string;
  method: string;
  checkType: string;
  
  // Result
  status: 'pending' | 'passed' | 'failed' | 'skipped';
  passed: boolean;
  
  // Evidence
  evidenceId?: string;
  evidenceStatus: EvidenceStatus;
  
  // Details
  expectedResults: string[];
  actualResults?: string[];
  notes?: string;
  
  // Timestamp
  executedAt?: number;
  durationMs?: number;
}

export interface TaskMemoryEntry {
  id: string;
  taskId: string;
  taskName: string;
  
  // What happened
  summary: string;
  whatWorked: string[];
  whatFailed: string[];
  
  // Learning
  insights: string[];
  recommendations: string[];
  
  // Context
  domain: KnowledgeDomain;
  toolsUsed: string[];
  durationMs: number;
  
  // Timestamp
  recordedAt: number;
}

// ═══════════════════════════════════════════════
// TASK DEPENDENCY GRAPH
// ═══════════════════════════════════════════════

export interface TaskDependency {
  sourceTaskId: string;
  targetTaskId: string;
  type: DependencyType;
  description: string;
}

export type DependencyType =
  | 'requires'        // Target must complete before source
  | 'feeds_into'      // Source output is target input
  | 'depends_on'      // General dependency
  | 'blocks'          // Source blocks target
  | 'enables';        // Source enables target

export interface TaskGraph {
  nodes: TaskGraphNode[];
  edges: TaskGraphEdge[];
  criticalPath: string[];
  estimatedDuration: number;
}

export interface TaskGraphNode {
  taskId: string;
  taskName: string;
  domain: KnowledgeDomain;
  status: TaskResultStatus;
  duration: number;
  critical: boolean;
}

export interface TaskGraphEdge {
  source: string;
  target: string;
  type: DependencyType;
  weight: number;
}

// ═══════════════════════════════════════════════
// QUALITY ASSESSMENT
// ═══════════════════════════════════════════════

export interface QualityAssessment {
  taskId: string;
  overallScore: number;        // 0..1
  
  // Dimensions
  completeness: number;        // All outputs produced?
  correctness: number;         // Verification passed?
  timeliness: number;          // Completed on time?
  documentation: number;       // Well documented?
  
  // Issues
  issues: QualityIssue[];
  
  // Recommendations
  recommendations: string[];
}

export interface QualityIssue {
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  description: string;
  recommendation: string;
}

// ═══════════════════════════════════════════════
// TASK RESULT CONNECTOR
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `trc_${Date.now().toString(36)}_${_nextId}`;
}

export class TaskResultConnector {
  private results: Map<string, TaskResult> = new Map();
  private dependencies: TaskDependency[] = [];
  private memories: Map<string, TaskMemoryEntry> = new Map();
  private listeners: Array<() => void> = [];

  // ─── CREATE RESULT ───────────────────────

  createResult(
    taskId: string,
    taskName: string,
    domain: KnowledgeDomain,
    inputs: TaskInput[],
  ): TaskResult {
    const id = uid();
    const result: TaskResult = {
      id,
      taskId,
      taskName,
      domain,
      status: 'pending',
      startedAt: Date.now(),
      outputs: [],
      verificationChain: [],
      evidenceStatus: 'unverified',
      lessonsLearned: [],
      failureModesEncountered: [],
      relatedArtifacts: [],
      relatedEvidence: [],
      relatedMemory: [],
      qualityScore: 0,
      confidence: 0,
      inputs,
      toolsUsed: [],
      skillsUsed: [],
    };
    this.results.set(id, result);
    this.notify();
    return result;
  }

  // ─── UPDATE RESULT ───────────────────────

  startExecution(resultId: string): void {
    const result = this.results.get(resultId);
    if (result) {
      result.status = 'in_progress';
      result.startedAt = Date.now();
      this.notify();
    }
  }

  addOutput(
    resultId: string,
    output: Omit<TaskOutput, 'quality' | 'validated'>,
  ): void {
    const result = this.results.get(resultId);
    if (result) {
      result.outputs.push({
        ...output,
        quality: 0,
        validated: false,
      });
      this.notify();
    }
  }

  completeVerification(
    resultId: string,
    verification: Omit<VerificationResult, 'passed' | 'evidenceStatus' | 'executedAt'>,
    passed: boolean,
    evidenceStatus: EvidenceStatus = 'unverified',
  ): void {
    const result = this.results.get(resultId);
    if (result) {
      const vResult: VerificationResult = {
        ...verification,
        passed,
        evidenceStatus,
        executedAt: Date.now(),
      };
      result.verificationChain.push(vResult);
      
      // Update evidence status based on verification
      if (passed) {
        result.evidenceStatus = this.getNextEvidenceStatus(result.evidenceStatus);
      }
      
      this.notify();
    }
  }

  private getNextEvidenceStatus(current: EvidenceStatus): EvidenceStatus {
    const chain: EvidenceStatus[] = [
      'unverified', 'claimed', 'sourced', 'cross_checked',
      'calculated', 'tested', 'simulated', 'verified', 'real_world_verified',
    ];
    const idx = chain.indexOf(current);
    return idx < chain.length - 1 ? chain[idx + 1] : current;
  }

  completeExecution(
    resultId: string,
    status: 'completed' | 'failed',
    lessonsLearned: string[] = [],
    failureModes: string[] = [],
  ): void {
    const result = this.results.get(resultId);
    if (result) {
      result.status = status;
      result.completedAt = Date.now();
      result.durationMs = result.completedAt - result.startedAt;
      result.lessonsLearned = lessonsLearned;
      result.failureModesEncountered = failureModes;
      
      // Calculate quality score
      result.qualityScore = this.calculateQualityScore(result);
      result.confidence = this.calculateConfidence(result);
      
      this.notify();
    }
  }

  private calculateQualityScore(result: TaskResult): number {
    let score = 0;
    
    // Completeness: all outputs produced
    const expectedOutputs = result.inputs.length > 0 ? result.inputs.length : 1;
    const actualOutputs = result.outputs.length;
    score += (actualOutputs / expectedOutputs) * 0.3;
    
    // Verification: all checks passed
    const totalChecks = result.verificationChain.length;
    const passedChecks = result.verificationChain.filter(v => v.passed).length;
    score += (totalChecks > 0 ? passedChecks / totalChecks : 0) * 0.4;
    
    // Evidence status
    const evidenceScores: Record<EvidenceStatus, number> = {
      unverified: 0.1, claimed: 0.2, sourced: 0.3, cross_checked: 0.4,
      calculated: 0.5, tested: 0.6, simulated: 0.7, verified: 0.8,
      real_world_verified: 1.0,
    };
    score += evidenceScores[result.evidenceStatus] * 0.3;
    
    return Math.min(1.0, score);
  }

  private calculateConfidence(result: TaskResult): number {
    if (result.verificationChain.length === 0) return 0.3;
    
    const passedRatio = result.verificationChain.filter(v => v.passed).length / result.verificationChain.length;
    const evidenceBonus = result.evidenceStatus === 'verified' ? 0.2 : 0;
    
    return Math.min(1.0, passedRatio * 0.7 + evidenceBonus + 0.1);
  }

  // ─── MEMORY ──────────────────────────────

  recordMemory(
    resultId: string,
    summary: string,
    whatWorked: string[],
    whatFailed: string[],
    insights: string[],
    recommendations: string[],
  ): TaskMemoryEntry {
    const result = this.results.get(resultId);
    if (!result) throw new Error('Result not found');
    
    const memory: TaskMemoryEntry = {
      id: uid(),
      taskId: result.taskId,
      taskName: result.taskName,
      summary,
      whatWorked,
      whatFailed,
      insights,
      recommendations,
      domain: result.domain,
      toolsUsed: result.toolsUsed,
      durationMs: result.durationMs || 0,
      recordedAt: Date.now(),
    };
    
    this.memories.set(memory.id, memory);
    result.memoryEntry = memory;
    result.relatedMemory.push(memory.id);
    
    this.notify();
    return memory;
  }

  // ─── DEPENDENCIES ────────────────────────

  addDependency(
    sourceTaskId: string,
    targetTaskId: string,
    type: DependencyType,
    description: string = '',
  ): void {
    const dep: TaskDependency = {
      sourceTaskId,
      targetTaskId,
      type,
      description,
    };
    this.dependencies.push(dep);
    this.notify();
  }

  getDependencies(taskId: string): TaskDependency[] {
    return this.dependencies.filter(d => d.sourceTaskId === taskId || d.targetTaskId === taskId);
  }

  getTaskGraph(): TaskGraph {
    const taskIds = new Set<string>();
    for (const dep of this.dependencies) {
      taskIds.add(dep.sourceTaskId);
      taskIds.add(dep.targetTaskId);
    }
    
    const nodes: TaskGraphNode[] = Array.from(taskIds).map(id => {
      const result = this.getResultByTaskId(id);
      return {
        taskId: id,
        taskName: result?.taskName || 'Unknown',
        domain: result?.domain || 'general',
        status: result?.status || 'pending',
        duration: result?.durationMs || 0,
        critical: false,
      };
    });
    
    const edges: TaskGraphEdge[] = this.dependencies.map(dep => ({
      source: dep.sourceTaskId,
      target: dep.targetTaskId,
      type: dep.type,
      weight: 1,
    }));
    
    // Find critical path (simplified)
    const criticalPath = this.findCriticalPath(nodes, edges);
    
    // Mark critical nodes
    for (const node of nodes) {
      node.critical = criticalPath.includes(node.taskId);
    }
    
    return {
      nodes,
      edges,
      criticalPath,
      estimatedDuration: nodes.reduce((sum, n) => sum + n.duration, 0),
    };
  }

  private findCriticalPath(nodes: TaskGraphNode[], edges: TaskGraphEdge[]): string[] {
    // Simplified critical path — longest duration path
    if (nodes.length === 0) return [];
    
    // Find nodes with no incoming edges (start nodes)
    const hasIncoming = new Set(edges.map(e => e.target));
    const startNodes = nodes.filter(n => !hasIncoming.has(n.taskId));
    
    if (startNodes.length === 0) return [nodes[0].taskId];
    
    // Simple: return path with longest total duration
    let longestPath: string[] = [];
    let longestDuration = 0;
    
    for (const start of startNodes) {
      const path = this.dfsPath(start.taskId, nodes, edges, new Set());
      const duration = path.reduce((sum, id) => {
        const node = nodes.find(n => n.taskId === id);
        return sum + (node?.duration || 0);
      }, 0);
      
      if (duration > longestDuration) {
        longestDuration = duration;
        longestPath = path;
      }
    }
    
    return longestPath;
  }

  private dfsPath(
    current: string,
    nodes: TaskGraphNode[],
    edges: TaskGraphEdge[],
    visited: Set<string>,
  ): string[] {
    if (visited.has(current)) return [current];
    visited.add(current);
    
    const outEdges = edges.filter(e => e.source === current);
    if (outEdges.length === 0) return [current];
    
    let longestPath: string[] = [];
    for (const edge of outEdges) {
      const path = this.dfsPath(edge.target, nodes, edges, new Set(visited));
      if (path.length > longestPath.length) {
        longestPath = path;
      }
    }
    
    return [current, ...longestPath];
  }

  // ─── QUALITY ASSESSMENT ──────────────────

  assessQuality(resultId: string): QualityAssessment {
    const result = this.results.get(resultId);
    if (!result) throw new Error('Result not found');
    
    const issues: QualityIssue[] = [];
    const recommendations: string[] = [];
    
    // Check completeness
    const completeness = result.outputs.length > 0 ? 1.0 : 0.0;
    if (completeness < 1.0) {
      issues.push({
        severity: 'high',
        category: 'completeness',
        description: 'Not all expected outputs were produced',
        recommendation: 'Review task requirements and ensure all outputs are generated',
      });
    }
    
    // Check verification
    const totalChecks = result.verificationChain.length;
    const passedChecks = result.verificationChain.filter(v => v.passed).length;
    const correctness = totalChecks > 0 ? passedChecks / totalChecks : 0;
    
    if (correctness < 1.0) {
      issues.push({
        severity: 'high',
        category: 'correctness',
        description: `${totalChecks - passedChecks} verification checks failed`,
        recommendation: 'Review failed checks and address issues',
      });
    }
    
    // Check timeliness
    const timeliness = result.status === 'completed' ? 1.0 : 0.5;
    
    // Check documentation
    const documentation = result.lessonsLearned.length > 0 ? 1.0 : 0.5;
    if (documentation < 1.0) {
      recommendations.push('Document lessons learned for future reference');
    }
    
    // Overall score
    const overallScore = (completeness * 0.3 + correctness * 0.4 + timeliness * 0.2 + documentation * 0.1);
    
    return {
      taskId: result.taskId,
      overallScore,
      completeness,
      correctness,
      timeliness,
      documentation,
      issues,
      recommendations,
    };
  }

  // ─── QUERIES ─────────────────────────────

  getResult(id: string): TaskResult | undefined {
    return this.results.get(id);
  }

  getResultByTaskId(taskId: string): TaskResult | undefined {
    return Array.from(this.results.values()).find(r => r.taskId === taskId);
  }

  getAllResults(): TaskResult[] {
    return Array.from(this.results.values());
  }

  getResultsByDomain(domain: KnowledgeDomain): TaskResult[] {
    return Array.from(this.results.values()).filter(r => r.domain === domain);
  }

  getResultsByStatus(status: TaskResultStatus): TaskResult[] {
    return Array.from(this.results.values()).filter(r => r.status === status);
  }

  getMemories(): TaskMemoryEntry[] {
    return Array.from(this.memories.values());
  }

  getMemoriesByDomain(domain: KnowledgeDomain): TaskMemoryEntry[] {
    return Array.from(this.memories.values()).filter(m => m.domain === domain);
  }

  // ─── STATS ───────────────────────────────

  getStats(): {
    totalResults: number;
    completed: number;
    failed: number;
    pending: number;
    avgQuality: number;
    avgConfidence: number;
    totalMemories: number;
    totalDependencies: number;
  } {
    const results = Array.from(this.results.values());
    return {
      totalResults: results.length,
      completed: results.filter(r => r.status === 'completed').length,
      failed: results.filter(r => r.status === 'failed').length,
      pending: results.filter(r => r.status === 'pending').length,
      avgQuality: results.length > 0 ? results.reduce((s, r) => s + r.qualityScore, 0) / results.length : 0,
      avgConfidence: results.length > 0 ? results.reduce((s, r) => s + r.confidence, 0) / results.length : 0,
      totalMemories: this.memories.size,
      totalDependencies: this.dependencies.length,
    };
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
    results: TaskResult[];
    dependencies: TaskDependency[];
    memories: TaskMemoryEntry[];
  } {
    return {
      results: Array.from(this.results.values()),
      dependencies: this.dependencies,
      memories: Array.from(this.memories.values()),
    };
  }

  importData(data: {
    results: TaskResult[];
    dependencies: TaskDependency[];
    memories: TaskMemoryEntry[];
  }): void {
    this.results.clear();
    this.dependencies = data.dependencies;
    this.memories.clear();
    
    for (const result of data.results) {
      this.results.set(result.id, result);
    }
    for (const memory of data.memories) {
      this.memories.set(memory.id, memory);
    }
    
    this.notify();
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const taskResultConnector = new TaskResultConnector();
