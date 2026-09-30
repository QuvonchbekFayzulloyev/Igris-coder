/**
 * System Integration Panel — Connects all knowledge systems
 * 
 * Shows:
 *   - AKMS entities with evidence status
 *   - PCM tasks with results
 *   - GCM artifacts with validation
 *   - Language terminology
 *   - Runtime context tiers
 *   - Workspace files
 *   - Task result connections
 * 
 * Usage:
 *   <SystemIntegrationPanel domain="electrical_engineering" />
 */

import React, { useState, useMemo } from 'react';
import { akms } from '../../db/akms-store';
import { pcm } from '../../db/pcm-store';
import { gcm } from '../../db/gcm-store';
import { languageStore } from '../../db/language-store';
import { runtime } from '../../db/runtime-store';
import { workspace } from '../../db/workspace-store';
import { taskResultConnector } from '../../db/task-results';
import type { KnowledgeDomain } from '../../db/akms-schema';
import type { EvidenceStatus } from '../../db/runtime-schema';
import type { TaskResultStatus } from '../../db/task-results';

// ═══════════════════════════════════════════════
// EVIDENCE STATUS COLORS
// ═══════════════════════════════════════════════

const EVIDENCE_COLORS: Record<EvidenceStatus, { bg: string; text: string; dot: string }> = {
  unverified:          { bg: 'bg-zinc-800', text: 'text-zinc-400', dot: 'bg-zinc-500' },
  claimed:             { bg: 'bg-amber-900/30', text: 'text-amber-400', dot: 'bg-amber-500' },
  sourced:             { bg: 'bg-blue-900/30', text: 'text-blue-400', dot: 'bg-blue-500' },
  cross_checked:       { bg: 'bg-purple-900/30', text: 'text-purple-400', dot: 'bg-purple-500' },
  calculated:          { bg: 'bg-cyan-900/30', text: 'text-cyan-400', dot: 'bg-cyan-500' },
  tested:              { bg: 'bg-emerald-900/30', text: 'text-emerald-400', dot: 'bg-emerald-500' },
  simulated:           { bg: 'bg-teal-900/30', text: 'text-teal-400', dot: 'bg-teal-500' },
  verified:            { bg: 'bg-green-900/30', text: 'text-green-400', dot: 'bg-green-500' },
  real_world_verified: { bg: 'bg-green-900/50', text: 'text-green-300', dot: 'bg-green-400' },
};

const STATUS_COLORS: Record<TaskResultStatus, { bg: string; text: string }> = {
  pending:     { bg: 'bg-zinc-800', text: 'text-zinc-400' },
  in_progress: { bg: 'bg-blue-900/30', text: 'text-blue-400' },
  completed:   { bg: 'bg-green-900/30', text: 'text-green-400' },
  failed:      { bg: 'bg-red-900/30', text: 'text-red-400' },
  cancelled:   { bg: 'bg-zinc-800', text: 'text-zinc-500' },
};

// ═══════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════

interface Props {
  domain?: KnowledgeDomain;
  compact?: boolean;
}

export function SystemIntegrationPanel({ domain, compact = false }: Props) {
  const [activeTab, setActiveTab] = useState<'overview' | 'tasks' | 'artifacts' | 'evidence' | 'files'>('overview');
  const [expandedEntity, setExpandedEntity] = useState<string | null>(null);

  // ─── DATA ────────────────────────────────

  const entities = useMemo(() => {
    const all = akms.getAllEntities();
    return domain ? all.filter(e => e.domain === domain) : all;
  }, [domain]);

  const relations = useMemo(() => akms.getAllRelations(), []);

  const tasks = useMemo(() => {
    const all = pcm.getAllTasks();
    return domain ? all.filter(t => t.domain === domain) : all;
  }, [domain]);

  const artifacts = useMemo(() => {
    const all = gcm.getAllArtifacts();
    return domain ? all.filter(a => a.domain === domain) : all;
  }, [domain]);

  const results = useMemo(() => {
    const all = taskResultConnector.getAllResults();
    return domain ? all.filter(r => r.domain === domain) : all;
  }, [domain]);

  const files = useMemo(() => workspace.getAllFiles(), []);

  const memories = useMemo(() => {
    const all = akms.findEntities({ memoryType: 'experience' });
    return domain ? all.filter(m => m.domain === domain) : all;
  }, [domain]);

  // ─── STATS ───────────────────────────────

  const stats = useMemo(() => ({
    entities: entities.length,
    relations: relations.length,
    tasks: tasks.length,
    artifacts: artifacts.length,
    results: results.length,
    files: files.length,
    memories: memories.length,
    verified: results.filter(r => r.evidenceStatus === 'verified' || r.evidenceStatus === 'real_world_verified').length,
    completed: results.filter(r => r.status === 'completed').length,
    failed: results.filter(r => r.status === 'failed').length,
  }), [entities, relations, tasks, artifacts, results, files, memories]);

  // ─── TABS ────────────────────────────────

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: '📊' },
    { id: 'tasks' as const, label: 'Tasks', icon: '⚡' },
    { id: 'artifacts' as const, label: 'Artifacts', icon: '📦' },
    { id: 'evidence' as const, label: 'Evidence', icon: '✅' },
    { id: 'files' as const, label: 'Files', icon: '📁' },
  ];

  return (
    <div className="flex flex-col h-full bg-zinc-900 border-l border-zinc-800">
      {/* Header */}
      <div className="px-3 py-2 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-sm">🔗</span>
          <span className="text-xs font-medium text-zinc-200">System Integration</span>
          {domain && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
              {domain}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-2 py-1.5 text-[10px] font-medium transition-colors ${
              activeTab === tab.id
                ? 'text-zinc-100 border-b-2 border-blue-500'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <span className="mr-1">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {activeTab === 'overview' && (
          <OverviewTab stats={stats} />
        )}
        {activeTab === 'tasks' && (
          <TasksTab tasks={tasks} results={results} />
        )}
        {activeTab === 'artifacts' && (
          <ArtifactsTab artifacts={artifacts} />
        )}
        {activeTab === 'evidence' && (
          <EvidenceTab results={results} memories={memories} />
        )}
        {activeTab === 'files' && (
          <FilesTab files={files} />
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════
// OVERVIEW TAB
// ═══════════════════════════════════════════════

function OverviewTab({ stats }: { stats: Record<string, number> }) {
  const items = [
    { label: 'Entities', value: stats.entities, icon: '🧠', color: 'text-blue-400' },
    { label: 'Relations', value: stats.relations, icon: '🔗', color: 'text-purple-400' },
    { label: 'Tasks', value: stats.tasks, icon: '⚡', color: 'text-amber-400' },
    { label: 'Artifacts', value: stats.artifacts, icon: '📦', color: 'text-emerald-400' },
    { label: 'Results', value: stats.results, icon: '📊', color: 'text-cyan-400' },
    { label: 'Files', value: stats.files, icon: '📁', color: 'text-zinc-400' },
    { label: 'Memories', value: stats.memories, icon: '💭', color: 'text-teal-400' },
    { label: 'Verified', value: stats.verified, icon: '✅', color: 'text-green-400' },
    { label: 'Completed', value: stats.completed, icon: '✓', color: 'text-green-500' },
    { label: 'Failed', value: stats.failed, icon: '✗', color: 'text-red-400' },
  ];

  return (
    <div className="space-y-2">
      <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
        System Statistics
      </div>
      <div className="grid grid-cols-2 gap-2">
        {items.map(item => (
          <div key={item.label} className="bg-zinc-800/50 rounded p-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs">{item.icon}</span>
              <span className="text-[10px] text-zinc-500">{item.label}</span>
            </div>
            <div className={`text-lg font-bold ${item.color}`}>{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════
// TASKS TAB
// ═══════════════════════════════════════════════

function TasksTab({ tasks, results }: { tasks: any[]; results: any[] }) {
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
        Tasks & Results ({tasks.length})
      </div>
      {tasks.map(task => {
        const result = results.find(r => r.taskId === task.id);
        const isExpanded = expandedTask === task.id;
        const statusColor = result ? STATUS_COLORS[result.status] : STATUS_COLORS.pending;

        return (
          <div key={task.id} className="bg-zinc-800/50 rounded overflow-hidden">
            <button
              onClick={() => setExpandedTask(isExpanded ? null : task.id)}
              className="w-full px-3 py-2 flex items-center gap-2 hover:bg-zinc-800 transition-colors"
            >
              <span className={`w-2 h-2 rounded-full ${statusColor.bg.replace('bg-', 'bg-')}`} />
              <span className="text-xs text-zinc-200 text-left flex-1">{task.name}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${statusColor.bg} ${statusColor.text}`}>
                {result?.status || 'pending'}
              </span>
              <span className="text-zinc-600 text-[10px]">{isExpanded ? '▼' : '▶'}</span>
            </button>
            
            {isExpanded && (
              <div className="px-3 pb-3 border-t border-zinc-700/50">
                <div className="mt-2 text-[10px] text-zinc-500 mb-2">{task.description}</div>
                
                {/* Inputs */}
                {task.inputs?.length > 0 && (
                  <div className="mb-2">
                    <div className="text-[9px] text-zinc-600 mb-1">Inputs:</div>
                    <div className="flex flex-wrap gap-1">
                      {task.inputs.map((inp: any, i: number) => (
                        <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-300">
                          {inp.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Outputs */}
                {task.outputs?.length > 0 && (
                  <div className="mb-2">
                    <div className="text-[9px] text-zinc-600 mb-1">Outputs:</div>
                    <div className="flex flex-wrap gap-1">
                      {task.outputs.map((out: any, i: number) => (
                        <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-900/30 text-emerald-400">
                          {out.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Verification */}
                {task.verification?.length > 0 && (
                  <div className="mb-2">
                    <div className="text-[9px] text-zinc-600 mb-1">Verification:</div>
                    <div className="flex flex-wrap gap-1">
                      {task.verification.map((v: any, i: number) => {
                        const vResult = result?.verificationChain?.find(
                          (vr: any) => vr.name === v.name
                        );
                        return (
                          <span
                            key={i}
                            className={`text-[9px] px-1.5 py-0.5 rounded ${
                              vResult?.passed
                                ? 'bg-green-900/30 text-green-400'
                                : vResult
                                ? 'bg-red-900/30 text-red-400'
                                : 'bg-zinc-700 text-zinc-400'
                            }`}
                          >
                            {vResult?.passed ? '✓' : vResult ? '✗' : '?'} {v.name}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Evidence Status */}
                {result && (
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[9px] text-zinc-600">Evidence:</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded ${EVIDENCE_COLORS[result.evidenceStatus].bg} ${EVIDENCE_COLORS[result.evidenceStatus].text}`}>
                      {result.evidenceStatus}
                    </span>
                    <span className="text-[9px] text-zinc-600">
                      Quality: {(result.qualityScore * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════
// ARTIFACTS TAB
// ═══════════════════════════════════════════════

function ArtifactsTab({ artifacts }: { artifacts: any[] }) {
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
        Generated Artifacts ({artifacts.length})
      </div>
      {artifacts.map(artifact => (
        <div key={artifact.id} className="bg-zinc-800/50 rounded p-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs">📦</span>
            <span className="text-xs text-zinc-200">{artifact.name}</span>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-zinc-500">
            <span className="px-1.5 py-0.5 rounded bg-zinc-700">{artifact.type}</span>
            <span className="px-1.5 py-0.5 rounded bg-zinc-700">{artifact.format}</span>
            <span className="px-1.5 py-0.5 rounded bg-zinc-700">{artifact.domain}</span>
          </div>
          {artifact.validation?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {artifact.validation.map((v: any, i: number) => (
                <span
                  key={i}
                  className={`text-[9px] px-1.5 py-0.5 rounded ${
                    v.passed ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                  }`}
                >
                  {v.passed ? '✓' : '✗'} {v.checkType}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════
// EVIDENCE TAB
// ═══════════════════════════════════════════════

function EvidenceTab({ results, memories }: { results: any[]; memories: any[] }) {
  const evidenceGroups = useMemo(() => {
    const groups: Record<string, number> = {};
    results.forEach(r => {
      groups[r.evidenceStatus] = (groups[r.evidenceStatus] || 0) + 1;
    });
    return groups;
  }, [results]);

  return (
    <div className="space-y-4">
      {/* Evidence Status Distribution */}
      <div>
        <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
          Evidence Status Distribution
        </div>
        <div className="space-y-1">
          {Object.entries(evidenceGroups).map(([status, count]) => (
            <div key={status} className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${EVIDENCE_COLORS[status as EvidenceStatus].dot}`} />
              <span className="text-[10px] text-zinc-400 flex-1">{status}</span>
              <span className="text-[10px] text-zinc-500">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Memories */}
      <div>
        <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
          Recent Memories ({memories.length})
        </div>
        <div className="space-y-2">
          {memories.slice(0, 10).map(memory => (
            <div key={memory.id} className="bg-zinc-800/50 rounded p-2">
              <div className="text-xs text-zinc-200 mb-1">{memory.name}</div>
              <div className="text-[10px] text-zinc-500 line-clamp-2">{memory.content}</div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">
                  {memory.domain}
                </span>
                <span className="text-[9px] text-zinc-600">
                  confidence: {(memory.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════
// FILES TAB
// ═══════════════════════════════════════════════

function FilesTab({ files }: { files: any[] }) {
  const filesByType = useMemo(() => {
    const groups: Record<string, number> = {};
    files.forEach(f => {
      groups[f.type] = (groups[f.type] || 0) + 1;
    });
    return groups;
  }, [files]);

  const filesByRole = useMemo(() => {
    const groups: Record<string, number> = {};
    files.forEach(f => {
      groups[f.role] = (groups[f.role] || 0) + 1;
    });
    return groups;
  }, [files]);

  return (
    <div className="space-y-4">
      {/* Files by Type */}
      <div>
        <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
          Files by Type ({files.length})
        </div>
        <div className="space-y-1">
          {Object.entries(filesByType).map(([type, count]) => (
            <div key={type} className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-400 flex-1">{type}</span>
              <span className="text-[10px] text-zinc-500">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Files by Role */}
      <div>
        <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
          Files by Role
        </div>
        <div className="space-y-1">
          {Object.entries(filesByRole).map(([role, count]) => (
            <div key={role} className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-400 flex-1">{role}</span>
              <span className="text-[10px] text-zinc-500">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Files */}
      <div>
        <div className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-3">
          Recent Files
        </div>
        <div className="space-y-1">
          {files.slice(0, 10).map(file => (
            <div key={file.id} className="bg-zinc-800/50 rounded p-2">
              <div className="flex items-center gap-2">
                <span className="text-xs">📄</span>
                <span className="text-[10px] text-zinc-200 truncate">{file.name}</span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">
                  {file.type}
                </span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">
                  {file.role}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
