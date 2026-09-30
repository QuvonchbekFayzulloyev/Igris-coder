/**
 * Professional Capability Model (PCM) — Universal profession/task/skill architecture
 * 
 * Architecture:
 *   Profession → Specialization → Competency → Task → Workflow
 *   ├── Knowledge (what to know)
 *   ├── Skills (how to do)
 *   ├── Tools (what to use)
 *   ├── Inputs (what's needed)
 *   ├── Outputs (what's produced)
 *   ├── Standards (rules to follow)
 *   ├── Constraints (limits)
 *   ├── Verification (how to check)
 *   └── Failure Modes (what can go wrong)
 * 
 * Philosophy:
 *   Knowledge tells the agent what is true.
 *   Skill tells it how to do something.
 *   Tool lets it do it.
 *   Task tells it what needs to be done.
 *   Workflow tells it in what order.
 *   Profession tells it which capabilities belong together.
 *   Evidence tells it why the result can be trusted.
 *   Memory tells it what happened before.
 */

import type { KnowledgeDomain, Entity, EntityType } from './akms-schema';

// ═══════════════════════════════════════════════
// CORE TYPES
// ═══════════════════════════════════════════════

export type ProficiencyLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert' | 'master';
export type TaskComplexity = 'simple' | 'moderate' | 'complex' | 'expert';
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'blocked' | 'cancelled';
export type VerificationMethod = 'simulation' | 'testing' | 'inspection' | 'calculation' | 'review' | 'certification' | 'measurement';
export type ConstraintType = 'physical' | 'temporal' | 'financial' | 'regulatory' | 'technical' | 'resource' | 'quality';

// ═══════════════════════════════════════════════
// PROFESSION
// ═══════════════════════════════════════════════

export interface Profession {
  id: string;
  name: string;
  description: string;
  domain: KnowledgeDomain;
  icon: string;
  color: string;
  
  // Hierarchy
  specializations: string[];  // Specialization IDs
  
  // Shared competencies with other professions
  sharedCompetencies: string[];  // Competency IDs shared across professions
  
  // Requirements
  requiredKnowledge: string[];   // Knowledge IDs
  requiredSkills: string[];      // Skill IDs
  requiredTools: string[];       // Tool IDs
  
  // Capabilities
  canPerform: string[];          // Task type patterns
  
  // Standards
  applicableStandards: string[]; // Standard IDs
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// SPECIALIZATION
// ═══════════════════════════════════════════════

export interface Specialization {
  id: string;
  name: string;
  description: string;
  professionId: string;
  
  // Hierarchy
  competencies: string[];  // Competency IDs
  
  // Requirements
  requiredKnowledge: string[];
  requiredSkills: string[];
  requiredTools: string[];
  
  // Sub-specializations
  subSpecializations: string[];
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// COMPETENCY
// ═══════════════════════════════════════════════

export interface Competency {
  id: string;
  name: string;
  description: string;
  domain: KnowledgeDomain;
  
  // Hierarchy
  tasks: string[];  // Task IDs
  
  // Requirements
  requiredKnowledge: string[];
  requiredSkills: string[];
  requiredTools: string[];
  
  // Shared across professions
  sharedWith: string[];  // Profession IDs that use this competency
  
  // Level requirements
  minimumLevel: ProficiencyLevel;
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// TASK — asosiy bajariladigan ish
// ═══════════════════════════════════════════════

export interface Task {
  id: string;
  name: string;
  description: string;
  domain: KnowledgeDomain;
  complexity: TaskComplexity;
  status: TaskStatus;
  
  // Hierarchy
  competencyId: string;
  subtasks: string[];       // Task IDs (decomposition)
  parentTaskId?: string;    // Parent task ID
  
  // Capability Package
  requiredKnowledge: string[];
  requiredSkills: string[];
  requiredTools: string[];
  
  // I/O
  inputs: TaskIO[];
  outputs: TaskIO[];
  
  // Process
  workflow: WorkflowStep[];
  
  // Verification
  verification: VerificationStep[];
  
  // Standards & Constraints
  standards: string[];
  constraints: Constraint[];
  
  // Failure Modes
  failureModes: FailureMode[];
  
  // Experience
  estimatedDuration?: number;  // minutes
  actualDuration?: number;
  successRate?: number;        // 0..1
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// WORKFLOW
// ═══════════════════════════════════════════════

export interface WorkflowStep {
  id: string;
  order: number;
  name: string;
  description: string;
  action: string;           // What to do
  
  // Requirements for this step
  requiredKnowledge: string[];
  requiredSkills: string[];
  requiredTools: string[];
  
  // I/O for this step
  inputs: TaskIO[];
  outputs: TaskIO[];
  
  // Verification for this step
  verification: VerificationStep[];
  
  // Conditional execution
  condition?: string;
  
  // Estimated time
  estimatedMinutes?: number;
}

// ═══════════════════════════════════════════════
// TASK I/O
// ═══════════════════════════════════════════════

export interface TaskIO {
  id: string;
  name: string;
  type: string;              // 'file', 'data', 'parameter', 'result', etc.
  format?: string;           // 'json', 'csv', 'pdf', 'gerber', 'schematic', etc.
  description: string;
  required: boolean;
  source?: string;           // Where to get it
  validator?: string;        // How to validate
}

// ═══════════════════════════════════════════════
// VERIFICATION
// ═══════════════════════════════════════════════

export interface VerificationStep {
  id: string;
  name: string;
  method: VerificationMethod;
  description: string;
  
  // What to check
  checkType: string;         // 'drc', 'erc', 'simulation', 'test', etc.
  checkCommand?: string;     // Command or procedure
  
  // Expected results
  expectedResults: string[];
  
  // Failure handling
  onFail: 'retry' | 'abort' | 'escalate' | 'skip';
  
  // Estimated time
  estimatedMinutes?: number;
}

// ═══════════════════════════════════════════════
// CONSTRAINT
// ═══════════════════════════════════════════════

export interface Constraint {
  id: string;
  type: ConstraintType;
  name: string;
  description: string;
  
  // Constraint details
  metric?: string;           // What's being constrained
  limit?: string;            // The limit value
  unit?: string;
  
  // Source
  source?: string;           // 'physics', 'budget', 'time', 'regulation', etc.
  
  // Severity
  hard: boolean;             // true = cannot be violated, false = can be relaxed
}

// ═══════════════════════════════════════════════
// FAILURE MODE
// ═══════════════════════════════════════════════

export interface FailureMode {
  id: string;
  name: string;
  description: string;
  
  // What can go wrong
  cause: string;
  symptom: string;
  
  // Impact
  severity: 'low' | 'medium' | 'high' | 'critical';
  probability: 'rare' | 'unlikely' | 'possible' | 'likely' | 'certain';
  
  // Detection
  detectionMethod: string;
  
  // Prevention
  prevention: string[];
  
  // Mitigation
  mitigation: string[];
  
  // Experience
  occurredBefore: boolean;
  lastOccurrence?: number;
  timesOccurred?: number;
}

// ═══════════════════════════════════════════════
// SKILL
// ═══════════════════════════════════════════════

export interface Skill {
  id: string;
  name: string;
  description: string;
  domain: KnowledgeDomain;
  
  // Level
  level: ProficiencyLevel;
  
  // Related
  relatedKnowledge: string[];
  relatedTools: string[];
  
  // Tasks that use this skill
  usedInTasks: string[];
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// TOOL
// ═══════════════════════════════════════════════

export interface Tool {
  id: string;
  name: string;
  description: string;
  category: string;           // 'cad', 'simulation', 'ide', 'office', etc.
  
  // Capabilities
  capabilities: string[];
  
  // Platform
  platform: string[];         // 'windows', 'linux', 'mac', 'web', 'cli'
  
  // Integration
  apiAvailable: boolean;
  cliAvailable: boolean;
  
  // Tasks that use this tool
  usedInTasks: string[];
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// KNOWLEDGE
// ═══════════════════════════════════════════════

export interface Knowledge {
  id: string;
  name: string;
  description: string;
  domain: KnowledgeDomain;
  
  // Type
  type: 'concept' | 'principle' | 'formula' | 'algorithm' | 'method' | 'standard' | 'procedure';
  
  // Level
  level: ProficiencyLevel;
  
  // Related
  relatedConcepts: string[];
  prerequisites: string[];
  
  // Tasks that use this knowledge
  usedInTasks: string[];
  
  // Evidence
  evidenceRequired: boolean;
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// STANDARD
// ═══════════════════════════════════════════════

export interface Standard {
  id: string;
  name: string;
  description: string;
  organization: string;      // 'IPC', 'ISO', 'IEEE', etc.
  
  // Scope
  applicableDomains: KnowledgeDomain[];
  applicableTasks: string[];
  
  // Requirements
  requirements: string[];
  
  // Compliance
  mandatory: boolean;
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// EXPERIENCE (Memory)
// ═══════════════════════════════════════════════

export interface Experience {
  id: string;
  taskId: string;
  taskName: string;
  domain: KnowledgeDomain;
  
  // What happened
  action: string;
  result: string;
  outcome: 'success' | 'failure' | 'partial';
  
  // Learnings
  lesson: string;
  confidence: number;
  
  // Context
  context: string;
  toolsUsed: string[];
  
  // Timing
  startedAt: number;
  completedAt: number;
  duration: number;          // minutes
  
  // Verification
  verified: boolean;
  verifiedBy?: string;
  
  // Metadata
  createdAt: number;
}

// ═══════════════════════════════════════════════
// VISUAL CONFIG
// ═══════════════════════════════════════════════

export const PROFICIENCY_COLORS: Record<ProficiencyLevel, string> = {
  beginner: '#94a3b8',
  intermediate: '#60a5fa',
  advanced: '#a78bfa',
  expert: '#f59e0b',
  master: '#10b981',
};

export const COMPLEXITY_COLORS: Record<TaskComplexity, string> = {
  simple: '#10b981',
  moderate: '#f59e0b',
  complex: '#f97316',
  expert: '#dc2626',
};

export const STATUS_COLORS: Record<TaskStatus, string> = {
  pending: '#71717a',
  in_progress: '#f59e0b',
  completed: '#10b981',
  failed: '#dc2626',
  blocked: '#f97316',
  cancelled: '#57534e',
};

export const CONSTRAINT_TYPE_COLORS: Record<ConstraintType, string> = {
  physical: '#3b82f6',
  temporal: '#f59e0b',
  financial: '#10b981',
  regulatory: '#dc2626',
  technical: '#8b5cf6',
  resource: '#06b6d4',
  quality: '#ec4899',
};

export const VERIFICATION_COLORS: Record<VerificationMethod, string> = {
  simulation: '#06b6d4',
  testing: '#10b981',
  inspection: '#f59e0b',
  calculation: '#8b5cf6',
  review: '#3b82f6',
  certification: '#ec4899',
  measurement: '#f97316',
};
