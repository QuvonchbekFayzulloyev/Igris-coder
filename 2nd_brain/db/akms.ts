/**
 * AKMS — Agent Knowledge & Memory System
 * 
 * Unified system for:
 *   - Knowledge (what the agent knows)
 *   - Memory (what the agent has done and learned)
 *   - Evidence (proof and verification)
 *   - Domains (multi-disciplinary coverage)
 *   - Language (multilingual terminology & quality)
 *   - Professions (capability maps for all professional tasks)
 *   - Generation (artifact production system)
 * 
 * Architecture:
 *   General-Purpose Multimodal AI Agent
 *   + Cognitive Knowledge & Memory System
 *   + Multilingual Language Layer (Uzbek first-class)
 *   + Professional Capability Model (all professions)
 *   + Generation Capability Model (artifact production)
 * 
 * Philosophy:
 *   Knowledge tells the agent what is true.
 *   Skill tells it how to do something.
 *   Tool lets it do it.
 *   Task tells it what needs to be done.
 *   Workflow tells it in what order.
 *   Profession tells it which capabilities belong together.
 *   Generation tells it how to create artifacts.
 *   Evidence tells it why the result can be trusted.
 *   Memory tells it what happened before.
 * 
 * Usage:
 *   import { akms, seedAKMS } from './db/akms';
 *   import { languageStore, seedUzbekTerminology } from './db/language';
 *   import { pcm, seedPCM } from './db/pcm';
 *   import { gcm } from './db/gcm';
 *   import { runtime } from './db/runtime';
 *   import { workspace } from './db/workspace';
 *   import { taskResultConnector } from './db/task-results';
 *   import { treeStore } from './db/tree';
 *   
 *   seedAKMS();
 *   seedUzbekTerminology();
 *   seedPCM();
 *   
 *   const entity = akms.createEntity('concept', 'Ohm\'s Law', '...', 'electrical_engineering');
 *   const response = akms.getNeighborhood(entity.id, 2);
 *   const quality = languageStore.runQualityPipeline(text, 'en', 'uz', 'electrical_engineering');
 *   const capMap = pcm.getProfessionCapabilityMap(professionId);
 *   const artifact = gcm.createArtifact('Report', 'report', 'pdf', 'Academic report', 'economics');
 *   const context = runtime.taskContextBuilder.buildContext(taskId);
 *   const projectId = workspace.createProject('My PCB', 'pcb', '/projects/my_pcb');
 *   const result = taskResultConnector.createResult(taskId, 'Schematic Design', 'electrical_engineering', inputs);
 *   const treeRoot = treeStore.createNode('root', 'My Project', 'Project root', 'general');
 */

export * from './akms-schema';
export { AKMSStore, akms } from './akms-store';
export { seedAKMS, getAKMSStats } from './akms-seed';
export * from './language';
export * from './pcm';
export * from './gcm';
export * from './runtime';
export * from './workspace';
export * from './task-results';
export * from './tree';

