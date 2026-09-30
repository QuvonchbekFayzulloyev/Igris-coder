/**
 * Workspace Store — Intelligent file/folder organization
 * 
 * Implements:
 *   - File CRUD with metadata
 *   - Folder structure management
 *   - Project type → structure strategy
 *   - Smart naming system
 *   - Version management
 *   - Dependency tracking
 *   - Duplicate detection
 *   - Archive management
 *   - Safe organization operations
 *   - Semantic file retrieval
 */

import type {
  FileMetadata, FileType, FileFormat, FileRole, FileStatus,
  FolderNode, FolderRole,
  ProjectType, ProjectStructureStrategy, FolderTemplate, NamingConvention,
  VersionEntry, DuplicateGroup, FileDependency, DependencyType,
  OrganizationOperation, OperationType, FileMove, FileRename, FileDelete, FileArchive,
  WorkspaceStats,
} from './workspace-schema';

import {
  FILE_TYPE_CONFIG, PROJECT_TYPE_CONFIG, FILE_ROLE_CONFIG,
} from './workspace-schema';

// ═══════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `ws_${Date.now().toString(36)}_${_nextId}`;
}

function now(): number {
  return Date.now();
}

function simpleHash(content: string): string {
  let hash = 0;
  for (let i = 0; i < content.length; i++) {
    const char = content.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(36);
}

// ═══════════════════════════════════════════════
// FILE TYPE DETECTION
// ═══════════════════════════════════════════════

const EXTENSION_MAP: Record<string, { type: FileType; format: FileFormat }> = {
  // Documents
  '.docx': { type: 'document', format: 'docx' },
  '.doc':  { type: 'document', format: 'doc' },
  '.pdf':  { type: 'document', format: 'pdf' },
  '.txt':  { type: 'text', format: 'txt' },
  '.md':   { type: 'text', format: 'md' },
  '.rtf':  { type: 'document', format: 'rtf' },
  '.odt':  { type: 'document', format: 'odt' },
  '.tex':  { type: 'document', format: 'tex' },
  '.latex': { type: 'document', format: 'latex' },
  // Spreadsheets
  '.xlsx': { type: 'spreadsheet', format: 'xlsx' },
  '.xls':  { type: 'spreadsheet', format: 'xls' },
  '.csv':  { type: 'data', format: 'csv' },
  '.tsv':  { type: 'data', format: 'tsv' },
  '.ods':  { type: 'spreadsheet', format: 'ods' },
  // Presentations
  '.pptx': { type: 'presentation', format: 'pptx' },
  '.ppt':  { type: 'presentation', format: 'ppt' },
  '.odp':  { type: 'presentation', format: 'odp' },
  '.key':  { type: 'presentation', format: 'key' },
  // Code
  '.py':   { type: 'code', format: 'py' },
  '.js':   { type: 'code', format: 'js' },
  '.ts':   { type: 'code', format: 'ts' },
  '.jsx':  { type: 'code', format: 'jsx' },
  '.tsx':  { type: 'code', format: 'tsx' },
  '.java': { type: 'code', format: 'java' },
  '.cpp':  { type: 'code', format: 'cpp' },
  '.c':    { type: 'code', format: 'c' },
  '.h':    { type: 'code', format: 'h' },
  '.rs':   { type: 'code', format: 'rs' },
  '.go':   { type: 'code', format: 'go' },
  '.rb':   { type: 'code', format: 'rb' },
  '.php':  { type: 'code', format: 'php' },
  '.swift': { type: 'code', format: 'swift' },
  '.kt':   { type: 'code', format: 'kt' },
  '.cs':   { type: 'code', format: 'cs' },
  '.vue':  { type: 'code', format: 'vue' },
  '.svelte': { type: 'code', format: 'svelte' },
  // Config
  '.json': { type: 'config', format: 'json' },
  '.yaml': { type: 'config', format: 'yaml' },
  '.yml':  { type: 'config', format: 'yaml' },
  '.toml': { type: 'config', format: 'toml' },
  '.ini':  { type: 'config', format: 'ini' },
  '.env':  { type: 'config', format: 'env' },
  '.xml':  { type: 'config', format: 'xml' },
  // Data
  '.sql':  { type: 'data', format: 'sql' },
  '.db':   { type: 'data', format: 'db' },
  '.sqlite': { type: 'data', format: 'sqlite' },
  '.parquet': { type: 'data', format: 'parquet' },
  '.feather': { type: 'data', format: 'feather' },
  '.hdf5': { type: 'data', format: 'hdf5' },
  '.npy':  { type: 'data', format: 'npy' },
  // Image
  '.png':  { type: 'image', format: 'png' },
  '.jpg':  { type: 'image', format: 'jpg' },
  '.jpeg': { type: 'image', format: 'jpeg' },
  '.gif':  { type: 'image', format: 'gif' },
  '.svg':  { type: 'image', format: 'svg' },
  '.webp': { type: 'image', format: 'webp' },
  '.bmp':  { type: 'image', format: 'bmp' },
  '.tiff': { type: 'image', format: 'tiff' },
  '.ico':  { type: 'image', format: 'ico' },
  '.psd':  { type: 'image', format: 'psd' },
  '.ai':   { type: 'image', format: 'ai' },
  '.eps':  { type: 'image', format: 'eps' },
  // Video
  '.mp4':  { type: 'video', format: 'mp4' },
  '.avi':  { type: 'video', format: 'avi' },
  '.mov':  { type: 'video', format: 'mov' },
  '.mkv':  { type: 'video', format: 'mkv' },
  '.webm': { type: 'video', format: 'webm' },
  '.flv':  { type: 'video', format: 'flv' },
  '.wmv':  { type: 'video', format: 'wmv' },
  // Audio
  '.mp3':  { type: 'audio', format: 'mp3' },
  '.wav':  { type: 'audio', format: 'wav' },
  '.flac': { type: 'audio', format: 'flac' },
  '.aac':  { type: 'audio', format: 'aac' },
  '.ogg':  { type: 'audio', format: 'ogg' },
  '.wma':  { type: 'audio', format: 'wma' },
  '.m4a':  { type: 'audio', format: 'm4a' },
  // 3D/CAD
  '.stl':  { type: '3d_model', format: 'stl' },
  '.obj':  { type: '3d_model', format: 'obj' },
  '.fbx':  { type: '3d_model', format: 'fbx' },
  '.step': { type: 'cad', format: 'step' },
  '.iges': { type: 'cad', format: 'iges' },
  '.brep': { type: 'cad', format: 'brep' },
  '.3mf':  { type: '3d_model', format: '3mf' },
  // PCB
  '.kicad_pcb': { type: 'pcb', format: 'kicad_pcb' },
  '.kicad_sch': { type: 'schematic', format: 'kicad_sch' },
  '.brd':  { type: 'pcb', format: 'brd' },
  '.sch':  { type: 'schematic', format: 'sch' },
  '.gbr':  { type: 'pcb', format: 'gbr' },
  '.drl':  { type: 'pcb', format: 'drl' },
  '.pos':  { type: 'pcb', format: 'pos' },
  // Archive
  '.zip':  { type: 'archive', format: 'zip' },
  '.rar':  { type: 'archive', format: 'rar' },
  '.7z':   { type: 'archive', format: '7z' },
  '.tar':  { type: 'archive', format: 'tar' },
  '.gz':   { type: 'archive', format: 'gz' },
  '.bz2':  { type: 'archive', format: 'bz2' },
  // Binary
  '.exe':  { type: 'binary', format: 'exe' },
  '.dll':  { type: 'binary', format: 'dll' },
  '.so':   { type: 'binary', format: 'so' },
  '.bin':  { type: 'binary', format: 'bin' },
  '.hex':  { type: 'binary', format: 'hex' },
  '.elf':  { type: 'binary', format: 'elf' },
};

function detectFileType(filename: string): { type: FileType; format: FileFormat } {
  const ext = '.' + filename.split('.').pop()?.toLowerCase();
  return EXTENSION_MAP[ext] || { type: 'other', format: 'other' };
}

function getFileRole(type: FileType, path: string): FileRole {
  const pathLower = path.toLowerCase();
  if (pathLower.includes('readme') || pathLower.includes('docs/') || pathLower.includes('documentation')) return 'documentation';
  if (pathLower.includes('test') || pathLower.includes('spec')) return 'test';
  if (pathLower.includes('config') || pathLower.includes('.env')) return 'config';
  if (pathLower.includes('output') || pathLower.includes('build') || pathLower.includes('dist')) return 'output';
  if (pathLower.includes('archive')) return 'archive';
  if (pathLower.includes('draft')) return 'draft';
  if (pathLower.includes('final')) return 'final';
  if (pathLower.includes('template')) return 'template';
  if (pathLower.includes('reference') || pathLower.includes('ref')) return 'reference';
  if (type === 'image' || type === 'video' || type === 'audio') return 'asset';
  if (type === '3d_model' || type === 'cad' || type === 'pcb' || type === 'schematic') return 'model';
  if (type === 'code') return 'source';
  if (type === 'data') return 'data';
  if (type === 'config') return 'config';
  return 'source';
}

// ═══════════════════════════════════════════════
// WORKSPACE STORE
// ═══════════════════════════════════════════════

export class WorkspaceStore {
  private files: Map<string, FileMetadata> = new Map();
  private folders: Map<string, FolderNode> = new Map();
  private projects: Map<string, { id: string; name: string; type: ProjectType; rootPath: string; created: number }> = new Map();
  private strategies: Map<ProjectType, ProjectStructureStrategy> = new Map();
  private dependencies: FileDependency[] = [];
  private operations: Map<string, OrganizationOperation> = new Map();
  private listeners: Array<() => void> = [];

  constructor() {
    this.registerDefaultStrategies();
  }

  // ─── PROJECT MANAGEMENT ──────────────────

  createProject(name: string, type: ProjectType, rootPath: string): string {
    const id = uid();
    this.projects.set(id, { id, name, type, rootPath, created: now() });
    
    // Create default folder structure
    const strategy = this.strategies.get(type);
    if (strategy) {
      this.createFolderStructure(id, strategy.rootFolders, rootPath);
    }
    
    this.notify();
    return id;
  }

  getProject(id: string) {
    return this.projects.get(id);
  }

  getAllProjects() {
    return Array.from(this.projects.values());
  }

  // ─── FOLDER MANAGEMENT ───────────────────

  private createFolderStructure(projectId: string, templates: FolderTemplate[], parentPath: string): void {
    for (const template of templates) {
      const path = `${parentPath}/${template.path}`.replace(/\/+/g, '/');
      const folder: FolderNode = {
        path,
        name: template.name,
        description: template.description,
        role: template.role,
        children: [],
        files: [],
        isRequired: template.isRequired,
        isGenerated: true,
        containsFileTypes: template.containsFileTypes,
        containsFileRoles: template.containsFileRoles,
      };
      this.folders.set(path, folder);
      
      if (template.children) {
        this.createFolderStructure(projectId, template.children, path);
      }
    }
  }

  getFolder(path: string): FolderNode | undefined {
    return this.folders.get(path);
  }

  getAllFolders(): FolderNode[] {
    return Array.from(this.folders.values());
  }

  getFoldersByProject(projectId: string): FolderNode[] {
    const project = this.projects.get(projectId);
    if (!project) return [];
    return Array.from(this.folders.values())
      .filter(f => f.path.startsWith(project.rootPath));
  }

  // ─── FILE MANAGEMENT ─────────────────────

  createFile(
    name: string,
    path: string,
    projectId: string,
    options: {
      content?: string;
      sizeBytes?: number;
      role?: FileRole;
      tags?: string[];
      semanticDescription?: string;
      sourceType?: FileMetadata['sourceType'];
      sourcePath?: string;
      language?: string;
    } = {},
  ): FileMetadata {
    const id = uid();
    const { type, format } = detectFileType(name);
    const role = options.role || getFileRole(type, path);
    const t = now();
    
    const file: FileMetadata = {
      id,
      name,
      displayName: name.replace(/\.[^/.]+$/, ''),
      path,
      type,
      format,
      role,
      project: projectId,
      parentFolder: path.split('/').slice(0, -1).join('/') || '/',
      tags: options.tags || [],
      semanticDescription: options.semanticDescription || '',
      version: 1,
      versionHistory: [{
        version: 1,
        timestamp: t,
        checksum: options.content ? simpleHash(options.content) : '',
        sizeBytes: options.sizeBytes || 0,
        message: 'Initial creation',
      }],
      status: 'active',
      isPrimary: true,
      sizeBytes: options.sizeBytes || 0,
      created: t,
      modified: t,
      accessed: t,
      dependencies: [],
      dependents: [],
      relatedArtifacts: [],
      relatedTasks: [],
      checksum: options.content ? simpleHash(options.content) : '',
      language: options.language,
      sourceType: options.sourceType || 'created',
      sourcePath: options.sourcePath,
    };
    
    this.files.set(id, file);
    
    // Add to parent folder
    const parent = this.folders.get(file.parentFolder);
    if (parent) {
      parent.files.push(id);
    }
    
    this.notify();
    return file;
  }

  getFile(id: string): FileMetadata | undefined {
    const file = this.files.get(id);
    if (file) {
      file.accessed = now();
    }
    return file;
  }

  getFileByPath(path: string): FileMetadata | undefined {
    return Array.from(this.files.values()).find(f => f.path === path);
  }

  getAllFiles(): FileMetadata[] {
    return Array.from(this.files.values());
  }

  getFilesByProject(projectId: string): FileMetadata[] {
    return Array.from(this.files.values()).filter(f => f.project === projectId);
  }

  getFilesByType(type: FileType): FileMetadata[] {
    return Array.from(this.files.values()).filter(f => f.type === type);
  }

  getFilesByRole(role: FileRole): FileMetadata[] {
    return Array.from(this.files.values()).filter(f => f.role === role);
  }

  searchFiles(query: string): FileMetadata[] {
    const q = query.toLowerCase();
    return Array.from(this.files.values()).filter(f =>
      f.name.toLowerCase().includes(q) ||
      f.displayName.toLowerCase().includes(q) ||
      f.path.toLowerCase().includes(q) ||
      f.semanticDescription.toLowerCase().includes(q) ||
      f.tags.some(t => t.toLowerCase().includes(q))
    );
  }

  // ─── VERSION MANAGEMENT ──────────────────

  updateFile(
    id: string,
    updates: {
      content?: string;
      sizeBytes?: number;
      message?: string;
      changes?: string[];
    },
  ): FileMetadata | undefined {
    const file = this.files.get(id);
    if (!file) return undefined;
    
    const t = now();
    file.version++;
    file.modified = t;
    file.sizeBytes = updates.sizeBytes || file.sizeBytes;
    file.checksum = updates.content ? simpleHash(updates.content) : file.checksum;
    
    file.versionHistory.push({
      version: file.version,
      timestamp: t,
      checksum: file.checksum,
      sizeBytes: file.sizeBytes,
      message: updates.message,
      changes: updates.changes,
    });
    
    this.notify();
    return file;
  }

  getVersionHistory(id: string): VersionEntry[] {
    return this.files.get(id)?.versionHistory || [];
  }

  // ─── DEPENDENCY MANAGEMENT ───────────────

  addDependency(sourceId: string, targetId: string, type: DependencyType, strength: number = 0.5, description: string = ''): void {
    const dep: FileDependency = {
      sourceId,
      targetId,
      type,
      strength,
      description,
    };
    this.dependencies.push(dep);
    
    // Update file records
    const source = this.files.get(sourceId);
    const target = this.files.get(targetId);
    if (source && !source.dependencies.includes(targetId)) {
      source.dependencies.push(targetId);
    }
    if (target && !target.dependents.includes(sourceId)) {
      target.dependents.push(sourceId);
    }
    
    this.notify();
  }

  getFileDependencies(id: string): FileDependency[] {
    return this.dependencies.filter(d => d.sourceId === id || d.targetId === id);
  }

  getDependencyGraph(id: string, depth: number = 2): { nodes: string[]; edges: [string, string][] } {
    const nodes: string[] = [];
    const edges: [string, string][] = [];
    const visited = new Set<string>();
    let frontier = [id];
    
    for (let d = 0; d < depth && frontier.length > 0; d++) {
      const next: string[] = [];
      for (const nodeId of frontier) {
        if (visited.has(nodeId)) continue;
        visited.add(nodeId);
        nodes.push(nodeId);
        
        for (const dep of this.dependencies) {
          if (dep.sourceId === nodeId && !visited.has(dep.targetId)) {
            edges.push([nodeId, dep.targetId]);
            next.push(dep.targetId);
          }
          if (dep.targetId === nodeId && !visited.has(dep.sourceId)) {
            edges.push([dep.sourceId, nodeId]);
            next.push(dep.sourceId);
          }
        }
      }
      frontier = next;
    }
    
    return { nodes, edges };
  }

  // ─── DUPLICATE DETECTION ─────────────────

  detectDuplicates(): DuplicateGroup[] {
    const checksumMap = new Map<string, string[]>();
    
    // Group files by checksum
    for (const [id, file] of this.files) {
      if (file.checksum) {
        const list = checksumMap.get(file.checksum) || [];
        list.push(id);
        checksumMap.set(file.checksum, list);
      }
    }
    
    // Create duplicate groups
    const groups: DuplicateGroup[] = [];
    for (const [checksum, fileIds] of checksumMap) {
      if (fileIds.length > 1) {
        groups.push({
          id: uid(),
          files: fileIds,
          checksum,
          sizeBytes: this.files.get(fileIds[0])?.sizeBytes || 0,
          recommendation: this.getDuplicateRecommendation(fileIds),
          confidence: 0.9,
        });
      }
    }
    
    return groups;
  }

  private getDuplicateRecommendation(fileIds: string[]): DuplicateGroup['recommendation'] {
    const files = fileIds.map(id => this.files.get(id)).filter(Boolean) as FileMetadata[];
    if (files.length === 0) return 'manual';
    
    // Check if any are marked as final
    if (files.some(f => f.role === 'final')) return 'keep_newest';
    
    // Check versions
    const maxVersion = Math.max(...files.map(f => f.version));
    if (maxVersion > 1) return 'keep_newest';
    
    // Default to keeping newest
    return 'keep_newest';
  }

  // ─── ORGANIZATION OPERATIONS ─────────────

  analyzeProject(projectId: string): OrganizationOperation {
    const files = this.getFilesByProject(projectId);
    const operation: OrganizationOperation = {
      id: uid(),
      type: 'analyze',
      status: 'completed',
      projectId,
      files: files.map(f => f.id),
      moves: [],
      renames: [],
      deletes: [],
      archives: [],
      executed: 0,
      failed: 0,
      skipped: 0,
      started: now(),
      completed: now(),
    };
    this.operations.set(operation.id, operation);
    return operation;
  }

  planOrganization(projectId: string, fileIds: string[]): OrganizationOperation {
    const files = fileIds.map(id => this.files.get(id)).filter(Boolean) as FileMetadata[];
    const project = this.projects.get(projectId);
    if (!project) throw new Error('Project not found');
    
    const strategy = this.strategies.get(project.type);
    const moves: FileMove[] = [];
    const renames: FileRename[] = [];
    
    // Analyze each file and plan moves/renames
    for (const file of files) {
      const targetFolder = this.determineTargetFolder(file, strategy);
      if (targetFolder && targetFolder !== file.parentFolder) {
        moves.push({
          fileId: file.id,
          fromPath: file.path,
          toPath: `${targetFolder}/${file.name}`,
          reason: `Move to appropriate folder based on file type and role`,
          dependenciesAffected: file.dependents,
        });
      }
      
      // Check naming convention
      if (strategy) {
        const convention = strategy.namingConventions.find(c => c.fileType === file.type);
        if (convention) {
          const newName = this.applyNamingConvention(file, convention);
          if (newName !== file.name) {
            renames.push({
              fileId: file.id,
              fromName: file.name,
              toName: newName,
              reason: `Apply naming convention: ${convention.pattern}`,
            });
          }
        }
      }
    }
    
    const operation: OrganizationOperation = {
      id: uid(),
      type: 'plan',
      status: 'completed',
      projectId,
      files: fileIds,
      moves,
      renames,
      deletes: [],
      archives: [],
      executed: 0,
      failed: 0,
      skipped: 0,
      started: now(),
      completed: now(),
    };
    this.operations.set(operation.id, operation);
    return operation;
  }

  private determineTargetFolder(file: FileMetadata, strategy?: ProjectStructureStrategy): string | null {
    if (!strategy) return null;
    
    // Find matching folder template
    for (const template of strategy.rootFolders) {
      if (this.folderMatchesFile(template, file)) {
        return template.path;
      }
    }
    
    return null;
  }

  private folderMatchesFile(template: FolderTemplate, file: FileMetadata): boolean {
    // Check file type match
    if (template.containsFileTypes.includes(file.type)) return true;
    
    // Check file role match
    if (template.containsFileRoles.includes(file.role)) return true;
    
    return false;
  }

  private applyNamingConvention(file: FileMetadata, convention: NamingConvention): string {
    // Simple pattern application
    const ext = file.name.split('.').pop() || '';
    const baseName = file.displayName.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    
    return convention.pattern
      .replace('{type}', file.type)
      .replace('{name}', baseName)
      .replace('{version}', file.version.toString())
      .replace('{ext}', ext)
      .replace('{date}', new Date().toISOString().split('T')[0]);
  }

  executeOrganization(operationId: string): boolean {
    const operation = this.operations.get(operationId);
    if (!operation) return false;
    
    operation.status = 'in_progress';
    operation.started = now();
    
    // Execute moves
    for (const move of operation.moves) {
      const file = this.files.get(move.fileId);
      if (file) {
        // Check dependencies
        if (move.dependenciesAffected.length > 0) {
          // Log warning but continue
          console.warn(`Moving ${file.name} affects ${move.dependenciesAffected.length} dependents`);
        }
        
        // Update file path
        file.path = move.toPath;
        file.parentFolder = move.toPath.split('/').slice(0, -1).join('/') || '/';
        file.modified = now();
        
        // Update folder references
        const oldParent = this.folders.get(move.fromPath.split('/').slice(0, -1).join('/') || '/');
        const newParent = this.folders.get(file.parentFolder);
        
        if (oldParent) {
          oldParent.files = oldParent.files.filter(id => id !== move.fileId);
        }
        if (newParent) {
          newParent.files.push(move.fileId);
        }
        
        operation.executed++;
      } else {
        operation.failed++;
      }
    }
    
    // Execute renames
    for (const rename of operation.renames) {
      const file = this.files.get(rename.fileId);
      if (file) {
        file.name = rename.toName;
        file.displayName = rename.toName.replace(/\.[^/.]+$/, '');
        file.modified = now();
        operation.executed++;
      } else {
        operation.failed++;
      }
    }
    
    operation.status = 'completed';
    operation.completed = now();
    this.notify();
    return true;
  }

  // ─── ARCHIVE MANAGEMENT ──────────────────

  archiveFile(fileId: string, archivePath: string): FileArchive | null {
    const file = this.files.get(fileId);
    if (!file) return null;
    
    const archive: FileArchive = {
      fileId,
      fromPath: file.path,
      toPath: `${archivePath}/${file.name}`,
      reason: 'Archive file',
    };
    
    // Move file
    file.path = archive.toPath;
    file.parentFolder = archivePath;
    file.status = 'archived';
    file.modified = now();
    
    // Update folder references
    const oldParent = this.folders.get(archive.fromPath.split('/').slice(0, -1).join('/') || '/');
    const newParent = this.folders.get(archivePath);
    
    if (oldParent) {
      oldParent.files = oldParent.files.filter(id => id !== fileId);
    }
    if (newParent) {
      newParent.files.push(fileId);
    }
    
    this.notify();
    return archive;
  }

  // ─── STRATEGY MANAGEMENT ─────────────────

  registerStrategy(strategy: ProjectStructureStrategy): void {
    this.strategies.set(strategy.projectType, strategy);
  }

  getStrategy(projectType: ProjectType): ProjectStructureStrategy | undefined {
    return this.strategies.get(projectType);
  }

  private registerDefaultStrategies(): void {
    // Software Project
    this.registerStrategy({
      projectType: 'software',
      name: 'Software Development',
      description: 'Standard software project structure',
      rootFolders: [
        { path: 'src', name: 'Source Code', description: 'Source code files', role: 'source', isRequired: true, containsFileTypes: ['code'], containsFileRoles: ['source'], children: [
          { path: 'src/core', name: 'Core', description: 'Core modules', role: 'source', isRequired: false, containsFileTypes: ['code'], containsFileRoles: ['source'] },
          { path: 'src/modules', name: 'Modules', description: 'Feature modules', role: 'source', isRequired: false, containsFileTypes: ['code'], containsFileRoles: ['source'] },
          { path: 'src/services', name: 'Services', description: 'Service layer', role: 'source', isRequired: false, containsFileTypes: ['code'], containsFileRoles: ['source'] },
          { path: 'src/utils', name: 'Utilities', description: 'Utility functions', role: 'source', isRequired: false, containsFileTypes: ['code'], containsFileRoles: ['source'] },
        ]},
        { path: 'tests', name: 'Tests', description: 'Test files', role: 'test', isRequired: true, containsFileTypes: ['code'], containsFileRoles: ['test'] },
        { path: 'docs', name: 'Documentation', description: 'Project documentation', role: 'documentation', isRequired: false, containsFileTypes: ['text', 'document'], containsFileRoles: ['documentation'] },
        { path: 'config', name: 'Configuration', description: 'Configuration files', role: 'config', isRequired: false, containsFileTypes: ['config'], containsFileRoles: ['config'] },
        { path: 'scripts', name: 'Scripts', description: 'Build/utility scripts', role: 'source', isRequired: false, containsFileTypes: ['code'], containsFileRoles: ['source'] },
        { path: 'archive', name: 'Archive', description: 'Archived files', role: 'archive', isRequired: false, containsFileTypes: [], containsFileRoles: ['archive'] },
      ],
      namingConventions: [
        { fileType: 'code', pattern: '{name}.{ext}', examples: ['main.py', 'utils.ts'], rules: ['Lowercase', 'Descriptive'] },
        { fileType: 'config', pattern: '{name}.{ext}', examples: ['config.json', '.env'], rules: ['Lowercase'] },
      ],
      organizationRules: [
        { name: 'Group by feature', description: 'Group related files by feature', condition: 'Multiple files for same feature', action: 'Create feature folder', priority: 1 },
      ],
      versionStrategy: { method: 'semantic', pattern: 'v{major}.{minor}.{patch}', autoVersion: true },
      archiveStrategy: { moveArchived: true, archivePath: 'archive', keepVersions: 5, compress: true },
      domain: 'computer_science_ai',
      artifactTypes: ['code'],
      typicalTools: ['git', 'npm', 'cargo', 'pip'],
    });

    // PCB Project
    this.registerStrategy({
      projectType: 'pcb',
      name: 'PCB Design',
      description: 'PCB design project structure',
      rootFolders: [
        { path: 'requirements', name: 'Requirements', description: 'Project requirements', role: 'documentation', isRequired: true, containsFileTypes: ['document', 'text'], containsFileRoles: ['documentation', 'reference'] },
        { path: 'datasheets', name: 'Datasheets', description: 'Component datasheets', role: 'reference', isRequired: false, containsFileTypes: ['document', 'other'], containsFileRoles: ['reference'] },
        { path: 'schematic', name: 'Schematic', description: 'Schematic files', role: 'source', isRequired: true, containsFileTypes: ['other'], containsFileRoles: ['source'] },
        { path: 'pcb', name: 'PCB Layout', description: 'PCB layout files', role: 'source', isRequired: true, containsFileTypes: ['pcb'], containsFileRoles: ['source'] },
        { path: 'simulation', name: 'Simulation', description: 'Simulation files', role: 'data', isRequired: false, containsFileTypes: ['data'], containsFileRoles: ['data'] },
        { path: 'firmware', name: 'Firmware', description: 'Firmware code', role: 'source', isRequired: false, containsFileTypes: ['code'], containsFileRoles: ['source'] },
        { path: 'mechanical', name: 'Mechanical', description: 'Mechanical files', role: 'model', isRequired: false, containsFileTypes: ['3d_model', 'cad'], containsFileRoles: ['model'] },
        { path: 'bom', name: 'Bill of Materials', description: 'BOM files', role: 'data', isRequired: false, containsFileTypes: ['spreadsheet', 'data'], containsFileRoles: ['data'] },
        { path: 'manufacturing', name: 'Manufacturing', description: 'Manufacturing files', role: 'output', isRequired: false, containsFileTypes: ['pcb', 'data'], containsFileRoles: ['output'] },
        { path: 'testing', name: 'Testing', description: 'Test files', role: 'test', isRequired: false, containsFileTypes: ['data', 'code'], containsFileRoles: ['test'] },
        { path: 'documentation', name: 'Documentation', description: 'Project documentation', role: 'documentation', isRequired: false, containsFileTypes: ['document', 'text'], containsFileRoles: ['documentation'] },
        { path: 'archive', name: 'Archive', description: 'Archived files', role: 'archive', isRequired: false, containsFileTypes: [], containsFileRoles: ['archive'] },
      ],
      namingConventions: [
        { fileType: 'pcb', pattern: '{name}_v{version}.{ext}', examples: ['main_board_v1.0.kicad_pcb'], rules: ['Versioned', 'Descriptive'] },
        { fileType: 'schematic', pattern: '{name}_v{version}.{ext}', examples: ['power_supply_v1.2.kicad_sch'], rules: ['Versioned'] },
      ],
      organizationRules: [
        { name: 'Separate schematic and layout', description: 'Keep schematic and PCB layout separate', condition: 'Always', action: 'Separate folders', priority: 1 },
      ],
      versionStrategy: { method: 'semantic', pattern: 'v{major}.{minor}.{patch}', autoVersion: true },
      archiveStrategy: { moveArchived: true, archivePath: 'archive', keepVersions: 10, compress: true },
      domain: 'electrical_engineering',
      artifactTypes: ['pcb', 'diagram', 'code'],
      typicalTools: ['kicad', 'altium', 'eagle', 'fusion360'],
    });

    // Academic Project
    this.registerStrategy({
      projectType: 'academic',
      name: 'Academic Research',
      description: 'Academic/research project structure',
      rootFolders: [
        { path: 'research_question', name: 'Research Question', description: 'Research question and hypothesis', role: 'documentation', isRequired: true, containsFileTypes: ['document', 'text'], containsFileRoles: ['documentation'] },
        { path: 'literature', name: 'Literature', description: 'Literature review', role: 'reference', isRequired: true, containsFileTypes: ['document', 'other'], containsFileRoles: ['reference'] },
        { path: 'sources', name: 'Sources', description: 'Source materials', role: 'reference', isRequired: false, containsFileTypes: ['document', 'other'], containsFileRoles: ['reference'] },
        { path: 'datasets', name: 'Datasets', description: 'Research datasets', role: 'data', isRequired: false, containsFileTypes: ['data', 'spreadsheet'], containsFileRoles: ['data'] },
        { path: 'analysis', name: 'Analysis', description: 'Analysis scripts and results', role: 'source', isRequired: false, containsFileTypes: ['code', 'data'], containsFileRoles: ['source', 'output'] },
        { path: 'figures', name: 'Figures', description: 'Figures and charts', role: 'asset', isRequired: false, containsFileTypes: ['image'], containsFileRoles: ['asset'] },
        { path: 'tables', name: 'Tables', description: 'Data tables', role: 'data', isRequired: false, containsFileTypes: ['spreadsheet', 'document'], containsFileRoles: ['data'] },
        { path: 'drafts', name: 'Drafts', description: 'Paper drafts', role: 'draft', isRequired: true, containsFileTypes: ['document'], containsFileRoles: ['draft'] },
        { path: 'references', name: 'References', description: 'Reference management', role: 'reference', isRequired: false, containsFileTypes: ['document'], containsFileRoles: ['reference'] },
        { path: 'final', name: 'Final', description: 'Final deliverables', role: 'other', isRequired: true, containsFileTypes: ['document', 'other'], containsFileRoles: ['final'] },
        { path: 'archive', name: 'Archive', description: 'Archived files', role: 'archive', isRequired: false, containsFileTypes: [], containsFileRoles: ['archive'] },
      ],
      namingConventions: [
        { fileType: 'document', pattern: '{name}_v{version}.{ext}', examples: ['paper_draft_v2.docx'], rules: ['Versioned', 'Descriptive'] },
        { fileType: 'image', pattern: '{type}_{name}.{ext}', examples: ['figure_results.png'], rules: ['Descriptive'] },
      ],
      organizationRules: [
        { name: 'Keep drafts separate from final', description: 'Drafts and final should be separate', condition: 'Always', action: 'Separate folders', priority: 1 },
      ],
      versionStrategy: { method: 'sequential', pattern: 'v{version}', autoVersion: true },
      archiveStrategy: { moveArchived: true, archivePath: 'archive', keepVersions: 20, compress: false },
      domain: 'academic_research',
      artifactTypes: ['document', 'dataset', 'image'],
      typicalTools: ['latex', 'overleaf', 'zotero', 'python'],
    });

    // Video Project
    this.registerStrategy({
      projectType: 'video',
      name: 'Video Production',
      description: 'Video production project structure',
      rootFolders: [
        { path: 'concept', name: 'Concept', description: 'Concept and planning', role: 'documentation', isRequired: true, containsFileTypes: ['document', 'text'], containsFileRoles: ['documentation', 'draft'] },
        { path: 'script', name: 'Script', description: 'Scripts and storyboards', role: 'source', isRequired: true, containsFileTypes: ['document', 'text', 'image'], containsFileRoles: ['source', 'reference'] },
        { path: 'footage', name: 'Footage', description: 'Raw footage', role: 'source', isRequired: true, containsFileTypes: ['video'], containsFileRoles: ['source'] },
        { path: 'audio', name: 'Audio', description: 'Audio files', role: 'asset', isRequired: false, containsFileTypes: ['audio'], containsFileRoles: ['asset'] },
        { path: 'graphics', name: 'Graphics', description: 'Graphics and overlays', role: 'asset', isRequired: false, containsFileTypes: ['image', '3d_model'], containsFileRoles: ['asset'] },
        { path: 'project_files', name: 'Project Files', description: 'NLE project files', role: 'config', isRequired: true, containsFileTypes: ['config', 'other'], containsFileRoles: ['config'] },
        { path: 'renders', name: 'Renders', description: 'Rendered outputs', role: 'output', isRequired: false, containsFileTypes: ['video'], containsFileRoles: ['output'] },
        { path: 'exports', name: 'Exports', description: 'Final exports', role: 'other', isRequired: true, containsFileTypes: ['video'], containsFileRoles: ['final'] },
        { path: 'archive', name: 'Archive', description: 'Archived files', role: 'archive', isRequired: false, containsFileTypes: [], containsFileRoles: ['archive'] },
      ],
      namingConventions: [
        { fileType: 'video', pattern: '{type}_{name}_v{version}.{ext}', examples: ['raw_interview_v1.mp4'], rules: ['Versioned', 'Descriptive'] },
        { fileType: 'image', pattern: '{type}_{name}.{ext}', examples: ['overlay_title.png'], rules: ['Descriptive'] },
      ],
      organizationRules: [
        { name: 'Keep raw footage separate', description: 'Raw footage should not be mixed with exports', condition: 'Always', action: 'Separate folders', priority: 1 },
      ],
      versionStrategy: { method: 'sequential', pattern: 'v{version}', autoVersion: true },
      archiveStrategy: { moveArchived: true, archivePath: 'archive', keepVersions: 5, compress: true },
      domain: 'creative',
      artifactTypes: ['video', 'audio', 'image'],
      typicalTools: ['premiere', 'davinci', 'after_effects', 'final_cut'],
    });
  }

  // ─── STATS ───────────────────────────────

  getStats(): WorkspaceStats {
    const files = Array.from(this.files.values());
    const byType: Record<string, number> = {};
    const byRole: Record<string, number> = {};
    const byProjectType: Record<string, number> = {};
    
    for (const file of files) {
      byType[file.type] = (byType[file.type] || 0) + 1;
      byRole[file.role] = (byRole[file.role] || 0) + 1;
    }
    
    for (const project of this.projects.values()) {
      byProjectType[project.type] = (byProjectType[project.type] || 0) + 1;
    }
    
    return {
      totalFiles: files.length,
      totalFolders: this.folders.size,
      totalSizeBytes: files.reduce((sum, f) => sum + f.sizeBytes, 0),
      byType: byType as Record<FileType, number>,
      byRole: byRole as Record<FileRole, number>,
      byProjectType: byProjectType as Record<ProjectType, number>,
      duplicates: this.detectDuplicates().length,
      obsolete: files.filter(f => f.status === 'deprecated').length,
      archived: files.filter(f => f.status === 'archived').length,
      avgVersion: files.length > 0 ? files.reduce((sum, f) => sum + f.version, 0) / files.length : 0,
      avgDepth: 0,
      lastOrganization: Math.max(...Array.from(this.operations.values()).map(o => o.completed || 0), 0),
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
    files: FileMetadata[];
    folders: FolderNode[];
    projects: Array<{ id: string; name: string; type: ProjectType; rootPath: string; created: number }>;
    dependencies: FileDependency[];
  } {
    return {
      files: Array.from(this.files.values()),
      folders: Array.from(this.folders.values()),
      projects: Array.from(this.projects.values()),
      dependencies: this.dependencies,
    };
  }

  importData(data: {
    files: FileMetadata[];
    folders: FolderNode[];
    projects: Array<{ id: string; name: string; type: ProjectType; rootPath: string; created: number }>;
    dependencies: FileDependency[];
  }): void {
    this.files.clear();
    this.folders.clear();
    this.projects.clear();
    this.dependencies = data.dependencies;
    
    for (const file of data.files) {
      this.files.set(file.id, file);
    }
    for (const folder of data.folders) {
      this.folders.set(folder.path, folder);
    }
    for (const project of data.projects) {
      this.projects.set(project.id, project);
    }
    
    this.notify();
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const workspace = new WorkspaceStore();
