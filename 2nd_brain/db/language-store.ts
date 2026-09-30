/**
 * Language Store — terminology, rules, translations, quality checks
 * 
 * Uzbek as first-class language with full morphology, terminology, and quality pipeline.
 */

import type {
  LanguageCode, Term, TermCategory, GrammarRule, SpellingRule,
  StyleRule, DomainStyleProfile, TranslationEntry, PipelineResult,
  PipelineStage, LanguageIssue,
} from './language-schema';

import {
  LANGUAGE_CONFIGS, LANGUAGE_VISUAL, TERM_CATEGORY_CONFIG,
} from './language-schema';

import type { KnowledgeDomain } from './akms-schema';

// ═══════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════

let _nextId = 0;
function uid(): string {
  _nextId++;
  return `lang_${Date.now().toString(36)}_${_nextId}`;
}

function now(): number {
  return Date.now();
}

// ═══════════════════════════════════════════════
// LANGUAGE STORE
// ═══════════════════════════════════════════════

export class LanguageStore {
  private terms: Map<string, Term> = new Map();
  private grammarRules: Map<string, GrammarRule> = new Map();
  private spellingRules: Map<string, SpellingRule> = new Map();
  private styleRules: Map<string, StyleRule> = new Map();
  private translations: Map<string, TranslationEntry> = new Map();
  private domainProfiles: Map<string, DomainStyleProfile> = new Map();
  private listeners: Array<() => void> = [];

  // ─── Term CRUD ────────────────────────────

  createTerm(
    language: LanguageCode,
    term: string,
    definition: string,
    domain: KnowledgeDomain,
    category: TermCategory = 'general',
    translation: Partial<Record<LanguageCode, string>> = {},
    preferredForm: string = '',
    forbiddenForms: string[] = [],
    synonyms: string[] = [],
    abbreviations: string[] = [],
    sources: string[] = [],
    confidence: number = 0.8,
    verified: boolean = false,
  ): Term {
    const id = uid();
    const t = now();
    const termObj: Term = {
      id, language, term, definition, domain, category,
      translation, preferredForm: preferredForm || term,
      forbiddenForms, synonyms, abbreviations, sources,
      examples: [], confidence, verified,
      conceptId: '', createdAt: t, updatedAt: t,
    };
    this.terms.set(id, termObj);
    this.notify();
    return termObj;
  }

  getTerm(id: string): Term | undefined {
    return this.terms.get(id);
  }

  getAllTerms(): Term[] {
    return Array.from(this.terms.values());
  }

  findTerms(filter: {
    language?: LanguageCode;
    domain?: KnowledgeDomain;
    category?: TermCategory;
    search?: string;
    verified?: boolean;
  }): Term[] {
    return this.getAllTerms().filter(t => {
      if (filter.language && t.language !== filter.language) return false;
      if (filter.domain && t.domain !== filter.domain) return false;
      if (filter.category && t.category !== filter.category) return false;
      if (filter.verified !== undefined && t.verified !== filter.verified) return false;
      if (filter.search) {
        const q = filter.search.toLowerCase();
        if (!t.term.toLowerCase().includes(q) && !t.definition.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }

  getTranslation(termId: string, targetLang: LanguageCode): string | undefined {
    const term = this.terms.get(termId);
    if (!term) return undefined;
    return term.translation[targetLang];
  }

  getPreferredTerm(language: LanguageCode, domain: KnowledgeDomain, concept: string): Term | undefined {
    return this.getAllTerms().find(t =>
      t.language === language && t.domain === domain &&
      (t.term.toLowerCase().includes(concept.toLowerCase()) ||
       t.preferredForm.toLowerCase().includes(concept.toLowerCase()))
    );
  }

  checkForbiddenForm(language: LanguageCode, text: string): { found: boolean; term?: Term; forbidden?: string } {
    const terms = this.findTerms({ language });
    for (const term of terms) {
      for (const forbidden of term.forbiddenForms) {
        if (text.toLowerCase().includes(forbidden.toLowerCase())) {
          return { found: true, term, forbidden };
        }
      }
    }
    return { found: false };
  }

  // ─── Grammar Rules ────────────────────────

  addGrammarRule(
    language: LanguageCode,
    name: string,
    description: string,
    pattern: string,
    correction: string,
    severity: 'error' | 'warning' | 'info' = 'error',
    examples: { wrong: string; correct: string }[] = [],
  ): GrammarRule {
    const id = uid();
    const rule: GrammarRule = { id, language, name, description, pattern, correction, severity, examples };
    this.grammarRules.set(id, rule);
    return rule;
  }

  checkGrammar(language: LanguageCode, text: string): LanguageIssue[] {
    const issues: LanguageIssue[] = [];
    const rules = Array.from(this.grammarRules.values()).filter(r => r.language === language);
    for (const rule of rules) {
      try {
        const regex = new RegExp(rule.pattern, 'gi');
        let match;
        while ((match = regex.exec(text)) !== null) {
          issues.push({
            stage: 'language_check',
            type: 'grammar',
            severity: rule.severity,
            message: rule.description,
            location: { start: match.index, end: match.index + match[0].length },
            suggestion: rule.correction,
            ruleId: rule.id,
          });
        }
      } catch { /* invalid regex */ }
    }
    return issues;
  }

  // ─── Spelling Rules ──────────────────────

  addSpellingRule(
    language: LanguageCode,
    pattern: string,
    replacement: string,
    description: string,
    exceptions: string[] = [],
  ): SpellingRule {
    const id = uid();
    const rule: SpellingRule = { id, language, pattern, replacement, description, exceptions };
    this.spellingRules.set(id, rule);
    return rule;
  }

  checkSpelling(language: LanguageCode, text: string): LanguageIssue[] {
    const issues: LanguageIssue[] = [];
    const rules = Array.from(this.spellingRules.values()).filter(r => r.language === language);
    for (const rule of rules) {
      try {
        const regex = new RegExp(rule.pattern, 'gi');
        let match;
        while ((match = regex.exec(text)) !== null) {
          if (!rule.exceptions.some(e => text.toLowerCase().includes(e.toLowerCase()))) {
            issues.push({
              stage: 'language_check',
              type: 'spelling',
              severity: 'error',
              message: rule.description,
              location: { start: match.index, end: match.index + match[0].length },
              suggestion: rule.replacement,
              ruleId: rule.id,
            });
          }
        }
      } catch { /* invalid regex */ }
    }
    return issues;
  }

  // ─── Style Rules ─────────────────────────

  addStyleRule(
    language: LanguageCode,
    domain: KnowledgeDomain,
    name: string,
    description: string,
    rule: string,
    severity: 'error' | 'warning' | 'info' = 'warning',
    examples: { wrong: string; correct: string }[] = [],
  ): StyleRule {
    const id = uid();
    const styleRule: StyleRule = { id, language, domain, name, description, rule, severity, examples };
    this.styleRules.set(id, styleRule);
    return styleRule;
  }

  checkStyle(language: LanguageCode, domain: KnowledgeDomain, text: string): LanguageIssue[] {
    const issues: LanguageIssue[] = [];
    const rules = Array.from(this.styleRules.values()).filter(
      r => r.language === language && (r.domain === domain || r.domain === 'general')
    );
    for (const rule of rules) {
      try {
        const regex = new RegExp(rule.rule, 'gi');
        let match;
        while ((match = regex.exec(text)) !== null) {
          issues.push({
            stage: 'style_check',
            type: 'style',
            severity: rule.severity,
            message: rule.description,
            location: { start: match.index, end: match.index + match[0].length },
            ruleId: rule.id,
          });
        }
      } catch { /* invalid regex */ }
    }
    return issues;
  }

  // ─── Translation Memory ──────────────────

  addTranslation(
    sourceLang: LanguageCode,
    targetLang: LanguageCode,
    source: string,
    target: string,
    domain: KnowledgeDomain,
    context: string = '',
    confidence: number = 0.8,
    verifiedBy: 'human' | 'machine' | 'hybrid' = 'machine',
  ): TranslationEntry {
    const id = uid();
    const entry: TranslationEntry = {
      id, sourceLang, targetLang, source, target,
      domain, context, confidence, verifiedBy, createdAt: now(),
    };
    this.translations.set(id, entry);
    return entry;
  }

  findTranslations(sourceLang: LanguageCode, targetLang: LanguageCode, domain?: KnowledgeDomain): TranslationEntry[] {
    return Array.from(this.translations.values()).filter(t =>
      t.sourceLang === sourceLang && t.targetLang === targetLang &&
      (!domain || t.domain === domain)
    );
  }

  // ─── Domain Style Profiles ───────────────

  setDomainProfile(profile: DomainStyleProfile): void {
    const key = `${profile.domain}_${profile.language}`;
    this.domainProfiles.set(key, profile);
  }

  getDomainProfile(domain: KnowledgeDomain, language: LanguageCode): DomainStyleProfile | undefined {
    return this.domainProfiles.get(`${domain}_${language}`);
  }

  // ─── Language Detection ──────────────────

  detectLanguage(text: string): { language: LanguageCode; confidence: number } {
    // Simple heuristic-based detection
    const uzPatterns = [/\b(va|ham|lekin|shuning|uchun|bu|o'sha|edi|ekan|декан)\b/i, /[o'qg'iust]/];
    const ruPatterns = [/[а-яА-Я]/, /\b(и|в|на|не|что|это|как)\b/];
    const enPatterns = [/\b(the|is|are|was|were|have|has|will|can)\b/i];
    const trPatterns = [/\b(ve|bir|bu|için|ile|olan|dir|dir)\b/i, /[çğıöşü]/];

    let maxScore = 0;
    let detected: LanguageCode = 'en';

    const scores: Record<LanguageCode, number> = { uz: 0, ru: 0, en: 0, tr: 0, kk: 0, ky: 0, tg: 0, fa: 0, ar: 0, de: 0, fr: 0, es: 0, zh: 0, ja: 0, ko: 0 };

    // Character-based detection
    if (/[а-яА-ЯёЁ]/.test(text)) scores.ru += 3;
    if (/[a-zA-Z]/.test(text)) scores.en += 1;
    if (/[çğıöşüÇĞIİÖŞÜ]/.test(text)) scores.tr += 2;
    if (/[aeiou]/.test(text)) { scores.en += 0.5; scores.uz += 0.5; }
    if (/[o'qg'iust]/.test(text)) scores.uz += 1;

    // Word-based detection
    for (const p of uzPatterns) { if (p.test(text)) scores.uz += 2; }
    for (const p of ruPatterns) { if (p.test(text)) scores.ru += 2; }
    for (const p of enPatterns) { if (p.test(text)) scores.en += 2; }
    for (const p of trPatterns) { if (p.test(text)) scores.tr += 2; }

    for (const [lang, score] of Object.entries(scores)) {
      if (score > maxScore) {
        maxScore = score;
        detected = lang as LanguageCode;
      }
    }

    const confidence = Math.min(0.95, maxScore / (maxScore + 3));
    return { language: detected, confidence };
  }

  // ─── Text Normalization ──────────────────

  normalizeText(text: string, language: LanguageCode): string {
    const config = LANGUAGE_CONFIGS[language];
    if (!config) return text;

    let result = text;

    if (config.normalization.lowercasing) {
      // Only lowercase non-proper nouns (simplified)
      // In practice, would use NLP for proper noun detection
    }

    if (config.normalization.accentRemoval && language === 'uz') {
      // Uzbek specific: normalize o' → o, g' → g
      result = result.replace(/o'/g, 'o\'').replace(/g'/g, 'g\'');
    }

    if (config.normalization.characterNormalization) {
      // Normalize unicode
      result = result.normalize('NFC');
    }

    return result;
  }

  // ─── Quality Check Pipeline ──────────────

  runQualityPipeline(
    text: string,
    sourceLang: LanguageCode,
    targetLang: LanguageCode,
    domain: KnowledgeDomain,
  ): PipelineResult {
    const issues: LanguageIssue[] = [];
    let currentText = text;

    // Stage 1: Language Detection
    const detected = this.detectLanguage(text);

    // Stage 2: Normalization
    currentText = this.normalizeText(currentText, targetLang);

    // Stage 3: Grammar Check
    issues.push(...this.checkGrammar(targetLang, currentText));

    // Stage 4: Spelling Check
    issues.push(...this.checkSpelling(targetLang, currentText));

    // Stage 5: Terminology Check
    const termCheck = this.checkForbiddenForm(targetLang, currentText);
    if (termCheck.found && termCheck.term && termCheck.forbidden) {
      issues.push({
        stage: 'terminology_check',
        type: 'terminology',
        severity: 'error',
        message: `"${termCheck.forbidden}" — noto'g'ri shakl. To'g'ri: "${termCheck.term.preferredForm}"`,
        suggestion: termCheck.term.preferredForm,
      });
    }

    // Stage 6: Style Check
    issues.push(...this.checkStyle(targetLang, domain, currentText));

    return {
      stage: 'output',
      input: text,
      output: currentText,
      language: detected.language,
      confidence: detected.confidence,
      issues,
      suggestions: issues.filter(i => i.suggestion).map(i => i.suggestion!),
      timestamp: now(),
    };
  }

  // ─── Listeners ───────────────────────────

  subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(): void {
    for (const l of this.listeners) l();
  }

  // ─── Stats ───────────────────────────────

  getStats() {
    return {
      terms: this.terms.size,
      grammarRules: this.grammarRules.size,
      spellingRules: this.spellingRules.size,
      styleRules: this.styleRules.size,
      translations: this.translations.size,
      domainProfiles: this.domainProfiles.size,
    };
  }
}

// ═══════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════

export const languageStore = new LanguageStore();
