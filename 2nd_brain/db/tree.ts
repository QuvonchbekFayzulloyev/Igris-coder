/**
 * Tree Module — Binary tree storage with semantic projection
 * 
 * Implements:
 *   - Binary tree CRUD (O(log n) lookup)
 *   - Semantic Father management
 *   - Radius-based traversal
 *   - Semantic relationship layer
 *   - Projection generation for visualization
 * 
 * Architecture:
 *   BINARY TREE = Actual Storage (fast lookup)
 *   SEMANTIC INDEX = Semantic mapping
 *   SEMANTIC FATHER = Subtree center
 *   RADIUS = Visualization layers
 *   SEMANTIC GRAPH = Relationship layer
 * 
 * Usage:
 *   import { treeStore } from './db/tree';
 *   
 *   // Create nodes
 *   const root = treeStore.createNode('root', 'My Project', 'Project root', 'general');
 *   const concept = treeStore.createNode('concept', 'Ohm\'s Law', 'V = IR', 'electrical_engineering', { parentId: root.id });
 *   
 *   // Create semantic father
 *   const father = treeStore.createFather(concept.id, 'Circuit Theory', 'electrical_engineering');
 *   
 *   // Add relations
 *   treeStore.addRelation(concept.id, anotherNode.id, 'related_to', 0.8);
 *   
 *   // Get projection
 *   const projection = treeStore.generateProjection(father.id);
 */

export * from './tree-schema';
export { TreeStore, treeStore } from './tree-store';
