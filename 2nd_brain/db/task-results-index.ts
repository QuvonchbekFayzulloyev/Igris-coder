/**
 * Task Results Module — Links task outputs to the broader knowledge system
 * 
 * Connects:
 *   - Task Outputs → GCM Artifacts
 *   - Task Verification → Evidence entries
 *   - Task Execution → Memory entries
 *   - Task Dependencies → Task graph
 *   - Task Results → Knowledge updates
 * 
 * Usage:
 *   import { taskResultConnector } from './db/task-results';
 *   
 *   // Create result
 *   const result = taskResultConnector.createResult('task_123', 'Schematic Design', 'electrical_engineering', inputs);
 *   
 *   // Add output
 *   taskResultConnector.addOutput(result.id, { name: 'Schematic', type: 'file', format: 'kicad_sch' });
 *   
 *   // Complete verification
 *   taskResultConnector.completeVerification(result.id, { name: 'ERC', method: 'testing' }, true, 'tested');
 *   
 *   // Complete execution
 *   taskResultConnector.completeExecution(result.id, 'completed', ['Simple topology worked']);
 *   
 *   // Record memory
 *   taskResultConnector.recordMemory(result.id, 'Designed LED driver', ['Topology selection'], [], ['Keep it simple']);
 */

export * from './task-results';
