/**
 * PCM Store — Professional Capability Model database
 * 
 * Handles:
 *   Profession CRUD
 *   Specialization management
 *   Competency tracking
 *   Task decomposition
 *   Workflow execution
 *   Experience recording
 *   Cross-profession capability sharing
 */

import type {
  Profession, Specialization, Competency, Task, WorkflowStep,
  TaskIO, VerificationStep, Constraint, FailureMode,
  Skill, Tool, Knowledge, Standard, Experience,
  ProficiencyLevel, TaskComplexity, TaskStatus,
} from './pcm-schema';
import type { KnowledgeDomain } from './akms-schema';

import {
  PROFICIENCY_COLORS, COMPLEXITY_COLORS, STATUS_COLORS,
} from './pcm-schema';

// ═══════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `pcm_${Date.now().toString(36)}_${_nextId}`;
}

function now(): number {
  return Date.now();
}

// ═══════════════════════════════════════════════
// PCM STORE
// ═══════════════════════════════════════════════

export class PCMStore {
  private professions: Map<string, Profession> = new Map();
  private specializations: Map<string, Specialization> = new Map();
  private competencies: Map<string, Competency> = new Map();
  private tasks: Map<string, Task> = new Map();
  private skills: Map<string, Skill> = new Map();
  private tools: Map<string, Tool> = new Map();
  private knowledge: Map<string, Knowledge> = new Map();
  private standards: Map<string, Standard> = new Map();
  private experiences: Map<string, Experience> = new Map();
  private listeners: Array<() => void> = [];

  // ─── Profession CRUD ──────────────────────

  createProfession(
    name: string,
    description: string,
    domain: KnowledgeDomain,
    icon: string = '👤',
    color: string = '#71717a',
  ): Profession {
    const id = uid();
    const t = now();
    const profession: Profession = {
      id, name, description, domain, icon, color,
      specializations: [],
      sharedCompetencies: [],
      requiredKnowledge: [],
      requiredSkills: [],
      requiredTools: [],
      canPerform: [],
      applicableStandards: [],
      createdAt: t, updatedAt: t,
    };
    this.professions.set(id, profession);
    this.notify();
    return profession;
  }

  getProfession(id: string): Profession | undefined {
    return this.professions.get(id);
  }

  getAllProfessions(): Profession[] {
    return Array.from(this.professions.values());
  }

  updateProfession(id: string, updates: Partial<Profession>): Profession | undefined {
    const p = this.professions.get(id);
    if (!p) return undefined;
    const updated = { ...p, ...updates, updatedAt: now() };
    this.professions.set(id, updated);
    this.notify();
    return updated;
  }

  // ─── Specialization CRUD ─────────────────

  createSpecialization(
    name: string,
    description: string,
    professionId: string,
  ): Specialization {
    const id = uid();
    const t = now();
    const spec: Specialization = {
      id, name, description, professionId,
      competencies: [],
      requiredKnowledge: [],
      requiredSkills: [],
      requiredTools: [],
      subSpecializations: [],
      createdAt: t, updatedAt: t,
    };
    this.specializations.set(id, spec);
    // Add to profession
    const prof = this.professions.get(professionId);
    if (prof) {
      prof.specializations.push(id);
      prof.updatedAt = t;
    }
    this.notify();
    return spec;
  }

  getSpecialization(id: string): Specialization | undefined {
    return this.specializations.get(id);
  }

  // ─── Competency CRUD ─────────────────────

  createCompetency(
    name: string,
    description: string,
    domain: KnowledgeDomain,
    sharedWith: string[] = [],
  ): Competency {
    const id = uid();
    const t = now();
    const comp: Competency = {
      id, name, description, domain,
      tasks: [],
      requiredKnowledge: [],
      requiredSkills: [],
      requiredTools: [],
      sharedWith,
      minimumLevel: 'intermediate',
      createdAt: t, updatedAt: t,
    };
    this.competencies.set(id, comp);
    // Add to shared professions
    for (const profId of sharedWith) {
      const prof = this.professions.get(profId);
      if (prof && !prof.sharedCompetencies.includes(id)) {
        prof.sharedCompetencies.push(id);
        prof.updatedAt = t;
      }
    }
    this.notify();
    return comp;
  }

  getCompetency(id: string): Competency | undefined {
    return this.competencies.get(id);
  }

  // ─── Task CRUD ───────────────────────────

  createTask(
    name: string,
    description: string,
    domain: KnowledgeDomain,
    complexity: TaskComplexity = 'moderate',
    competencyId: string = '',
  ): Task {
    const id = uid();
    const t = now();
    const task: Task = {
      id, name, description, domain, complexity,
      status: 'pending',
      competencyId,
      subtasks: [],
      requiredKnowledge: [],
      requiredSkills: [],
      requiredTools: [],
      inputs: [],
      outputs: [],
      workflow: [],
      verification: [],
      standards: [],
      constraints: [],
      failureModes: [],
      createdAt: t, updatedAt: t,
    };
    this.tasks.set(id, task);
    // Add to competency
    if (competencyId) {
      const comp = this.competencies.get(competencyId);
      if (comp) {
        comp.tasks.push(id);
        comp.updatedAt = t;
      }
    }
    this.notify();
    return task;
  }

  getTask(id: string): Task | undefined {
    return this.tasks.get(id);
  }

  getAllTasks(): Task[] {
    return Array.from(this.tasks.values());
  }

  updateTask(id: string, updates: Partial<Task>): Task | undefined {
    const t = this.tasks.get(id);
    if (!t) return undefined;
    const updated = { ...t, ...updates, updatedAt: now() };
    this.tasks.set(id, updated);
    this.notify();
    return updated;
  }

  /**
   * Decompose a complex task into subtasks.
   * This is the key feature — agent breaks down tasks automatically.
   */
  decomposeTask(taskId: string, subtasks: Partial<Task>[]): Task[] {
    const parent = this.tasks.get(taskId);
    if (!parent) return [];

    const created: Task[] = [];
    for (const sub of subtasks) {
      const subtask = this.createTask(
        sub.name || 'Subtask',
        sub.description || '',
        parent.domain,
        sub.complexity || 'moderate',
        parent.competencyId,
      );
      parent.subtasks.push(subtask.id);
      created.push(subtask);
    }
    parent.updatedAt = now();
    this.notify();
    return created;
  }

  /**
   * Get task's full capability package — everything needed to execute.
   */
  getTaskCapabilityPackage(taskId: string): {
    task: Task;
    knowledge: Knowledge[];
    skills: Skill[];
    tools: Tool[];
    subtasks: Task[];
    parents: Task[];
  } | null {
    const task = this.tasks.get(taskId);
    if (!task) return null;

    const knowledge = task.requiredKnowledge
      .map(id => this.knowledge.get(id))
      .filter((k): k is Knowledge => Boolean(k));

    const skills = task.requiredSkills
      .map(id => this.skills.get(id))
      .filter((s): s is Skill => Boolean(s));

    const tools = task.requiredTools
      .map(id => this.tools.get(id))
      .filter((t): t is Tool => Boolean(t));

    const subtasks = task.subtasks
      .map(id => this.tasks.get(id))
      .filter((t): t is Task => Boolean(t));

    // Find parent tasks
    const parents: Task[] = [];
    for (const [, t] of this.tasks) {
      if (t.subtasks.includes(taskId)) {
        parents.push(t);
      }
    }

    return { task, knowledge, skills, tools, subtasks, parents };
  }

  /**
   * Get task graph — full decomposition tree.
   */
  getTaskGraph(taskId: string, depth: number = 3): { nodes: Task[]; edges: [string, string][] } {
    const nodes: Task[] = [];
    const edges: [string, string][] = [];
    const visited = new Set<string>();
    let frontier = [taskId];

    for (let d = 0; d < depth && frontier.length > 0; d++) {
      const next: string[] = [];
      for (const id of frontier) {
        const task = this.tasks.get(id);
        if (!task || visited.has(id)) continue;
        visited.add(id);
        nodes.push(task);

        for (const subId of task.subtasks) {
          edges.push([id, subId]);
          next.push(subId);
        }
      }
      frontier = next;
    }

    return { nodes, edges };
  }

  // ─── Skill CRUD ──────────────────────────

  createSkill(
    name: string,
    description: string,
    domain: KnowledgeDomain,
    level: ProficiencyLevel = 'intermediate',
  ): Skill {
    const id = uid();
    const t = now();
    const skill: Skill = {
      id, name, description, domain, level,
      relatedKnowledge: [],
      relatedTools: [],
      usedInTasks: [],
      createdAt: t, updatedAt: t,
    };
    this.skills.set(id, skill);
    this.notify();
    return skill;
  }

  getSkill(id: string): Skill | undefined {
    return this.skills.get(id);
  }

  // ─── Tool CRUD ───────────────────────────

  createTool(
    name: string,
    description: string,
    category: string,
    platform: string[] = ['windows', 'linux', 'mac'],
  ): Tool {
    const id = uid();
    const t = now();
    const tool: Tool = {
      id, name, description, category,
      capabilities: [],
      platform,
      apiAvailable: false,
      cliAvailable: false,
      usedInTasks: [],
      createdAt: t, updatedAt: t,
    };
    this.tools.set(id, tool);
    this.notify();
    return tool;
  }

  getTool(id: string): Tool | undefined {
    return this.tools.get(id);
  }

  // ─── Knowledge CRUD ──────────────────────

  createKnowledge(
    name: string,
    description: string,
    domain: KnowledgeDomain,
    type: Knowledge['type'] = 'concept',
    level: ProficiencyLevel = 'intermediate',
  ): Knowledge {
    const id = uid();
    const t = now();
    const k: Knowledge = {
      id, name, description, domain, type, level,
      relatedConcepts: [],
      prerequisites: [],
      usedInTasks: [],
      evidenceRequired: false,
      createdAt: t, updatedAt: t,
    };
    this.knowledge.set(id, k);
    this.notify();
    return k;
  }

  getKnowledge(id: string): Knowledge | undefined {
    return this.knowledge.get(id);
  }

  // ─── Standard CRUD ──────────────────────

  createStandard(
    name: string,
    description: string,
    organization: string,
    applicableDomains: KnowledgeDomain[] = [],
    mandatory: boolean = true,
  ): Standard {
    const id = uid();
    const t = now();
    const std: Standard = {
      id, name, description, organization,
      applicableDomains,
      applicableTasks: [],
      requirements: [],
      mandatory,
      createdAt: t, updatedAt: t,
    };
    this.standards.set(id, std);
    this.notify();
    return std;
  }

  getStandard(id: string): Standard | undefined {
    return this.standards.get(id);
  }

  // ─── Experience CRUD ─────────────────────

  recordExperience(
    taskId: string,
    action: string,
    result: string,
    outcome: 'success' | 'failure' | 'partial',
    lesson: string,
    toolsUsed: string[] = [],
    duration: number = 0,
  ): Experience {
    const id = uid();
    const t = now();
    const task = this.tasks.get(taskId);
    const exp: Experience = {
      id, taskId, taskName: task?.name || 'Unknown',
      domain: task?.domain || 'general',
      action, result, outcome, lesson,
      confidence: outcome === 'success' ? 0.9 : outcome === 'failure' ? 0.8 : 0.7,
      context: '',
      toolsUsed,
      startedAt: t - duration * 60 * 1000,
      completedAt: t,
      duration,
      verified: false,
      createdAt: t,
    };
    this.experiences.set(id, exp);
    this.notify();
    return exp;
  }

  getExperience(id: string): Experience | undefined {
    return this.experiences.get(id);
  }

  getExperiencesForTask(taskId: string): Experience[] {
    return Array.from(this.experiences.values()).filter(e => e.taskId === taskId);
  }

  getExperiencesForDomain(domain: KnowledgeDomain): Experience[] {
    return Array.from(this.experiences.values()).filter(e => e.domain === domain);
  }

  // ─── Query Methods ──────────────────────

  /**
   * Find tasks by domain, complexity, or status.
   */
  findTasks(filter: {
    domain?: KnowledgeDomain;
    complexity?: TaskComplexity;
    status?: TaskStatus;
    search?: string;
  }): Task[] {
    return this.getAllTasks().filter(t => {
      if (filter.domain && t.domain !== filter.domain) return false;
      if (filter.complexity && t.complexity !== filter.complexity) return false;
      if (filter.status && t.status !== filter.status) return false;
      if (filter.search) {
        const q = filter.search.toLowerCase();
        if (!t.name.toLowerCase().includes(q) && !t.description.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }

  /**
   * Get profession's full capability map.
   */
  getProfessionCapabilityMap(professionId: string): {
    profession: Profession;
    specializations: Specialization[];
    competencies: Competency[];
    tasks: Task[];
    sharedCompetencies: Competency[];
  } | null {
    const prof = this.professions.get(professionId);
    if (!prof) return null;

    const specializations = prof.specializations
      .map(id => this.specializations.get(id))
      .filter((s): s is Specialization => Boolean(s));

    const competencies: Competency[] = [];
    for (const spec of specializations) {
      for (const compId of spec.competencies) {
        const comp = this.competencies.get(compId);
        if (comp && !competencies.find(c => c.id === comp.id)) {
          competencies.push(comp);
        }
      }
    }

    const tasks: Task[] = [];
    for (const comp of competencies) {
      for (const taskId of comp.tasks) {
        const task = this.tasks.get(taskId);
        if (task && !tasks.find(t => t.id === task.id)) {
          tasks.push(task);
        }
      }
    }

    const sharedCompetencies = prof.sharedCompetencies
      .map(id => this.competencies.get(id))
      .filter((c): c is Competency => Boolean(c));

    return { profession: prof, specializations, competencies, tasks, sharedCompetencies };
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
      professions: this.professions.size,
      specializations: this.specializations.size,
      competencies: this.competencies.size,
      tasks: this.tasks.size,
      skills: this.skills.size,
      tools: this.tools.size,
      knowledge: this.knowledge.size,
      standards: this.standards.size,
      experiences: this.experiences.size,
    };
  }

  // ─── Import/Export ───────────────────────

  exportJSON(): string {
    return JSON.stringify({
      professions: Array.from(this.professions.values()),
      specializations: Array.from(this.specializations.values()),
      competencies: Array.from(this.competencies.values()),
      tasks: Array.from(this.tasks.values()),
      skills: Array.from(this.skills.values()),
      tools: Array.from(this.tools.values()),
      knowledge: Array.from(this.knowledge.values()),
      standards: Array.from(this.standards.values()),
      experiences: Array.from(this.experiences.values()),
    }, null, 2);
  }

  importJSON(json: string): void {
    const data = JSON.parse(json);
    if (data.professions) data.professions.forEach((p: Profession) => this.professions.set(p.id, p));
    if (data.specializations) data.specializations.forEach((s: Specialization) => this.specializations.set(s.id, s));
    if (data.competencies) data.competencies.forEach((c: Competency) => this.competencies.set(c.id, c));
    if (data.tasks) data.tasks.forEach((t: Task) => this.tasks.set(t.id, t));
    if (data.skills) data.skills.forEach((s: Skill) => this.skills.set(s.id, s));
    if (data.tools) data.tools.forEach((t: Tool) => this.tools.set(t.id, t));
    if (data.knowledge) data.knowledge.forEach((k: Knowledge) => this.knowledge.set(k.id, k));
    if (data.standards) data.standards.forEach((s: Standard) => this.standards.set(s.id, s));
    if (data.experiences) data.experiences.forEach((e: Experience) => this.experiences.set(e.id, e));
    this.notify();
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const pcm = new PCMStore();
