/**
 * Workspace & File Organization System
 * 
 * Agent capability for intelligent file/folder management:
 *   - Project type → structure strategy
 *   - Semantic file classification
 *   - Smart naming system
 *   - Version management
 *   - Dependency tracking
 *   - Duplicate detection
 *   - Archive management
 *   - Semantic file retrieval
 * 
 * Philosophy:
 *   The agent doesn't just create files — it understands project semantics,
 *   organizes files intelligently, and can find them later by meaning, not just name.
 * 
 * Architecture:
 *   Project Type → Folder Strategy → File Classification → Naming → Versioning
 *   → Dependency Tracking → Duplicate Detection → Archive → Semantic Retrieval
 */

import type { KnowledgeDomain } from './akms-schema';
import type { ArtifactType, ArtifactFormat } from './gcm-schema';

// ═══════════════════════════════════════════════
// FILE METADATA
// ═══════════════════════════════════════════════

export type FileStatus = 'active' | 'archived' | 'deleted' | 'deprecated' | 'template';

export type FileRole =
  | 'source'           // Source code, original documents
  | 'output'           // Generated outputs
  | 'config'           // Configuration files
  | 'documentation'    // Docs, README, guides
  | 'data'             // Datasets, inputs
  | 'asset'            // Images, audio, video
  | 'model'            // 3D models, ML models
  | 'test'             // Test files
  | 'build'            // Build artifacts
  | 'dependency'       // External dependencies
  | 'archive'          // Archived versions
  | 'reference'        // Reference materials
  | 'draft'            // Work in progress
  | 'final'            // Final deliverables
  | 'template'         // Reusable templates
  | 'unknown';

export interface FileMetadata {
  id: string;
  name: string;               // Original filename
  displayName: string;        // Human-readable name
  path: string;               // Full path relative to project root
  type: FileType;
  format: FileFormat;
  role: FileRole;
  
  // Organization
  project: string;            // Project ID
  parentFolder: string;       // Folder path
  tags: string[];
  semanticDescription: string;
  
  // Version
  version: number;
  versionHistory: VersionEntry[];
  
  // Status
  status: FileStatus;
  isPrimary: boolean;         // Primary file (vs copy/backup)
  
 // Size
  sizeBytes: number;
  
  // Timestamps
  created: number;
  modified: number;
  accessed: number;
  
  // Dependencies
  dependencies: string[];     // Files this depends on
  dependents: string[];       // Files that depend on this
  relatedArtifacts: string[]; // GCM artifact IDs
  relatedTasks: string[];     // PCM task IDs
  
  // Metadata
  checksum: string;           // Content hash
  language?: string;          // For code files
  encoding?: string;          // For text files
  
  // Source
  sourceType: 'created' | 'imported' | 'downloaded' | 'generated' | 'copied';
  sourcePath?: string;        // Original path if copied
}

export type FileType =
  | 'document'
  | 'spreadsheet'
  | 'presentation'
  | 'code'
  | 'config'
  | 'data'
  | 'image'
  | 'video'
  | 'audio'
  | '3d_model'
  | 'cad'
  | 'pcb'
  | 'schematic'
  | 'archive'
  | 'binary'
  | 'text'
  | 'other';

export type FileFormat =
  // Documents
  | 'docx' | 'doc' | 'pdf' | 'txt' | 'md' | 'rtf' | 'odt' | 'tex' | 'latex'
  // Spreadsheets
  | 'xlsx' | 'xls' | 'csv' | 'tsv' | 'ods'
  // Presentations
  | 'pptx' | 'ppt' | 'odp' | 'key'
  // Code
  | 'py' | 'js' | 'ts' | 'jsx' | 'tsx' | 'java' | 'cpp' | 'c' | 'h' | 'rs' | 'go' | 'rb' | 'php' | 'swift' | 'kt' | 'cs' | 'vue' | 'svelte'
  // Config
  | 'json' | 'yaml' | 'yml' | 'toml' | 'ini' | 'env' | 'xml'
  // Data
  | 'sql' | 'db' | 'sqlite' | 'parquet' | 'feather' | 'hdf5' | 'npy'
  // Image
  | 'png' | 'jpg' | 'jpeg' | 'gif' | 'svg' | 'webp' | 'bmp' | 'tiff' | 'ico' | 'psd' | 'ai' | 'eps'
  // Video
  | 'mp4' | 'avi' | 'mov' | 'mkv' | 'webm' | 'flv' | 'wmv'
  // Audio
  | 'mp3' | 'wav' | 'flac' | 'aac' | 'ogg' | 'wma' | 'm4a'
  // 3D/CAD
  | 'stl' | 'obj' | 'fbx' | 'step' | 'iges' | 'brep' | '3mf'
  // PCB
  | 'kicad_pcb' | 'kicad_sch' | 'brd' | 'sch' | 'gbr' | 'drl' | 'pos'
  // Archive
  | 'zip' | 'rar' | '7z' | 'tar' | 'gz' | 'bz2'
  // Other
  | 'exe' | 'dll' | 'so' | 'bin' | 'hex' | 'elf'
  | 'other';

// ═══════════════════════════════════════════════
// VERSION MANAGEMENT
// ═══════════════════════════════════════════════

export interface VersionEntry {
  version: number;
  timestamp: number;
  checksum: string;
  sizeBytes: number;
  message?: string;           // Commit message
  author?: string;
  changes?: string[];         // What changed
}

// ═══════════════════════════════════════════════
// FOLDER STRUCTURE
// ═══════════════════════════════════════════════

export interface FolderNode {
  path: string;
  name: string;
  description: string;
  role: FolderRole;
  children: FolderNode[];
  files: string[];            // File IDs
  
  // Metadata
  isRequired: boolean;        // Must exist for this project type
  isGenerated: boolean;       // Created by agent
  containsFileTypes: FileType[];
  containsFileRoles: FileRole[];
}

export type FolderRole =
  | 'root'
  | 'source'
  | 'output'
  | 'config'
  | 'documentation'
  | 'data'
  | 'asset'
  | 'model'
  | 'test'
  | 'build'
  | 'dependency'
  | 'archive'
  | 'reference'
  | 'draft'
  | 'other';

// ═══════════════════════════════════════════════
// PROJECT TYPES & STRUCTURE STRATEGIES
// ═══════════════════════════════════════════════

export type ProjectType =
  | 'general'
  | 'software'
  | 'pcb'
  | 'academic'
  | 'video'
  | 'audio'
  | 'data_science'
  | 'web'
  | 'mobile'
  | 'embedded'
  | 'robotics'
  | 'mechanical'
  | 'design'
  | 'writing'
  | 'education'
  | 'other';

export interface ProjectStructureStrategy {
  projectType: ProjectType;
  name: string;
  description: string;
  
  // Root folders
  rootFolders: FolderTemplate[];
  
  // Naming conventions
  namingConventions: NamingConvention[];
  
  // File organization rules
  organizationRules: OrganizationRule[];
  
  // Version strategy
  versionStrategy: VersionStrategy;
  
  // Archive strategy
  archiveStrategy: ArchiveStrategy;
  
  // Metadata
  domain?: KnowledgeDomain;
  artifactTypes?: ArtifactType[];
  typicalTools?: string[];
}

export interface FolderTemplate {
  path: string;
  name: string;
  description: string;
  role: FolderRole;
  isRequired: boolean;
  containsFileTypes: FileType[];
  containsFileRoles: FileRole[];
  children?: FolderTemplate[];
}

export interface NamingConvention {
  fileType: FileType;
  pattern: string;            // e.g., "{type}_{name}_v{version}.{ext}"
  examples: string[];
  rules: string[];
}

export interface OrganizationRule {
  name: string;
  description: string;
  condition: string;          // When to apply
  action: string;             // What to do
  priority: number;
}

export interface VersionStrategy {
  method: 'semantic' | 'sequential' | 'timestamp' | 'git';
  pattern: string;            // e.g., "v{major}.{minor}.{patch}"
  autoVersion: boolean;
  maxVersions?: number;
}

export interface ArchiveStrategy {
  moveArchived: boolean;
  archivePath: string;
  keepVersions: number;
  compress: boolean;
  deleteAfterDays?: number;
}

// ═══════════════════════════════════════════════
// DUPLICATE DETECTION
// ═══════════════════════════════════════════════

export interface DuplicateGroup {
  id: string;
  files: string[];            // File IDs with same content
  checksum: string;
  sizeBytes: number;
  recommendation: 'keep_newest' | 'keep_largest' | 'keep_most_recent' | 'manual';
  confidence: number;         // 0..1
}

// ═══════════════════════════════════════════════
// DEPENDENCY TRACKING
// ═══════════════════════════════════════════════

export interface FileDependency {
  sourceId: string;           // File that depends on
  targetId: string;           // File that is depended on
  type: DependencyType;
  strength: number;           // 0..1, how critical
  description: string;
}

export type DependencyType =
  | 'imports'           // Code imports
  | 'includes'          // C includes
  | 'references'        // Document references
  | 'extends'           // Class inheritance
  | 'uses'              // General usage
  | 'requires'          // Required dependency
  | 'optional'          // Optional dependency
  | 'generates'         // One generates the other
  | 'consumes';         // One consumes the other

// ═══════════════════════════════════════════════
// ORGANIZATION OPERATION
// ═══════════════════════════════════════════════

export type OperationType =
  | 'analyze'
  | 'plan'
  | 'preview'
  | 'check_dependencies'
  | 'execute'
  | 'verify'
  | 'update_memory';

export interface OrganizationOperation {
  id: string;
  type: OperationType;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  
  // Input
  projectId: string;
  files: string[];            // File IDs to organize
  
  // Plan
  moves: FileMove[];
  renames: FileRename[];
  deletes: FileDelete[];
  archives: FileArchive[];
  
  // Results
  executed: number;
  failed: number;
  skipped: number;
  
  // Timestamps
  started: number;
  completed?: number;
  
  // Memory
  memoryEntry?: string;       // What was learned
}

export interface FileMove {
  fileId: string;
  fromPath: string;
  toPath: string;
  reason: string;
  dependenciesAffected: string[];
}

export interface FileRename {
  fileId: string;
  fromName: string;
  toName: string;
  reason: string;
}

export interface FileDelete {
  fileId: string;
  path: string;
  reason: string;
  archived: boolean;
}

export interface FileArchive {
  fileId: string;
  fromPath: string;
  toPath: string;
  reason: string;
}

// ═══════════════════════════════════════════════
// WORKSPACE STATS
// ═══════════════════════════════════════════════

export interface WorkspaceStats {
  totalFiles: number;
  totalFolders: number;
  totalSizeBytes: number;
  
  byType: Record<FileType, number>;
  byRole: Record<FileRole, number>;
  byProjectType: Record<ProjectType, number>;
  
  duplicates: number;
  obsolete: number;
  archived: number;
  
  avgVersion: number;
  avgDepth: number;
  
  lastOrganization?: number;
}

// ═══════════════════════════════════════════════
// VISUAL CONFIG
// ═══════════════════════════════════════════════

export const FILE_TYPE_CONFIG: Record<FileType, { color: string; icon: string; label: string }> = {
  document:      { color: '#3b82f6', icon: '📄', label: 'Document' },
  spreadsheet:   { color: '#10b981', icon: '📊', label: 'Spreadsheet' },
  presentation:  { color: '#f59e0b', icon: '📽️', label: 'Presentation' },
  code:          { color: '#8b5cf6', icon: '💻', label: 'Code' },
  config:        { color: '#6b7280', icon: '⚙️', label: 'Config' },
  data:          { color: '#06b6d4', icon: '💾', label: 'Data' },
  image:         { color: '#ec4899', icon: '🖼️', label: 'Image' },
  video:         { color: '#ef4444', icon: '🎬', label: 'Video' },
  audio:         { color: '#f97316', icon: '🎵', label: 'Audio' },
  '3d_model':    { color: '#14b8a6', icon: '🧊', label: '3D Model' },
  cad:           { color: '#0ea5e9', icon: '📐', label: 'CAD' },
  pcb:           { color: '#22c55e', icon: '🔌', label: 'PCB' },
  schematic:     { color: '#a855f7', icon: '⚡', label: 'Schematic' },
  archive:       { color: '#78716c', icon: '📦', label: 'Archive' },
  binary:        { color: '#57534e', icon: '🔧', label: 'Binary' },
  text:          { color: '#a1a1aa', icon: '📝', label: 'Text' },
  other:         { color: '#d6d3d1', icon: '❓', label: 'Other' },
};

export const PROJECT_TYPE_CONFIG: Record<ProjectType, { color: string; icon: string; label: string; description: string }> = {
  general:       { color: '#6b7280', icon: '📁', label: 'General', description: 'General project' },
  software:      { color: '#8b5cf6', icon: '💻', label: 'Software', description: 'Software development' },
  pcb:           { color: '#22c55e', icon: '🔌', label: 'PCB', description: 'PCB design project' },
  academic:      { color: '#3b82f6', icon: '🎓', label: 'Academic', description: 'Research/Academic' },
  video:         { color: '#ef4444', icon: '🎬', label: 'Video', description: 'Video production' },
  audio:         { color: '#f97316', icon: '🎵', label: 'Audio', description: 'Audio production' },
  data_science:  { color: '#06b6d4', icon: '📈', label: 'Data Science', description: 'Data analysis/ML' },
  web:           { color: '#ec4899', icon: '🌐', label: 'Web', description: 'Web development' },
  mobile:        { color: '#a855f7', icon: '📱', label: 'Mobile', description: 'Mobile app' },
  embedded:      { color: '#14b8a6', icon: '🔧', label: 'Embedded', description: 'Embedded systems' },
  robotics:      { color: '#0ea5e9', icon: '🤖', label: 'Robotics', description: 'Robotics project' },
  mechanical:    { color: '#f59e0b', icon: '⚙️', label: 'Mechanical', description: 'Mechanical design' },
  design:        { color: '#ec4899', icon: '🎨', label: 'Design', description: 'Design project' },
  writing:       { color: '#78716c', icon: '✍️', label: 'Writing', description: 'Writing project' },
  education:     { color: '#10b981', icon: '📚', label: 'Education', description: 'Educational content' },
  other:         { color: '#d6d3d1', icon: '❓', label: 'Other', description: 'Other project type' },
};

export const FILE_ROLE_CONFIG: Record<FileRole, { color: string; icon: string; label: string }> = {
  source:         { color: '#8b5cf6', icon: '📝', label: 'Source' },
  output:         { color: '#10b981', icon: '📤', label: 'Output' },
  config:         { color: '#6b7280', icon: '⚙️', label: 'Config' },
  documentation:  { color: '#3b82f6', icon: '📚', label: 'Documentation' },
  data:           { color: '#06b6d4', icon: '💾', label: 'Data' },
  asset:          { color: '#ec4899', icon: '🎨', label: 'Asset' },
  model:          { color: '#14b8a6', icon: '🧊', label: 'Model' },
  test:           { color: '#f59e0b', icon: '🧪', label: 'Test' },
  build:          { color: '#78716c', icon: '🔨', label: 'Build' },
  dependency:     { color: '#ef4444', icon: '🔗', label: 'Dependency' },
  archive:        { color: '#57534e', icon: '📦', label: 'Archive' },
  reference:      { color: '#a855f7', icon: '📖', label: 'Reference' },
  draft:          { color: '#f97316', icon: '✏️', label: 'Draft' },
  final:          { color: '#22c55e', icon: '✅', label: 'Final' },
  template:       { color: '#0ea5e9', icon: '📋', label: 'Template' },
  unknown:        { color: '#d6d3d1', icon: '❓', label: 'Unknown' },
};
