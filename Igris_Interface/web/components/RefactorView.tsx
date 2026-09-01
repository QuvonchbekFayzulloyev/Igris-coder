import React, { useEffect, useState } from 'react';
import {
  refactorReport,
  refactorTelemetry,
  refactorAssess,
  probeRun,
  probeRunStatus,
  probeReport,
  clarificationAnalytics,
  RefactorReport,
  RefactorTelemetryResult,
  RefactorAssessResult,
  RefactorTelemetrySnapshot,
  ProbeReport,
  ClarificationAnalytics,
} from '../backend';

/**
 * Brain Quality — REAL Refactor Machine ko'rsatkichlari.
 *
 * Igris_brain'dagi assessor qatlamini (aniqlik & sabablilik mezonlari) jonli
 * ko'rsatadi:
 *   - telemetry: ok/fail rate, o'rtacha confidence (aniqlik), LLM/heal ulushi
 *   - refactor report: inventory, DIKW bandlar, tasniflar, aloqalar
 *   - assess so'rovi: istalgan query'ni baholash (semantik aniqlik + natija)
 * Backend ulanmagan bo'lsa — halol bo'sh holat (demo mock yo'q).
 */
export function RefactorView() {
  const [report, setReport] = useState<RefactorReport | null>(null);
  const [telemetry, setTelemetry] = useState<RefactorTelemetryResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [live, setLive] = useState(false);
  const [query, setQuery] = useState('');
  const [assessing, setAssessing] = useState(false);
  const [assess, setAssess] = useState<RefactorAssessResult | null>(null);
  const [error, setError] = useState('');
  const [probeReport_, setProbeReport] = useState<ProbeReport | null>(null);
  const [probeRunning, setProbeRunning] = useState(false);
  const [probeDone, setProbeDone] = useState<string[]>([]);
  const [clarificationData, setClarificationData] = useState<ClarificationAnalytics | null>(null);

  const load = () => {
    setLoading(true);
    // Ikkala endpoint mustaqil — biri yiqilsa, ikkinchisini yo'qotmaymiz.
    refactorReport()
      .then(setReport)
      .catch(() => setReport(null));
    refactorTelemetry()
      .then((t) => {
        setTelemetry(t);
        setLive(true);
      })
      .catch(() => {
        setTelemetry(null);
        setLive(false);
      });
    // Clarification analytics — mustaqil yuklanadi
    clarificationAnalytics()
      .then(setClarificationData)
      .catch(() => setClarificationData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runAssess = async () => {
    const q = query.trim();
    if (!q) return;
    setAssessing(true);
    setError('');
    try {
      const res = await refactorAssess(q);
      setAssess(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setAssessing(false);
    }
  };

  const loadProbeReport = () => {
    probeReport()
      .then((r) => { if (r.exists) setProbeReport(r.report ?? null); })
      .catch(() => {});
  };

  const runProbe = async () => {
    if (probeRunning) return;
    setProbeRunning(true);
    setProbeDone([]);
    setError('');
    let runId: string;
    try {
      const started = await probeRun('all');
      runId = started.run_id;
    } catch (e) {
      setError(`probe boshlanmadi: ${String(e)}`);
      setProbeRunning(false);
      return;
    }
    // poll — har bir task bajarilgach yangilanadi (max ~15 daqiqa, keyin to'xtaymiz)
    const MAX_POLLS = 180;
    let polls = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      await new Promise((r) => setTimeout(r, 5000));
      polls += 1;
      let st;
      try {
        st = await probeRunStatus(runId);
      } catch {
        if (polls >= MAX_POLLS) break;
        continue;
      }
      if (st.completed?.length) setProbeDone(st.completed);
      if (st.status === 'done' || st.status === 'error') {
        setProbeRunning(false);
        if (st.report) {
          setProbeReport(st.report);
        } else {
          loadProbeReport();
        }
        if (st.status === 'error') setError(`probe xatosi: ${st.error || '?'}`);
        return;
      }
      if (polls >= MAX_POLLS) {
        setProbeRunning(false);
        setError('probe vaqti tugadi — server qayta ishga tushgan bo\'lishi mumkin');
        loadProbeReport();
        return;
      }
    }
  };

  useEffect(() => {
    loadProbeReport();
  }, []);

  const last = telemetry?.stats?.last;
  const trend = telemetry?.trend || [];

  const pct = (v?: number) => (v == null ? '—' : `${(v * 100).toFixed(0)}%`);
  const conf = (v?: number) => (v == null ? '—' : v.toFixed(2));

  const bandColor = (q?: number) => {
    if (q == null) return 'bg-zinc-800 text-zinc-400';
    if (q >= 0.85) return 'bg-amber-500/20 text-amber-300';
    if (q >= 0.7) return 'bg-teal-500/20 text-teal-300';
    if (q >= 0.5) return 'bg-sky-500/20 text-sky-300';
    return 'bg-zinc-700/40 text-zinc-400';
  };

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-ui text-zinc-200">📊 Brain Quality — Refactor Machine</span>
          <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${live ? 'bg-teal-900/50 text-teal-300' : 'bg-zinc-800 text-zinc-500'}`}>
            {loading ? 'yuklanmoqda…' : live ? '● real ma\'lumotlar' : '○ offline (backend ulangan emas)'}
          </span>
        </div>
        <button
          onClick={load}
          className="text-[10px] font-mono px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors"
        >
          ↻ yangilash
        </button>
      </div>

      {!loading && !live && (
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="text-center space-y-2 max-w-sm">
            <div className="text-2xl">📊</div>
            <div className="text-sm font-ui text-zinc-300">Refactor Machine offline</div>
            <div className="text-xs font-ui text-zinc-600 leading-relaxed">
              Telemetry va baholash Igris_brain serveri orqali real yoziladi.
              Backend'ni ishga tushiring: <code className="font-mono text-zinc-500">python server.py</code> (Igris_brain).
            </div>
          </div>
        </div>
      )}

      {live && (
        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-4">
          {/* ---------- Telemetry (aniqlik & sabablilik) ---------- */}
          <section className="bg-zinc-900/50 border border-zinc-800 rounded-md p-3">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-ui font-medium text-zinc-300">Telemetry — jarayon sifat</h3>
              <span className="text-[10px] font-mono text-zinc-600">
                {last?.window_size ?? 0} window · {telemetry?.stats?.total_events ?? 0} events
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Metric label="OK rate (aniqlik)" value={pct(last?.ok_rate)} good={(last?.ok_rate ?? 0) >= 0.7} />
              <Metric label="Failed rate" value={pct(last?.failed_rate)} warn={(last?.failed_rate ?? 0) > 0.3} />
              <Metric label="Avg confidence (sabablilik)" value={conf(last?.avg_confidence)} good={(last?.avg_confidence ?? 0) >= 0.5} />
              <Metric
                label="LLM fallback"
                value={pct(last?.llm_usage_rate)}
                hint={last?.llm_usage_rate != null && last.llm_usage_rate > 0.5 ? '>50% — deterministic coverage kuchsiz' : ''}
              />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
              <Metric label="Healed rate" value={pct(last?.healed_rate)} />
              <Metric label="Confidence declining" value={last?.confidence_declining ? '⚠ ha' : 'yo\'q'} warn={last?.confidence_declining} />
              <Metric label="Top chain" value={Object.keys(last?.top_chains ?? {})[0] || '—'} />
              <Metric label="Chains" value={last ? `${Object.keys(last.top_chains ?? {}).length}ta` : '—'} />
            </div>
            {last?.suggestions?.length ? (
              <div className="mt-3 space-y-1">
                {last.suggestions.map((s, i) => (
                  <div key={i} className="text-[11px] font-ui text-amber-200/90 bg-amber-950/30 border border-amber-800/40 rounded px-2 py-1">
                    ⚑ {s}
                  </div>
                ))}
              </div>
            ) : null}
            {/* Trend sparkline */}
            {trend.length > 1 && (
              <div className="mt-3">
                <div className="flex items-end gap-[2px] h-10">
                  {trend.map((s, i) => (
                    <div
                      key={i}
                      className="flex-1 rounded-t bg-teal-800/60 hover:bg-teal-600/70 transition-colors"
                      style={{ height: `${Math.max(6, (s.avg_confidence ?? 0) * 100)}%` }}
                      title={`conf ${conf(s.avg_confidence)} · ok ${pct(s.ok_rate)}`}
                    />
                  ))}
                </div>
                <div className="text-[10px] font-mono text-zinc-600 mt-1">so'nggi {trend.length} snapshot · avg confidence</div>
              </div>
            )}
          </section>

          {/* ---------- Clarification Analytics ---------- */}
          {clarificationData && clarificationData.enabled && (
            <section className="bg-zinc-900/50 border border-zinc-800 rounded-md p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-ui font-medium text-zinc-300">Clarification analytics — so'rov aniqlashtirish</h3>
                <span className="text-[10px] font-mono text-zinc-600">
                  {clarificationData.total_clarifications} clarification · {clarificationData.total_questions} questions
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <Metric
                  label="Total clarifications"
                  value={String(clarificationData.total_clarifications)}
                  good={clarificationData.total_clarifications > 0}
                />
                <Metric
                  label="Total questions"
                  value={String(clarificationData.total_questions)}
                />
                <Metric
                  label="Avg questions/session"
                  value={clarificationData.avg_questions_per_session.toFixed(1)}
                  good={clarificationData.avg_questions_per_session <= 3}
                  hint={clarificationData.avg_questions_per_session > 3 ? "Ko'p savol so'ralmoqda — prompt yaxshilash kerak" : ''}
                />
                <Metric
                  label="Clarification rate"
                  value={(clarificationData.clarification_rate ?? 0) > 0 ? `${((clarificationData.clarification_rate ?? 0) * 100).toFixed(0)}%` : '—'}
                />
              </div>
              {/* Common questions */}
              {clarificationData.common_questions.length > 0 && (
                <div className="mt-3">
                  <div className="text-[10px] font-mono text-zinc-600 mb-1.5">Eng ko'p berilgan savollar</div>
                  <div className="space-y-1">
                    {clarificationData.common_questions.slice(0, 5).map((q, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px] font-mono">
                        <span className="text-teal-400 w-6 shrink-0">{q.count}x</span>
                        <span className="text-zinc-300 truncate" title={q.question}>{q.question}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Common answers */}
              {clarificationData.common_answers.length > 0 && (
                <div className="mt-3">
                  <div className="text-[10px] font-mono text-zinc-600 mb-1.5">Eng ko'p berilgan javoblar</div>
                  <div className="flex flex-wrap gap-1.5">
                    {clarificationData.common_answers.slice(0, 8).map((a, i) => (
                      <span
                        key={i}
                        className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-900/40 text-amber-300"
                        title={`${a.count}x: ${a.answer}`}
                      >
                        {a.answer.slice(0, 30)}{a.answer.length > 30 ? '…' : ''} ({a.count})
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {/* Insights */}
              {clarificationData.total_clarifications > 0 && (
                <div className="mt-3 space-y-1">
                  {clarificationData.avg_questions_per_session > 3 && (
                    <div className="text-[11px] font-ui text-amber-200/90 bg-amber-950/30 border border-amber-800/40 rounded px-2 py-1">
                      ⚑ O'rtacha {clarificationData.avg_questions_per_session.toFixed(1)} ta savol — promptlarni aniqroq yozish tavsiya etiladi
                    </div>
                  )}
                  {clarificationData.total_clarifications > 10 && (
                    <div className="text-[11px] font-ui text-teal-200/90 bg-teal-950/30 border border-teal-800/40 rounded px-2 py-1">
                      ✓ {clarificationData.total_clarifications} ta clarification — agent so'rovlarni yaxshi aniqlashtirmoqda
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

          {/* ---------- Refactor report (inventory) ---------- */}
          {report?.inventory && (
            <section className="bg-zinc-900/50 border border-zinc-800 rounded-md p-3">
              <h3 className="text-xs font-ui font-medium text-zinc-300 mb-2">Refactor report — bilim inventari</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <Metric label="Items" value={String(report.inventory.items)} />
                <Metric
                  label="Avg quality"
                  value={report.inventory.avg_quality.toFixed(3)}
                  good={report.inventory.avg_quality >= 0.7}
                />
              <Metric label="Bricks" value={String(report.inventory.by_category?.brick ?? 0)} />
              <Metric label="Experience" value={String(report.inventory.by_category?.experience ?? 0)} />
              <Metric label="Derived" value={String(report.inventory.by_category?.derived ?? 0)} />
              <Metric label="Links" value={String(report.links?.total_links ?? 0)} />
              </div>
              <div className="mt-3">
                <div className="text-[10px] font-mono text-zinc-600 mb-1.5">4 o'lchov bo'yicha o'rtacha (situation · information · volume · semantics)</div>
                <div className="space-y-1.5">
                  {Object.entries(report.inventory.dimension_averages || {}).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-2">
                      <span className="text-[11px] font-mono text-zinc-500 w-24 shrink-0">{k}</span>
                      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${v >= 0.7 ? 'bg-teal-500' : v >= 0.4 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${Math.min(100, v * 100)}%` }}
                        />
                      </div>
                      <span className={`text-[11px] font-mono w-10 text-right ${v >= 0.7 ? 'text-teal-300' : v >= 0.4 ? 'text-amber-300' : 'text-red-300'}`}>
                        {v.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              {report.links && (
                <div className="flex items-center gap-3 mt-3 text-[10px] font-mono text-zinc-600">
                  <span>{report.links.total_links} aloqa</span>
                  <span>{report.links.nodes} node</span>
                  {Object.entries(report.links.by_type || {}).map(([t, n]) => (
                    <span key={t} className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">{t}:{n}</span>
                  ))}
                </div>
              )}
              {report.classifications && report.classifications.length > 0 && (
                <div className="mt-3 border-t border-zinc-800/70 pt-2">
                  <div className="text-[10px] font-mono text-zinc-600 mb-1.5">Tasniflar (brick / experience / derived)</div>
                  <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
                    {report.classifications.map((c) => (
                      <span
                        key={c.item_id}
                        className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                          c.category === 'brick'
                            ? 'bg-teal-900/40 text-teal-300'
                            : c.category === 'experience'
                              ? 'bg-amber-900/40 text-amber-300'
                              : 'bg-zinc-800 text-zinc-500'
                        }`}
                        title={`${c.item_id} · brickness ${c.brickness} · ${c.reasons.join('; ')}`}
                      >
                        {c.item_id.replace(/^concept_|^chain_/, '')}:{c.category[0]}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* ---------- Decision probe (aniqlik & reasoning) ---------- */}
          <section className="bg-zinc-900/50 border border-zinc-800 rounded-md p-3">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-ui font-medium text-zinc-300">Decision probe — real vazifalarda aql</h3>
              <button
                onClick={runProbe}
                disabled={probeRunning}
                className="px-2.5 py-1 rounded bg-amber-400 hover:bg-amber-300 disabled:opacity-40 text-[11px] font-ui text-zinc-950 transition-colors"
              >
                {probeRunning ? '⚡ ishlamoqda…' : '⚡ Probe ishga tushirish'}
              </button>
            </div>
            {probeRunning && (
              <div className="text-[11px] font-mono text-zinc-500 mb-2">
                bajarildi: {probeDone.length ? probeDone.join(', ') : '(birinchi task…)'} — LLM 4 ta real taskni bajaradi, ~2-4 daqiqa
              </div>
            )}
            {probeReport_?.tasks?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px] font-mono">
                  <thead>
                    <tr className="text-zinc-600">
                      <th className="py-1 pr-2 font-normal">task</th>
                      <th className="py-1 pr-2 font-normal">tool</th>
                      <th className="py-1 pr-2 font-normal">args</th>
                      <th className="py-1 pr-2 font-normal">reason</th>
                      <th className="py-1 pr-2 font-normal">recover</th>
                      <th className="py-1 pr-2 font-normal">outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {probeReport_.tasks.map((t) => (
                      <tr key={t.id} className="border-t border-zinc-800/60">
                        <td className="py-1.5 pr-2 text-zinc-300 max-w-[140px] truncate" title={t.task}>{t.id}</td>
                        <ScoreCell v={t.scores.tool_selection} />
                        <ScoreCell v={t.scores.args_correctness} />
                        <ScoreCell v={t.scores.reasoning} />
                        <ScoreCell v={t.scores.recovery} />
                        <ScoreCell v={t.scores.outcome} />
                      </tr>
                    ))}
                    {probeReport_.aggregate && (
                      <tr className="border-t border-zinc-700/60">
                        <td className="py-1.5 pr-2 text-amber-300">avg</td>
                        <ScoreCell bold v={probeReport_.aggregate.tool_selection} />
                        <ScoreCell bold v={probeReport_.aggregate.args_correctness} />
                        <ScoreCell bold v={probeReport_.aggregate.reasoning} />
                        <ScoreCell bold v={probeReport_.aggregate.recovery} />
                        <ScoreCell bold v={probeReport_.aggregate.outcome} />
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              !probeRunning && (
                <div className="text-[11px] font-ui text-zinc-600">
                  Hali probe o'tkazilmagan. Tugma orqali agent 4 ta real vazifani bajaradi
                  (kod yozish, fayllar, rasm chizish, xatoni tuzatish) va
                  tool_selection · args · reasoning · recovery · outcome bo'yicha baholanadi.
                </div>
              )
            )}
          </section>

          {/* ---------- Assess a query ---------- */}
          <section className="bg-zinc-900/50 border border-zinc-800 rounded-md p-3">
            <h3 className="text-xs font-ui font-medium text-zinc-300 mb-2">So'rovni baholash — assess</h3>
            <div className="flex items-center gap-2">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') runAssess(); }}
                placeholder="masalan: matritsani teskari top"
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-xs font-ui text-zinc-200 placeholder-zinc-600 outline-none focus:border-amber-500/60 transition-colors"
              />
              <button
                onClick={runAssess}
                disabled={assessing || !query.trim()}
                className="px-3 py-1.5 rounded bg-amber-400 hover:bg-amber-300 disabled:opacity-40 text-xs font-ui text-zinc-950 transition-colors"
              >
                {assessing ? 'baholanmoqda…' : 'Baholash'}
              </button>
            </div>
            {error && <div className="mt-2 text-[11px] font-ui text-red-300">{error}</div>}
            {assess?.query_semantics && (
              <div className="mt-3 space-y-2">
                <div className="flex flex-wrap gap-2">
                  <span className={`px-2 py-0.5 rounded text-[11px] font-mono ${bandColor(assess.query_semantics.semantic_clarity)}`}>
                    semantik aniqlik {assess.query_semantics.semantic_clarity.toFixed(2)}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-800 text-zinc-400">
                    ambiguity {assess.query_semantics.ambiguity.toFixed(2)}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-800 text-zinc-400">
                    {assess.query_semantics.tokens} token · {assess.query_semantics.language}
                  </span>
                </div>
                {assess.resolution && (
                  <div className="border border-zinc-800 rounded p-2 space-y-1">
                    <div className="flex items-center gap-2 text-[11px] font-mono">
                      <span className={`px-1.5 py-0.5 rounded ${assess.resolution.status === 'ok' ? 'bg-teal-900/50 text-teal-300' : 'bg-red-900/50 text-red-300'}`}>
                        {assess.resolution.status}
                      </span>
                      <span className="text-zinc-400">conf {assess.resolution.confidence.toFixed(2)}</span>
                      <span className="text-zinc-400">{assess.resolution.engine}</span>
                      <span className="text-zinc-600">{(assess.resolution.chains || []).join(', ')}</span>
                    </div>
                    {assess.resolution.output && (
                      <pre className="text-[11px] font-mono text-zinc-300 bg-zinc-950 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
                        {assess.resolution.output.slice(0, 400)}
                      </pre>
                    )}
                  </div>
                )}
                {assess.telemetry_snapshot && (
                  <div className="text-[10px] font-mono text-zinc-600">
                    telemetry: ok {pct(assess.telemetry_snapshot.ok_rate)} · conf {conf(assess.telemetry_snapshot.avg_confidence)} · window {assess.telemetry_snapshot.window_size}
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function ScoreCell({ v, bold }: { v?: number; bold?: boolean }) {
  const c = v == null ? 'text-zinc-600' : v >= 0.7 ? 'text-teal-300' : v >= 0.4 ? 'text-amber-300' : 'text-red-300';
  return <td className={`py-1.5 pr-2 ${c} ${bold ? 'font-bold' : ''}`}>{v == null ? '—' : v.toFixed(2)}</td>;
}

function Metric({ label, value, good, warn, hint }: {
  label: string;
  value: string;
  good?: boolean;
  warn?: boolean;
  hint?: string;
}) {
  const color = warn ? 'text-amber-300' : good ? 'text-teal-300' : 'text-zinc-300';
  return (
    <div className="bg-zinc-950/60 border border-zinc-800 rounded px-2 py-1.5">
      <div className="text-[10px] font-mono text-zinc-600 truncate">{label}</div>
      <div className={`text-sm font-mono ${color} truncate`} title={hint}>{value}</div>
      {hint ? <div className="text-[9px] font-ui text-amber-400/80 truncate">{hint}</div> : null}
    </div>
  );
}
