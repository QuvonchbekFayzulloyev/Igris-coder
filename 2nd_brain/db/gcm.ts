/**
 * GCM — Generation Capability Model
 * 
 * Artifact Production System:
 *   Intent → Purpose → Context → Requirements → Knowledge →
 *   Capabilities → Tools → Generation → Validation →
 *   Real-Use Test → Artifact → Version / Memory
 * 
 * Usage:
 *   import { gcm, seedGCM } from './db/gcm';
 *   seedGCM();
 *   const artifact = gcm.createArtifact('Report', 'report', 'pdf', 'Academic report', 'economics');
 *   const pipeline = gcm.createStandardPipeline('Generate Report', 'Write economics report', 'economics', 'report');
 */

export * from './gcm-schema';
export { GCMStore, gcm } from './gcm-store';
