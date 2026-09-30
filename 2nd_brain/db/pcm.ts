/**
 * PCM — Professional Capability Model
 * 
 * Universal profession/task/skill architecture:
 *   Profession → Specialization → Competency → Task → Workflow
 * 
 * Usage:
 *   import { pcm, seedPCM } from './db/pcm';
 *   seedPCM();
 *   const capMap = pcm.getProfessionCapabilityMap(professionId);
 *   const taskGraph = pcm.getTaskGraph(taskId);
 */

export * from './pcm-schema';
export { PCMStore, pcm } from './pcm-store';
export { seedPCM, getPCMStats } from './pcm-seed';
