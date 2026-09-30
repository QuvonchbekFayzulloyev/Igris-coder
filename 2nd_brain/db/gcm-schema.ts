/**
 * Generation Capability Model (GCM) — Artifact Production System
 * 
 * Agent nafaqat "nimadir yaratadi", balki:
 *   - Nima uchun yaratayotganini
 *   - Kim ishlatishini
 *   - Qanday talablar borligini
 *   - Qaysi format kerakligini
 *   - Qanday tekshirilishini
 *   - Real foydalanishga tayyormi-yo'qligini
 *   ham boshqaradi.
 * 
 * Architecture:
 *   USER INTENT → PURPOSE → CONTEXT → REQUIREMENTS
 *   → DOMAIN KNOWLEDGE → CAPABILITIES → TOOLS
 *   → GENERATION → VALIDATION → REAL-USE TEST
 *   → ARTIFACT → VERSION / MEMORY
 */

import type { KnowledgeDomain, Entity } from './akms-schema';
import type { TaskComplexity, TaskStatus } from './pcm-schema';

// ═══════════════════════════════════════════════
// ARTIFACT TYPES
// ═══════════════════════════════════════════════

export type ArtifactType =
  | 'document'
  | 'code'
  | 'image'
  | 'video'
  | 'audio'
  | 'model_3d'
  | 'cad'
  | 'pcb'
  | 'blueprint'
  | 'dataset'
  | 'presentation'
  | 'spreadsheet'
  | 'report'
  | 'paper'
  | 'thesis'
  | 'book'
  | 'manual'
  | 'specification'
  | 'contract'
  | 'proposal'
  | 'certificate'
  | 'invoice'
  | 'resume'
  | 'website'
  | 'api'
  | 'database'
  | 'diagram'
  | 'chart'
  | 'map'
  | 'simulation'
  | 'firmware'
  | 'driver'
  | 'plugin'
  | 'extension'
  | 'other';

export type ArtifactFormat =
  | 'docx' | 'pdf' | 'txt' | 'md' | 'html' | 'latex'
  | 'py' | 'js' | 'ts' | 'java' | 'cpp' | 'c' | 'rs' | 'go'
  | 'png' | 'jpg' | 'svg' | 'gif' | 'webp' | 'bmp' | 'tiff'
  | 'mp4' | 'avi' | 'mov' | 'mkv' | 'webm'
  | 'mp3' | 'wav' | 'ogg' | 'flac' | 'aac'
  | 'stl' | 'obj' | 'step' | 'iges' | 'fbx'
  | 'kicad_pcb' | 'kicad_sch' | 'gerber' | 'brd' | 'sch'
  | 'dwg' | 'dxf'
  | 'csv' | 'json' | 'xml' | 'yaml' | 'parquet'
  | 'pptx' | 'key'
  | 'xlsx' | 'xls'
  | 'zip' | 'tar' | 'gz'
  | 'dockerfile' | 'yaml_config'
  | 'sql' | 'graphql'
  | 'other';

export type UsabilityStatus =
  | 'draft'
  | 'generated'
  | 'validated'
  | 'reviewed'
  | 'ready_for_use'
  | 'in_use'
  | 'archived'
  | 'rejected'
  | 'needs_revision';

// ═══════════════════════════════════════════════
// ARTIFACT
// ═══════════════════════════════════════════════

export interface Artifact {
  id: string;
  name: string;
  type: ArtifactType;
  format: ArtifactFormat;
  purpose: string;
  domain: KnowledgeDomain;
  
  // Hierarchy
  projectId?: string;
  taskId?: string;
  
  // Requirements
  requirements: ArtifactRequirement[];
  constraints: ArtifactConstraint[];
  
  // Source
  sourceMaterial: SourceMaterial[];
  dependencies: string[];  // Other artifact IDs
  
  // Generation
  generationMethod: GenerationMethod;
  creatorAgent: string;
  generationPrompt?: string;
  
  // Validation
  validation: ValidationResult[];
  usabilityStatus: UsabilityStatus;
  
  // Evidence
  evidence: ArtifactEvidence[];
  
  // Location
  filePath?: string;
  fileSize?: number;
  mimeType?: string;
  
  // Version
  version: number;
  versionHistory: VersionEntry[];
  
  // Timing
  createdAt: number;
  updatedAt: number;
  validatedAt?: number;
  readyAt?: number;
  
  // Metadata
  metadata: Record<string, unknown>;
}

// ═══════════════════════════════════════════════
// ARTIFACT REQUIREMENT
// ═══════════════════════════════════════════════

export interface ArtifactRequirement {
  id: string;
  category: 'functional' | 'non_functional' | 'format' | 'content' | 'quality' | 'compliance';
  name: string;
  description: string;
  priority: 'must' | 'should' | 'could';
  satisfied: boolean;
  verificationMethod?: string;
  notes?: string;
}

// ═══════════════════════════════════════════════
// ARTIFACT CONSTRAINT
// ═══════════════════════════════════════════════

export interface ArtifactConstraint {
  id: string;
  type: 'technical' | 'format' | 'size' | 'time' | 'budget' | 'quality' | 'compliance';
  name: string;
  description: string;
  limit: string;
  unit?: string;
  hard: boolean;  // Can it be relaxed?
}

// ═══════════════════════════════════════════════
// SOURCE MATERIAL
// ═══════════════════════════════════════════════

export interface SourceMaterial {
  id: string;
  type: 'data' | 'reference' | 'template' | 'existing_artifact' | 'knowledge' | 'user_input';
  name: string;
  description: string;
  location?: string;  // File path or URL
  format?: string;
  reliability: 'high' | 'medium' | 'low';
}

// ═══════════════════════════════════════════════
// GENERATION METHOD
// ═══════════════════════════════════════════════

export interface GenerationMethod {
  type: 'llm' | 'template' | 'code' | 'hybrid' | 'human' | 'algorithm';
  description: string;
  model?: string;          // e.g., "gpt-4", "stable-diffusion"
  temperature?: number;
  maxTokens?: number;
  prompt?: string;
  templateId?: string;
  codePath?: string;
}

// ═══════════════════════════════════════════════
// VALIDATION
// ═══════════════════════════════════════════════

export interface ValidationResult {
  id: string;
  checkType: ValidationCheckType;
  name: string;
  description: string;
  passed: boolean;
  score?: number;         // 0..1
  issues: ValidationIssue[];
  verifiedAt?: number;
  verifiedBy?: string;    // 'agent', 'tool', 'human'
}

export type ValidationCheckType =
  | 'format_check'        // File format valid?
  | 'structure_check'     // Document structure correct?
  | 'content_check'       // Content meets requirements?
  | 'grammar_check'       // Language quality?
  | 'terminology_check'   // Domain terms correct?
  | 'citation_check'      // References valid?
  | 'calculation_check'   // Math/formulas correct?
  | 'simulation_check'    // Simulation passes?
  | 'drc_check'           // Design rule check (PCB)?
  | 'erc_check'           // Electrical rule check?
  | 'lint_check'          // Code quality?
  | 'test_check'          // Tests pass?
  | 'security_check'      // Security audit?
  | 'performance_check'   // Performance acceptable?
  | 'accessibility_check' // Accessibility standards?
  | 'compliance_check'    // Regulatory compliance?
  | 'usability_check'     // User can open/use?
  | 'render_check'        // Visual output correct?
  | 'audio_check'         // Audio quality?
  | 'video_check'         // Video quality?
  | 'integration_check'   // Works with other systems?
  | 'real_world_check'    // Works in real environment?

export interface ValidationIssue {
  id: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  location?: string;      // Line number, coordinates, etc.
  suggestion?: string;
  autoFixable: boolean;
}

// ═══════════════════════════════════════════════
// ARTIFACT EVIDENCE
// ═══════════════════════════════════════════════

export interface ArtifactEvidence {
  id: string;
  type: 'test_result' | 'screenshot' | 'log' | 'measurement' | 'expert_review' | 'user_feedback';
  description: string;
  location?: string;      // File path or URL
  timestamp: number;
  confidence: number;
}

// ═══════════════════════════════════════════════
// VERSION
// ═══════════════════════════════════════════════

export interface VersionEntry {
  version: number;
  timestamp: number;
  changes: string;
  author: string;
  filePath?: string;
}

// ═══════════════════════════════════════════════
// GENERATION PIPELINE
// ═══════════════════════════════════════════════

export interface GenerationPipeline {
  id: string;
  name: string;
  description: string;
  
  // Pipeline stages
  stages: PipelineStage[];
  
  // Input
  userInput: string;
  purpose: string;
  context: string;
  domain: KnowledgeDomain;
  
  // Output
  expectedArtifactType: ArtifactType;
  expectedFormat: ArtifactFormat;
  
  // Status
  currentStage: number;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'paused';
  
  // Timing
  startedAt?: number;
  completedAt?: number;
  estimatedMinutes?: number;
  
  // Result
  artifactId?: string;
  
  // Metadata
  createdAt: number;
  updatedAt: number;
}

export interface PipelineStage {
  id: string;
  order: number;
  name: string;
  description: string;
  type: 'analysis' | 'planning' | 'generation' | 'validation' | 'iteration' | 'delivery';
  
  // Requirements for this stage
  requiredKnowledge: string[];
  requiredSkills: string[];
  requiredTools: string[];
  
  // Input/Output
  inputs: string[];
  outputs: string[];
  
  // Status
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  
  // Validation
  validationChecks: ValidationCheckType[];
  
  // Retry
  retryCount: number;
  maxRetries: number;
  
  // Timing
  startedAt?: number;
  completedAt?: number;
}

// ═══════════════════════════════════════════════
// GENERATION TEMPLATES
// ═══════════════════════════════════════════════

export interface GenerationTemplate {
  id: string;
  name: string;
  description: string;
  artifactType: ArtifactType;
  domain: KnowledgeDomain;
  
  // Template
  promptTemplate: string;
  requiredInputs: string[];
  optionalInputs: string[];
  
  // Validation
  requiredChecks: ValidationCheckType[];
  
  // Output
  expectedFormat: ArtifactFormat;
  outputRequirements: ArtifactRequirement[];
  
  // Metadata
  createdAt: number;
  usageCount: number;
}

// ═══════════════════════════════════════════════
// REAL-WORLD USABILITY CHECKS
// ═══════════════════════════════════════════════

export interface UsabilityCheck {
  artifactType: ArtifactType;
  checks: {
    name: string;
    description: string;
    method: string;
    critical: boolean;
  }[];
}

export const USABILITY_CHECKS: Record<ArtifactType, UsabilityCheck> = {
  document: {
    artifactType: 'document',
    checks: [
      { name: 'File opens', description: 'Document can be opened without errors', method: 'open_file', critical: true },
      { name: 'Format correct', description: 'Formatting is preserved', method: 'visual_inspection', critical: true },
      { name: 'Content complete', description: 'All required sections present', method: 'structure_check', critical: true },
      { name: 'Language quality', description: 'Grammar and spelling correct', method: 'grammar_check', critical: false },
      { name: 'Citations valid', description: 'All references exist', method: 'citation_check', critical: false },
    ],
  },
  code: {
    artifactType: 'code',
    checks: [
      { name: 'Compiles', description: 'Code compiles without errors', method: 'compile', critical: true },
      { name: 'Tests pass', description: 'All unit tests pass', method: 'test', critical: true },
      { name: 'No lint errors', description: 'Code quality acceptable', method: 'lint', critical: false },
      { name: 'Security clean', description: 'No known vulnerabilities', method: 'security_scan', critical: true },
      { name: 'Performance ok', description: 'Meets performance requirements', method: 'benchmark', critical: false },
    ],
  },
  pcb: {
    artifactType: 'pcb',
    checks: [
      { name: 'DRC passes', description: 'Design rule check passes', method: 'drc', critical: true },
      { name: 'ERC passes', description: 'Electrical rule check passes', method: 'erc', critical: true },
      { name: 'Simulation passes', description: 'Circuit simulation correct', method: 'simulation', critical: true },
      { name: 'Manufacturable', description: 'Meets fab house requirements', method: 'fab_check', critical: true },
      { name: 'Signal integrity', description: 'Signal quality acceptable', method: 'si_check', critical: false },
    ],
  },
  image: {
    artifactType: 'image',
    checks: [
      { name: 'Resolution', description: 'Meets resolution requirements', method: 'resolution_check', critical: true },
      { name: 'Aspect ratio', description: 'Correct aspect ratio', method: 'aspect_check', critical: true },
      { name: 'File size', description: 'Within size limits', method: 'size_check', critical: false },
      { name: 'Visual quality', description: 'No artifacts or errors', method: 'visual_inspection', critical: true },
    ],
  },
  video: {
    artifactType: 'video',
    checks: [
      { name: 'Plays', description: 'Video plays without errors', method: 'playback_test', critical: true },
      { name: 'Duration', description: 'Correct duration', method: 'duration_check', critical: true },
      { name: 'Resolution', description: 'Correct resolution', method: 'resolution_check', critical: true },
      { name: 'Audio sync', description: 'Audio synchronized with video', method: 'sync_check', critical: true },
      { name: 'File size', description: 'Within size limits', method: 'size_check', critical: false },
    ],
  },
  audio: {
    artifactType: 'audio',
    checks: [
      { name: 'Plays', description: 'Audio plays without errors', method: 'playback_test', critical: true },
      { name: 'Duration', description: 'Correct duration', method: 'duration_check', critical: true },
      { name: 'Quality', description: 'Audio quality acceptable', method: 'quality_check', critical: true },
      { name: 'Format', description: 'Correct format and codec', method: 'format_check', critical: false },
    ],
  },
  presentation: {
    artifactType: 'presentation',
    checks: [
      { name: 'Opens', description: 'Presentation opens correctly', method: 'open_file', critical: true },
      { name: 'Slides complete', description: 'All required slides present', method: 'structure_check', critical: true },
      { name: 'Visual quality', description: 'Images and charts render', method: 'visual_inspection', critical: true },
      { name: 'Notes present', description: 'Speaker notes included', method: 'content_check', critical: false },
    ],
  },
  spreadsheet: {
    artifactType: 'spreadsheet',
    checks: [
      { name: 'Opens', description: 'Spreadsheet opens correctly', method: 'open_file', critical: true },
      { name: 'Formulas work', description: 'All formulas calculate correctly', method: 'formula_check', critical: true },
      { name: 'Data complete', description: 'All required data present', method: 'content_check', critical: true },
      { name: 'Charts render', description: 'Charts display correctly', method: 'visual_inspection', critical: false },
    ],
  },
  model_3d: {
    artifactType: 'model_3d',
    checks: [
      { name: 'Loads', description: '3D model loads in viewer', method: 'load_test', critical: true },
      { name: 'Geometry valid', description: 'No holes or intersecting faces', method: 'geometry_check', critical: true },
      { name: 'Scale correct', description: 'Correct dimensions', method: 'scale_check', critical: true },
      { name: 'Printable', description: '3D printable if required', method: 'printability_check', critical: false },
    ],
  },
  cad: {
    artifactType: 'cad',
    checks: [
      { name: 'Opens', description: 'CAD file opens correctly', method: 'open_file', critical: true },
      { name: 'Constraints valid', description: 'All constraints satisfied', method: 'constraint_check', critical: true },
      { name: 'Dimensions correct', description: 'Dimensions match requirements', method: 'dimension_check', critical: true },
      { name: 'Manufacturable', description: 'Can be manufactured', method: 'manufacturability_check', critical: false },
    ],
  },
  firmware: {
    artifactType: 'firmware',
    checks: [
      { name: 'Compiles', description: 'Firmware compiles for target', method: 'compile', critical: true },
      { name: 'Fits in flash', description: 'Binary fits in MCU flash', method: 'size_check', critical: true },
      { name: 'No warnings', description: 'Clean compilation', method: 'lint', critical: false },
      { name: 'Boots', description: 'Firmware boots on hardware', method: 'boot_test', critical: true },
    ],
  },
  blueprint: {
    artifactType: 'blueprint',
    checks: [
      { name: 'Opens', description: 'Blueprint file opens correctly', method: 'open_file', critical: true },
      { name: 'Scale valid', description: 'Drawing scale is valid', method: 'scale_check', critical: true },
      { name: 'Annotations complete', description: 'All annotations present', method: 'annotation_check', critical: false },
      { name: 'Standards compliant', description: 'Follows drawing standards', method: 'standards_check', critical: false },
    ],
  },
  dataset: {
    artifactType: 'dataset',
    checks: [
      { name: 'Schema valid', description: 'Data matches expected schema', method: 'schema_check', critical: true },
      { name: 'No missing values', description: 'Required fields complete', method: 'completeness_check', critical: true },
      { name: 'No duplicates', description: 'No duplicate records', method: 'uniqueness_check', critical: false },
      { name: 'Quality acceptable', description: 'Data quality meets standards', method: 'quality_check', critical: true },
    ],
  },
  website: {
    artifactType: 'website',
    checks: [
      { name: 'Loads', description: 'Website loads without errors', method: 'load_test', critical: true },
      { name: 'Responsive', description: 'Works on mobile devices', method: 'responsive_check', critical: true },
      { name: 'Accessible', description: 'Meets accessibility standards', method: 'accessibility_check', critical: false },
      { name: 'Performance', description: 'Page load time acceptable', method: 'performance_check', critical: false },
    ],
  },
  // Default for other types
  report: {
    artifactType: 'report',
    checks: [
      { name: 'Opens', description: 'Report opens correctly', method: 'open_file', critical: true },
      { name: 'Structure complete', description: 'All sections present', method: 'structure_check', critical: true },
      { name: 'Content quality', description: 'Content meets requirements', method: 'content_check', critical: true },
    ],
  },
  paper: {
    artifactType: 'paper',
    checks: [
      { name: 'Opens', description: 'Paper opens correctly', method: 'open_file', critical: true },
      { name: 'Structure valid', description: 'IMRAD structure correct', method: 'structure_check', critical: true },
      { name: 'Citations valid', description: 'All references exist', method: 'citation_check', critical: true },
    ],
  },
  thesis: {
    artifactType: 'thesis',
    checks: [
      { name: 'Opens', description: 'Thesis opens correctly', method: 'open_file', critical: true },
      { name: 'Structure valid', description: 'Required chapters present', method: 'structure_check', critical: true },
      { name: 'Citations valid', description: 'All references exist', method: 'citation_check', critical: true },
      { name: 'Formatting valid', description: 'University formatting requirements met', method: 'format_check', critical: true },
    ],
  },
  book: {
    artifactType: 'book',
    checks: [
      { name: 'Opens', description: 'Book file opens correctly', method: 'open_file', critical: true },
      { name: 'Chapters present', description: 'All chapters present', method: 'structure_check', critical: true },
      { name: 'TOC valid', description: 'Table of contents correct', method: 'toc_check', critical: false },
    ],
  },
  manual: {
    artifactType: 'manual',
    checks: [
      { name: 'Opens', description: 'Manual opens correctly', method: 'open_file', critical: true },
      { name: 'Structure complete', description: 'All sections present', method: 'structure_check', critical: true },
      { name: 'Images clear', description: 'Images and diagrams clear', method: 'visual_inspection', critical: false },
    ],
  },
  specification: {
    artifactType: 'specification',
    checks: [
      { name: 'Opens', description: 'Spec opens correctly', method: 'open_file', critical: true },
      { name: 'Requirements complete', description: 'All requirements numbered', method: 'structure_check', critical: true },
    ],
  },
  contract: {
    artifactType: 'contract',
    checks: [
      { name: 'Opens', description: 'Contract opens correctly', method: 'open_file', critical: true },
      { name: 'Clauses complete', description: 'All required clauses present', method: 'structure_check', critical: true },
      { name: 'Legal review', description: 'Legal terms acceptable', method: 'legal_review', critical: true },
    ],
  },
  proposal: {
    artifactType: 'proposal',
    checks: [
      { name: 'Opens', description: 'Proposal opens correctly', method: 'open_file', critical: true },
      { name: 'Sections complete', description: 'All required sections present', method: 'structure_check', critical: true },
      { name: 'Budget valid', description: 'Budget calculations correct', method: 'calculation_check', critical: true },
    ],
  },
  certificate: {
    artifactType: 'certificate',
    checks: [
      { name: 'Opens', description: 'Certificate opens correctly', method: 'open_file', critical: true },
      { name: 'Text correct', description: 'All text fields correct', method: 'content_check', critical: true },
    ],
  },
  invoice: {
    artifactType: 'invoice',
    checks: [
      { name: 'Opens', description: 'Invoice opens correctly', method: 'open_file', critical: true },
      { name: 'Calculations valid', description: 'Totals and taxes correct', method: 'calculation_check', critical: true },
    ],
  },
  resume: {
    artifactType: 'resume',
    checks: [
      { name: 'Opens', description: 'Resume opens correctly', method: 'open_file', critical: true },
      { name: 'Sections complete', description: 'All required sections present', method: 'structure_check', critical: true },
      { name: 'Length appropriate', description: 'Within page limit', method: 'length_check', critical: false },
    ],
  },
  api: {
    artifactType: 'api',
    checks: [
      { name: 'Spec valid', description: 'OpenAPI spec valid', method: 'spec_check', critical: true },
      { name: 'Endpoints work', description: 'All endpoints respond', method: 'integration_test', critical: true },
      { name: 'Auth works', description: 'Authentication functional', method: 'auth_test', critical: true },
    ],
  },
  database: {
    artifactType: 'database',
    checks: [
      { name: 'Schema valid', description: 'Database schema valid', method: 'schema_check', critical: true },
      { name: 'Migrations work', description: 'Migrations execute cleanly', method: 'migration_test', critical: true },
      { name: 'Queries perform', description: 'Queries perform acceptably', method: 'performance_check', critical: false },
    ],
  },
  diagram: {
    artifactType: 'diagram',
    checks: [
      { name: 'Renders', description: 'Diagram renders correctly', method: 'render_check', critical: true },
      { name: 'Labels readable', description: 'All text is readable', method: 'readability_check', critical: true },
    ],
  },
  chart: {
    artifactType: 'chart',
    checks: [
      { name: 'Renders', description: 'Chart renders correctly', method: 'render_check', critical: true },
      { name: 'Data accurate', description: 'Data matches source', method: 'data_check', critical: true },
    ],
  },
  map: {
    artifactType: 'map',
    checks: [
      { name: 'Renders', description: 'Map renders correctly', method: 'render_check', critical: true },
      { name: 'Coordinates valid', description: 'Geographic coordinates correct', method: 'coordinate_check', critical: true },
    ],
  },
  simulation: {
    artifactType: 'simulation',
    checks: [
      { name: 'Runs', description: 'Simulation runs without errors', method: 'run_test', critical: true },
      { name: 'Results valid', description: 'Results are reasonable', method: 'result_check', critical: true },
      { name: 'Converges', description: 'Simulation converges', method: 'convergence_check', critical: false },
    ],
  },
  driver: {
    artifactType: 'driver',
    checks: [
      { name: 'Compiles', description: 'Driver compiles', method: 'compile', critical: true },
      { name: 'Loads', description: 'Driver loads on target', method: 'load_test', critical: true },
      { name: 'Works', description: 'Device functions correctly', method: 'functionality_test', critical: true },
    ],
  },
  plugin: {
    artifactType: 'plugin',
    checks: [
      { name: 'Loads', description: 'Plugin loads in host', method: 'load_test', critical: true },
      { name: 'Functions', description: 'Plugin functions correctly', method: 'functionality_test', critical: true },
      { name: 'No conflicts', description: 'No conflicts with other plugins', method: 'conflict_test', critical: false },
    ],
  },
  extension: {
    artifactType: 'extension',
    checks: [
      { name: 'Loads', description: 'Extension loads in browser', method: 'load_test', critical: true },
      { name: 'Manifest valid', description: 'Manifest file valid', method: 'manifest_check', critical: true },
      { name: 'Permissions', description: 'Permissions appropriate', method: 'permission_check', critical: false },
    ],
  },
  other: {
    artifactType: 'other',
    checks: [
      { name: 'Opens', description: 'File opens correctly', method: 'open_file', critical: true },
      { name: 'Valid', description: 'File is valid', method: 'validity_check', critical: true },
    ],
  },
};

// ═══════════════════════════════════════════════
// VISUAL CONFIG
// ═══════════════════════════════════════════════

export const ARTIFACT_TYPE_CONFIG: Record<ArtifactType, { color: string; icon: string; label: string }> = {
  document:      { color: '#3b82f6', icon: '📄', label: 'Document' },
  code:          { color: '#10b981', icon: '💻', label: 'Code' },
  image:         { color: '#ec4899', icon: '🖼️', label: 'Image' },
  video:         { color: '#dc2626', icon: '🎬', label: 'Video' },
  audio:         { color: '#7c3aed', icon: '🎵', label: 'Audio' },
  model_3d:      { color: '#0891b2', icon: '🧊', label: '3D Model' },
  cad:           { color: '#78716c', icon: '📐', label: 'CAD' },
  pcb:           { color: '#16a34a', icon: '🔌', label: 'PCB' },
  blueprint:     { color: '#1e40af', icon: '📏', label: 'Blueprint' },
  dataset:       { color: '#059669', icon: '📊', label: 'Dataset' },
  presentation:  { color: '#ea580c', icon: '📽️', label: 'Presentation' },
  spreadsheet:   { color: '#16a34a', icon: '📊', label: 'Spreadsheet' },
  report:        { color: '#0ea5e9', icon: '📋', label: 'Report' },
  paper:         { color: '#8b5cf6', icon: '📑', label: 'Paper' },
  thesis:        { color: '#6366f1', icon: '📕', label: 'Thesis' },
  book:          { color: '#92400e', icon: '📚', label: 'Book' },
  manual:        { color: '#57534e', icon: '📖', label: 'Manual' },
  specification: { color: '#475569', icon: '📋', label: 'Specification' },
  contract:      { color: '#9333ea', icon: '⚖️', label: 'Contract' },
  proposal:      { color: '#2563eb', icon: '📝', label: 'Proposal' },
  certificate:   { color: '#d97706', icon: '🎓', label: 'Certificate' },
  invoice:       { color: '#059669', icon: '💰', label: 'Invoice' },
  resume:        { color: '#0891b2', icon: '👤', label: 'Resume' },
  website:       { color: '#3b82f6', icon: '🌐', label: 'Website' },
  api:           { color: '#6366f1', icon: '🔗', label: 'API' },
  database:      { color: '#f59e0b', icon: '🗄️', label: 'Database' },
  diagram:       { color: '#8b5cf6', icon: '📊', label: 'Diagram' },
  chart:         { color: '#10b981', icon: '📈', label: 'Chart' },
  map:           { color: '#14b8a6', icon: '🗺️', label: 'Map' },
  simulation:    { color: '#06b6d4', icon: '🔬', label: 'Simulation' },
  firmware:      { color: '#f97316', icon: '🔧', label: 'Firmware' },
  driver:        { color: '#71717a', icon: '⚙️', label: 'Driver' },
  plugin:        { color: '#a855f7', icon: '🧩', label: 'Plugin' },
  extension:     { color: '#10b981', icon: '🧩', label: 'Extension' },
  other:         { color: '#71717a', icon: '📦', label: 'Other' },
};

export const USABILITY_STATUS_CONFIG: Record<UsabilityStatus, { color: string; icon: string; label: string }> = {
  draft:           { color: '#71717a', icon: '📝', label: 'Draft' },
  generated:       { color: '#f59e0b', icon: '⚡', label: 'Generated' },
  validated:       { color: '#3b82f6', icon: '✓', label: 'Validated' },
  reviewed:        { color: '#8b5cf6', icon: '👁', label: 'Reviewed' },
  ready_for_use:   { color: '#10b981', icon: '✅', label: 'Ready for Use' },
  in_use:          { color: '#06b6d4', icon: '🔄', label: 'In Use' },
  archived:        { color: '#57534e', icon: '📁', label: 'Archived' },
  rejected:        { color: '#dc2626', icon: '✗', label: 'Rejected' },
  needs_revision:  { color: '#f97316', icon: '⚠️', label: 'Needs Revision' },
};
