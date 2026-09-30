/**
 * AKMSOverlay — adds AKMS-specific visual indicators to BrainView
 * 
 * Features:
 *   - Domain-based coloring (alternative to kind-based)
 *   - Evidence/verification indicators on nodes
 *   - Terminology check results
 *   - Memory type indicators
 *   - Confidence level visualization
 * 
 * This component is designed to be added to BrainView without breaking
 * the existing kind-based coloring and interaction system.
 */

import React, { useState, useMemo } from 'react';
import type { Entity, KnowledgeDomain, VerificationStatus, EntityType } from '../../db/akms-schema';
import { ENTITY_TYPE_CONFIG, DOMAIN_CONFIG, STATE_CONFIG, VERIFICATION_CONFIG } from '../../db/akms-schema';
import { akms } from '../../db/akms-store';
import { languageStore } from '../../db/language-store';
import { seedAKMS } from '../../db/akms-seed';
import { seedUzbekTerminology } from '../../db/uzbek-terminology';

// ═══════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════

interface AKMSOverlayProps {
  /** BrainView dan kelgan node ID'lar */
  nodeIds: string[];
  /** Tanlangan node ID */
  selectedNodeId: string | null;
  /** Hover qilingan node ID */
  hoveredNodeId: string | null;
  /** Visual mode: 'kind' (default) yoki 'domain' */
  visualMode: 'kind' | 'domain' | 'verification';
  /** Overlay'ni yoqish/o'chirish */
  enabled: boolean;
  /** Terminology check natijasi */
  terminologyResults?: TerminologyResult[];
}

interface TerminologyResult {
  term: string;
  correctForm: string;
  forbiddenForm?: string;
  domain: KnowledgeDomain;
  confidence: number;
}

interface DomainStats {
  domain: KnowledgeDomain;
  count: number;
  percentage: number;
  color: string;
  icon: string;
  label: string;
}

// ═══════════════════════════════════════════════
// DOMAIN COLOR MAPPING (AKMS asosida)
// ═══════════════════════════════════════════════

const DOMAIN_COLORS: Record<KnowledgeDomain, string> = {
  academic_research: '#8b5cf6',
  microsoft_365: '#0078d4',
  software_engineering: '#10b981',
  computer_science_ai: '#6366f1',
  electrical_engineering: '#f59e0b',
  mechanical_engineering: '#78716c',
  civil_engineering: '#a16207',
  control_automation: '#0891b2',
  hardware_engineering: '#475569',
  systems_engineering: '#7c3aed',
  creative: '#ec4899',
  economics: '#059669',
  finance: '#d97706',
  business: '#2563eb',
  project_management: '#ea580c',
  data_science: '#0ea5e9',
  mathematics: '#be185d',
  physics: '#1d4ed8',
  chemistry_materials: '#65a30d',
  legal_compliance: '#9333ea',
  cybersecurity: '#dc2626',
  research_operations: '#7c2d12',
  personal_productivity: '#16a34a',
  general: '#71717a',
};

// ═══════════════════════════════════════════════
// VERIFICATION STATUS COLORS
// ═══════════════════════════════════════════════

const VERIFICATION_COLORS: Record<VerificationStatus, string> = {
  unverified: '#71717a',
  claim: '#f59e0b',
  sourced: '#3b82f6',
  reasoned: '#8b5cf6',
  tested: '#f97316',
  simulated: '#06b6d4',
  verified: '#10b981',
  disputed: '#dc2626',
  refuted: '#dc2626',
};

// ═══════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════

export function AKMSOverlay({
  nodeIds,
  selectedNodeId,
  hoveredNodeId,
  visualMode,
  enabled,
  terminologyResults = [],
}: AKMSOverlayProps) {
  const [showDomainPanel, setShowDomainPanel] = useState(false);
  const [showTerminologyPanel, setShowTerminologyPanel] = useState(false);

  // Initialize AKMS if empty
  React.useEffect(() => {
    if (akms.getAllEntities().length === 0) {
      seedAKMS();
    }
    if (languageStore.getAllTerms().length === 0) {
      seedUzbekTerminology();
    }
  }, []);

  // Get entities for displayed nodes
  const nodeEntities = useMemo(() => {
    const entities: Map<string, Entity> = new Map();
    for (const id of nodeIds) {
      const entity = akms.getEntity(id);
      if (entity) {
        entities.set(id, entity);
      }
    }
    return entities;
  }, [nodeIds]);

  // Domain statistics
  const domainStats = useMemo((): DomainStats[] => {
    const counts: Record<KnowledgeDomain, number> = {} as Record<KnowledgeDomain, number>;
    for (const entity of nodeEntities.values()) {
      counts[entity.domain] = (counts[entity.domain] || 0) + 1;
    }
    const total = nodeEntities.size || 1;
    return Object.entries(counts)
      .map(([domain, count]) => ({
        domain: domain as KnowledgeDomain,
        count,
        percentage: (count / total) * 100,
        color: DOMAIN_COLORS[domain as KnowledgeDomain] || '#71717a',
        icon: DOMAIN_CONFIG[domain as KnowledgeDomain]?.icon || '📝',
        label: DOMAIN_CONFIG[domain as KnowledgeDomain]?.label || domain,
      }))
      .sort((a, b) => b.count - a.count);
  }, [nodeEntities]);

  // Verification statistics
  const verificationStats = useMemo(() => {
    const counts: Record<VerificationStatus, number> = {} as Record<VerificationStatus, number>;
    for (const entity of nodeEntities.values()) {
      counts[entity.verification] = (counts[entity.verification] || 0) + 1;
    }
    return Object.entries(counts).map(([status, count]) => ({
      status: status as VerificationStatus,
      count,
      color: VERIFICATION_COLORS[status as VerificationStatus] || '#71717a',
      label: VERIFICATION_CONFIG[status as VerificationStatus]?.label || status,
      icon: VERIFICATION_CONFIG[status as VerificationStatus]?.icon || '?',
    }));
  }, [nodeEntities]);

  // Get node visual properties based on mode
  const getNodeVisual = (nodeId: string): { fill: string; stroke: string; indicator: string } => {
    const entity = nodeEntities.get(nodeId);
    if (!entity) {
      return { fill: '#71717a', stroke: '#09090b', indicator: '' };
    }

    if (visualMode === 'domain') {
      return {
        fill: DOMAIN_COLORS[entity.domain] || '#71717a',
        stroke: '#09090b',
        indicator: DOMAIN_CONFIG[entity.domain]?.icon || '📝',
      };
    }

    if (visualMode === 'verification') {
      return {
        fill: VERIFICATION_COLORS[entity.verification] || '#71717a',
        stroke: '#09090b',
        indicator: VERIFICATION_CONFIG[entity.verification]?.icon || '?',
      };
    }

    // Default: kind-based (handled by BrainView)
    return { fill: '#71717a', stroke: '#09090b', indicator: '' };
  };

  // Get verification badge for node
  const getVerificationBadge = (nodeId: string): string | null => {
    const entity = nodeEntities.get(nodeId);
    if (!entity) return null;
    return VERIFICATION_CONFIG[entity.verification]?.icon || null;
  };

  // Get evidence count for node
  const getEvidenceCount = (nodeId: string): number => {
    return akms.getEvidenceFor(nodeId).length;
  };

  if (!enabled) return null;

  return (
    <>
      {/* Domain Statistics Panel */}
      {showDomainPanel && (
        <div className="absolute top-12 right-2 z-40 w-64 bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-mono text-zinc-400">📚 DOMAIN STATS</span>
            <button
              onClick={() => setShowDomainPanel(false)}
              className="text-[10px] font-mono text-zinc-500 hover:text-zinc-300"
            >
              ✕
            </button>
          </div>
          <div className="space-y-1.5">
            {domainStats.map((stat) => (
              <div key={stat.domain} className="flex items-center gap-2">
                <span className="text-xs">{stat.icon}</span>
                <span className="text-[10px] font-mono text-zinc-300 flex-1 truncate">{stat.label}</span>
                <span className="text-[10px] font-mono text-zinc-500">{stat.count}</span>
                <div className="w-12 h-1 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${stat.percentage}%`, backgroundColor: stat.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Terminology Check Panel */}
      {showTerminologyPanel && terminologyResults.length > 0 && (
        <div className="absolute bottom-12 right-2 z-40 w-72 bg-zinc-950/95 border border-zinc-700 rounded-lg shadow-2xl p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-mono text-zinc-400">🔤 TERMINOLOGY CHECK</span>
            <button
              onClick={() => setShowTerminologyPanel(false)}
              className="text-[10px] font-mono text-zinc-500 hover:text-zinc-300"
            >
              ✕
            </button>
          </div>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {terminologyResults.map((result, i) => (
              <div key={i} className="px-2 py-1.5 bg-zinc-900/60 rounded border border-zinc-800">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-amber-400">⚠</span>
                  <span className="text-[10px] font-mono text-zinc-300">{result.term}</span>
                </div>
                {result.forbiddenForm && (
                  <div className="text-[9px] font-mono text-red-400 mt-0.5">
                    ✗ {result.forbiddenForm}
                  </div>
                )}
                <div className="text-[9px] font-mono text-green-400">
                  ✓ {result.correctForm}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Verification Status Legend (when in verification mode) */}
      {visualMode === 'verification' && (
        <div className="absolute bottom-2 left-2 z-40 bg-zinc-950/90 border border-zinc-800 rounded px-2 py-1.5">
          <div className="flex items-center gap-3">
            {verificationStats.map((stat) => (
              <div key={stat.status} className="flex items-center gap-1">
                <span className="text-[8px]">{stat.icon}</span>
                <span className="text-[8px] font-mono text-zinc-400">{stat.label}</span>
                <span className="text-[8px] font-mono text-zinc-600">({stat.count})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Toggle Buttons (always visible) */}
      <div className="absolute top-12 left-2 z-40 flex flex-col gap-1">
        <button
          onClick={() => setShowDomainPanel(!showDomainPanel)}
          className={`w-6 h-6 flex items-center justify-center rounded text-xs transition-colors ${
            showDomainPanel ? 'bg-zinc-700 text-zinc-200' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
          }`}
          title="Domain statistics"
        >
          📚
        </button>
        {terminologyResults.length > 0 && (
          <button
            onClick={() => setShowTerminologyPanel(!showTerminologyPanel)}
            className={`w-6 h-6 flex items-center justify-center rounded text-xs transition-colors ${
              showTerminologyPanel ? 'bg-amber-900/50 text-amber-300' : 'text-zinc-500 hover:text-amber-300 hover:bg-zinc-800'
            }`}
            title={`Terminology issues: ${terminologyResults.length}`}
          >
            🔤
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-amber-500 rounded-full text-[7px] font-mono text-white flex items-center justify-center">
              {terminologyResults.length}
            </span>
          </button>
        )}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════
// NODE INDICATOR COMPONENT (SVG)
// ═══════════════════════════════════════════════

interface NodeIndicatorProps {
  nodeId: string;
  x: number;
  y: number;
  radius: number;
  visualMode: 'kind' | 'domain' | 'verification';
}

/**
 * SVG component that adds AKMS indicators to a node.
 * Renders verification badge and evidence count.
 */
export function NodeIndicator({ nodeId, x, y, radius, visualMode }: NodeIndicatorProps) {
  const entity = akms.getEntity(nodeId);
  if (!entity) return null;

  const verificationIcon = VERIFICATION_CONFIG[entity.verification]?.icon;
  const evidenceCount = akms.getEvidenceFor(nodeId).length;

  return (
    <g>
      {/* Verification badge (top-right) */}
      {verificationIcon && visualMode === 'verification' && (
        <text
          x={x + radius + 2}
          y={y - radius - 2}
          fontSize="7"
          fill={VERIFICATION_COLORS[entity.verification]}
          fontFamily="IBM Plex Mono, monospace"
          style={{ pointerEvents: 'none' }}
        >
          {verificationIcon}
        </text>
      )}

      {/* Evidence count indicator (bottom-right) */}
      {evidenceCount > 0 && (
        <g>
          <circle
            cx={x + radius + 3}
            cy={y + radius + 2}
            r={4}
            fill="#f59e0b"
            opacity={0.8}
          />
          <text
            x={x + radius + 3}
            y={y + radius + 4}
            fontSize="5"
            fill="#000"
            textAnchor="middle"
            fontFamily="IBM Plex Mono, monospace"
            style={{ pointerEvents: 'none' }}
          >
            {evidenceCount}
          </text>
        </g>
      )}

      {/* Domain icon (when in domain mode) */}
      {visualMode === 'domain' && (
        <text
          x={x}
          y={y + 2}
          fontSize="8"
          textAnchor="middle"
          fill="white"
          style={{ pointerEvents: 'none' }}
        >
          {DOMAIN_CONFIG[entity.domain]?.icon || '📝'}
        </text>
      )}
    </g>
  );
}

// ═══════════════════════════════════════════════
// HELPER HOOKS
// ═══════════════════════════════════════════════

/**
 * Get domain color for a node (for use in BrainView).
 */
export function getDomainColor(nodeId: string): string {
  const entity = akms.getEntity(nodeId);
  if (!entity) return '#71717a';
  return DOMAIN_COLORS[entity.domain] || '#71717a';
}

/**
 * Get verification color for a node (for use in BrainView).
 */
export function getVerificationColor(nodeId: string): string {
  const entity = akms.getEntity(nodeId);
  if (!entity) return '#71717a';
  return VERIFICATION_COLORS[entity.verification] || '#71717a';
}

/**
 * Check terminology for a text (for use in BrainView).
 */
export function checkTerminology(text: string, domain: KnowledgeDomain): TerminologyResult[] {
  const results: TerminologyResult[] = [];
  const terms = languageStore.findTerms({ domain });
  
  for (const term of terms) {
    for (const forbidden of term.forbiddenForms) {
      if (text.toLowerCase().includes(forbidden.toLowerCase())) {
        results.push({
          term: term.term,
          correctForm: term.preferredForm,
          forbiddenForm: forbidden,
          domain: term.domain,
          confidence: term.confidence,
        });
      }
    }
  }
  
  return results;
}
