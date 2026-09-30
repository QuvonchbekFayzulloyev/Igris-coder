/**
 * Workspace Module — Intelligent file/folder organization
 * 
 * Implements:
 *   - File Organization with metadata
 *   - Folder Architecture (project type → structure strategy)
 *   - File Classification (type detection, role assignment)
 *   - Naming System with conventions
 *   - Version Management
 *   - Dependency Tracking
 *   - Duplicate Detection
 *   - Archive Management
 *   - Semantic File Retrieval
 * 
 * Architecture:
 *   Project Type → Folder Strategy → File Classification → Naming
 *   → Versioning → Dependency Tracking → Duplicate Detection
 *   → Archive → Semantic Retrieval
 * 
 * Usage:
 *   import { workspace } from './db/workspace';
 *   
 *   // Create project
 *   const projectId = workspace.createProject('My PCB', 'pcb', '/projects/my_pcb');
 *   
 *   // Create file
 *   const file = workspace.createFile('main.kicad_pcb', 'pcb/main.kicad_pcb', projectId, {
 *     semanticDescription: 'Main PCB layout',
 *   });
 *   
 *   // Detect duplicates
 *   const duplicates = workspace.detectDuplicates();
 *   
 *   // Search files
 *   const results = workspace.searchFiles('PCB layout');
 */

export * from './workspace-schema';
export { WorkspaceStore, workspace } from './workspace-store';
