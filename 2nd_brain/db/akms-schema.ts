/**
 * AKMS — Agent Knowledge & Memory System
 * 
 * Unified system combining:
 *   KNOWLEDGE (what the agent knows about the world)
 *   MEMORY (what the agent has done and learned)
 *   EVIDENCE (proof and verification for hallucination-free operation)
 *   DOMAINS (multi-disciplinary coverage)
 * 
 * Architecture:
 *   DB (source of truth) → Graph API → Graph UI
 *   AI → DB/Graph (retrieve, reason, update, verify, act)
 */

// ═══════════════════════════════════════════════
// KNOWLEDGE DOMAINS — agent qamrab olishi kerak
// ═══════════════════════════════════════════════

export type KnowledgeDomain =
  | 'academic_research'
  | 'microsoft_365'
  | 'software_engineering'
  | 'computer_science_ai'
  | 'electrical_engineering'
  | 'mechanical_engineering'
  | 'civil_engineering'
  | 'control_automation'
  | 'hardware_engineering'
  | 'systems_engineering'
  | 'creative'
  | 'economics'
  | 'finance'
  | 'business'
  | 'project_management'
  | 'data_science'
  | 'mathematics'
  | 'physics'
  | 'chemistry_materials'
  | 'legal_compliance'
  | 'cybersecurity'
  | 'research_operations'
  | 'personal_productivity'
  | 'general';

export const DOMAIN_CONFIG: Record<KnowledgeDomain, {
  label: string;
  icon: string;
  color: string;
  subdomains: string[];
  tools: string[];
}> = {
  academic_research: {
    label: 'Academic & Research',
    icon: '📚',
    color: '#8b5cf6',
    subdomains: ['papers', 'thesis', 'textbook', 'lecture', 'literature_review', 'citation', 'research_design', 'data_analysis', 'presentation'],
    tools: ['document_creation', 'citation_management', 'literature_discovery', 'reference_checking'],
  },
  microsoft_365: {
    label: 'Microsoft 365',
    icon: '🪟',
    color: '#0078d4',
    subdomains: ['word', 'excel', 'powerpoint', 'outlook', 'onenote', 'teams', 'sharepoint', 'onedrive'],
    tools: ['document_editing', 'spreadsheet_modeling', 'presentation_creation', 'email_management', 'note_organization'],
  },
  software_engineering: {
    label: 'Software Engineering',
    icon: '💻',
    color: '#10b981',
    subdomains: ['frontend', 'backend', 'fullstack', 'api', 'database', 'devops', 'testing', 'debugging', 'architecture', 'refactoring'],
    tools: ['code_generation', 'code_review', 'debugging', 'testing', 'deployment', 'documentation'],
  },
  computer_science_ai: {
    label: 'CS & AI',
    icon: '🤖',
    color: '#6366f1',
    subdomains: ['ml', 'dl', 'llm', 'agents', 'nlp', 'computer_vision', 'robotics', 'algorithms', 'distributed_systems'],
    tools: ['model_training', 'algorithm_design', 'system_architecture', 'optimization'],
  },
  electrical_engineering: {
    label: 'Electrical Engineering',
    icon: '⚡',
    color: '#f59e0b',
    subdomains: ['circuit_design', 'pcb', 'schematic', 'component_selection', 'simulation', 'embedded', 'firmware', 'signal_processing'],
    tools: ['schematic_design', 'pcb_layout', 'simulation', 'component_selection', 'signal_analysis'],
  },
  mechanical_engineering: {
    label: 'Mechanical Engineering',
    icon: '⚙️',
    color: '#78716c',
    subdomains: ['cad', '3d_models', 'assemblies', 'mechanisms', 'materials', 'manufacturing', 'simulation', 'thermodynamics'],
    tools: ['3d_modeling', 'stress_analysis', 'thermal_simulation', 'manufacturing_planning'],
  },
  civil_engineering: {
    label: 'Civil Engineering',
    icon: '🏗️',
    color: '#a16207',
    subdomains: ['blueprint', 'architectural_plans', 'structural_analysis', 'bim', 'infrastructure', 'construction'],
    tools: ['blueprint_creation', 'structural_calculation', 'bim_modeling', 'construction_planning'],
  },
  control_automation: {
    label: 'Control & Automation',
    icon: '🔧',
    color: '#0891b2',
    subdomains: ['plc', 'scada', 'robotics', 'sensors', 'actuators', 'industrial_automation', 'control_systems'],
    tools: ['plc_programming', 'scada_design', 'control_system_design', 'sensor_integration'],
  },
  hardware_engineering: {
    label: 'Hardware Engineering',
    icon: '🖥️',
    color: '#475569',
    subdomains: ['computer_architecture', 'custom_boards', 'embedded_hardware', 'fpga', 'soc', 'high_performance'],
    tools: ['board_design', 'fpga_development', 'hardware_simulation', 'performance_analysis'],
  },
  systems_engineering: {
    label: 'Systems Engineering',
    icon: '🔗',
    color: '#7c3aed',
    subdomains: ['complex_systems', 'requirements', 'dependencies', 'interfaces', 'verification', 'lifecycle'],
    tools: ['requirements_analysis', 'system_design', 'interface_definition', 'verification_planning'],
  },
  creative: {
    label: 'Creative',
    icon: '🎨',
    color: '#ec4899',
    subdomains: ['image', 'video', 'audio', 'music', '3d_art', 'animation', 'visual_design', 'storytelling'],
    tools: ['image_generation', 'video_creation', 'audio_synthesis', 'music_composition', '3d_modeling', 'ui_design'],
  },
  economics: {
    label: 'Economics',
    icon: '📈',
    color: '#059669',
    subdomains: ['macro', 'micro', 'econometrics', 'forecasting', 'policy', 'market_analysis'],
    tools: ['economic_modelling', 'forecasting', 'policy_analysis', 'market_research'],
  },
  finance: {
    label: 'Finance',
    icon: '💰',
    color: '#d97706',
    subdomains: ['modelling', 'valuation', 'budgeting', 'investment', 'risk', 'accounting'],
    tools: ['financial_modelling', 'valuation', 'budget_planning', 'risk_analysis'],
  },
  business: {
    label: 'Business',
    icon: '🏢',
    color: '#2563eb',
    subdomains: ['plans', 'strategy', 'operations', 'marketing', 'sales', 'management', 'consulting'],
    tools: ['business_planning', 'strategy_analysis', 'marketing_planning', 'operations_optimization'],
  },
  project_management: {
    label: 'Project Management',
    icon: '📋',
    color: '#ea580c',
    subdomains: ['planning', 'wbs', 'dependencies', 'scheduling', 'resources', 'risks', 'milestones', 'reporting'],
    tools: ['project_planning', 'wbs_creation', 'scheduling', 'risk_management', 'status_reporting'],
  },
  data_science: {
    label: 'Data Science',
    icon: '📊',
    color: '#0ea5e9',
    subdomains: ['cleaning', 'statistics', 'visualization', 'ml', 'forecasting', 'dashboards', 'experimentation'],
    tools: ['data_cleaning', 'statistical_analysis', 'visualization', 'model_building', 'dashboard_creation'],
  },
  mathematics: {
    label: 'Mathematics',
    icon: '🔢',
    color: '#be185d',
    subdomains: ['symbolic', 'numerical', 'optimization', 'probability', 'statistics', 'proofs'],
    tools: ['symbolic_computation', 'numerical_analysis', 'optimization', 'proof_verification'],
  },
  physics: {
    label: 'Physics',
    icon: '⚛️',
    color: '#1d4ed8',
    subdomains: ['modelling', 'simulation', 'numerical', 'theoretical', 'experimental'],
    tools: ['physics_modelling', 'simulation', 'data_analysis'],
  },
  chemistry_materials: {
    label: 'Chemistry & Materials',
    icon: '🧪',
    color: '#65a30d',
    subdomains: ['molecular', 'material_properties', 'modelling', 'experimental'],
    tools: ['molecular_analysis', 'material_characterization', 'experiment_planning'],
  },
  legal_compliance: {
    label: 'Legal & Compliance',
    icon: '⚖️',
    color: '#9333ea',
    subdomains: ['document_analysis', 'regulation', 'compliance', 'contracts'],
    tools: ['document_review', 'regulation_lookup', 'compliance_checking'],
  },
  cybersecurity: {
    label: 'Cybersecurity',
    icon: '🛡️',
    color: '#dc2626',
    subdomains: ['defensive', 'code_audit', 'threat_modelling', 'vulnerability', 'hardening'],
    tools: ['security_audit', 'vulnerability_scan', 'threat_analysis', 'hardening'],
  },
  research_operations: {
    label: 'Research Operations',
    icon: '🔬',
    color: '#7c2d12',
    subdomains: ['literature_discovery', 'source_verification', 'evidence_mapping', 'citation_management', 'experiment_tracking'],
    tools: ['literature_search', 'source_verification', 'evidence_collection', 'experiment_tracking'],
  },
  personal_productivity: {
    label: 'Personal Productivity',
    icon: '✅',
    color: '#16a34a',
    subdomains: ['files', 'notes', 'calendar', 'email', 'tasks', 'reminders', 'knowledge_organization'],
    tools: ['task_management', 'note_taking', 'calendar_management', 'email_drafting'],
  },
  general: {
    label: 'General',
    icon: '🌐',
    color: '#71717a',
    subdomains: ['conversation', 'reasoning', 'planning', 'analysis'],
    tools: ['text_generation', 'summarization', 'translation', 'analysis'],
  },
};

// ═══════════════════════════════════════════════
// ENTITY TYPES — asosiy ma'lumot turlari
// ═══════════════════════════════════════════════

export type EntityType =
  // Knowledge entities
  | 'concept'
  | 'fact'
  | 'principle'
  | 'law'
  | 'formula'
  | 'algorithm'
  | 'method'
  | 'standard'
  | 'specification'
  | 'documentation'
  | 'tutorial'
  | 'book'
  | 'paper'
  | 'article'
  | 'dataset'
  | 'code_snippet'
  | 'design_pattern'
  | 'procedure'
  | 'reference'
  // Project entities
  | 'project'
  | 'task'
  | 'milestone'
  | 'requirement'
  | 'decision'
  | 'risk'
  // Agent entities
  | 'agent'
  | 'skill'
  | 'tool'
  | 'capability'
  // File entities
  | 'file'
  | 'document'
  | 'spreadsheet'
  | 'presentation'
  | 'image'
  | 'video'
  | 'audio'
  | 'model_3d'
  | 'schematic'
  | 'pcb_layout'
  | 'blueprint'
  | 'code'
  // Memory entities
  | 'experience'
  | 'failure'
  | 'lesson'
  | 'observation'
  | 'session'
  | 'note'
  | 'group'
  | 'evidence'
  | 'verification'
  | 'claim'
  | 'source'
  | 'event';

// ═══════════════════════════════════════════════
// ENTITY STATES — entity holati
// ═══════════════════════════════════════════════

export type EntityState =
  | 'active'
  | 'inactive'
  | 'planning'
  | 'executing'
  | 'verifying'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'waiting'
  | 'reading'
  | 'writing'
  | 'idle'
  | 'draft'
  | 'published'
  | 'archived'
  | 'verified'
  | 'unverified'
  | 'disputed';

// ═══════════════════════════════════════════════
// RELATION TYPES — entitylar orasidagi bog'lanishlar
// ═══════════════════════════════════════════════

export type RelationType =
  // Knowledge relations
  | 'defines'
  | 'explains'
  | 'relates_to'
  | 'depends_on'
  | 'extends'
  | 'implements'
  | 'uses'
  | 'applies_to'
  | 'derived_from'
  | 'contradicts'
  | 'supports'
  | 'example_of'
  // Project relations
  | 'belongs_to'
  | 'contains'
  | 'part_of'
  | 'blocks'
  | 'triggers'
  | 'produces'
  | 'consumes'
  | 'monitors'
  | 'controls'
  | 'executed_by'
  | 'created_by'
  | 'assigned_to'
  // Memory relations
  | 'learned_from'
  | 'caused_by'
  | 'led_to'
  | 'similar_to'
  | 'different_from'
  | 'replaces'
  | 'supersedes'
  // Evidence relations
  | 'used_in'
  | 'verified_by'
  | 'sourced_from'
  | 'contradicted_by'
  | 'supported_by'
  | 'tested_by'
  | 'simulated_by'
  // Domain relations
  | 'in_domain'
  | 'cross_domain'
  | 'prerequisite_of'
  | 'specialization_of';

// ═══════════════════════════════════════════════
// MEMORY TYPES — xotira turlari
// ═══════════════════════════════════════════════

export type MemoryType =
  | 'episodic'     // Nima sodir bo'ldi?
  | 'semantic'     // Agent nimani o'rgandi?
  | 'procedural'   // Qanday bajariladi?
  | 'project'      // Loyiha holati
  | 'experience'   // Oldin nima ishladi?
  | 'failure'      // Nima ishlamadi?
  | 'decision'     // Nega shunday qaror qilindi?
  | 'user'         // Foydalanuvchi bilan bog'liq
  | 'task'         // Vazifa tarixi
  | 'social'       // Jamoa bilan bog'liq
  | 'lesson'       // Qoida/dars sifatida shakllangan bilim
  | 'session'      // Ish sessiyasi yozuvi
  | 'observation'; // Kuzatuv (hali qoida bo'lmagan)

// ═══════════════════════════════════════════════
// EVIDENCE & VERIFICATION
// ═══════════════════════════════════════════════

export type VerificationStatus =
  | 'unverified'
  | 'claim'          // "Menimcha shunday"
  | 'sourced'        // Manba ko'rsatilgan
  | 'reasoned'       // Mantiqiy asoslangan
  | 'tested'         // Test qilingan
  | 'simulated'      // Simulyatsiya qilingan
  | 'verified'       // To'liq tasdiqlangan
  | 'disputed'       // Munozarali
  | 'refuted';       // Rad etilgan

export type SourceType =
  | 'datasheet'
  | 'textbook'
  | 'paper'
  | 'documentation'
  | 'reference_design'
  | 'simulation'
  | 'measurement'
  | 'expert_opinion'
  | 'code_analysis'
  | 'user_input'
  | 'web_search'
  | 'internal_knowledge';

// ═══════════════════════════════════════════════
// CORE INTERFACES
// ═══════════════════════════════════════════════

export interface Entity {
  id: string;
  type: EntityType;
  name: string;
  content: string;
  properties: Record<string, unknown>;
  state: EntityState;
  domain: KnowledgeDomain;
  tags: string[];
  created_at: number;
  updated_at: number;
  created_by: string;
  confidence: number;       // 0..1 — agentning ishonchi darajasi
  verification: VerificationStatus;
  memory_type?: MemoryType; // Agar memory entity bo'lsa
}

export interface Relation {
  id: string;
  source: string;
  target: string;
  type: RelationType;
  weight: number;
  metadata: Record<string, unknown>;
  created_at: number;
  confidence: number;
}

export interface Evidence {
  id: string;
  claim_id: string;        // qaysi claim/entity ga tegishli
  source_type: SourceType;
  source_url?: string;
  source_text: string;     // manbadan olingan matn
  extracted_fact: string;  // ajratilgan fakt
  reasoning: string;       // mantiqiy zanjir
  test_result?: string;    // test natijasi
  confidence: number;
  verified_at?: number;
  verified_by?: string;
}

export interface Event {
  id: string;
  entity_id: string;
  action: string;
  timestamp: number;
  actor: string;
  result: string;
  metadata: Record<string, unknown>;
}

// ═══════════════════════════════════════════════
// KNOWLEDGE NODE — graph uchun knowledge node
// ═══════════════════════════════════════════════

export interface KnowledgeNode {
  id: string;
  entity: Entity;
  x: number;
  y: number;
  depth: number;
  visible: boolean;
  expanded: boolean;
  highlighted: boolean;
  focused: boolean;
  children: string[];
  evidence: Evidence[];
}

// ═══════════════════════════════════════════════
// GRAPH EDGE — relation vizualizatsiyasi
// ═══════════════════════════════════════════════

export interface KnowledgeEdge {
  id: string;
  relation: Relation;
  sourceNode: KnowledgeNode;
  targetNode: KnowledgeNode;
  visible: boolean;
  highlighted: boolean;
  label: string;
}

// ═══════════════════════════════════════════════
// AI QUERY INTERFACE
// ═══════════════════════════════════════════════

export interface AIQuery {
  entity_id: string;
  depth: number;
  include_evidence: boolean;
  include_memory: boolean;
  domain_filter?: KnowledgeDomain[];
  type_filter?: EntityType[];
  max_results: number;
}

export interface AIResponse {
  entity: Entity;
  neighbors: { entity: Entity; relation: Relation }[];
  evidence: Evidence[];
  memory: Entity[];
  context: string;          // AI uchun tayyorlangan kontekst matni
  confidence: number;
  sources: string[];
}

// ═══════════════════════════════════════════════
// SEMANTIC ZOOM CONFIG
// ═══════════════════════════════════════════════

export type ZoomLevel = 'overview' | 'structure' | 'detail' | 'properties';

export interface SemanticZoomConfig {
  level: ZoomLevel;
  scale: number;
  showLabels: boolean;
  showStates: boolean;
  showEvents: boolean;
  showProperties: boolean;
  showEvidence: boolean;
  showRelations: boolean;
  nodeSize: 'small' | 'medium' | 'large';
}

// ═══════════════════════════════════════════════
// FOCUS STATE
// ═══════════════════════════════════════════════

export interface FocusState {
  nodeId: string | null;
  depth: number;
  neighbors: string[];
  path: string[];
}

// ═══════════════════════════════════════════════
// ENTITY TYPE VISUAL CONFIG
// ═══════════════════════════════════════════════

export const ENTITY_TYPE_CONFIG: Record<EntityType, { color: string; icon: string; label: string; size: number }> = {
  // Knowledge
  concept:        { color: '#a855f7', icon: '💡', label: 'Concept', size: 7 },
  fact:           { color: '#10b981', icon: '✓', label: 'Fact', size: 6 },
  principle:      { color: '#8b5cf6', icon: '⚖', label: 'Principle', size: 7 },
  law:            { color: '#6366f1', icon: '📜', label: 'Law', size: 7 },
  formula:        { color: '#06b6d4', icon: '∑', label: 'Formula', size: 6 },
  algorithm:      { color: '#0ea5e9', icon: '🔀', label: 'Algorithm', size: 7 },
  method:         { color: '#14b8a6', icon: '📐', label: 'Method', size: 6 },
  standard:       { color: '#78716c', icon: '📏', label: 'Standard', size: 6 },
  specification:  { color: '#57534e', icon: '📋', label: 'Spec', size: 6 },
  documentation:  { color: '#71717a', icon: '📄', label: 'Docs', size: 5 },
  tutorial:       { color: '#f97316', icon: '📖', label: 'Tutorial', size: 6 },
  book:           { color: '#92400e', icon: '📕', label: 'Book', size: 7 },
  paper:          { color: '#1e40af', icon: '📑', label: 'Paper', size: 7 },
  article:        { color: '#3b82f6', icon: '📰', label: 'Article', size: 6 },
  dataset:        { color: '#059669', icon: '📊', label: 'Dataset', size: 6 },
  code_snippet:   { color: '#10b981', icon: '<>', label: 'Code', size: 5 },
  design_pattern: { color: '#7c3aed', icon: '🔷', label: 'Pattern', size: 6 },
  procedure:      { color: '#d97706', icon: '📝', label: 'Procedure', size: 6 },
  reference:      { color: '#6b7280', icon: '🔗', label: 'Reference', size: 5 },
  // Project
  project:        { color: '#8b5cf6', icon: '📁', label: 'Project', size: 9 },
  task:           { color: '#f59e0b', icon: '📋', label: 'Task', size: 7 },
  milestone:      { color: '#ef4444', icon: '🏁', label: 'Milestone', size: 7 },
  requirement:    { color: '#0891b2', icon: '📝', label: 'Requirement', size: 6 },
  decision:       { color: '#ef4444', icon: '⚡', label: 'Decision', size: 7 },
  risk:           { color: '#dc2626', icon: '⚠', label: 'Risk', size: 6 },
  // Agent
  agent:          { color: '#10b981', icon: '🤖', label: 'Agent', size: 8 },
  skill:          { color: '#14b8a6', icon: '🎯', label: 'Skill', size: 6 },
  tool:           { color: '#6366f1', icon: '🔧', label: 'Tool', size: 6 },
  capability:     { color: '#a855f7', icon: '⚡', label: 'Capability', size: 6 },
  // File
  file:           { color: '#6366f1', icon: '📄', label: 'File', size: 5 },
  document:       { color: '#3b82f6', icon: '📝', label: 'Document', size: 6 },
  spreadsheet:    { color: '#16a34a', icon: '📊', label: 'Spreadsheet', size: 6 },
  presentation:   { color: '#ea580c', icon: '📽', label: 'Presentation', size: 6 },
  image:          { color: '#ec4899', icon: '🖼', label: 'Image', size: 6 },
  video:          { color: '#dc2626', icon: '🎬', label: 'Video', size: 6 },
  audio:          { color: '#7c3aed', icon: '🎵', label: 'Audio', size: 6 },
  model_3d:       { color: '#0891b2', icon: '🧊', label: '3D Model', size: 7 },
  schematic:      { color: '#f59e0b', icon: '⚡', label: 'Schematic', size: 7 },
  pcb_layout:     { color: '#16a34a', icon: '🔌', label: 'PCB', size: 7 },
  blueprint:      { color: '#1e40af', icon: '📐', label: 'Blueprint', size: 7 },
  code:           { color: '#10b981', icon: '</>', label: 'Code', size: 6 },
  // Memory
  experience:     { color: '#06b6d4', icon: '🧠', label: 'Experience', size: 7 },
  failure:        { color: '#dc2626', icon: '❌', label: 'Failure', size: 6 },
  lesson:         { color: '#10b981', icon: '💡', label: 'Lesson', size: 6 },
  observation:    { color: '#71717a', icon: '👁', label: 'Observation', size: 5 },
  session:        { color: '#2dd4bf', icon: '💬', label: 'Session', size: 6 },
  note:           { color: '#71717a', icon: '📝', label: 'Note', size: 5 },
  group:          { color: '#3b82f6', icon: '📦', label: 'Group', size: 7 },
  evidence:       { color: '#f59e0b', icon: '🔍', label: 'Evidence', size: 6 },
  verification:   { color: '#10b981', icon: '✓', label: 'Verification', size: 6 },
  claim:          { color: '#f97316', icon: '💭', label: 'Claim', size: 6 },
  source:         { color: '#6366f1', icon: '📖', label: 'Source', size: 5 },
  event:          { color: '#ec4899', icon: '🕐', label: 'Event', size: 5 },
};

// ═══════════════════════════════════════════════
// RELATION TYPE VISUAL CONFIG
// ═══════════════════════════════════════════════

export const RELATION_TYPE_CONFIG: Record<RelationType, { color: string; label: string; dashed?: boolean; thickness?: number }> = {
  defines:           { color: '#a855f7', label: 'defines' },
  explains:          { color: '#8b5cf6', label: 'explains' },
  relates_to:        { color: '#71717a', label: 'relates to', dashed: true },
  depends_on:        { color: '#ef4444', label: 'depends on', thickness: 2 },
  extends:           { color: '#6366f1', label: 'extends' },
  implements:        { color: '#10b981', label: 'implements' },
  uses:              { color: '#3b82f6', label: 'uses' },
  used_in:           { color: '#0ea5e9', label: 'used in', dashed: true },
  applies_to:        { color: '#0ea5e9', label: 'applies to', dashed: true },
  derived_from:      { color: '#78716c', label: 'derived from' },
  contradicts:       { color: '#dc2626', label: 'contradicts', dashed: true },
  supports:          { color: '#16a34a', label: 'supports' },
  example_of:        { color: '#d97706', label: 'example of', dashed: true },
  belongs_to:        { color: '#8b5cf6', label: 'belongs to' },
  contains:          { color: '#6366f1', label: 'contains', dashed: true },
  part_of:           { color: '#7c3aed', label: 'part of' },
  blocks:            { color: '#dc2626', label: 'blocks', thickness: 2 },
  triggers:          { color: '#f59e0b', label: 'triggers' },
  produces:          { color: '#10b981', label: 'produces' },
  consumes:          { color: '#f97316', label: 'consumes' },
  monitors:          { color: '#06b6d4', label: 'monitors', dashed: true },
  controls:          { color: '#f59e0b', label: 'controls', thickness: 2 },
  executed_by:       { color: '#10b981', label: 'executed by' },
  created_by:        { color: '#ec4899', label: 'created by' },
  assigned_to:       { color: '#3b82f6', label: 'assigned to' },
  learned_from:      { color: '#14b8a6', label: 'learned from' },
  caused_by:         { color: '#ef4444', label: 'caused by' },
  led_to:            { color: '#f97316', label: 'led to' },
  similar_to:        { color: '#71717a', label: 'similar to', dashed: true },
  different_from:    { color: '#dc2626', label: 'different from', dashed: true },
  replaces:          { color: '#10b981', label: 'replaces' },
  supersedes:        { color: '#8b5cf6', label: 'supersedes' },
  verified_by:       { color: '#10b981', label: 'verified by', thickness: 2 },
  sourced_from:      { color: '#6366f1', label: 'sourced from' },
  contradicted_by:   { color: '#dc2626', label: 'contradicted by', dashed: true },
  supported_by:      { color: '#16a34a', label: 'supported by' },
  tested_by:         { color: '#f59e0b', label: 'tested by' },
  simulated_by:      { color: '#0ea5e9', label: 'simulated by' },
  in_domain:         { color: '#71717a', label: 'in domain', dashed: true },
  cross_domain:      { color: '#a855f7', label: 'cross-domain' },
  prerequisite_of:   { color: '#ef4444', label: 'prerequisite' },
  specialization_of: { color: '#6366f1', label: 'specialization', dashed: true },
};

// ═══════════════════════════════════════════════
// STATE VISUAL CONFIG
// ═══════════════════════════════════════════════

export const STATE_CONFIG: Record<EntityState, { color: string; pulse: boolean; label: string }> = {
  active:      { color: '#10b981', pulse: true,  label: 'Active' },
  inactive:    { color: '#71717a', pulse: false, label: 'Inactive' },
  planning:    { color: '#8b5cf6', pulse: true,  label: 'Planning' },
  executing:   { color: '#f59e0b', pulse: true,  label: 'Executing' },
  verifying:   { color: '#a855f7', pulse: true,  label: 'Verifying' },
  completed:   { color: '#10b981', pulse: false, label: 'Completed' },
  failed:      { color: '#dc2626', pulse: true,  label: 'Failed' },
  paused:      { color: '#f97316', pulse: false, label: 'Paused' },
  waiting:     { color: '#06b6d4', pulse: true,  label: 'Waiting' },
  reading:     { color: '#06b6d4', pulse: true,  label: 'Reading' },
  writing:     { color: '#f97316', pulse: true,  label: 'Writing' },
  idle:        { color: '#71717a', pulse: false, label: 'Idle' },
  draft:       { color: '#d97706', pulse: false, label: 'Draft' },
  published:   { color: '#10b981', pulse: false, label: 'Published' },
  archived:    { color: '#57534e', pulse: false, label: 'Archived' },
  verified:    { color: '#10b981', pulse: false, label: 'Verified' },
  unverified:  { color: '#f59e0b', pulse: true,  label: 'Unverified' },
  disputed:    { color: '#dc2626', pulse: true,  label: 'Disputed' },
};

// ═══════════════════════════════════════════════
// VERIFICATION STATUS CONFIG
// ═══════════════════════════════════════════════

export const VERIFICATION_CONFIG: Record<VerificationStatus, { color: string; icon: string; label: string }> = {
  unverified: { color: '#71717a', icon: '?', label: 'Unverified' },
  claim:      { color: '#f59e0b', icon: '💭', label: 'Claim' },
  sourced:    { color: '#3b82f6', icon: '📖', label: 'Sourced' },
  reasoned:   { color: '#8b5cf6', icon: '🧠', label: 'Reasoned' },
  tested:     { color: '#f97316', icon: '🧪', label: 'Tested' },
  simulated:  { color: '#06b6d4', icon: '💻', label: 'Simulated' },
  verified:   { color: '#10b981', icon: '✓', label: 'Verified' },
  disputed:   { color: '#dc2626', icon: '⚠', label: 'Disputed' },
  refuted:    { color: '#dc2626', icon: '✗', label: 'Refuted' },
};
