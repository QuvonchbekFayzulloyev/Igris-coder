/**
 * Runtime Module — Lightweight inference from deep knowledge
 * 
 * Implements:
 *   - Context Manager (HOT/WARM/COLD tiers)
 *   - Selective Retrieval Engine
 *   - Shared Capability Registry
 *   - Task Context Builder
 *   - Evidence Status tracking
 * 
 * Architecture:
 *   DEEP DATA → STRUCTURED KNOWLEDGE → GRAPH RELATIONS
 *   → SELECTIVE RETRIEVAL → TASK-SPECIFIC CONTEXT
 *   → MINIMAL REASONING → SPECIALIZED TOOL
 *   → OBJECTIVE VERIFICATION → EVIDENCE
 *   → TRUSTED ARTIFACT
 * 
 * Usage:
 *   import { runtime } from './db/runtime';
 *   
 *   // Build context for a task
 *   const context = runtime.taskContextBuilder.buildContext('taskId');
 *   
 *   // Get summary for LLM
 *   const summary = runtime.taskContextBuilder.getContextSummary(context);
 *   
 *   // Check stats
 *   const stats = runtime.getStats();
 */

export * from './runtime-schema';
export { ContextManager, RetrievalEngine, SharedCapabilityRegistry, TaskContextBuilder, RuntimeStore, runtime } from './runtime-store';
