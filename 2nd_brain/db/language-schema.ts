/**
 * AKMS Language Layer — Multilingual Knowledge & Quality System
 * 
 * Uzbek as first-class language with:
 *   - Terminology Graph (concept → translations, domain, forbidden forms)
 *   - Language Quality Pipeline (detect → normalize → check → output)
 *   - Domain-specific style rules (academic, engineering, economic)
 *   - Grammar & morphology rules
 *   - Evidence-based translation verification
 * 
 * Architecture:
 *   User Input → Language Detection → Normalization → Intent Parsing
 *   → Knowledge Retrieval → Reasoning → Uzbek Generation
 *   → Language Check → Terminology Check → Fact Check → Final Output
 */

import type { KnowledgeDomain, Entity, Evidence } from './akms-schema';

// ═══════════════════════════════════════════════
// LANGUAGE TYPES
// ═══════════════════════════════════════════════

export type LanguageCode = 'uz' | 'ru' | 'en' | 'tr' | 'kk' | 'ky' | 'tg' | 'fa' | 'ar' | 'de' | 'fr' | 'es' | 'zh' | 'ja' | 'ko';

export interface LanguageConfig {
  code: LanguageCode;
  name: string;
  nativeName: string;
  isRtl: boolean;
  script: 'latin' | 'cyrillic' | 'arabic' | 'other';
  features: {
    cases: boolean;
    genders: boolean;
    articles: boolean;
    tonal: boolean;
    agglutinative: boolean;
    vowelHarmony: boolean;
  };
  normalization: {
    lowercasing: boolean;
    accentRemoval: boolean;
    characterNormalization: boolean;
  };
}

export const LANGUAGE_CONFIGS: Record<LanguageCode, LanguageConfig> = {
  uz: {
    code: 'uz', name: 'Uzbek', nativeName: "O'zbek tili",
    isRtl: false, script: 'latin',
    features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: true, vowelHarmony: true },
    normalization: { lowercasing: true, accentRemoval: true, characterNormalization: true },
  },
  ru: {
    code: 'ru', name: 'Russian', nativeName: 'Русский язык',
    isRtl: false, script: 'cyrillic',
    features: { cases: true, genders: true, articles: false, tonal: false, agglutinative: false, vowelHarmony: false },
    normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true },
  },
  en: {
    code: 'en', name: 'English', nativeName: 'English',
    isRtl: false, script: 'latin',
    features: { cases: false, genders: false, articles: true, tonal: false, agglutinative: false, vowelHarmony: false },
    normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true },
  },
  tr: {
    code: 'tr', name: 'Turkish', nativeName: 'Türkçe',
    isRtl: false, script: 'latin',
    features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: true, vowelHarmony: true },
    normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true },
  },
  kk: { code: 'kk', name: 'Kazakh', nativeName: 'Қазақ тілі', isRtl: false, script: 'latin', features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: true, vowelHarmony: true }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  ky: { code: 'ky', name: 'Kyrgyz', nativeName: 'Кыргызча', isRtl: false, script: 'cyrillic', features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: true, vowelHarmony: true }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  tg: { code: 'tg', name: 'Tajik', nativeName: 'Тоҷикӣ', isRtl: false, script: 'cyrillic', features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: false, vowelHarmony: false }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  fa: { code: 'fa', name: 'Persian', nativeName: 'فارسی', isRtl: true, script: 'arabic', features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: false, vowelHarmony: false }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  ar: { code: 'ar', name: 'Arabic', nativeName: 'العربية', isRtl: true, script: 'arabic', features: { cases: false, genders: true, articles: true, tonal: false, agglutinative: false, vowelHarmony: false }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  de: { code: 'de', name: 'German', nativeName: 'Deutsch', isRtl: false, script: 'latin', features: { cases: true, genders: true, articles: true, tonal: false, agglutinative: false, vowelHarmony: false }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  fr: { code: 'fr', name: 'French', nativeName: 'Français', isRtl: false, script: 'latin', features: { cases: false, genders: true, articles: true, tonal: false, agglutinative: false, vowelHarmony: false }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  es: { code: 'es', name: 'Spanish', nativeName: 'Español', isRtl: false, script: 'latin', features: { cases: false, genders: true, articles: true, tonal: false, agglutinative: false, vowelHarmony: false }, normalization: { lowercasing: true, accentRemoval: false, characterNormalization: true } },
  zh: { code: 'zh', name: 'Chinese', nativeName: '中文', isRtl: false, script: 'other', features: { cases: false, genders: false, articles: false, tonal: true, agglutinative: false, vowelHarmony: false }, normalization: { lowercasing: false, accentRemoval: false, characterNormalization: true } },
  ja: { code: 'ja', name: 'Japanese', nativeName: '日本語', isRtl: false, script: 'other', features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: true, vowelHarmony: false }, normalization: { lowercasing: false, accentRemoval: false, characterNormalization: true } },
  ko: { code: 'ko', name: 'Korean', nativeName: '한국어', isRtl: false, script: 'other', features: { cases: false, genders: false, articles: false, tonal: false, agglutinative: true, vowelHarmony: false }, normalization: { lowercasing: false, accentRemoval: false, characterNormalization: true } },
};

// ═══════════════════════════════════════════════
// TERMINOLOGY — asosiy termin modeli
// ═══════════════════════════════════════════════

export type TermCategory =
  | 'general'
  | 'academic'
  | 'technical'
  | 'scientific'
  | 'engineering'
  | 'economic'
  | 'legal'
  | 'medical'
  | 'creative'
  | 'it'
  | 'math'
  | 'physics'
  | 'chemistry'
  | 'linguistic';

export interface Term {
  id: string;
  conceptId: string;           // bog'langan concept entity ID
  language: LanguageCode;
  term: string;                // "mashinali o'rganish"
  definition: string;          // qisqacha ta'rif
  domain: KnowledgeDomain;
  category: TermCategory;
  synonyms: string[];          // "sun'iy intellekt o'rganishi"
  abbreviations: string[];     // "MO", "ML"
  translation: Partial<Record<LanguageCode, string>>;  // { en: "machine learning", ru: "машинное обучение" }
  preferredForm: string;       // "mashinali o'rganish" (rasmiy)
  forbiddenForms: string[];    // ["mashina o'rganishi", "mashinaviy o'rganish"]
  examples: string[];          // ["Mashinali o'rganish algoritmlari..."]
  sources: string[];           // ["O'zbekiston FA terminologiya komissiyasi"]
  confidence: number;          // 0..1
  verified: boolean;
  createdAt: number;
  updatedAt: number;
}

// ═══════════════════════════════════════════════
// LANGUAGE RULES
// ═══════════════════════════════════════════════

export interface GrammarRule {
  id: string;
  language: LanguageCode;
  name: string;
  description: string;
  pattern: string;             // regex yoki qoida
  correction: string;
  severity: 'error' | 'warning' | 'info';
  examples: { wrong: string; correct: string }[];
}

export interface SpellingRule {
  id: string;
  language: LanguageCode;
  pattern: string;             // regex
  replacement: string;
  description: string;
  exceptions: string[];
}

export interface StyleRule {
  id: string;
  language: LanguageCode;
  domain: KnowledgeDomain;
  name: string;
  description: string;
  rule: string;
  examples: { wrong: string; correct: string }[];
  severity: 'error' | 'warning' | 'info';
}

// ═══════════════════════════════════════════════
// LANGUAGE QUALITY PIPELINE
// ═══════════════════════════════════════════════

export type PipelineStage =
  | 'input'
  | 'language_detection'
  | 'normalization'
  | 'intent_parsing'
  | 'knowledge_retrieval'
  | 'reasoning'
  | 'generation'
  | 'language_check'
  | 'terminology_check'
  | 'fact_check'
  | 'style_check'
  | 'output';

export interface PipelineResult {
  stage: PipelineStage;
  input: string;
  output: string;
  language: LanguageCode;
  confidence: number;
  issues: LanguageIssue[];
  suggestions: string[];
  timestamp: number;
}

export interface LanguageIssue {
  stage: PipelineStage;
  type: 'grammar' | 'spelling' | 'terminology' | 'style' | 'fact' | 'consistency';
  severity: 'error' | 'warning' | 'info';
  message: string;
  location?: { start: number; end: number };
  suggestion?: string;
  ruleId?: string;
}

// ═══════════════════════════════════════════════
// DOMAIN STYLE PROFILES
// ═══════════════════════════════════════════════

export interface DomainStyleProfile {
  domain: KnowledgeDomain;
  language: LanguageCode;
  formality: 'formal' | 'semi_formal' | 'informal';
  technicalDepth: 'basic' | 'intermediate' | 'advanced' | 'expert';
  preferredTerminology: 'native' | 'borrowed' | 'mixed';
  citationStyle: 'apa' | 'mla' | 'chicago' | 'gost' | 'none';
  sentenceLength: 'short' | 'medium' | 'long' | 'mixed';
  vocabulary: 'standard' | 'technical' | 'academic' | 'colloquial';
  features: {
    usePassiveVoice: boolean;
    useFirstPerson: boolean;
    useAbbreviations: boolean;
    useNumbersInText: boolean;
    maxSentenceLength: number;
  };
}

// ═══════════════════════════════════════════════
// TRANSLATION MEMORY
// ═══════════════════════════════════════════════

export interface TranslationEntry {
  id: string;
  sourceLang: LanguageCode;
  targetLang: LanguageCode;
  source: string;
  target: string;
  domain: KnowledgeDomain;
  context: string;
  confidence: number;
  verifiedBy: 'human' | 'machine' | 'hybrid';
  createdAt: number;
}

// ═══════════════════════════════════════════════
// UZBEK-SPECIFIC MORPHOLOGY
// ═══════════════════════════════════════════════

export interface UzbekMorphology {
  suffixes: {
    case: Record<string, string>;    // nominoz: -ni, dativ: -ga, etc.
    tense: Record<string, string>;   // o'tgan: -di, kelajak: -yapti, etc.
    person: Record<string, string>;  // 1-shaxs: -man, 2-shaxs: -san, etc.
    plural: Record<string, string>;  // -lar, -lar
    possessive: Record<string, string>;  // -im, -ing, -i, etc.
  };
  vowelHarmony: {
    front: string[];
    back: string[];
    rules: string[];
  };
  commonSuffixes: Record<string, string>;
}

// ═══════════════════════════════════════════════
// VISUAL CONFIG
// ═══════════════════════════════════════════════

export const LANGUAGE_VISUAL: Record<LanguageCode, { color: string; flag: string; label: string }> = {
  uz: { color: '#10b981', flag: '🇺🇿', label: "O'zbekcha" },
  ru: { color: '#3b82f6', flag: '🇷🇺', label: 'Русский' },
  en: { color: '#8b5cf6', flag: '🇬🇧', label: 'English' },
  tr: { color: '#ef4444', flag: '🇹🇷', label: 'Türkçe' },
  kk: { color: '#06b6d4', flag: '🇰🇿', label: 'Қазақша' },
  ky: { color: '#f59e0b', flag: '🇰🇬', label: 'Кыргызча' },
  tg: { color: '#ec4899', flag: '🇹🇯', label: 'Тоҷикӣ' },
  fa: { color: '#14b8a6', flag: '🇮🇷', label: 'فارسی' },
  ar: { color: '#d97706', flag: '🇸🇦', label: 'العربية' },
  de: { color: '#6366f1', flag: '🇩🇪', label: 'Deutsch' },
  fr: { color: '#1e40af', flag: '🇫🇷', label: 'Français' },
  es: { color: '#f97316', flag: '🇪🇸', label: 'Español' },
  zh: { color: '#dc2626', flag: '🇨🇳', label: '中文' },
  ja: { color: '#be185d', flag: '🇯🇵', label: '日本語' },
  ko: { color: '#7c3aed', flag: '🇰🇷', label: '한국어' },
};

export const TERM_CATEGORY_CONFIG: Record<TermCategory, { color: string; icon: string; label: string }> = {
  general:     { color: '#71717a', icon: '📝', label: 'General' },
  academic:    { color: '#8b5cf6', icon: '📚', label: 'Academic' },
  technical:   { color: '#0891b2', icon: '🔧', label: 'Technical' },
  scientific:  { color: '#6366f1', icon: '🔬', label: 'Scientific' },
  engineering: { color: '#f59e0b', icon: '⚙️', label: 'Engineering' },
  economic:    { color: '#10b981', icon: '📈', label: 'Economic' },
  legal:       { color: '#9333ea', icon: '⚖️', label: 'Legal' },
  medical:     { color: '#dc2626', icon: '🏥', label: 'Medical' },
  creative:    { color: '#ec4899', icon: '🎨', label: 'Creative' },
  it:          { color: '#3b82f6', icon: '💻', label: 'IT' },
  math:        { color: '#be185d', icon: '🔢', label: 'Mathematics' },
  physics:     { color: '#1d4ed8', icon: '⚛️', label: 'Physics' },
  chemistry:   { color: '#65a30d', icon: '🧪', label: 'Chemistry' },
  linguistic:  { color: '#a855f7', icon: '🗣️', label: 'Linguistics' },
};
