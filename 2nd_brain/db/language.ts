/**
 * AKMS Language Layer — Multilingual Knowledge & Quality System
 * 
 * Uzbek as first-class language with:
 *   - Terminology Graph
 *   - Language Quality Pipeline
 *   - Domain-specific style rules
 *   - Grammar & morphology rules
 * 
 * Usage:
 *   import { languageStore, seedUzbekTerminology } from './db/language';
 *   seedUzbekTerminology();
 *   const result = languageStore.runQualityPipeline(text, 'en', 'uz', 'academic_research');
 */

export * from './language-schema';
export { LanguageStore, languageStore } from './language-store';
export { seedUzbekTerminology, getLanguageStats } from './uzbek-terminology';
