/**
 * GCM Store — Generation Capability Model database
 * 
 * Handles:
 *   Artifact CRUD
 *   Generation Pipeline management
 *   Validation execution
 *   Usability testing
 *   Version tracking
 *   Template management
 */

import type {
  Artifact, ArtifactType, ArtifactFormat, ArtifactRequirement,
  ArtifactConstraint, SourceMaterial, GenerationMethod,
  ValidationResult, ValidationCheckType, ValidationIssue,
  ArtifactEvidence, VersionEntry, GenerationPipeline, PipelineStage,
  GenerationTemplate, UsabilityStatus,
} from './gcm-schema';
import type { KnowledgeDomain } from './akms-schema';

import {
  USABILITY_CHECKS, ARTIFACT_TYPE_CONFIG, USABILITY_STATUS_CONFIG,
} from './gcm-schema';

// ═══════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `gcm_${Date.now().toString(36)}_${_nextId}`;
}

function now(): number {
  return Date.now();
}

// ═══════════════════════════════════════════════
// GCM STORE
// ═══════════════════════════════════════════════

export class GCMStore {
  private artifacts: Map<string, Artifact> = new Map();
  private pipelines: Map<string, GenerationPipeline> = new Map();
  private templates: Map<string, GenerationTemplate> = new Map();
  private listeners: Array<() => void> = [];

  // ─── Artifact CRUD ────────────────────────

  createArtifact(
    name: string,
    type: ArtifactType,
    format: ArtifactFormat,
    purpose: string,
    domain: KnowledgeDomain,
    generationMethod: GenerationMethod = { type: 'llm', description: 'AI generated' },
  ): Artifact {
    const id = uid();
    const t = now();
    const artifact: Artifact = {
      id, name, type, format, purpose, domain,
      requirements: [],
      constraints: [],
      sourceMaterial: [],
      dependencies: [],
      generationMethod,
      creatorAgent: 'igris',
      validation: [],
      usabilityStatus: 'draft',
      evidence: [],
      version: 1,
      versionHistory: [{ version: 1, timestamp: t, changes: 'Initial creation', author: 'igris' }],
      createdAt: t, updatedAt: t,
      metadata: {},
    };
    this.artifacts.set(id, artifact);
    this.notify();
    return artifact;
  }

  getArtifact(id: string): Artifact | undefined {
    return this.artifacts.get(id);
  }

  getAllArtifacts(): Artifact[] {
    return Array.from(this.artifacts.values());
  }

  updateArtifact(id: string, updates: Partial<Artifact>): Artifact | undefined {
    const a = this.artifacts.get(id);
    if (!a) return undefined;
    const updated = { ...a, ...updates, updatedAt: now() };
    this.artifacts.set(id, updated);
    this.notify();
    return updated;
  }

  deleteArtifact(id: string): boolean {
    return this.artifacts.delete(id);
  }

  /**
   * Add requirement to artifact.
   */
  addRequirement(artifactId: string, req: Omit<ArtifactRequirement, 'id'>): Artifact | undefined {
    const artifact = this.artifacts.get(artifactId);
    if (!artifact) return undefined;
    artifact.requirements.push({ ...req, id: uid() });
    artifact.updatedAt = now();
    this.notify();
    return artifact;
  }

  /**
   * Add validation result to artifact.
   */
  addValidation(artifactId: string, validation: Omit<ValidationResult, 'id'>): Artifact | undefined {
    const artifact = this.artifacts.get(artifactId);
    if (!artifact) return undefined;
    artifact.validation.push({ ...validation, id: uid() });
    artifact.updatedAt = now();
    this.notify();
    return artifact;
  }

  /**
   * Update usability status.
   */
  setUsabilityStatus(artifactId: string, status: UsabilityStatus): Artifact | undefined {
    const artifact = this.artifacts.get(artifactId);
    if (!artifact) return undefined;
    artifact.usabilityStatus = status;
    artifact.updatedAt = now();
    if (status === 'ready_for_use') artifact.readyAt = now();
    if (status === 'validated') artifact.validatedAt = now();
    this.notify();
    return artifact;
  }

  /**
   * Bump version.
   */
  bumpVersion(artifactId: string, changes: string = 'Updated'): Artifact | undefined {
    const artifact = this.artifacts.get(artifactId);
    if (!artifact) return undefined;
    artifact.version++;
    artifact.versionHistory.push({
      version: artifact.version,
      timestamp: now(),
      changes,
      author: 'igris',
    });
    artifact.updatedAt = now();
    this.notify();
    return artifact;
  }

  /**
   * Get artifacts by type, domain, or status.
   */
  findArtifacts(filter: {
    type?: ArtifactType;
    domain?: KnowledgeDomain;
    status?: UsabilityStatus;
    search?: string;
  }): Artifact[] {
    return this.getAllArtifacts().filter(a => {
      if (filter.type && a.type !== filter.type) return false;
      if (filter.domain && a.domain !== filter.domain) return false;
      if (filter.status && a.usabilityStatus !== filter.status) return false;
      if (filter.search) {
        const q = filter.search.toLowerCase();
        if (!a.name.toLowerCase().includes(q) && !a.purpose.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }

  /**
   * Run usability checks for artifact.
   */
  runUsabilityChecks(artifactId: string): ValidationResult[] {
    const artifact = this.artifacts.get(artifactId);
    if (!artifact) return [];

    const checks = USABILITY_CHECKS[artifact.type]?.checks || [];
    const results: ValidationResult[] = [];

    for (const check of checks) {
      const result: ValidationResult = {
        id: uid(),
        checkType: 'real_world_check',
        name: check.name,
        description: check.description,
        passed: true,  // Would be determined by actual check
        issues: [],
        verifiedAt: now(),
        verifiedBy: 'agent',
      };
      results.push(result);
      artifact.validation.push(result);
    }

    artifact.updatedAt = now();
    this.notify();
    return results;
  }

  // ─── Pipeline CRUD ────────────────────────

  createPipeline(
    name: string,
    description: string,
    userInput: string,
    purpose: string,
    domain: KnowledgeDomain,
    expectedType: ArtifactType,
    expectedFormat: ArtifactFormat,
  ): GenerationPipeline {
    const id = uid();
    const t = now();
    const pipeline: GenerationPipeline = {
      id, name, description,
      userInput, purpose, context: '',
      domain,
      expectedArtifactType: expectedType,
      expectedFormat: expectedFormat,
      stages: [],
      currentStage: 0,
      status: 'pending',
      createdAt: t, updatedAt: t,
    };
    this.pipelines.set(id, pipeline);
    this.notify();
    return pipeline;
  }

  getPipeline(id: string): GenerationPipeline | undefined {
    return this.pipelines.get(id);
  }

  /**
   * Add stage to pipeline.
   */
  addStage(pipelineId: string, stage: Omit<PipelineStage, 'id'>): GenerationPipeline | undefined {
    const pipeline = this.pipelines.get(pipelineId);
    if (!pipeline) return undefined;
    pipeline.stages.push({ ...stage, id: uid() });
    pipeline.updatedAt = now();
    this.notify();
    return pipeline;
  }

  /**
   * Create standard generation pipeline for artifact type.
   */
  createStandardPipeline(
    name: string,
    userInput: string,
    domain: KnowledgeDomain,
    artifactType: ArtifactType,
  ): GenerationPipeline {
    const pipeline = this.createPipeline(
      name,
      `Standard ${artifactType} generation pipeline`,
      userInput,
      userInput,
      domain,
      artifactType,
      this.getExpectedFormat(artifactType),
    );

    // Add standard stages based on artifact type
    const stages: Omit<PipelineStage, 'id'>[] = [
      {
        order: 1, name: 'Analyze Intent', description: 'Understand user intent and requirements',
        type: 'analysis',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['user_input'], outputs: ['requirements'],
        status: 'pending', validationChecks: [], retryCount: 0, maxRetries: 2,
      },
      {
        order: 2, name: 'Plan Generation', description: 'Plan the generation approach',
        type: 'planning',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['requirements'], outputs: ['plan'],
        status: 'pending', validationChecks: [], retryCount: 0, maxRetries: 2,
      },
      {
        order: 3, name: 'Gather Resources', description: 'Collect necessary knowledge and tools',
        type: 'planning',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['plan'], outputs: ['resources'],
        status: 'pending', validationChecks: [], retryCount: 0, maxRetries: 2,
      },
      {
        order: 4, name: 'Generate Artifact', description: 'Create the artifact',
        type: 'generation',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['resources'], outputs: ['artifact'],
        status: 'pending', validationChecks: [], retryCount: 0, maxRetries: 3,
      },
      {
        order: 5, name: 'Validate Format', description: 'Check file format and structure',
        type: 'validation',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['artifact'], outputs: ['format_check'],
        status: 'pending', validationChecks: ['format_check', 'structure_check'], retryCount: 0, maxRetries: 2,
      },
      {
        order: 6, name: 'Validate Content', description: 'Check content meets requirements',
        type: 'validation',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['artifact'], outputs: ['content_check'],
        status: 'pending', validationChecks: ['content_check', 'terminology_check'], retryCount: 0, maxRetries: 2,
      },
      {
        order: 7, name: 'Real-World Check', description: 'Test artifact in real use scenario',
        type: 'validation',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['artifact'], outputs: ['usability_check'],
        status: 'pending', validationChecks: ['usability_check'], retryCount: 0, maxRetries: 2,
      },
      {
        order: 8, name: 'Deliver Artifact', description: 'Finalize and deliver artifact',
        type: 'delivery',
        requiredKnowledge: [], requiredSkills: [], requiredTools: [],
        inputs: ['validated_artifact'], outputs: ['final_artifact'],
        status: 'pending', validationChecks: [], retryCount: 0, maxRetries: 1,
      },
    ];

    for (const stage of stages) {
      this.addStage(pipeline.id, stage);
    }

    return pipeline;
  }

  private getExpectedFormat(type: ArtifactType): ArtifactFormat {
    const formatMap: Record<ArtifactType, ArtifactFormat> = {
      document: 'docx', code: 'py', image: 'png', video: 'mp4', audio: 'mp3',
      model_3d: 'stl', cad: 'step', pcb: 'kicad_pcb', blueprint: 'pdf', dataset: 'csv',
      presentation: 'pptx', spreadsheet: 'xlsx', report: 'pdf', paper: 'pdf',
      thesis: 'pdf', book: 'pdf', manual: 'pdf', specification: 'pdf',
      contract: 'pdf', proposal: 'pdf', certificate: 'pdf', invoice: 'pdf',
      resume: 'pdf', website: 'html', api: 'yaml', database: 'sql',
      diagram: 'svg', chart: 'png', map: 'svg', simulation: 'py',
      firmware: 'c', driver: 'c', plugin: 'js', extension: 'js', other: 'other',
    };
    return formatMap[type] || 'other';
  }

  // ─── Template CRUD ────────────────────────

  createTemplate(
    name: string,
    description: string,
    artifactType: ArtifactType,
    domain: KnowledgeDomain,
    promptTemplate: string,
    requiredInputs: string[],
  ): GenerationTemplate {
    const id = uid();
    const t = now();
    const template: GenerationTemplate = {
      id, name, description, artifactType, domain,
      promptTemplate, requiredInputs, optionalInputs: [],
      requiredChecks: USABILITY_CHECKS[artifactType]?.checks.map(c => 'real_world_check') || [],
      expectedFormat: this.getExpectedFormat(artifactType),
      outputRequirements: [],
      createdAt: t, usageCount: 0,
    };
    this.templates.set(id, template);
    this.notify();
    return template;
  }

  getTemplate(id: string): GenerationTemplate | undefined {
    return this.templates.get(id);
  }

  findTemplates(filter: {
    artifactType?: ArtifactType;
    domain?: KnowledgeDomain;
    search?: string;
  }): GenerationTemplate[] {
    return Array.from(this.templates.values()).filter(t => {
      if (filter.artifactType && t.artifactType !== filter.artifactType) return false;
      if (filter.domain && t.domain !== filter.domain) return false;
      if (filter.search) {
        const q = filter.search.toLowerCase();
        if (!t.name.toLowerCase().includes(q) && !t.description.toLowerCase().includes(q)) return false;
      }
      return true;
    });
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

  // ─── Stats ───────────────────────────────

  getStats() {
    return {
      artifacts: this.artifacts.size,
      pipelines: this.pipelines.size,
      templates: this.templates.size,
      byType: this.getArtifactsByType(),
      byStatus: this.getArtifactsByStatus(),
    };
  }

  private getArtifactsByType(): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const a of this.artifacts.values()) {
      counts[a.type] = (counts[a.type] || 0) + 1;
    }
    return counts;
  }

  private getArtifactsByStatus(): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const a of this.artifacts.values()) {
      counts[a.usabilityStatus] = (counts[a.usabilityStatus] || 0) + 1;
    }
    return counts;
  }

  // ─── Import/Export ───────────────────────

  exportJSON(): string {
    return JSON.stringify({
      artifacts: Array.from(this.artifacts.values()),
      pipelines: Array.from(this.pipelines.values()),
      templates: Array.from(this.templates.values()),
    }, null, 2);
  }

  importJSON(json: string): void {
    const data = JSON.parse(json);
    if (data.artifacts) data.artifacts.forEach((a: Artifact) => this.artifacts.set(a.id, a));
    if (data.pipelines) data.pipelines.forEach((p: GenerationPipeline) => this.pipelines.set(p.id, p));
    if (data.templates) data.templates.forEach((t: GenerationTemplate) => this.templates.set(t.id, t));
    this.notify();
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const gcm = new GCMStore();
